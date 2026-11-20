from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pytest

from research.conventional.data import Scan, Cadence
from research.conventional.search import SearchConfig, search
from research.conventional.events import group_events, match_tracks


def test_reversal_preserves_samples_and_mask(make_scan):
    scan = make_scan()
    mask = scan.usable.copy(); mask[2, 5] = False
    reversed_scan = replace(scan, power=scan.power[:, ::-1], frequency_hz=scan.frequency_hz[::-1], usable=mask[:, ::-1])
    np.testing.assert_array_equal(reversed_scan.power, scan.power)
    np.testing.assert_array_equal(reversed_scan.usable, mask)
    with pytest.raises(ValueError): reversed_scan.power[0, 0] = 0


def test_ghz_origin_does_not_hide_bad_channel_spacing(make_scan):
    scan = make_scan()
    freq = scan.frequency_hz.copy(); freq[20] += 0.1
    with pytest.raises(ValueError, match="lattice"): replace(scan, frequency_hz=freq)


def test_nonfinite_only_allowed_when_explicitly_masked(make_scan):
    scan = make_scan(); data = scan.power.copy(); data[0, 3] = np.nan
    with pytest.raises(ValueError, match="Non-finite"): replace(scan, power=data)
    mask = scan.usable.copy(); mask[0, 3] = False
    masked = replace(scan, power=data, usable=mask)
    result = search(masked, SearchConfig(max_abs_drift_hz_per_s=0.5))
    assert result.coverage["masked_track_trials"] > 0


@pytest.mark.parametrize("change", [{"time_s": np.arange(16)+1}, {"role": "UNKNOWN"}, {"session_id": ""}])
def test_invalid_observation_contracts_rejected(make_scan, change):
    with pytest.raises(ValueError): replace(make_scan(), **change)


def brute_scores(scan, result):
    """Independent scalar enumeration, no production support/tile helper."""
    normalized = np.zeros_like(scan.power)
    for t in range(len(scan.time_s)):
        row = scan.power[t, scan.usable[t]]
        med = np.median(row); sigma = 1.482602218505602*np.median(np.abs(row-med))
        normalized[t, scan.usable[t]] = (row-med)/sigma
    output = np.full_like(result.scores, np.nan)
    radius = result.config.boxcar_width_channels//2
    physical = masked = 0
    for di, drift in enumerate(result.drift_grid):
        values, starts = [], []
        for start in range(scan.power.shape[1]):
            cells = [(t, start+int(np.rint(drift*scan.time_s[t]/scan.df))+b)
                     for t in range(len(scan.time_s)) for b in range(-radius, radius+1)]
            if any(c < 0 or c >= scan.power.shape[1] for _, c in cells): continue
            physical += 1
            if any(not scan.usable[t, c] for t, c in cells): masked += 1; continue
            starts.append(start); values.append(sum(normalized[t, c] for t, c in cells))
        if len(values) >= 3:
            med = np.median(values); sigma = 1.482602218505602*np.median(np.abs(np.array(values)-med))
            if sigma > 0: output[di, starts] = (np.array(values)-med)/sigma
    return output, physical, masked


@pytest.mark.parametrize("tile", [1, 5, 13, 32, 1000])
def test_tiles_match_independent_brute_force_with_masks(make_scan, tile):
    mask = np.ones((5, 32), bool); mask[2, 8] = False; mask[4, 25] = False
    scan = make_scan(nt=5, nf=32, mask=mask)
    result = search(scan, SearchConfig(max_abs_drift_hz_per_s=1, tile_core_channels=tile))
    expected, physical, masked = brute_scores(scan, result)
    np.testing.assert_array_equal(np.isnan(result.scores), np.isnan(expected))
    np.testing.assert_allclose(result.scores, expected, atol=2e-12, rtol=2e-12, equal_nan=True)
    assert result.coverage["physical_track_trials"] == physical
    assert result.coverage["masked_track_trials"] == masked
    assert result.coverage["catalogue_truncated"] is False


def test_tile_boundary_crossing_and_signed_tracks_survive(make_scan):
    scan = make_scan(nt=12, nf=128)
    power = scan.power.copy(); channels = np.arange(128)
    truths = []
    for i, (start, drift) in enumerate([(25, 1.0), (100, -1.0), (65, 0.0)]):
        power += 35*np.exp(-0.5*((channels[None, :]-start-drift*scan.time_s[:, None])/0.7)**2)
        truths.append({"truth_id": str(i), "start_frequency_hz": scan.frequency_hz[start], "drift_hz_per_s": drift})
    altered = scan.with_power(power)
    small = search(altered, SearchConfig(max_abs_drift_hz_per_s=1, tile_core_channels=7))
    full = search(altered, SearchConfig(max_abs_drift_hz_per_s=1, tile_core_channels=128))
    np.testing.assert_allclose(small.scores, full.scores, rtol=0, atol=1e-12, equal_nan=True)
    assert [h['hit_id'] for h in small.hits] == [h['hit_id'] for h in full.hits]
    matched = match_tracks(truths, group_events(small)["events"], scan.time_s, scan.df)
    assert all(m["matched_id"] for m in matched)


