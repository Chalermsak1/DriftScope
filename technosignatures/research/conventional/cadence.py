"""Associate scan events through real gaps and audit explicit cadence policies.

The default review-safe policy never automatically discards ON-supported
events. A separately recorded strict persistence/OFF veto is an engineering
comparison, not an origin classifier.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .data import Cadence
from .events import track_values
from .search import SearchResult, forced_measurement


@dataclass(frozen=True)
class CadenceConfig:
    link_tolerance_channels: float = 3.0
    off_score_threshold: float = 6.0

    def __post_init__(self):
        if not all(np.isfinite(v) and v > 0 for v in (self.link_tolerance_channels, self.off_score_threshold)):
            raise ValueError("Invalid cadence tolerances")


def _fit_corridor(members, tolerance_channels):
    """Intersect endpoint strips for one common physical linear path.

    For t_j>t_i, feasibility requires
      (f_j-e_j-f_i-e_i)/dt <= drift <= (f_j+e_j-f_i+e_i)/dt.
    Intersect ALL pairs, then choose a feasible clipped least-squares fit.
    This uses measured path precision, not grid spacing as an error bar.
    """
    times, freqs, errors = [], [], []
    for event in members:
        t = event["epoch_s"]+np.array([0.0, event["time_support_end_s"]])
        times.extend(t.tolist()); freqs.extend(track_values(event, t).tolist())
        errors.extend([tolerance_channels*event["df_hz"]]*2)
    times, freqs, errors = np.asarray(times), np.asarray(freqs), np.asarray(errors)
    t0, f0 = float(np.mean(times)), float(np.mean(freqs))
    relative = freqs-f0
    low, high = -np.inf, np.inf
    for i in range(len(times)):
        for j in range(i+1, len(times)):
            if times[j] == times[i]:
                if abs(relative[j]-relative[i]) > errors[i]+errors[j]: return None
                continue
            a, b = (i, j) if times[j] > times[i] else (j, i)
            dt = times[b]-times[a]
            low = max(low, (relative[b]-relative[a]-errors[a]-errors[b])/dt)
            high = min(high, (relative[b]-relative[a]+errors[a]+errors[b])/dt)
    if low > high: return None
    slope = float(np.clip(np.dot(times-t0, relative)/np.dot(times-t0, times-t0), low, high))
    lower = float(np.max(relative-errors-slope*(times-t0)))
    upper = float(np.min(relative+errors-slope*(times-t0)))
    if lower > upper+1e-8: return None
    intercept_at_t0 = float(np.clip(0.0, lower, max(lower, upper)))
    model = {"start_frequency_hz": f0+intercept_at_t0-slope*t0, "drift_hz_per_s": slope, "epoch_s": 0.0,
             "feasible_drift_interval_hz_per_s": [float(low), float(high)]}
    model["fit_max_endpoint_residual_hz"] = float(np.max(np.abs(freqs-track_values(model, times))))
    return model


def filter_cadence(cadence: Cadence, searches: dict[str, SearchResult], grouped: dict[str, dict], config=CadenceConfig()):
    scans = {s.scan_id: s for s in cadence.scans}
    if set(searches) != set(scans) or set(grouped) != set(scans):
        raise ValueError("Search/event records must cover every represented scan")
    offsets = dict(zip(scans, cadence.offsets_s.tolist()))
    on_events = []
    for scan in cadence.scans:
        if searches[scan.scan_id].scan is not scan:
            raise ValueError("Search belongs to a different observation")
        if scan.role == "ON":
            for event in grouped[scan.scan_id]["events"]:
                on_events.append({**event, "epoch_s": offsets[scan.scan_id]+scan.dt/2, "df_hz": scan.df})
    pending = sorted(on_events, key=lambda e: (-e["robust_score"], e["event_id"]))
    associations = []
    while pending:
        members = [pending.pop(0)]
        remaining = []
        for event in pending:
            if (event["scan_id"] not in {m["scan_id"] for m in members}
                    and _fit_corridor(members+[event], config.link_tolerance_channels) is not None):
                members.append(event)
            else:
                remaining.append(event)
        pending = remaining
        model = _fit_corridor(members, config.link_tolerance_channels)
        measurements = []
        for scan in cadence.scans:
            offset = offsets[scan.scan_id]
            start_frequency = float(track_values(model, np.array([offset+scan.dt/2]))[0])
            forced = forced_measurement(searches[scan.scan_id], start_frequency, model["drift_hz_per_s"], config.link_tolerance_channels)
            # Membership is evidence; a failed forced grid lookup is separately visible.
            measurements.append({"scan_id": scan.scan_id, "role": scan.role, "elapsed_start_s": offset,
                                 "associated_event_ids": [m["event_id"] for m in members if m["scan_id"] == scan.scan_id],
                                 "forced": forced,
                                 "off_evidence": scan.role == "OFF" and forced["status"] == "searched" and forced["score"] >= config.off_score_threshold})
        off_evidence = any(m["off_evidence"] for m in measurements)
        unknown = not cadence.complete or any(m["forced"]["status"] != "searched" for m in measurements)
        all_on = cadence.complete and len({m["scan_id"] for m in members}) == 3
        if off_evidence:
            strict_decision, strict_keep = "reject_off_coincidence", False
        elif unknown:
            strict_decision, strict_keep = "escalate_incomplete_search_or_cadence", True
        elif not all_on:
            strict_decision, strict_keep = "reject_missing_on_persistence", False
        else:
            strict_decision, strict_keep = "retain", True
        associations.append({**model, "cadence_event_id": f"{cadence.cadence_id}_ce_{len(associations):06d}",
                             "member_on_event_ids": [m["event_id"] for m in members],
                             "on_scans_with_events": len(members), "all_three_on_scans_have_events": all_on,
                             "measurements": measurements, "off_coincidence": off_evidence,
                             "coverage_unknown": unknown,
                             "review_safe": {"retained": True, "decision": "escalate" if off_evidence or unknown or not all_on else "retain"},
                             "strict_experimental": {"retained": strict_keep, "decision": strict_decision}})
    memberships = [event_id for e in associations for event_id in e["member_on_event_ids"]]
    assert len(memberships) == len(set(memberships)) == len(on_events)
    return {"cadence_id": cadence.cadence_id, "complete_six_scan_roles": cadence.complete,
            "scan_offsets_s": offsets, "events": associations,
            "input_on_event_count": len(on_events), "unassigned_on_events": 0,
            "native_origin_labels": "unresolved; OFF coincidence does not establish terrestrial origin",
            "policies": {"default": "review_safe", "strict_experimental": "all three ON events and OFF forced scores below threshold; unknown coverage escalates"},
            "off_score_threshold": config.off_score_threshold,
            "score_caveat": "descriptive robust score, not a calibrated significance"}
