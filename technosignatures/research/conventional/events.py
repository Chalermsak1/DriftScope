"""Truth-blind complete-link event grouping and separate recovery evaluation."""
from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from .search import SearchResult


def track_values(track, time_s):
    t = np.asarray(time_s)-float(track.get("epoch_s", 0.0))
    return (track["start_frequency_hz"]+track["drift_hz_per_s"]*t
            +0.5*float(track.get("curvature_hz_per_s2", 0.0))*t*t)


def path_distance(a, b, times):
    return float(np.max(np.abs(track_values(a, times)-track_values(b, times))))


def group_events(result: SearchResult, tolerance_channels=3.0):
    """No cap and no starting-frequency NMS. Prevent transitive bridge merges.

    Each member must agree with EVERY other member over the scan support.
    Distinct partial-overlap aliases can remain separate events; conservative
    grouping intentionally does not claim to solve arbitrary deblending.
    """
    if not np.isfinite(tolerance_channels) or tolerance_channels <= 0:
        raise ValueError("Positive finite grouping tolerance required")
    groups = []
    hits = sorted(result.hits, key=lambda h: (-h["robust_score"], h["hit_id"]))
    if len({h["hit_id"] for h in hits}) != len(hits):
        raise ValueError("Duplicate hit IDs")
    times = result.scan.time_s
    for hit in hits:
        compatible = next((g for g in groups if all(path_distance(hit, other, times) <= tolerance_channels*result.scan.df for other in g)), None)
        if compatible is None:
            groups.append([hit])
        else:
            compatible.append(hit)
    events, membership = [], []
    for i, members in enumerate(groups):
        anchor = members[0]
        event_id = f"{result.scan.scan_id}_event_{i:06d}"
        events.append({**anchor, "event_id": event_id, "representative_hit_id": anchor["hit_id"],
                       "member_hit_ids": [h["hit_id"] for h in members], "member_count": len(members),
                       "maximum_representative_path_deviation_hz": max(path_distance(anchor, h, times) for h in members)})
        membership.extend({"hit_id": h["hit_id"], "event_id": event_id} for h in members)
    assert len(membership) == len(hits)
    return {"events": events, "membership": membership,
            "settings": {"algorithm": "score-ordered complete-link path grouping", "tolerance_channels": tolerance_channels,
                         "hidden_truth_used": False, "cap": None},
            "hit_count": len(hits), "event_count": len(events),
            "unassigned_hits": 0, "aliases_may_remain_distinct": True}


def match_tracks(truths, recovered, times, df, tolerance_channels=3.0, id_key="event_id"):
    """Maximum-cardinality then minimum-error one-to-one assignment.

    This evaluator is the only matching stage allowed access to truth. A single
    event cannot count as recovery of two injected physical signals.
    """
    if not np.isfinite(df) or df <= 0 or tolerance_channels <= 0:
        raise ValueError("Invalid recovery resolution/tolerance")
    if len({t['truth_id'] for t in truths}) != len(truths) or len({r[id_key] for r in recovered}) != len(recovered):
        raise ValueError("Nonunique recovery identifiers")
    if not truths:
        return []
    penalty = (len(truths)+1)*(tolerance_channels+1)
    cost = np.full((len(truths), len(recovered)+len(truths)), penalty)
    # Truth with no active samples has NO admissible real match. Equal costs
    # for real/dummy columns would otherwise create a spurious recovery.
    cost[:, :len(recovered)] = penalty*100
    errors = np.full((len(truths), len(recovered)), np.inf)
    for i, truth in enumerate(truths):
        support = np.ones(len(times), bool)
        if "active_intervals_s" in truth:
            support[:] = False
            for start, stop in truth["active_intervals_s"]:
                support |= (times >= start) & (times < stop)
        if not support.any():
            continue
        for j, event in enumerate(recovered):
            error = path_distance(truth, event, np.asarray(times)[support])/df
            errors[i, j] = error
            cost[i, j] = error if error <= tolerance_channels else penalty*100
    rows, columns = linear_sum_assignment(cost)
    assigned = dict(zip(rows.tolist(), columns.tolist()))
    return [{"truth_id": t["truth_id"], "matched_id": recovered[assigned[i]][id_key] if assigned[i] < len(recovered) else None,
             "max_path_error_channels": float(errors[i, assigned[i]]) if assigned[i] < len(recovered) else None}
            for i, t in enumerate(truths)]


def hierarchical_matches(truths, hits, events, times, df, tolerance_channels=3.0):
    """Keep per-signal stage ancestry coherent without reusing a hit.

    First assign final event representatives one to one. Reserve their parent
    hits, then match remaining truths to remaining hits. This conservative
    ancestry assignment need not maximize unconstrained raw-hit recovery;
    that separate maximum is reported for auditing assignment ambiguity.
    """
    grouped = match_tracks(truths, events, times, df, tolerance_channels)
    event_by_id = {e['event_id']: e for e in events}
    hit_ids = {h['hit_id'] for h in hits}
    assigned = {}
    used = set()
    for match in grouped:
        if match['matched_id'] is None: continue
        parent = event_by_id[match['matched_id']]['representative_hit_id']
        if parent not in hit_ids or parent in used:
            raise ValueError('Invalid event parent or duplicate parent-hit assignment')
        used.add(parent)
        assigned[match['truth_id']] = {**match, 'matched_id': parent}
    remaining_truths = [t for t in truths if t['truth_id'] not in assigned]
    remaining_hits = [h for h in hits if h['hit_id'] not in used]
    assigned.update({r['truth_id']: r for r in match_tracks(remaining_truths, remaining_hits, times, df, tolerance_channels, 'hit_id')})
    unconstrained = match_tracks(truths, hits, times, df, tolerance_channels, 'hit_id')
    return {'hits': [assigned[t['truth_id']] for t in truths], 'events': grouped,
            'unconstrained_maximum_raw_hit_recovery': sum(r['matched_id'] is not None for r in unconstrained),
            'ancestry_constrained_raw_hit_recovery': sum(r['matched_id'] is not None for r in assigned.values())}
