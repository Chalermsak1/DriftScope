from dataclasses import replace
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import ndtr

from research.conventional.cadence import filter_cadence
from research.conventional.data import Cadence
from research.conventional.events import group_events, match_tracks
from research.conventional.injection import integrated_gaussian, inject, parameter_manifest
from research.conventional.search import SearchConfig, search


def process(cadence):
    searches = {s.scan_id: search(s, SearchConfig(max_abs_drift_hz_per_s=0.25, score_threshold=10)) for s in cadence.scans}
    groups = {k: group_events(v) for k, v in searches.items()}
    return filter_cadence(cadence, searches, groups)


def recovered_truth(cadence, result, truths):
    times = np.concatenate([s.time_s+offset+s.dt/2 for s, offset in zip(cadence.scans, cadence.offsets_s) if s.role == 'ON'])
    matches = match_tracks(truths, result['events'], times, cadence.scans[0].df, id_key='cadence_event_id')
    assert matches[0]['matched_id'] is not None
    return next(e for e in result['events'] if e['cadence_event_id'] == matches[0]['matched_id'])


def test_global_chirp_through_gaps_and_off_unchanged(synthetic_cadence, signal_parameters):
    after, truths, _ = inject(synthetic_cadence, signal_parameters)
    for before, altered in zip(synthetic_cadence.scans, after.scans):
        if before.role == 'OFF': np.testing.assert_array_equal(before.power, altered.power)
    event = recovered_truth(after, process(after), truths)
    assert event['on_scans_with_events'] == 3
    assert event['strict_experimental']['retained']
    assert abs(event['drift_hz_per_s']-0.08) < 0.01


@pytest.mark.parametrize('response', [0.1, 1.0])
def test_off_leakage_is_measured_and_safe_policy_retains(synthetic_cadence, signal_parameters, response):
    after, truths, _ = inject(synthetic_cadence, {**signal_parameters, 'off_response': response})
    event = recovered_truth(after, process(after), truths)
    assert event['off_coincidence']
    assert event['review_safe']['retained'] and not event['strict_experimental']['retained']


def test_intermittent_on_loss_is_explicit(synthetic_cadence, signal_parameters):
    params = {**signal_parameters, 'active_intervals_s': [[0, 16]], 'family': 'intermittent'}
    after, truths, _ = inject(synthetic_cadence, params)
    result = process(after)
    event = next(e for e in result['events'] if e['on_scans_with_events'] == 1)
    assert event['strict_experimental']['decision'] == 'reject_missing_on_persistence'
    assert event['review_safe']['retained']


def test_missing_off_is_not_evidence_of_absence(synthetic_cadence, signal_parameters):
    after, truths, _ = inject(synthetic_cadence, signal_parameters)
    partial = replace(after, scans=after.scans[:-1])
    event = recovered_truth(partial, process(partial), truths)
    assert event['coverage_unknown']
    assert event['strict_experimental']['decision'] == 'escalate_incomplete_search_or_cadence'


def test_masked_off_path_escalates(synthetic_cadence, signal_parameters):
    after, truths, _ = inject(synthetic_cadence, signal_parameters)
    scans = list(after.scans); mask = scans[1].usable.copy(); mask[:, 65:125] = False
    scans[1] = replace(scans[1], usable=mask)
    after = replace(after, scans=tuple(scans))
    event = recovered_truth(after, process(after), truths)
    assert event['coverage_unknown'] and event['strict_experimental']['retained']


def test_reordered_cadence_rejected(synthetic_cadence):
    with pytest.raises(ValueError, match='reordered'): replace(synthetic_cadence, scans=synthetic_cadence.scans[::-1])


def test_mislabeled_on_as_off_rejected(synthetic_cadence):
    scans = list(synthetic_cadence.scans); scans[2] = replace(scans[2], role='OFF')
    with pytest.raises(ValueError, match='OFF target'): replace(synthetic_cadence, scans=tuple(scans))


@pytest.mark.parametrize('drift', [-2.3, 0.0, 2.3])
def test_integrated_profile_power_and_centroid(drift):
    freq = np.arange(-100, 101, dtype=float); times = np.array([0., 1., 2.])
    truth = {'start_frequency_hz': 0., 'drift_hz_per_s': drift, 'fwhm_hz': 2.}
    profile = integrated_gaussian(freq, times, 1., truth, 4., 128)
    sigma = 2/(2*np.sqrt(2*np.log(2)))
    np.testing.assert_allclose(profile.sum(axis=1), 4*sigma*np.sqrt(2*np.pi), rtol=1e-12)
    np.testing.assert_allclose((profile*freq).sum(axis=1)/profile.sum(axis=1), drift*(times+0.5), atol=1e-5)


def test_time_quadrature_matches_independent_adaptive_integral():
    freq = np.arange(-8, 9, dtype=float); truth = {'start_frequency_hz': 0.2, 'drift_hz_per_s': 4.3, 'fwhm_hz': 0.8}
    sigma = truth['fwhm_hz']/(2*np.sqrt(2*np.log(2)))
    def at_time(t):
        center = 0.2+4.3*t
        return sigma*np.sqrt(2*np.pi)*(ndtr((2.5-center)/sigma)-ndtr((1.5-center)/sigma))
    expected = quad(at_time, 0, 1, epsabs=1e-12)[0]
    low = integrated_gaussian(freq, np.array([0.]), 1, truth, 1, 4)[0, 10]
    high = integrated_gaussian(freq, np.array([0.]), 1, truth, 1, 256)[0, 10]
    assert abs(high-expected) < abs(low-expected)
    assert abs(high-expected) < 1e-6


def test_sham_is_exact_and_original_arrays_untouched(synthetic_cadence, signal_parameters):
    saved = [s.power.copy() for s in synthetic_cadence.scans]
    after, _, _ = inject(synthetic_cadence, {**signal_parameters, 'peak_power_sigma': 0})
    for scan, altered, before in zip(synthetic_cadence.scans, after.scans, saved):
        np.testing.assert_array_equal(scan.power, before)
        np.testing.assert_array_equal(altered.power, before)


def test_full_design_records_all_parameters_and_signal_denominators():
    a = parameter_manifest('development', 1024, 45, 1.4, seed=11)
    b = parameter_manifest('development', 1024, 45, 1.4, seed=11)
    assert a == b and a['trial_count'] == 1152 and a['signal_count'] == 1344
    assert any(t['start_channel'] < 30 for t in a['trials'])
    assert a['status'] == 'generated_design_not_a_claim_of_execution'
