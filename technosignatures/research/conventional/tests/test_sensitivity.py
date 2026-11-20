import numpy as np
import pytest

from research.conventional.events import hierarchical_matches
from research.conventional.injection import parameter_manifest
from research.conventional.search import SearchConfig
from research.conventional.sensitivity import evaluate_single_scan


def test_stage_ancestry_never_reuses_one_parent_hit():
    truths = [{'truth_id': str(i), 'start_frequency_hz': 100+i, 'drift_hz_per_s': 0} for i in range(2)]
    hits = [{'hit_id': 'h', 'start_frequency_hz': 100, 'drift_hz_per_s': 0}]
    events = [{'event_id': 'e', 'representative_hit_id': 'h', **hits[0]}]
    matches = hierarchical_matches(truths, hits, events, np.arange(8), 1)
    assert sum(m['matched_id'] is not None for m in matches['hits']) == 1
    assert sum(m['matched_id'] is not None for m in matches['events']) == 1
    for raw, grouped in zip(matches['hits'], matches['events']):
        if grouped['matched_id'] is not None: assert raw['matched_id'] is not None


def test_conditional_engine_counts_weak_edge_and_strong_cases(make_scan):
    scan = make_scan(nt=16, nf=256)
    design = parameter_manifest(scan.scan_id, 256, 16, 1, seed=91, placements=2,
                                families=('continuous_linear',), amplitudes=(0.25, 8.), max_drift=0.5)
    result = evaluate_single_scan(scan, design, SearchConfig(max_abs_drift_hz_per_s=0.5), subsamples=16,
                                  source_kind='fully_synthetic_unit_fixture')
    assert len(result['signal_rows']) == design['signal_count'] == 4
    assert result['technical_failure_signal_count'] == 0
    assert not result['cadence_filtering_applied'] and not result['representative_cohort_gate_passed']
    assert result['paired']['interval_95'] is None
    assert any(not r['cadence_retained'] for r in result['signal_rows'])
    assert all(not r['grouped'] or r['generated'] for r in result['signal_rows'])


def test_post_injection_search_failure_stays_in_experiment_denominator(make_scan, monkeypatch):
    import research.conventional.sensitivity as module
    original = module.search
    calls = 0
    def fail_after_control(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1: raise RuntimeError('intentional unit-test search failure')
        return original(*args, **kwargs)
    monkeypatch.setattr(module, 'search', fail_after_control)
    scan = make_scan()
    design = parameter_manifest(scan.scan_id, 256, 16, 1, 1, placements=1, families=('continuous_linear',), amplitudes=(1.,), max_drift=0.5)
    result = evaluate_single_scan(scan, design, SearchConfig(max_abs_drift_hz_per_s=0.5))
    assert result['technical_failure_signal_count'] == 1
    assert result['conservative']['eligible_count'] == 1
    assert result['conservative']['full_declared_domain_recovery'] == 0


def test_failure_before_truth_allocation_aborts_instead_of_reporting_complete(make_scan, monkeypatch):
    import research.conventional.sensitivity as module
    def fail(*args, **kwargs): raise ValueError('intentional unit-test injector failure')
    monkeypatch.setattr(module, 'inject', fail)
    scan = make_scan()
    design = parameter_manifest(scan.scan_id, 256, 16, 1, 1, placements=1, families=('continuous_linear',), amplitudes=(1.,), max_drift=0.5)
    with pytest.raises(RuntimeError, match='execution incomplete'):
        evaluate_single_scan(scan, design, SearchConfig(max_abs_drift_hz_per_s=0.5))


def test_development_runner_rejects_locked_test_and_wrong_observation(make_scan):
    scan = make_scan()
    design = parameter_manifest(scan.scan_id, 256, 16, 1, 1, placements=1, families=('continuous_linear',), amplitudes=(1.,), max_drift=0.5)
    design['trials'][0]['partition'] = 'test'
    with pytest.raises(ValueError, match='locked-test'): evaluate_single_scan(scan, design)
    design['trials'][0]['partition'] = 'development'; design['cadence_id'] = 'other'
    with pytest.raises(ValueError, match='different observation'): evaluate_single_scan(scan, design)
