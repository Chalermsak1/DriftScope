"""Independent source-map, quadrature, offline-array and repeat-run checks."""
import argparse
import json
from pathlib import Path
import time

import numpy as np

from research.conventional.search import search as reference_search, SearchConfig
from research.conventional.injection import inject, parameter_manifest
from .fast_search import search as vectorized_search
from .acquire import load_cadence, array_hash
from .frame import HERE, write, digest


def compare_acquisitions(online, offline):
    a, b = [json.loads(Path(p).read_text()) for p in [online, offline]]
    checks = {k: a[k] == b[k] for k in ['selection_sha256', 'frequency_plan_sha256', 'selected_cadences',
                                        'acquired_complete_cadences', 'files_acquired']}
    checks['offline_no_network'] = b['offline'] and b['http_payload_bytes_reserved_including_retry_attempts'] == 0
    left = {r['archive_id']: r for c in a['cadences'] for r in c['source_records']}
    right = {r['archive_id']: r for c in b['cadences'] for r in c['source_records']}
    checks['source_ids'] = left.keys() == right.keys()
    for key in left:
        checks[str(key)] = key in right and left[key]['status'] == right[key]['status'] == 'acquired' and all(
            left[key][field] == right[key][field] for field in ['scientific_array_sha256', 'header', 'original_channel_slice_half_open'])
    result = {'all_checks_passed': all(checks.values()), 'checks': checks,
              'scope': 'Every power, physical frequency, integration-start time and usable-mask array; whole originals remain unverified.'}
    if not result['all_checks_passed']: raise AssertionError(result)
    return result


def source_checks(acquisition, directory, config):
    evidence = json.loads(Path(acquisition).read_text()); settings = json.loads(Path(config).read_text())
    if evidence['acquired_complete_cadences'] != evidence['selected_cadences']: raise ValueError('Incomplete cohort')
    search_config = SearchConfig(**settings['search']); maps = []; quadrature = []
    for record in evidence['cadences']:
        cadence = load_cadence(record, directory)
        for scan in cadence.scans:
            start = time.perf_counter(); a = reference_search(scan, search_config); scalar_time = time.perf_counter()-start
            start = time.perf_counter(); b = vectorized_search(scan, search_config); vector_time = time.perf_counter()-start
            check = {'scan_id': scan.scan_id, 'score_maps_bitwise_equal': array_hash(a.scores) == array_hash(b.scores),
                     'score_values_equal': np.array_equal(a.scores, b.scores, equal_nan=True),
                     'reference_score_sha256': array_hash(a.scores), 'vectorized_score_sha256': array_hash(b.scores),
                     'hits_identical': a.hits == b.hits, 'coverage_identical': a.coverage == b.coverage,
                     'tiles_identical': a.tiles == b.tiles, 'reference_wall_s': scalar_time, 'vectorized_wall_s': vector_time}
            maps.append(check)
            if not all(check[k] for k in ['score_maps_bitwise_equal', 'score_values_equal', 'hits_identical', 'coverage_identical', 'tiles_identical']):
                raise AssertionError(check)
        span = float(cadence.offsets_s[-1]+len(cadence.scans[-1].time_s)*cadence.scans[-1].dt)
        design = parameter_manifest(cadence.cadence_id, len(cadence.scans[0].frequency_hz), span, cadence.scans[0].df,
                                    20261125, 1, settings['families'], [8.], search_config.max_abs_drift_hz_per_s)
        for parameters in design['trials']:
            versions = [inject(cadence, parameters, n) for n in [32, 64, 128]]
            peak = versions[0][2]['continuous_peak_power_before_bin_time_averaging']
            differences = {}
            for left, right in [(0, 2), (1, 2)]:
                differences[f'{[32,64,128][left]}_versus_128_max_abs_difference_over_continuous_peak'] = float(max(
                    np.max(np.abs(x.power-y.power)) for x, y in zip(versions[left][0].scans, versions[right][0].scans))/peak)
            quadrature.append({'cadence_id': cadence.cadence_id, 'family': parameters['family'], **differences})
        print('Independent source checks:', cadence.cadence_id, flush=True)
    return {'all_source_maps_identical': True, 'source_map_count': len(maps), 'source_maps': maps,
            'quadrature_audits': quadrature, 'quadrature_scope': 'One independently seeded placement per family/component. Comparisons are numerical diagnostics, not exhaustive error bounds. Intermittent edges use midpoint sampling and can have larger error.',
            'timing_scope': 'Individual executions with concurrent workloads; not a dedicated performance benchmark.'}


def compare_runs(reference, repeat):
    reference, repeat = Path(reference), Path(repeat)
    excluded = {'runtime.json', 'incomplete_execution.json'}
    files = [p for p in reference.iterdir() if p.suffix in {'.json', '.jsonl'} and p.name not in excluded]
    checks = {p.name: (repeat/p.name).is_file() and p.read_bytes() == (repeat/p.name).read_bytes() for p in sorted(files)}
    left = sorted(p.name for p in (reference/'trials').glob('*.json'))
    right = sorted(p.name for p in (repeat/'trials').glob('*.json'))
    checks['checkpoint_ids'] = left == right
    checks['all_trial_checkpoints'] = all((reference/'trials'/n).read_bytes() == (repeat/'trials'/n).read_bytes() for n in left) if left == right else False
    result = {'all_checks_passed': all(checks.values()), 'checks': checks, 'trial_checkpoints_compared': len(left),
              'scope': 'Exact scientific JSON/JSONL and all trial records in the same environment. PNG container bytes and wall time are excluded.'}
    if not result['all_checks_passed']: raise AssertionError(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acquisition', type=Path, default=HERE/'evidence/acquisition.json')
    parser.add_argument('--offline', type=Path)
    parser.add_argument('--data', type=Path, default=HERE/'data')
    parser.add_argument('--config', type=Path, default=HERE/'configs/evaluation.json')
    parser.add_argument('--source-checks', action='store_true')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--repeat', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = {}
    if args.offline: result['offline_reconstruction'] = compare_acquisitions(args.acquisition, args.offline)
    if args.source_checks: result['source_checks'] = source_checks(args.acquisition, args.data, args.config)
    if args.reference and args.repeat: result['numerical_repeat'] = compare_runs(args.reference, args.repeat)
    if not result: parser.error('Select at least one verification')
    result['input_acquisition_sha256'] = digest(args.acquisition)
    write(args.output, result)


if __name__ == '__main__': main()
