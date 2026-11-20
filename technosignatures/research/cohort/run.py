"""Execute a full paired morphology/amplitude pilot on acquired real cadences."""
import argparse
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import time

import numpy as np
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[2]/'.cache/matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', str(Path(__file__).resolve().parents[2]/'.cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from research.conventional.search import SearchConfig
from research.conventional.injection import parameter_manifest, inject
from research.pilot.run import preserved_original
from .acquire import load_cadence, array_hash
from .frame import HERE, write, digest
from .evaluate import process, evaluate_trial
from .statistics import rate, uncertainty, independent_cell_intervals

OUTCOMES = ['new_safe', 'new_strict', 'legacy_safe', 'legacy_strict']
ROOT = HERE.parents[1]


def make_design(cadences, selections, config):
    if not cadences or config['placements_per_family_amplitude_total'] < len(cadences): raise ValueError('Need at least one placement per component/cell')
    rng = np.random.default_rng(config['seed']); trials = []
    allocation = []
    n = config['placements_per_family_amplitude_total']; size = len(cadences)
    for family in config['families']:
        for amplitude in config['amplitudes']:
            counts = np.full(size, n//size, dtype=int); counts[rng.permutation(size)[:n % size]] += 1
            for index, (cadence, selected, count) in enumerate(zip(cadences, selections, counts.tolist())):
                if selected.get('partition') != 'development': raise ValueError('Locked partitions cannot be accessed by the development runner')
                span = float(cadence.offsets_s[-1]+cadence.scans[-1].power.shape[0]*cadence.scans[-1].dt)
                design = parameter_manifest(cadence.cadence_id, len(cadence.scans[0].frequency_hz), span, cadence.scans[0].df,
                                            int(rng.integers(2**32)), count, (family,), (amplitude,), config['search']['max_abs_drift_hz_per_s'])
                for trial in design['trials']:
                    trials.append({**trial, 'trial_id': f'trial_{len(trials):06d}', 'component_id': selected['component_id'],
                                   'sampling_weight': selected['sampling_weight'], 'placements_in_cell': count, 'partition': 'development'})
                allocation.append({'cadence_id': cadence.cadence_id, 'family': family, 'peak_power_sigma': amplitude, 'trials': count})
    return {'version': config['version'], 'seed': config['seed'], 'allocation': allocation, 'trials': trials,
            'trial_count': len(trials), 'signal_count': sum(2 if p.get('collision_offset_channels') is not None else 1 for p in trials),
            'weight_definition': 'inverse cadence inclusion probability divided by placements in component/cell and physical companions per trial; equal family/amplitude contribution',
            'created_before_injected_outcomes': True}


def ordered_bounded_map(function, trials, workers):
    """Keep only `workers` trials in flight; emit in the frozen design order."""
    if not isinstance(workers, int) or not 1 <= workers <= 4: raise ValueError('Trial workers must be 1..4')
    if workers == 1:
        yield from map(function, trials)
        return
    iterator = iter(trials)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = deque()
        for _ in range(workers):
            trial = next(iterator, None)
            if trial is not None: pending.append(executor.submit(function, trial))
        while pending:
            yield pending.popleft().result()
            trial = next(iterator, None)
            if trial is not None: pending.append(executor.submit(function, trial))


def run(output, acquisition_path, data_directory, config_path, smoke=False, resume=False):
    start = time.perf_counter(); output = Path(output)
    existing = output.exists() and any(output.iterdir())
    if existing and not resume: raise FileExistsError('Use a new results directory or explicit verified resume')
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(config_path).read_text())
    if config['legacy_cap'] != 50: raise ValueError('Historical reference cap is fixed at 50')
    acquisition = json.loads(Path(acquisition_path).read_text())
    if acquisition['acquired_complete_cadences'] != acquisition['selected_cadences']:
        raise ValueError('Acquisition attrition unresolved; refusing to label a successful-only subset as the intended cohort')
    records = acquisition['cadences']; cadences = [load_cadence(r, data_directory) for r in records]
    selected = [r['selection'] for r in records]
    if len({s['component_id'] for s in selected}) != len(selected): raise ValueError('Access batch must contain unique true parent-catalogue components')
    if smoke:
        config = {**config, 'seed': config['seed']+1000, 'families': ['continuous_linear'], 'amplitudes': [2., 8.],
                  'placements_per_family_amplitude_total': len(cadences)}
    design = make_design(cadences, selected, config)
    source_files = ([p for p in sorted(HERE.rglob('*.py')) if '__pycache__' not in p.parts and 'private' not in p.parts]
                    +sorted((HERE/'configs').glob('*.json'))+sorted((ROOT/'research/conventional').glob('*.py'))
                    +sorted((ROOT/'research/pilot').glob('*.py'))+[ROOT/'pipeline.py', ROOT/'requirements.lock'])
    source_manifest = {str(p.relative_to(ROOT)): {'sha256': digest(p), 'bytes': p.stat().st_size} for p in source_files}
    inputs = {'acquisition_sha256': digest(acquisition_path),
                                       'selection_sha256': acquisition['selection_sha256'],
                                       'frequency_plan_sha256': acquisition['frequency_plan_sha256'],
              'source_arrays': {str(r['archive_id']): r['scientific_array_sha256'] for c in records for r in c['source_records']}}
    frozen = {'execution_config.json': config, 'injection_design.json': design,
              'source_manifest.json': source_manifest, 'input_manifest.json': inputs}
    for name, value in frozen.items():
        if existing:
            if json.loads((output/name).read_text()) != value: raise ValueError(f'Resume rejected: frozen source/input/design differs in {name}')
        else: write(output/name, value)
    if existing:
        history = output/'resume_history'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        history.mkdir(parents=True)
        for name in ['signal_rows.jsonl', 'trial_metrics.jsonl']:
            if (output/name).exists(): shutil.copy2(output/name, history/name)
    settings = SearchConfig(**config['search']); controls = {}; native = []
    for cadence, selection in zip(cadences, selected):
        print('Native controls:', cadence.cadence_id, flush=True)
        arms = {arm: process(cadence, settings, arm, group_tolerance=config['group_tolerance_channels'],
                             off_threshold=config['cadence_off_score_threshold']) for arm in ['new', 'legacy']}
        controls[cadence.cadence_id] = arms
        native.append({'cadence_id': cadence.cadence_id, 'component_id': selection['component_id'],
                       'sampling_weight': selection['sampling_weight'],
                       'represented_exposure_s': sum(s.power.shape[0]*s.dt for s in cadence.scans),
                       'usable_time_bandwidth_hz_s': sum(int(s.usable.sum())*s.dt*s.df for s in cadence.scans),
                       'native_origin_labels': 'unresolved', 'arms': {arm: {'hit_count': sum(len(r.hits) for r in value['searches'].values()),
                           'cadence_event_count': len(value['cadence']['events']),
                           'strict_retained_events': sum(e['strict_experimental']['retained'] for e in value['cadence']['events']),
                           'coverage': {k: r.coverage for k, r in value['searches'].items()},
                           'score_sha256': {k: array_hash(r.scores) for k, r in value['searches'].items()}} for arm, value in arms.items()}})
    write(output/'native_controls.json', native)
    lookup = {c.cadence_id: c for c in cadences}; all_rows = []; metrics = []
    def checkpointed(trial):
        checkpoint = output/'trials'/f"{trial['trial_id']}.json"
        if checkpoint.exists():
            saved = json.loads(checkpoint.read_text())
            if saved['parameters'] != trial: raise ValueError('Checkpoint parameters do not match frozen design')
            return saved['rows'], saved['metrics']
        rows, detail = evaluate_trial(lookup[trial['cadence_id']], trial, controls[trial['cadence_id']], settings,
                                      trial['component_id'], trial['sampling_weight'], trial['placements_in_cell'],
                                      config['time_subsamples'], config['group_tolerance_channels'], config['cadence_off_score_threshold'])
        write(checkpoint, {'parameters': trial, 'rows': rows, 'metrics': detail})
        return rows, detail
    visual_id = next((t['trial_id'] for t in design['trials'] if t['family'] == 'continuous_linear' and t['peak_power_sigma'] == max(config['amplitudes'])), None)
    with (output/'signal_rows.jsonl').open('w') as row_file, (output/'trial_metrics.jsonl').open('w') as metric_file:
        executed = ordered_bounded_map(checkpointed, design['trials'], config.get('trial_workers', 1))
        for index, (trial, (rows, detail)) in enumerate(zip(design['trials'], executed)):
            if time.perf_counter()-start > config['max_wall_s']:
                write(output/'incomplete_execution.json', {'reason': 'wall_time_resource_limit', 'completed_trials': index, 'planned_trials': design['trial_count']})
                raise RuntimeError('Execution budget reached; partial records retained, no completed assessment claimed')
            cadence = lookup[trial['cadence_id']]
            for row in rows: row_file.write(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')
            metric_file.write(json.dumps(detail, sort_keys=True, allow_nan=False)+'\n'); row_file.flush(); metric_file.flush()
            all_rows.extend(rows); metrics.append(detail)
            if trial['trial_id'] == visual_id and not (output/'cohort_before_after.png').exists():
                after, _, _ = inject(cadence, trial, config['time_subsamples']); cadence_plot(output, cadence, after, trial['trial_id'])
            if index % 12 == 0 or index+1 == design['trial_count']:
                print(f"Trial {index+1}/{design['trial_count']}; signal rows {len(all_rows)}; elapsed {time.perf_counter()-start:.1f}s", flush=True)
    if len(all_rows) != design['signal_count']: raise AssertionError('Physical-signal denominator mismatch')
    summary = {'version': config['version'], 'smoke_only': smoke, 'trial_count': design['trial_count'], 'physical_signal_count': len(all_rows),
               'acquired_cadences': len(cadences), 'independent_components': len({r['component_id'] for r in all_rows}),
               'technical_failure_signals': sum(r['failure_type'] is not None for r in all_rows),
               'arms': {a: {'conservative': rate(all_rows, a), 'optimistic': rate(all_rows, a+'_optimistic'),
                            'searchable': rate(all_rows, a, True)} for a in OUTCOMES},
               'first_loss_counts': {arm: dict(Counter(r[arm+'_first_loss'] for r in all_rows)) for arm in ['new', 'legacy']},
               'policy_first_loss_counts': {arm: dict(Counter(r[arm+'_first_loss'] for r in all_rows)) for arm in OUTCOMES},
               'statistical_scope': 'Exploratory finite-frame spectral-tile cohort. Confidence procedures do not validate transport to arbitrary observations.',
               'main_60_component_gate_passed': False, 'receiver_hardware_identity_independently_verified': False,
               'locked_test_accessed': False, 'llm_introduced': False, 'preservation': preserved_original()}
    write(output/'summary.json', summary)
    write(output/'uncertainty.json', uncertainty(all_rows, OUTCOMES, replicates=config['bootstrap_replicates']))
    cells = []
    for family in config['families']:
        for amplitude in config['amplitudes']:
            rows = [r for r in all_rows if r['family'] == family and r['peak_power_sigma'] == amplitude]
            cells.append({'family': family, 'peak_power_sigma': amplitude, 'physical_signals': len(rows),
                          'arms': {a: rate(rows, a) for a in OUTCOMES},
                          'uncertainty': uncertainty(rows, OUTCOMES, replicates=config['bootstrap_replicates'])})
    write(output/'sensitivity_cells.json', cells)
    write(output/'conditional_binomial_diagnostics.json', independent_cell_intervals(all_rows, 'new_safe'))
    sensitivity_plot(output, cells, len(cadences))
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    write(output/'runtime.json', {'wall_s': time.perf_counter()-start, 'process_peak_rss_bytes': rss if platform.system() == 'Darwin' else rss*1024,
                                 'platform': platform.platform(), 'python': platform.python_version(), 'finished_utc': datetime.now(timezone.utc).isoformat()})
    if any(digest(ROOT/name) != entry['sha256'] for name, entry in source_manifest.items()):
        raise AssertionError('Source/config changed during execution; cannot validate this run as a frozen implementation')
    print(json.dumps({k: v for k, v in summary.items() if k != 'arms'}, indent=2), flush=True)
    if summary['technical_failure_signals']: raise RuntimeError('Technical failures remain in denominators; inspect retained records before claiming validated completion')
    return summary


def cadence_plot(output, before, after, trial_id):
    fig, axes = plt.subplots(6, 2, figsize=(12, 13), sharex=True, layout='constrained')
    low, high = np.percentile(np.concatenate([s.power[s.usable] for s in before.scans]), [1, 99.5])
    for i, (a, b, offset) in enumerate(zip(before.scans, after.scans, before.offsets_s)):
        for j, scan in enumerate([a, b]):
            x = (scan.frequency_hz-a.frequency_hz[0])/1000
            axes[i, j].imshow(scan.power, origin='lower', aspect='auto', extent=[x[0], x[-1], 0, len(scan.time_s)*scan.dt],
                              vmin=low, vmax=high, cmap='magma')
            axes[i, j].set_title(f"{scan.role}, cadence +{offset:.1f}s | "+('observed' if j == 0 else 'synthetic addition'))
            axes[i, j].set_ylabel('Scan time [s]')
    for ax in axes[-1]: ax.set_xlabel('Frequency offset [kHz]')
    fig.suptitle(f'Prospective cohort: predetermined example {trial_id}; common intensity limits')
    fig.savefig(output/'cohort_before_after.png', dpi=130); plt.close(fig)


def sensitivity_plot(output, cells, groups):
    families = list(dict.fromkeys(c['family'] for c in cells))
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained', squeeze=False)
    for ax, family in zip(axes.ravel(), families):
        chosen = [c for c in cells if c['family'] == family]
        for arm, label in [('new_safe', 'V2 review-safe'), ('legacy_safe', 'Historical + same downstream rules')]:
            ax.plot([c['peak_power_sigma'] for c in chosen], [c['arms'][arm]['rate'] for c in chosen], marker='o', label=label)
        ax.set_title(family.replace('_', ' ')); ax.set_xscale('log', base=2); ax.set_ylim(-0.03, 1.03)
        ax.set_xlabel('Peak / local power sigma'); ax.set_ylabel('Weighted full-domain recovery')
    for ax in axes.ravel()[len(families):]: ax.set_visible(False)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle(f'Prospective reduced cohort: {groups} independent components\nExploratory point curves; placement and group uncertainty are reported separately in JSON')
    fig.savefig(output/'cohort_sensitivity.png', dpi=140); plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acquisition', type=Path, default=HERE/'evidence/acquisition.json')
    p.add_argument('--data', type=Path, default=HERE/'data')
    p.add_argument('--config', type=Path, default=HERE/'configs/evaluation.json')
    p.add_argument('--output', type=Path, default=HERE/'results/pilot_v1')
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--resume', action='store_true')
    a = p.parse_args(); run(a.output, a.acquisition, a.data, a.config, a.smoke, a.resume)


if __name__ == '__main__': main()
