from copy import deepcopy
import urllib.parse

import numpy as np
import pytest

from research.conventional.archive import collect_frame
from research.conventional.cohort import components, assert_no_split_leakage, propose_split, sample_components, readiness, propose_metadata_cadences
from research.conventional.statistics import summary, paired_cluster_interval


def records():
    """Fabricated metadata for unit testing only; never observational evidence."""
    return [{'cadence_id': name, 'target_ids': [target], 'session_ids': [session], 'raw_ids': [raw],
             'candidate_selected': False, 'receiver': 'SYNTHETIC_METADATA', 'receiver_verified': True,
             'headers_validated': True, 'samples_acquired_and_verified': True}
            for name, target, session, raw in [('A', 'T1', 'S1', 'R1'), ('B', 'T2', 'S2', 'R1'),
                                               ('C', 'T2', 'S3', 'R3'), ('D', 'T4', 'S4', 'R4')]]


def test_transitive_raw_target_session_components_and_leakage():
    graph = components(records())
    assert sorted(g['cadence_ids'] for g in graph['components']) == [['A', 'B', 'C'], ['D']]
    with pytest.raises(ValueError, match='crosses'):
        assert_no_split_leakage(records(), {'A': 'development', 'B': 'development', 'C': 'test', 'D': 'test'})


def test_split_cannot_break_component_to_fill_quota():
    with pytest.raises(ValueError, match='Allocation'):
        propose_split(records(), {'development': 2, 'validation': 1, 'test': 1}, 5)
    split = propose_split(records(), {'development': 1, 'validation': 0, 'test': 1}, 5)
    assert_no_split_leakage(records(), split['assignments'])
    assert split['status'] == 'proposed_not_locked'


def test_candidate_selected_data_cannot_enter_locked_partitions():
    rows = records(); rows[3]['candidate_selected'] = True
    with pytest.raises(ValueError, match='Candidate-selected'):
        assert_no_split_leakage(rows, {'A': 'development', 'B': 'development', 'C': 'development', 'D': 'test'})
    with pytest.raises(ValueError, match='independent'): sample_components(rows, 1, 2)


def test_unknown_linkage_prevents_false_independence():
    rows = records(); rows[0]['session_ids'] = ['unknown']
    with pytest.raises(ValueError, match='Missing'): components(rows)


def test_coordinate_aliases_link_even_with_different_target_names():
    rows = records()
    rows[0]['on_pointings'] = [{'ra_deg': 359.9999, 'dec_deg': 0.}]
    rows[3]['on_pointings'] = [{'ra_deg': 0.0001, 'dec_deg': 0.}]
    assert components(rows)['component_count'] == 1
    assert any(e['link_type'].startswith('coordinate_alias') for e in components(rows)['edges'])


def test_sampling_probabilities_account_for_two_stages():
    selected = sample_components(records(), 2, 7)
    assert len(selected) == 2
    for item in selected:
        expected = 1/3 if item['cadence_id'] in {'A', 'B', 'C'} else 1
        assert item['cadence_inclusion_probability'] == expected
        assert item['sampling_weight'] == 1/expected


def test_readiness_requires_actual_data_not_only_good_metadata():
    rows = records(); rows[0]['samples_acquired_and_verified'] = False
    gate = readiness(rows, True, min_components=2)
    assert not gate['ready_for_representative_sensitivity']
    assert 'observational_samples_not_acquired_and_verified' in gate['unmet_gates']
    assert not readiness(records(), False, 2)['ready_for_representative_sensitivity']


def archive_config(**kwargs):
    return {'api_url': 'https://example.invalid/api', 'start_mjd': 58000., 'stop_mjd': 58001.,
            'frequency_start_mhz': 4000., 'frequency_stop_mhz': 8000., 'max_requests': 8,
            'query_limit': 4, 'max_response_bytes': 10000, 'seed': 1, **kwargs}


def test_saturated_metadata_queries_bisect_instead_of_taking_first_page():
    data = [{'id': i, 'mjd': 58000+(i+0.5)/6, 'telescope': 'GBT', 'center_freq': 6000,
             'target': 'unit_test', 'url': f'https://example.invalid/AGBT_TEST/file{i}.gpuspec.0000.h5', 'size': 1} for i in range(6)]
    def fake(url):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        lo, hi = float(query['time-start'][0]), float(query['time-end'][0])
        selected = [r for r in data if lo <= r['mjd'] <= hi][:4]
        return {'result': 'success', 'data': selected}, url
    frame = collect_frame(archive_config(), fake)
    assert frame['frame_complete_with_respect_to_unsaturated_api_queries']
    assert len(frame['rows']) == 6 and len(frame['attempts']) == 3


