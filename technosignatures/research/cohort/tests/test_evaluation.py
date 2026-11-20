import json
import numpy as np
import pytest

from research.conventional.data import Scan, Cadence
from research.conventional.search import SearchConfig
from research.conventional.injection import inject
from research.cohort.evaluate import process, evaluate_trial, truths_for_parameters, native_ambiguities
from research.cohort.run import make_design


def background():
    return Cadence('synthetic_unit', tuple(Scan(f's{i}', 20+np.random.default_rng(i+11).normal(size=(16, 128)),
                   1e9+np.arange(128), np.arange(16.), 59000+i*50/86400, 'ON' if i % 2 == 0 else 'OFF',
                   'A' if i % 2 == 0 else f'OFF_{i}', 'synthetic_session', f'synthetic_raw_{i}', 'SYNTHETIC_ONLY') for i in range(6)), False)


def parameters():
    return {'trial_id': 'opaque_case', 'cadence_id': 'synthetic_unit', 'family': 'continuous_linear',
            'start_channel': 40., 'drift_hz_per_s': 0.05, 'fwhm_channels': 2., 'peak_power_sigma': 8.,
            'off_response': 0., 'curvature_hz_per_s2': 0., 'modulation_phase': 0.3}


@pytest.mark.parametrize('family', ['continuous_linear', 'intermittent', 'collision_or_crowded'])
def test_paired_complete_chain_and_preallocated_truth(family):
    cadence = background(); trial = {**parameters(), 'family': family}
    if family == 'intermittent': trial['active_intervals_s'] = [[0., 16.]]
    if family == 'collision_or_crowded': trial['collision_offset_channels'] = 5.
    preallocated = truths_for_parameters(cadence, trial)
    _, true, _ = inject(cadence, trial)
    assert preallocated == true
    config = SearchConfig(max_abs_drift_hz_per_s=0.25)
    controls = {arm: process(cadence, config, arm) for arm in ['new', 'legacy']}
    rows, metrics = evaluate_trial(cadence, trial, controls, config, 'SYNTHETIC_COMPONENT', 2., 4)
    assert len(rows) == len(true) and all(r['failure_type'] is None for r in rows)
    assert sum(r['weight'] for r in rows) == 0.5
    assert all(not r['new_strict'] or r['new_safe'] for r in rows)
    json.dumps(rows, allow_nan=False)
    if family == 'intermittent': assert any(r['new_safe'] and not r['new_strict'] for r in rows)


def test_one_control_event_can_ambiguously_explain_two_truths():
    truths = [{'truth_id': str(i), 'start_frequency_hz': 100+i, 'drift_hz_per_s': 0} for i in range(2)]
    result = native_ambiguities(truths, [{'cadence_event_id': 'native_unknown', 'start_frequency_hz': 100, 'drift_hz_per_s': 0}], np.arange(8), 1)
    assert all(result.values())


def test_unrelated_cadence_parent_cannot_satisfy_a_truth_matched_local_chain(monkeypatch):
    import research.cohort.evaluate as module
    cadence = background(); config = SearchConfig(max_abs_drift_hz_per_s=.25)
    controls = {arm: process(cadence, config, arm) for arm in ['new', 'legacy']}
    normal, _ = evaluate_trial(cadence, parameters(), controls, config, 'synthetic', 1., 1)
    assert normal[0]['new_safe']
    original = module.filter_cadence
    def unrelated_parent(*args, **kwargs):
        result = original(*args, **kwargs)
        # Deliberately break only the final parent identity while keeping the
        # fitted track and every local hit/event unchanged. Independent truth
        # matches at both stages must not create a fabricated survival chain.
        result['events'] = [{**e, 'member_on_event_ids': ['unrelated_synthetic_parent']} for e in result['events']]
        return result
    monkeypatch.setattr(module, 'filter_cadence', unrelated_parent)
    rows, _ = evaluate_trial(cadence, parameters(), controls, config, 'synthetic', 1., 1)
    assert rows[0]['failure_type'] is None and not rows[0]['new_safe']
    assert rows[0]['new_stages']['grouped'] and rows[0]['new_stages']['associated']
    assert rows[0]['new_first_loss'] == 'cadence_ancestry_or_assignment'
    assert rows[0]['new_stages']['association_ancestry_competition_not_counted']


