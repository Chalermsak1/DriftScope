"""Execute the versioned conventional-development evidence package."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import time

import numpy as np
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[2]/'.cache/matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', str(Path(__file__).resolve().parents[2]/'.cache'))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pipeline as legacy
from research.pilot.run import preserved_original, gaussian_fixture
from research.pilot.accounting import traced_search
from .cadence import CadenceConfig, filter_cadence
from .cohort import records_from_release, components, readiness
from .data import Scan, release_cadences
from .events import group_events, match_tracks
from .injection import parameter_manifest, inject, integrated_gaussian
from .search import SearchConfig, search
from .sensitivity import evaluate_single_scan, _matching_grid
from .statistics import first_loss

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n")


def array_hash(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def baseline_scan():
    config = json.loads((ROOT/"config.json").read_text())
    power, freq, times, meta = legacy.load_observation(ROOT/config["dataset"]["path"], config["dataset"])
    return Scan("baseline_regression", power, freq, times, meta["start_mjd"], "ON", "DIAG_SGR_B2",
                "development_regression", meta["rawdatafile"], "GBT_C_regression"), config


def coverage_and_legacy_cases(output, config):
    scan, original = baseline_scan()
    settings = SearchConfig(**config["baseline_search"])
    corrected = search(scan, settings)
    whole = search(scan, replace(settings, tile_core_channels=scan.power.shape[1]))
    np.testing.assert_allclose(corrected.scores, whole.scores, rtol=0, atol=2e-12, equal_nan=True)
    assert [h["hit_id"] for h in corrected.hits] == [h["hit_id"] for h in whole.hits]
    old, _, old_coverage = traced_search(scan.power, scan.frequency_hz, scan.time_s, original["detector"])
    rows = []
    audit = json.loads((ROOT/"research/pilot/configs/audit.json").read_text())
    for case in audit["real_fixture_synthetic_trials"]:
        params = {**original["injection"], **{k: v for k, v in case.items() if k != "id"}}
        power, _, truth = legacy.inject_signal(scan.power, scan.frequency_hz, scan.time_s, params)
        old_after, old_trace, _ = traced_search(power, scan.frequency_hz, scan.time_s, original["detector"])
        result = search(scan.with_power(power), settings)
        grouped = group_events(result)
        truth["truth_id"] = case["id"]
        old_matches = match_tracks([truth], [{**c, "event_id": str(i)} for i, c in enumerate(old_after["candidates"])], scan.time_s, scan.df)
        new_matches = match_tracks([truth], grouped["events"], scan.time_s, scan.df)
        rows.append({"case_id": case["id"], "truth": truth,
                     "legacy_recovered": old_matches[0]["matched_id"] is not None,
                     "v2_recovered": new_matches[0]["matched_id"] is not None,
                     "v2_match": new_matches[0], "legacy_cap_loss_count": old_trace["summary"]["candidates_lost_to_cap"],
                     "v2_hit_count": len(result.hits), "v2_event_count": grouped["event_count"],
                     "experiment_kind": "original sampled-power regression scenarios; numerical start-coordinate comparison, separate from integrated-power sensitivity"})
    result = {"original_preservation": preserved_original(), "legacy": old_coverage, "v2": corrected.coverage,
              "whole_tile_scores_equal_atol": 2e-12, "whole_tile_hits_identical": True,
              "additional_discrete_tracks_evaluated": corrected.coverage["evaluated_track_trials"]-old_coverage["legacy_searched_track_trials"],
              "legacy_score_shape": list(old["score_map"].shape), "v2_score_shape": list(corrected.scores.shape),
              "v2_score_sha256": array_hash(corrected.scores), "regression_cases": rows,
              "score_compatibility": "Same row normalization and drift grid; profile normalization now uses all valid starts at each drift. V2 scores are not assumed identical/calibrated against the old common-guard scores."}
    write(output/"coverage_remediation.json", result)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout="constrained", sharey=True)
    original_mask = np.zeros_like(corrected.scores, dtype=float)
    original_mask[:, old['start_channels']] = 1
    for ax, title, data in zip(axes, ['Historical common guard', 'V2: every valid discrete path'], [original_mask, np.isfinite(corrected.scores)]):
        ax.imshow(data, origin='lower', aspect='auto', extent=[0, scan.power.shape[1], -4, 4], vmin=0, vmax=1, cmap='Blues')
        ax.set_title(title); ax.set_xlabel('Starting channel (ascending frequency)')
    axes[0].set_ylabel('Trial drift [Hz/s]')
    fig.suptitle('Search-domain accounting on original real regression observation')
    fig.savefig(output/'coverage_comparison.png', dpi=140); plt.close(fig)
    return scan, result


def crowded_case(output, config):
    audit = json.loads((ROOT/"research/pilot/configs/audit.json").read_text())
    detector = json.loads((ROOT/"config.json").read_text())["detector"]
    _, power, freq, times, truths, old_config = gaussian_fixture(audit["fully_synthetic_crowded_fixture"], detector)
    scan = Scan("synthetic_80", power, freq, times, 59000, 'ON', 'synthetic', 'synthetic_session', 'synthetic_raw', 'SYNTHETIC_ONLY')
    new = search(scan, SearchConfig(max_abs_drift_hz_per_s=0.5))
    grouped = group_events(new)
    old, trace, _ = traced_search(power, freq, times, old_config)
    truths = [{**t, 'truth_id': t['id']} for t in truths]
    matched = match_tracks(truths, grouped['events'], times, scan.df)
    old_matched = match_tracks(truths, [{**e, 'event_id': str(i)} for i, e in enumerate(old['candidates'])], times, scan.df)
    result = {'source_kind': 'fully_synthetic_stress_fixture', 'physical_signal_count': len(truths),
              'legacy': trace['summary'], 'legacy_signals_recovered': sum(m['matched_id'] is not None for m in old_matched),
              'v2_hit_count': len(new.hits), 'v2_event_count': len(grouped['events']),
              'v2_signals_recovered_one_to_one': sum(m['matched_id'] is not None for m in matched),
              'v2_catalogue_truncated': False, 'grouping': grouped, 'matches': matched}
    assert result['v2_signals_recovered_one_to_one'] == 80
    write(output/'crowded_stress.json', result)
    return result


def native_cadence_cases(output, config, release_path):
    cadences, spec = release_cadences(release_path)
    records = records_from_release(cadences)
    cohort = {'records': records, 'graph': components(records), 'readiness': readiness(records, True),
              'source_sha256': spec['sha256'], 'selection': 'existing candidate-selected release, development only'}
    write(output/'release_cohort_audit.json', cohort)
    cadence = cadences[0]
    settings = SearchConfig(**config['native_cadence_search'])
    cadence_settings = CadenceConfig(config['cadence_link_tolerance_channels'], config['off_forced_score_threshold'])
    before = {s.scan_id: search(s, settings) for s in cadence.scans}
    before_groups = {k: group_events(v) for k, v in before.items()}
    before_cadence = filter_cadence(cadence, before, before_groups, cadence_settings)
    write(output/'native_cadence_events.json', before_cadence)
    write(output/'native_scan_catalogues.json', {k: {'coverage': v.coverage, 'tiles': v.tiles, 'hits': v.hits, 'grouping': before_groups[k],
                                                   'score_shape': list(v.scores.shape), 'score_sha256': array_hash(v.scores)} for k, v in before.items()})
    physical_times = np.concatenate([s.time_s+offset+s.dt/2 for s, offset in zip(cadence.scans, cadence.offsets_s) if s.role == 'ON'])
    results = []
    for parameters in config['native_cases']:
        print('Cadence case:', parameters['trial_id'], flush=True)
        parameters = dict(parameters)
        if parameters.pop('first_on_only', False):
            parameters['active_intervals_s'] = [[0, cadence.scans[0].power.shape[0]*cadence.scans[0].dt]]
        after, truths, diagnostics = inject(cadence, parameters, config['integrated_injection_subsamples'])
        searches = {s.scan_id: (before[s.scan_id] if np.array_equal(s.power, original.power) else search(s, settings))
                    for s, original in zip(after.scans, cadence.scans)}
        # Reused search records refer to immutable original scans; preserve object identity.
        after = replace(after, scans=tuple(searches[s.scan_id].scan for s in after.scans))
        groups = {k: group_events(v) for k, v in searches.items()}
        filtered = filter_cadence(after, searches, groups, cadence_settings)
        native_matches = match_tracks(truths, before_cadence['events'], physical_times, cadence.scans[0].df, id_key='cadence_event_id')
        matches = {}
        for policy in ['review_safe', 'strict_experimental']:
            events = [e for e in filtered['events'] if e[policy]['retained']]
            matches[policy] = match_tracks(truths, events, physical_times, cadence.scans[0].df, id_key='cadence_event_id')
        scan_ledger = []
        for scan, offset in zip(after.scans, cadence.offsets_s):
            if scan.role != 'ON': continue
            local_events = [{**e, 'epoch_s': offset+scan.dt/2} for e in groups[scan.scan_id]['events']]
            local_hits = [{**h, 'epoch_s': offset+scan.dt/2} for h in searches[scan.scan_id].hits]
            scan_ledger.append({'scan_id': scan.scan_id, 'elapsed_start_s': float(offset),
                                'matches': match_tracks(truths, local_events, scan.time_s+offset+scan.dt/2, scan.df),
                                'hit_matches': match_tracks(truths, local_hits, scan.time_s+offset+scan.dt/2, scan.df, id_key='hit_id'),
                                'compatible_grid_scores': {t['truth_id']: _matching_grid(searches[scan.scan_id], {**t, 'epoch_s': -float(offset)}) for t in truths}})
        policy_ledger = []
        for policy, policy_matches in matches.items():
            for truth, matched, native_matched in zip(truths, policy_matches, native_matches):
                tid = truth['truth_id']
                generated = any(any(m['truth_id'] == tid and m['matched_id'] is not None for m in row['hit_matches']) for row in scan_ledger)
                grouped_signal = any(any(m['truth_id'] == tid and m['matched_id'] is not None for m in row['matches']) for row in scan_ledger)
                searchable = any(row['compatible_grid_scores'][tid] is not None for row in scan_ledger)
                entry = {'truth_id': tid, 'policy': policy, 'eligible': bool(abs(truth['drift_hz_per_s']) <= settings.max_abs_drift_hz_per_s),
                         'searchable': searchable, 'generated': generated, 'grouped': grouped_signal,
                         'cadence_retained': matched['matched_id'] is not None,
                         'ambiguous_native_match': native_matched['matched_id'] is not None,
                         'failure_type': None}
                entry['first_loss'] = first_loss(entry)
                policy_ledger.append(entry)
        record = {'case_id': parameters['trial_id'], 'source_kind': 'synthetic_injection_on_real_candidate_selected_cadence',
                  'parameters': parameters, 'truths': truths, 'injection': diagnostics,
                  'native_control_matches': native_matches, 'policy_matches': matches, 'on_scan_survival': scan_ledger,
                  'policy_signal_survival_ledger': policy_ledger,
                  'before_power_sha256': {s.scan_id: array_hash(s.power) for s in cadence.scans},
                  'after_power_sha256': {s.scan_id: array_hash(s.power) for s in after.scans},
                  'unchanged_off_scans': all(np.array_equal(a.power, b.power) for a, b in zip(cadence.scans, after.scans) if a.role == 'OFF'),
                  'cadence': filtered}
        results.append(record)
        write(output/f"cadence_case_{parameters['trial_id']}.json", record)
        if parameters['trial_id'] == 'global_on_only':
            _cadence_plot(output, cadence, after)
    write(output/'cadence_cases.json', {'search_config': asdict(settings), 'cadence_config': asdict(cadence_settings),
                                     'records': results, 'population_estimate': False})
    return cohort, results


def _cadence_plot(output, before, after):
    fig, axes = plt.subplots(6, 2, figsize=(12, 13), sharex=True, layout='constrained')
    low, high = np.percentile(np.concatenate([s.power.ravel() for s in before.scans]), [1, 99.5])
    for i, (a, b, offset) in enumerate(zip(before.scans, after.scans, before.offsets_s)):
        for j, scan in enumerate([a, b]):
            lo, hi = 700, 1300
            axes[i, j].imshow(scan.power[:, lo:hi], origin='lower', aspect='auto', cmap='magma', vmin=low, vmax=high,
                              extent=[(scan.frequency_hz[lo]-a.frequency_hz[0])/1000,
                                      (scan.frequency_hz[hi]-a.frequency_hz[0])/1000, 0, scan.power.shape[0]*scan.dt])
            axes[i, j].set_title(f'{scan.role}, cadence +{offset:.1f} s | '+('original observation' if j == 0 else 'integrated synthetic addition'))
            axes[i, j].set_ylabel('Scan time [s]')
    for ax in axes[-1]: ax.set_xlabel('Frequency offset from first channel [kHz]')
    fig.suptitle('One real candidate-selected cadence; same intensity limits before/after')
    fig.savefig(output/'integrated_cadence_before_after.png', dpi=130); plt.close(fig)


def convergence_cases(output, config, scan):
    records = []
    for name, df, dt, drift in [('C_fixture_max_drift', scan.df, scan.dt, 4.), ('L_engineering_max_drift', 2.7939677238464355, 18.253611008, 1.)]:
        freq = np.arange(256)*df
        truth = {'start_frequency_hz': 64*df, 'drift_hz_per_s': drift, 'fwhm_hz': 2*df}
        arrays = [integrated_gaussian(freq, np.arange(4)*dt, dt, truth, 1., n) for n in [32, 64, 128]]
        error = float(np.max(np.abs(arrays[1]-arrays[2]))/arrays[2].max())
        records.append({'case': name, 'dt_s': dt, 'df_hz': df, 'drift_hz_per_s': drift,
                        'relative_peak_error_32_vs_64': float(np.max(np.abs(arrays[0]-arrays[1]))/arrays[1].max()),
                        'relative_peak_error_64_vs_128': error,
                        'tolerance': config['convergence_relative_peak_tolerance_64_vs_128'],
                        'passed': error <= config['convergence_relative_peak_tolerance_64_vs_128']})
    write(output/'integration_convergence.json', records)
    if not all(r['passed'] for r in records): raise AssertionError('Integration convergence criterion failed')
    return records


def run(output, release_path, config_path=HERE/'configs/development.json'):
    start = time.perf_counter()
    output = Path(output)
    if output.exists() and any(output.iterdir()): raise FileExistsError('Use a new output directory to preserve prior evidence')
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(config_path).read_text())
    write(output/'execution_config.json', config)
    print('Coverage, regression and truncation audits', flush=True)
    scan, coverage = coverage_and_legacy_cases(output, config)
    crowded = crowded_case(output, config)
    convergence = convergence_cases(output, config, scan)
    full = parameter_manifest(scan.scan_id, scan.power.shape[1], scan.time_s[-1]+scan.dt, scan.df,
                              config['seed'], config['full_design_placements_per_family_amplitude'])
    write(output/'full_1152_trial_design_not_executed.json', full)
    design = parameter_manifest(scan.scan_id, scan.power.shape[1], scan.time_s[-1]+scan.dt, scan.df, config['seed']+1,
                                config['conditional_development_placements_per_amplitude'], families=('continuous_linear',))
    write(output/'executed_development_design.json', design)
    print('Executing conditional development trials:', design['trial_count'], flush=True)
    sensitivity = evaluate_single_scan(scan, design, SearchConfig(**config['baseline_search']), subsamples=config['integrated_injection_subsamples'],
                                       source_kind='synthetic_injection_on_real_development_observation')
    write(output/'conditional_sensitivity.json', sensitivity)
    if sensitivity['technical_failure_signal_count']: raise AssertionError('Development trials contain technical failures; inspect the retained ledger')
    _sensitivity_plot(output, sensitivity)
    cohort, cadence_cases = native_cadence_cases(output, config, release_path)
    preserved = preserved_original()
    summary = {'version': config['version'], 'preservation': preserved,
               'additional_valid_discrete_tracks_searched': coverage['additional_discrete_tracks_evaluated'],
               'v2_valid_discrete_support_coverage': coverage['v2']['physical_fraction_evaluated'],
               'fully_synthetic_80_line_recovered': crowded['v2_signals_recovered_one_to_one'],
               'executed_conditional_sensitivity_trials': design['trial_count'], 'executed_conditional_sensitivity_signals': len(sensitivity['signal_rows']),
               'generated_full_design_trials_not_executed': full['trial_count'], 'generated_full_design_signals_not_executed': full['signal_count'],
               'native_cadence_engineering_cases': len(cadence_cases), 'integration_convergence_passed': all(r['passed'] for r in convergence),
               'release_connected_components': cohort['graph']['component_count'],
               'representative_cohort_gate_passed': False, 'population_sensitivity_estimated': False, 'locked_test_opened': False,
               'llm_introduced': False,
               'scope': 'Validated conventional-development implementation and specified engineering experiments; representative cohort acquisition remains a separate unmet scientific gate.'}
    write(output/'summary.json', summary)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write(output/'runtime.json', {'wall_s': time.perf_counter()-start, 'process_peak_rss_bytes': rss if platform.system() == 'Darwin' else rss*1024,
                                'platform': platform.platform(), 'python': platform.python_version()})
    paths = [p for p in sorted(HERE.rglob('*.py')) if '__pycache__' not in p.parts]+sorted((HERE/'configs').glob('*.json'))
    write(output/'source_manifest.json', {str(p.relative_to(ROOT)): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in paths})
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def _sensitivity_plot(output, result):
    rows = result['signal_rows']
    amplitudes = sorted({r['peak_power_sigma'] for r in rows})
    values = {'Historical capped detector': [], 'V2 grouped events': []}
    for amplitude in amplitudes:
        cell = [r for r in rows if r['peak_power_sigma'] == amplitude and r['eligible']]
        for label, key in [('Historical capped detector', 'legacy_retained_conservative'), ('V2 grouped events', 'new_retained_conservative')]:
            values[label].append(sum(r[key] for r in cell)/len(cell) if cell else np.nan)
    fig, ax = plt.subplots(figsize=(8, 5), layout='constrained')
    for label, value in values.items(): ax.plot(amplitudes, value, marker='o', label=label)
    ax.set_xscale('log', base=2); ax.set_xticks(amplitudes, [str(a) for a in amplitudes]); ax.set_ylim(-0.03, 1.03)
    ax.set_xlabel('Continuous peak amplitude / pre-injection local power sigma')
    ax.set_ylabel('Conservative recovery / full declared eligible domain')
    ax.set_title('Conditional development recovery on ONE real regression cutout\n8 randomized placements/amplitude; no population confidence interval')
    ax.legend(); fig.savefig(output/'conditional_recovery.png', dpi=140); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE/'results/development_v2')
    parser.add_argument('--release-path', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=HERE/'configs/development.json')
    args = parser.parse_args()
    run(args.output, args.release_path, args.config)


if __name__ == '__main__': main()