def test_search_budget_fails_before_partial_catalogue(make_scan):
    with pytest.raises(ValueError, match="budget"): search(make_scan(), SearchConfig(max_score_cells=10))


def test_zero_scale_is_an_error_not_clean_observation(make_scan):
    with pytest.raises(ValueError, match="noise scale"): search(make_scan().with_power(np.ones((16, 256))))


def test_original_support_remediation_counts():
    import pipeline
    config = json.loads((pipeline.ROOT/"config.json").read_text())
    data, freq, times, metadata = pipeline.load_observation(pipeline.ROOT/config['dataset']['path'], config['dataset'])
    scan = Scan('regression', data, freq, times, metadata['start_mjd'], 'ON', 'DIAG_SGR_B2', 'fixture', 'fixture_raw', 'GBT_C_fixture')
    result = search(scan)
    assert result.coverage['physical_track_trials'] == result.coverage['evaluated_track_trials'] == 489730
    assert result.coverage['physical_track_trials']-390404 == 99326


def artificial_hits(result, paths):
    return [{"hit_id": str(i), "scan_id": result.scan.scan_id, "start_frequency_hz": result.scan.frequency_hz[0]+start,
             "start_channel_ascending": start, "drift_hz_per_s": drift, "robust_score": 30-i,
             "drift_grid_spacing_hz_per_s": result.drift_step, "time_support_end_s": float(result.scan.time_s[-1])}
            for i, (start, drift) in enumerate(paths)]


def test_complete_link_prevents_bridge_merging(make_scan):
    result = search(make_scan(), SearchConfig(max_abs_drift_hz_per_s=0.5))
    result.hits = artificial_hits(result, [(20, 0), (22, 0), (24, 0)])
    grouped = group_events(result, 3)
    assert [e['member_count'] for e in grouped['events']] == [2, 1]
    assert len(grouped['membership']) == 3


def test_crossing_tracks_distinct_but_compatible_duplicates_group(make_scan):
    result = search(make_scan(), SearchConfig(max_abs_drift_hz_per_s=1))
    result.hits = artificial_hits(result, [(20, 1), (21, 1), (25, -1)])
    events = group_events(result)['events']
    assert len(events) == 2 and events[0]['member_count'] == 2


def test_one_event_cannot_recover_two_signals():
    truths = [{"truth_id": str(i), "start_frequency_hz": 100+i, "drift_hz_per_s": 0} for i in range(2)]
    event = {"event_id": "e", "start_frequency_hz": 100, "drift_hz_per_s": 0}
    matches = match_tracks(truths, [event], np.arange(4), 1)
    assert sum(m['matched_id'] is not None for m in matches) == 1


def test_intermittent_truth_with_no_active_samples_cannot_match():
    truth = {'truth_id': 'inactive', 'start_frequency_hz': 100, 'drift_hz_per_s': 0, 'active_intervals_s': [[20, 30]]}
    event = {'event_id': 'native_unrelated', 'start_frequency_hz': 100, 'drift_hz_per_s': 0}
    match = match_tracks([truth], [event], np.arange(8.), 1)[0]
    assert match['matched_id'] is None and match['max_path_error_channels'] is None


def test_assignment_maximizes_recovered_signals_before_minimizing_error():
    truths = [{"truth_id": str(i), "start_frequency_hz": 20+i, "drift_hz_per_s": 0} for i in range(2)]
    events = [{"event_id": str(i), "start_frequency_hz": f, "drift_hz_per_s": 0} for i, f in enumerate([20, 18])]
    matches = match_tracks(truths, events, np.arange(4), 1, tolerance_channels=2)
    assert all(m['matched_id'] for m in matches)


def test_eighty_signals_not_cut_to_fifty():
    from research.pilot.run import gaussian_fixture
    root = Path(__file__).resolve().parents[3]
    audit = json.loads((root/'research/pilot/configs/audit.json').read_text())
    detector = json.loads((root/'config.json').read_text())['detector']
    _, power, freq, times, truths, _ = gaussian_fixture(audit['fully_synthetic_crowded_fixture'], detector)
    scan = Scan('crowded', power, freq, times, 59000, 'ON', 'synthetic', 'synthetic_session', 'synthetic_raw', 'SYNTHETIC_TEST_ONLY')
    result = search(scan, SearchConfig(max_abs_drift_hz_per_s=0.5))
    events = group_events(result)['events']
    truth_records = [{**t, 'truth_id': t['id']} for t in truths]
    matches = match_tracks(truth_records, events, times, 1)
    assert len(events) >= 80 and sum(m['matched_id'] is not None for m in matches) == 80