def test_injector_failure_stays_in_known_physical_signal_denominator(monkeypatch):
    cadence = background(); config = SearchConfig(max_abs_drift_hz_per_s=0.25)
    def failed(*args, **kwargs): raise RuntimeError('synthetic unit failure')
    monkeypatch.setattr('research.cohort.evaluate.inject', failed)
    rows, _ = evaluate_trial(cadence, parameters(), {}, config, 'SYNTHETIC_COMPONENT', 1, 1)
    assert len(rows) == 1 and rows[0]['eligible'] and not rows[0]['new_safe']
    assert rows[0]['failure_type'] == 'RuntimeError'


def test_full_matrix_arithmetic_and_companion_weights_for_uneven_allocation():
    cadence = background()
    cfg = {'version': 'unit', 'seed': 7, 'placements_per_family_amplitude_total': 5,
           'families': ['continuous_linear', 'collision_or_crowded'], 'amplitudes': [1., 2.],
           'search': {'max_abs_drift_hz_per_s': 0.25}}
    selections = [{'component_id': str(i), 'sampling_weight': 1., 'partition': 'development'} for i in range(3)]
    a = make_design([cadence]*3, selections, cfg); b = make_design([cadence]*3, selections, cfg)
    assert a == b and a['trial_count'] == 20 and a['signal_count'] == 30
    assert len({t['trial_id'] for t in a['trials']}) == 20


def test_known_crowded_catalogue_loss_is_traced_before_grouping():
    # All source values here are synthetic. Identical ON arrays deliberately
    # make the same weak native line fall below the fixed 50-candidate prefix.
    rng = np.random.default_rng(772); power = 1000+rng.normal(size=(16, 2048))
    for channel in np.arange(20, 2048, 24): power[:, channel-1:channel+2] += 100
    scans = tuple(Scan(f'crowded_{i}', power.copy() if i % 2 == 0 else 1000+rng.normal(size=power.shape),
                       1e9+np.arange(2048), np.arange(16.), 59000+i*50/86400, 'ON' if i % 2 == 0 else 'OFF',
                       'A' if i % 2 == 0 else f'OFF_{i}', 'synthetic_session', f'raw_{i}', 'SYNTHETIC_ONLY') for i in range(6))
    cadence = Cadence('synthetic_crowded', scans, False); config = SearchConfig(max_abs_drift_hz_per_s=.25)
    controls = {arm: process(cadence, config, arm) for arm in ['new', 'legacy']}
    result = controls['legacy']['searches']['crowded_0']
    assert result.coverage['uncapped_nms_candidates'] == 85
    assert result.coverage['candidates_lost_to_cap'] == 35 and len(result.hits) == 50
    dropped = result.catalogue_trace['uncapped_nms_candidates'][-1]
    trial = {**parameters(), 'cadence_id': cadence.cadence_id, 'start_channel': dropped['start_channel_ascending'],
             'drift_hz_per_s': 0., 'peak_power_sigma': .001}
    rows, _ = evaluate_trial(cadence, trial, controls, config, 'synthetic_component', 1., 1)
    row = rows[0]
    assert row['failure_type'] is None
    assert row['legacy_first_loss'] == 'catalogue_truncation_or_assignment'
    assert row['legacy_stages']['local_maximum_compatible'] and row['legacy_stages']['after_frequency_suppression_compatible']
    assert not row['legacy_stages']['generated'] and not row['legacy_stages']['grouped']
    assert row['legacy_safe_first_loss'] == row['legacy_strict_first_loss'] == row['legacy_first_loss']