def test_query_budget_exhaustion_marks_frame_incomplete():
    def saturated(url): return {'result': 'success', 'data': [dict(id=i) for i in range(4)]}, url
    result = collect_frame(archive_config(max_requests=1), saturated)
    assert not result['frame_complete_with_respect_to_unsaturated_api_queries']
    assert not result['readiness']['ready_for_representative_sensitivity']


def test_metadata_http_failure_is_evidence_not_an_empty_complete_frame():
    def failure(url): raise TimeoutError('synthetic network failure')
    result = collect_frame(archive_config(), failure)
    assert result['attempts'][0]['failure_type'] == 'TimeoutError'
    assert not result['frame_complete_with_respect_to_unsaturated_api_queries']


def test_names_alone_do_not_establish_same_on_pointing():
    rows = []
    for i in range(6):
        on = i % 2 == 0
        rows.append({'id': i, 'mjd': 59000+i*0.001, 'target': 'A' if on else 'A_OFF',
                     'ra': 10+(0.0006 if i == 2 else 0) if on else 20, 'decl': 0.,
                     'url': f'https://example.invalid/AGBT_TEST/file{i}.gpuspec.0000.h5', 'size': 1,
                     'telescope': 'GBT', 'center_freq': 6000.})
    rejected = []
    assert propose_metadata_cadences(rows, rejected) == []
    assert 'ON_pointing' in rejected[0]['reasons'][0]


def outcome(eligible=True, searchable=True, kept=True, ambiguous=False, component='g1', weight=1.):
    return {'eligible': eligible, 'searchable': searchable, 'generated': kept, 'grouped': kept,
            'cadence_retained': kept, 'ambiguous_native_match': ambiguous, 'component_id': component,
            'weight': weight, 'left': False, 'right': kept}


def test_domain_denominators_and_ambiguity_bounds():
    rows = [outcome(weight=2), outcome(searchable=False, kept=False), outcome(ambiguous=True), outcome(eligible=False, searchable=False, kept=False)]
    conservative = summary(rows); optimistic = summary(rows, conservative=False)
    assert conservative['eligible_weight'] == 4 and conservative['searchable_weight'] == 3
    assert conservative['full_declared_domain_recovery'] == 0.5
    assert conservative['searchable_domain_recovery'] == 2/3
    assert optimistic['full_declared_domain_recovery'] == 0.75


def test_technical_failure_stays_in_denominator():
    broken = outcome(searchable=False, kept=False); broken['failure_type'] = 'SyntheticTestFailure'
    result = summary([outcome(), broken])
    assert result['full_declared_domain_recovery'] == 0.5
    assert result['first_loss_counts']['technical_failure:SyntheticTestFailure'] == 1


def test_one_component_does_not_create_population_interval():
    result = paired_cluster_interval([outcome(), outcome(kept=False)], 'left', 'right')
    assert result['point_difference'] == 0.5 and result['interval_95'] is None
    assert result['component_count'] == 1


def test_cluster_bootstrap_preserves_pairing_and_group_multiplicity():
    rows = [outcome(component='a', weight=2), outcome(component='a'), outcome(component='b', kept=False), outcome(component='c', kept=False)]
    first = paired_cluster_interval(rows, 'left', 'right', seed=9)
    second = paired_cluster_interval(rows, 'left', 'right', seed=9)
    assert first == second and first['component_count'] == 3
    assert first['point_difference'] == 3/5
    assert first['interval_95'][0] <= 3/5 <= first['interval_95'][1]


def test_degenerate_bootstrap_does_not_certify_zero_future_loss():
    rows = [outcome(component='a'), outcome(component='b')]
    result = paired_cluster_interval(rows, 'left', 'right')
    assert result['empirical_percentiles_95'] == [1., 1.]
    assert result['interval_95'] is None and 'unresolved' in result['status']


@pytest.mark.parametrize('weight', [0., -1., np.inf, np.nan])
def test_invalid_weights_rejected(weight):
    with pytest.raises(ValueError): summary([outcome(weight=weight)])
