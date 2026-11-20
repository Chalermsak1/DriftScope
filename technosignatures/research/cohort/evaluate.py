"""Paired conventional pipelines on prospectively acquired complete cadences."""
from dataclasses import asdict, dataclass
import numpy as np

import pipeline as legacy
from research.pilot.accounting import catalogue_trace, coverage as legacy_coverage
from research.conventional.search import SearchConfig, SearchResult
from .fast_search import search
from research.conventional.events import group_events, hierarchical_matches, match_tracks, track_values, path_distance
from research.conventional.cadence import filter_cadence, CadenceConfig
from research.conventional.injection import inject


@dataclass
class AuditedSearchResult(SearchResult):
    catalogue_trace: dict = None


def safe_search(scan, config, arm):
    """Record preprocessing failure as unsearched support, never absent signal."""
    try:
        if arm == 'new': return search(scan, config)
        if not scan.usable.all(): raise ValueError('Historical reference cannot process missing/masked samples')
        settings = {k: v for k, v in asdict(config).items() if k not in {'tile_core_channels', 'max_score_cells'}}
        settings['max_candidates'] = 50
        result = legacy.detect(scan.power, scan.frequency_hz, scan.time_s, settings)
        trace = catalogue_trace(result, settings, scan.frequency_hz)
        scores = np.full((len(result['drift_grid_hz_per_s']), len(scan.frequency_hz)), np.nan)
        scores[:, result['start_channels']] = result['score_map']
        hits = [{**h, 'hit_id': f'{scan.scan_id}_legacy_{i:06d}', 'scan_id': scan.scan_id,
                 'drift_grid_spacing_hz_per_s': float(result['drift_grid_hz_per_s'][1]-result['drift_grid_hz_per_s'][0]),
                 'time_support_start_s': 0.0, 'time_support_end_s': float(scan.time_s[-1]),
                 'reference_time_after_scan_start_s': scan.dt/2} for i, h in enumerate(result['candidates'])]
        return AuditedSearchResult(scan, config, result['drift_grid_hz_per_s'], scores, hits,
                            {'evaluated_track_trials': int(np.isfinite(scores).sum()), **trace['summary'],
                             'coverage_accounting': legacy_coverage(len(scan.frequency_hz), scan.time_s, scan.df, settings),
                             'event_grouping_status': 'applied_downstream_by_process',
                             'cadence_filter_status': 'applied_downstream_by_process'}, [], trace)
    except ValueError as exc:
        half = max(1, int(np.ceil(config.max_abs_drift_hz_per_s*scan.time_s[-1]/(config.max_endpoint_grid_error_channels*scan.df))))
        drifts = np.linspace(-config.max_abs_drift_hz_per_s, config.max_abs_drift_hz_per_s, 2*half+1)
        if len(drifts)*len(scan.frequency_hz) > config.max_score_cells: raise
        return SearchResult(scan, config, drifts, np.full((len(drifts), len(scan.frequency_hz)), np.nan), [],
                            {'evaluated_track_trials': 0, 'preprocessing_failure': str(exc), 'candidate_cap': 50 if arm == 'legacy' else None}, [])


def process(cadence, config, arm, reuse=None, group_tolerance=3.0, off_threshold=6.0):
    results = {}
    for scan in cadence.scans:
        previous = reuse['searches'].get(scan.scan_id) if reuse else None
        results[scan.scan_id] = previous if previous is not None and np.array_equal(previous.scan.power, scan.power, equal_nan=True) else safe_search(scan, config, arm)
    # The cadence validator requires identity with the actual searched immutable arrays.
    from dataclasses import replace
    represented = replace(cadence, scans=tuple(results[s.scan_id].scan for s in cadence.scans))
    grouped = {k: group_events(v, group_tolerance) for k, v in results.items()}
    events = filter_cadence(represented, results, grouped, CadenceConfig(group_tolerance, off_threshold))
    return {'searches': results, 'grouped': grouped, 'cadence': events}


def active_times(truth, times):
    if 'active_intervals_s' not in truth: return np.ones(len(times), bool)
    active = np.zeros(len(times), bool)
    for low, high in truth['active_intervals_s']: active |= (times >= low) & (times < high)
    return active


def compatible_score(result, truth, offset, tolerance=3.0):
    scan = result.scan; physical = scan.time_s+offset+scan.dt/2
    active = active_times(truth, physical)
    if not active.any(): return None
    targets = track_values(truth, physical[active]); times = scan.time_s[active]
    bound = tolerance*scan.df; best = None
    for di, drift in enumerate(result.drift_grid):
        origins = targets-drift*times
        low, high = float(np.max(origins-bound)), float(np.min(origins+bound))
        if low > high: continue
        a = np.searchsorted(scan.frequency_hz, low, side='left'); b = np.searchsorted(scan.frequency_hz, high, side='right')
        values = result.scores[di, a:b]; values = values[np.isfinite(values)]
        if len(values): best = max(best, float(values.max())) if best is not None else float(values.max())
    return best


