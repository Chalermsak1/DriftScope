"""Final-first one-to-one evaluation with explicit hit/event/cadence ancestry.

Truth enters only after the blind pipeline has finished. Cadence events have
nonoverlapping local-event parents. Restricting assignment edges to events
with a compatible actual parent therefore permits maximum-cardinality global
matching without allowing two truths to reuse a parent. Local stages reserve
those parents before assigning the remaining truths.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment
from research.conventional.events import path_distance, match_tracks, hierarchical_matches


def active_support(truth, times):
    mask = np.ones(len(times), bool)
    if 'active_intervals_s' in truth:
        mask[:] = False
        for low, high in truth['active_intervals_s']: mask |= (times >= low) & (times < high)
    return mask


def cadence_matches(truths, cadence, processed, tolerance=3.0):
    df = cadence.scans[0].df
    if not np.isfinite(tolerance) or tolerance <= 0 or len({t['truth_id'] for t in truths}) != len(truths): raise ValueError('Invalid matching contract')
    parents, local_times = {}, {}
    for scan, offset in zip(cadence.scans, cadence.offsets_s):
        if scan.role != 'ON': continue
        local_times[scan.scan_id] = scan.time_s+offset+scan.dt/2
        hits = {h['hit_id']:h for h in processed['searches'][scan.scan_id].hits}
        for event in processed['grouped'][scan.scan_id]['events']:
            if event['event_id'] in parents or event['representative_hit_id'] not in hits:
                raise ValueError('Invalid or duplicate local-event parent')
            parents[event['event_id']] = {**event, 'epoch_s': float(offset)+scan.dt/2,
                                         '_actual_hit': {**hits[event['representative_hit_id']], 'epoch_s': float(offset)+scan.dt/2}}
    final = processed['cadence']['events']
    if len({e['cadence_event_id'] for e in final}) != len(final): raise ValueError('Duplicate cadence-event IDs')
    ownership = []
    for event in final:
        members = event['member_on_event_ids']
        if not members or any(p not in parents for p in members): raise ValueError('Cadence event has missing local-event ancestry')
        if len({parents[p]['scan_id'] for p in members}) != len(members): raise ValueError('Multiple parents from the same ON scan')
        ownership.extend(members)
    if len(set(ownership)) != len(ownership): raise ValueError('A local event cannot belong to two cadence events')
    times = np.concatenate(list(local_times.values()))
    penalty = (len(truths)+1)*(tolerance+1)
    cost = np.full((len(truths), len(final)+len(truths)), penalty)
    cost[:, :len(final)] = penalty*100
    errors = np.full((len(truths), len(final)), np.inf)
    compatible = [[[] for _ in final] for _ in truths]
    unconstrained = [0]*len(truths)
    for i, truth in enumerate(truths):
        support = active_support(truth, times)
        if not support.any(): continue
        for j, event in enumerate(final):
            error = path_distance(truth, event, times[support])/df
            errors[i,j] = error
            if error > tolerance: continue
            unconstrained[i] += 1
            for parent_id in event['member_on_event_ids']:
                parent = parents[parent_id]; physical = local_times[parent['scan_id']]
                active = active_support(truth, physical)
                if (active.any() and path_distance(truth, parent, physical[active])/df <= tolerance
                        and path_distance(truth, parent['_actual_hit'], physical[active])/df <= tolerance):
                    compatible[i][j].append(parent_id)
            if compatible[i][j]: cost[i,j] = error
    row, col = linear_sum_assignment(cost); chosen = dict(zip(row.tolist(), col.tolist()))
    assignments, reservations = [], {k:{} for k in local_times}
    for i, truth in enumerate(truths):
        j = chosen[i]; real = j < len(final)
        ids = compatible[i][j] if real else []
        assignments.append({'truth_id':truth['truth_id'], 'matched_id':final[j]['cadence_event_id'] if real else None,
                            'max_path_error_channels':float(errors[i,j]) if real else None,
                            'unconstrained_compatible_event_count':unconstrained[i],
                            'ancestry_feasible_event_count':sum(bool(v) for v in compatible[i]),
                            'reserved_parent_event_ids':list(ids)})
        for parent_id in ids:
            scan_id = parents[parent_id]['scan_id']
            reservations[scan_id][truth['truth_id']] = parent_id
    return assignments, reservations


def local_matches(truths, hits, events, times, df, reservations, tolerance=3.0):
    if not reservations: return hierarchical_matches(truths, hits, events, times, df, tolerance)
    truth_by_id = {t['truth_id']:t for t in truths}; event_by_id = {e['event_id']:e for e in events}
    hit_by_id = {h['hit_id']:h for h in hits}; used_events, used_hits = set(), set()
    event_matches, hit_matches = {}, {}
    for truth_id, event_id in reservations.items():
        if truth_id not in truth_by_id or event_id not in event_by_id or event_id in used_events:
            raise ValueError('Invalid or reused reserved local event')
        event = event_by_id[event_id]; parent = event['representative_hit_id']
        if parent not in hit_by_id or parent in used_hits: raise ValueError('Invalid or reused reserved hit')
        match = match_tracks([truth_by_id[truth_id]], [event], times, df, tolerance)[0]
        if match['matched_id'] is None: raise ValueError('Reserved parent does not match the physical truth')
        actual_hit = {**hit_by_id[parent], 'epoch_s': event.get('epoch_s', 0.)}
        if match_tracks([truth_by_id[truth_id]], [actual_hit], times, df, tolerance, 'hit_id')[0]['matched_id'] is None:
            raise ValueError('Reserved hit does not match the physical truth')
        event_matches[truth_id] = match
        hit_matches[truth_id] = {**match, 'matched_id':parent}
        used_events.add(event_id); used_hits.add(parent)
    remaining = [t for t in truths if t['truth_id'] not in event_matches]
    result = hierarchical_matches(remaining, [h for h in hits if h['hit_id'] not in used_hits],
                                  [e for e in events if e['event_id'] not in used_events], times, df, tolerance)
    event_matches.update({m['truth_id']:m for m in result['events']}); hit_matches.update({m['truth_id']:m for m in result['hits']})
    return {'events':[event_matches[t['truth_id']] for t in truths], 'hits':[hit_matches[t['truth_id']] for t in truths]}
