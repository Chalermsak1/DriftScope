"""Metadata-only sampling and indivisible acquisition/target/raw components."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import PurePosixPath
from urllib.parse import urlparse
import numpy as np


def components(records):
    ids = [r["cadence_id"] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate cadence IDs")
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i

    seen, edges = {}, []
    for i, record in enumerate(records):
        for kind, values in (("target", record["target_ids"]), ("session", record["session_ids"]), ("raw", record["raw_ids"])):
            if not values or any(not isinstance(v, str) or not v.strip() or v.lower() == "unknown" for v in values):
                raise ValueError(f"Missing {kind} linkage; cannot certify an independent split")
            for value in sorted(set(values)):
                key = (kind, value.strip().casefold())
                if key in seen:
                    j = seen[key]
                    parent[find(i)] = find(j)
                    edges.append({"left": ids[j], "right": ids[i], "link_type": kind, "link_value": key[1]})
                else:
                    seen[key] = i
    # Name aliases at the same pointing must not escape target linkage.
    from research.pilot.observations import separation_deg
    for i, a in enumerate(records):
        for j in range(i):
            b = records[j]
            close = any(separation_deg(pa['ra_deg'], pa['dec_deg'], pb['ra_deg'], pb['dec_deg']) <= 1/3600
                        for pa in a.get('on_pointings', []) for pb in b.get('on_pointings', []))
            if close:
                parent[find(i)] = find(j)
                edges.append({'left': ids[j], 'right': ids[i], 'link_type': 'coordinate_alias_within_1_arcsec', 'link_value': 'ON pointing'})
    buckets = defaultdict(list)
    for i, record in enumerate(records):
        buckets[find(i)].append(record["cadence_id"])
    groups = []
    for members in sorted(sorted(v) for v in buckets.values()):
        fingerprint = hashlib.sha256(json.dumps(members).encode()).hexdigest()[:16]
        groups.append({"component_id": f"component_{fingerprint}", "cadence_ids": members})
    return {"components": groups, "edges": edges, "component_count": len(groups), "cadence_count": len(records)}


def assert_no_split_leakage(records, assignment):
    if set(assignment) != {r["cadence_id"] for r in records}:
        raise ValueError("Split assignments do not cover the full frame")
    for component in components(records)["components"]:
        if len({assignment[c] for c in component["cadence_ids"]}) != 1:
            raise ValueError("Shared acquisition/target/raw component crosses partitions")
    if any(r.get("candidate_selected", True) and assignment[r["cadence_id"]] != "development" for r in records):
        raise ValueError("Candidate-selected/regression data cannot enter locked validation/test")


def propose_split(records, allocation, seed):
    groups = components(records)["components"]
    if set(allocation) != {"development", "validation", "test"} or any(not isinstance(v, int) or v < 0 for v in allocation.values()):
        raise ValueError("Explicit nonnegative component counts required")
    if sum(allocation.values()) != len(groups):
        raise ValueError("Allocation must match actual connected components; never break links to fill quotas")
    order = np.random.default_rng(seed).permutation(len(groups))
    labels = [label for label in ("development", "validation", "test") for _ in range(allocation[label])]
    assignment = {cadence: label for index, label in zip(order, labels) for cadence in groups[int(index)]["cadence_ids"]}
    assert_no_split_leakage(records, assignment)
    return {"assignments": assignment, "allocation_components": allocation, "seed": seed,
            "status": "proposed_not_locked", "locked_test_outcomes_accessed": False}


def sample_components(records, count, seed):
    """Equal-probability groups, then one cadence/group; preserve both probabilities."""
    if count < 1 or any(r.get("candidate_selected", True) for r in records):
        raise ValueError("Need a candidate-independent frame and positive sample size")
    groups = components(records)["components"]
    rng = np.random.default_rng(seed)
    count = min(count, len(groups))
    if not count:
        return []
    selected = []
    for i in sorted(rng.choice(len(groups), count, replace=False).tolist()):
        group = groups[i]
        cadence_id = group["cadence_ids"][int(rng.integers(len(group["cadence_ids"])))]
        probability = (count/len(groups))/len(group["cadence_ids"])
        selected.append({"cadence_id": cadence_id, "component_id": group["component_id"],
                         "group_inclusion_probability": count/len(groups),
                         "conditional_cadence_probability": 1/len(group["cadence_ids"]),
                         "cadence_inclusion_probability": probability, "sampling_weight": 1/probability})
    return selected


def readiness(records, frame_complete, min_components=60):
    failures = []
    if not frame_complete: failures.append("metadata_frame_incomplete_or_truncated")
    if not records: failures.append("empty_sampling_frame")
    if any(r.get("candidate_selected", True) for r in records): failures.append("candidate_selected_backgrounds")
    graph = components(records)
    if graph["component_count"] < min_components: failures.append("insufficient_independent_components")
    if any(not r.get("headers_validated", False) for r in records): failures.append("source_headers_not_validated")
    if any(not r.get("samples_acquired_and_verified", False) for r in records): failures.append("observational_samples_not_acquired_and_verified")
    if any(not r.get("receiver_verified", False) for r in records): failures.append("receiver_regime_not_verified")
    if any(not r.get('on_pointings') for r in records): failures.append('target_coordinate_alias_linkage_unavailable')
    if len({r.get("receiver", "unknown") for r in records}) != 1: failures.append("receiver_regimes_not_single")
    return {"ready_for_representative_sensitivity": not failures, "unmet_gates": failures,
            "component_count": graph["component_count"], "required_components": min_components,
            "claim_scope": "specified finite sampling frame; no claim of universal sky representativeness"}


def records_from_release(cadences):
    return [{"cadence_id": c.cadence_id, "target_ids": sorted({s.target for s in c.scans if s.role == "ON"}),
             'on_pointings': [{'ra_deg': s.ra_deg, 'dec_deg': s.dec_deg} for s in c.scans if s.role == 'ON' and s.ra_deg is not None],
             "session_ids": sorted({s.session_id for s in c.scans}), "raw_ids": sorted({s.raw_id for s in c.scans}),
             "candidate_selected": c.candidate_selected, "headers_validated": True,
             "samples_acquired_and_verified": False,
             "receiver_verified": False, "receiver": c.scans[0].receiver,
             "scope": "release structural headers only; independent source-sample validation was performed for mlc1 only"} for c in cadences]


def propose_metadata_cadences(rows, rejected=None):
    """Conservative ABACAD metadata proposals; headers still require acquisition."""
    streams = defaultdict(list)
    for row in rows:
        if row.get("telescope") != "GBT" or not row.get("url", "").endswith(".gpuspec.0000.h5"):
            continue
        parts = PurePosixPath(urlparse(row["url"]).path).parts
        sessions = [part for part in parts if part.startswith("AGBT")]
        if not sessions:
            continue
        streams[(sessions[0], float(row["center_freq"]))].append(row)
    records = []
    rejected = rejected if rejected is not None else []
    from research.pilot.observations import separation_deg
    for (session, center), stream in sorted(streams.items()):
        # Duplicate product copies never create extra integrations/cadences.
        unique = {(r["target"], r["mjd"]): r for r in sorted(stream, key=lambda r: r["id"])}
        ordered = sorted(unique.values(), key=lambda r: (r["mjd"], r["id"]))
        for i in range(len(ordered)-5):
            scans = ordered[i:i+6]
            target = scans[0]["target"]
            # ABABAB permits a shifted false primary B when the repeated OFF
            # pointing is itself used as A. Explicit archive _OFF names cannot
            # become primary science targets; all proposals still need headers.
            gaps = np.diff([float(r["mjd"]) for r in scans])*86400
            if not all(scans[j]["target"] == target for j in (0, 2, 4)):
                continue
            if any(scans[j]["target"] == target for j in (1, 3, 5)) or np.any(gaps <= 0) or np.any(gaps > 1800):
                continue
            on_sep = [separation_deg(scans[0]['ra'], scans[0]['decl'], r['ra'], r['decl'])*3600 for r in scans[::2]]
            off_sep = [separation_deg(scans[0]['ra'], scans[0]['decl'], r['ra'], r['decl'])*3600 for r in scans[1::2]]
            reasons = []
            if target.casefold().endswith('_off'): reasons.append('explicit_OFF_name_as_primary')
            if max(on_sep) > 1: reasons.append('ON_pointing_exceeds_current_1_arcsec_engineering_tolerance')
            if min(off_sep) <= 60: reasons.append('OFF_pointing_not_distinct_over_1_arcmin')
            if reasons:
                rejected.append({'archive_ids': [r['id'] for r in scans], 'target': target, 'reasons': reasons,
                                 'on_separation_arcsec': on_sep, 'off_separation_arcsec': off_sep})
                continue
            records.append({"cadence_id": "archive_"+"_".join(str(r["id"]) for r in scans),
                            "target_ids": [target], "session_ids": [session],
                            "on_pointings": [{'ra_deg': float(r['ra']), 'dec_deg': float(r['decl'])} for r in scans[::2]],
                            "raw_ids": [r["url"].split(".gpuspec.")[0] for r in scans],
                            "candidate_selected": False, "headers_validated": False,
                            "samples_acquired_and_verified": False, "receiver_verified": False,
                            "receiver": f"GBT_center_{center:g}_MHz_unverified",
                            "archive_ids": [r["id"] for r in scans], "full_file_bytes": sum(int(r["size"]) for r in scans),
                            "status": "metadata_only_ABACAD_proposal_not_header_validated"})
    return records