def truths_for_parameters(cadence, parameters):
    """Allocate complete truth before invoking an injector that can fail."""
    scan = cadence.scans[0]
    base = {'truth_id': parameters['trial_id']+'_signal_0', 'epoch_s': 0.0,
            'start_frequency_hz': float(scan.frequency_hz[0]+parameters['start_channel']*scan.df),
            'drift_hz_per_s': parameters['drift_hz_per_s'], 'fwhm_hz': parameters['fwhm_channels']*scan.df,
            'curvature_hz_per_s2': parameters.get('curvature_hz_per_s2', 0.0)}
    for name in ['active_intervals_s', 'modulation_period_s', 'modulation_phase']:
        if parameters.get(name) is not None: base[name] = parameters[name]
    truths = [base]
    if parameters.get('collision_offset_channels') is not None:
        truths.append({**base, 'truth_id': parameters['trial_id']+'_signal_1',
                       'start_frequency_hz': base['start_frequency_hz']+parameters['collision_offset_channels']*scan.df,
                       'drift_hz_per_s': -base['drift_hz_per_s']})
    return truths


def native_ambiguities(truths, native_events, physical_times, df):
    # Ambiguity is ANY compatible control event. Unlike positive recovery, two
    # truths may both be confounded by the same unknown native event.
    return {t['truth_id']: match_tracks([t], native_events, physical_times, df, id_key='cadence_event_id')[0]['matched_id'] is not None for t in truths}


def evaluate_trial(cadence, parameters, controls, settings, component_id, sampling_weight, placements_in_cell, subsamples=32,
                   group_tolerance=3.0, off_threshold=6.0):
    if parameters.get('partition', 'development') != 'development': raise ValueError('Development evaluation cannot open locked partitions')
    truths = truths_for_parameters(cadence, parameters)
    df = cadence.scans[0].df; first = cadence.scans[0]
    physical = np.concatenate([s.time_s+o+s.dt/2 for s, o in zip(cadence.scans, cadence.offsets_s) if s.role == 'ON'])
    weight = sampling_weight/(placements_in_cell*len(truths))
    rows = [{'trial_id': parameters['trial_id'], 'truth_id': t['truth_id'], 'component_id': component_id,
             'cadence_id': cadence.cadence_id, 'family': parameters['family'], 'peak_power_sigma': parameters['peak_power_sigma'],
             'weight': weight, 'eligible': bool(first.frequency_hz[0] <= t['start_frequency_hz'] <= first.frequency_hz[-1]
                                                and abs(t['drift_hz_per_s']) <= settings.max_abs_drift_hz_per_s),
             'searchable': False, 'failure_type': None} for t in truths]
    try:
        altered, injected_truths, diagnostics = inject(cadence, parameters, subsamples)
        if truths != injected_truths: raise AssertionError('Independent preallocated truth differs from injector')
        stages = {}
        for arm in ['new', 'legacy']:
            processed = process(altered, settings, arm, controls[arm], group_tolerance, off_threshold)
            by_truth = {t['truth_id']: {'searchable': False, 'generated': False, 'grouped': False, 'best_score': None, 'on_piece_count': 0,
                                      'matched_on_event_ids': [],
                                      'local_maximum_compatible': False, 'after_frequency_suppression_compatible': False} for t in truths}
            for scan, offset in zip(altered.scans, altered.offsets_s):
                if scan.role != 'ON': continue
                result = processed['searches'][scan.scan_id]; group = processed['grouped'][scan.scan_id]
                epoch = float(offset)+scan.dt/2
                ancestors = hierarchical_matches(truths, [{**h, 'epoch_s': epoch} for h in result.hits],
                                                 [{**e, 'epoch_s': epoch} for e in group['events']], scan.time_s+epoch, scan.df)
                trace = getattr(result, 'catalogue_trace', None)
                compatibility = {}
                if trace:
                    for label, key in [('local_maximum_compatible', 'all_thresholded_local_maxima'),
                                       ('after_frequency_suppression_compatible', 'uncapped_nms_candidates')]:
                        candidates = [{**h, 'epoch_s': epoch} for h in trace[key]]
                        compatibility[label] = match_tracks(truths, candidates, scan.time_s+epoch, scan.df, id_key='peak_id')
                for t, hit, event in zip(truths, ancestors['hits'], ancestors['events']):
                    cell = by_truth[t['truth_id']]; score = compatible_score(result, t, offset)
                    cell['searchable'] |= score is not None
                    if score is not None: cell['best_score'] = max(cell['best_score'], score) if cell['best_score'] is not None else score
                    cell['generated'] |= hit['matched_id'] is not None
                    cell['grouped'] |= event['matched_id'] is not None
                    cell['on_piece_count'] += event['matched_id'] is not None
                    if event['matched_id'] is not None: cell['matched_on_event_ids'].append(event['matched_id'])
                    for label, matches in compatibility.items():
                        cell[label] |= matches[truths.index(t)]['matched_id'] is not None
                    if arm == 'new':
                        cell['local_maximum_compatible'] |= hit['matched_id'] is not None
                        cell['after_frequency_suppression_compatible'] |= hit['matched_id'] is not None
            all_events = processed['cadence']['events']
            assignments = match_tracks(truths, all_events, physical, df, id_key='cadence_event_id')
            native = native_ambiguities(truths, controls[arm]['cadence']['events'], physical, df)
            events = {e['cadence_event_id']: e for e in all_events}
            stages[arm] = {'by_truth': by_truth, 'assigned': assignments, 'native_ambiguous': native,
                           'events': events, 'hit_count': sum(len(r.hits) for r in processed['searches'].values()),
                           'event_count': len(all_events),
                           'preprocessing_failures': {k: v.coverage['preprocessing_failure'] for k, v in processed['searches'].items() if 'preprocessing_failure' in v.coverage},
                           'scan_coverage': {k: {name: v.coverage.get(name) for name in ['physical_track_trials', 'evaluated_track_trials',
                                               'masked_track_trials', 'unscorable_track_trials', 'candidates_lost_to_cap']}
                                             for k, v in processed['searches'].items()},
                           'candidate_cap_loss_count': sum(r.coverage.get('candidates_lost_to_cap', 0) for r in processed['searches'].values())}
            for row, truth, match in zip(rows, truths, assignments):
                facts = by_truth[truth['truth_id']]
                companion_ambiguous = any(other['truth_id'] != truth['truth_id'] and path_distance(truth, other, physical) <= 6*df for other in truths)
                ambiguous = native[truth['truth_id']] or companion_ambiguous
                event = events.get(match['matched_id'])
                coherent_parents = sorted(set(facts['matched_on_event_ids']) & set(event['member_on_event_ids'])) if event else []
                chain = row['eligible'] and facts['searchable'] and facts['generated'] and facts['grouped'] and bool(coherent_parents)
                for suffix, policy in [('safe', 'review_safe'), ('strict', 'strict_experimental')]:
                    compatible = bool(chain and event[policy]['retained'])
                    row[arm+'_'+suffix+'_optimistic'] = compatible
                    row[arm+'_'+suffix] = compatible and not ambiguous
                row[arm+'_stages'] = {**facts, 'associated': event is not None,
                                     'native_ambiguous': native[truth['truth_id']], 'companion_overlap_ambiguous': companion_ambiguous,
                                     'association_localization_rescue_not_counted': event is not None and not facts['grouped'],
                                     'coherent_association_parent_event_ids': coherent_parents,
                                     'association_ancestry_competition_not_counted': event is not None and facts['grouped'] and not coherent_parents,
                                     'association_max_path_error_channels': match['max_path_error_channels'],
                                     'strict_decision': event['strict_experimental']['decision'] if event else 'not_reached'}
                if not row['eligible']: reason = 'outside_declared_domain'
                elif not facts['searchable']: reason = 'unsearched_or_unavailable_support'
                elif facts['best_score'] is not None and facts['best_score'] < settings.score_threshold: reason = 'below_threshold'
                elif not facts['local_maximum_compatible']: reason = 'local_maximum_or_assignment'
                elif not facts['after_frequency_suppression_compatible']: reason = 'frequency_suppression_or_assignment'
                elif not facts['generated']: reason = 'catalogue_truncation_or_assignment' if arm == 'legacy' else 'candidate_assignment'
                elif not facts['grouped']: reason = 'grouping_or_assignment'
                elif event is None: reason = 'cadence_association'
                elif not coherent_parents: reason = 'cadence_ancestry_or_assignment'
                elif ambiguous: reason = 'ambiguous_attribution'
                else: reason = 'retained'
                row[arm+'_first_loss'] = reason
                for suffix, policy in [('safe', 'review_safe'), ('strict', 'strict_experimental')]:
                    row[arm+'_'+suffix+'_first_loss'] = (reason if reason != 'retained' else
                        ('retained' if event[policy]['retained'] else 'cadence_policy_'+event[policy]['decision']))
                if arm == 'new': row['searchable'] = facts['searchable']
        return rows, {'trial_id': parameters['trial_id'], 'injection': diagnostics,
                      'arm_metrics': {a: {k: v for k, v in s.items() if k not in {'by_truth', 'assigned', 'native_ambiguous', 'events'}} for a, s in stages.items()}}
    except Exception as exc:
        for row in rows:
            row.update({a+'_'+s: False for a in ['new', 'legacy'] for s in ['safe', 'strict', 'safe_optimistic', 'strict_optimistic']})
            row.update(failure_type=type(exc).__name__, failure=str(exc), new_first_loss='technical_failure', legacy_first_loss='technical_failure')
            row.update({a+'_'+s+'_first_loss': 'technical_failure' for a in ['new', 'legacy'] for s in ['safe', 'strict']})
        return rows, {'trial_id': parameters['trial_id'], 'failure_type': type(exc).__name__, 'failure': str(exc)}
