"""Trace the immutable legacy detector without changing its numerical method.

Coverage and catalogue stages are audited independently from injection truth.
Truth is admitted only by survival_record(), after blind searches finish.
No event grouping, cadence veto, or LLM filtering is represented as executed.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
from scipy.ndimage import maximum_filter

import pipeline as legacy


def coverage(nchannels, times, df, detector):
    """Count discrete boxcar/nearest-channel valid paths and legacy guard loss."""
    span = float(times[-1])
    max_drift = float(detector["max_abs_drift_hz_per_s"])
    half = int(np.ceil(max_drift / (detector["max_endpoint_grid_error_channels"] * df / span)))
    drifts = np.linspace(-max_drift, max_drift, 2*half+1)
    radius = detector["boxcar_width_channels"] // 2
    margin = int(np.ceil(max_drift*span/df)) + radius + 1
    starts = np.arange(margin, nchannels-margin)
    rows = []
    for drift in drifts:
        shifts = np.rint(drift*np.asarray(times)/df).astype(int)
        lo = max(0, radius-int(shifts.min()))
        hi = min(nchannels-1, nchannels-1-radius-int(shifts.max()))
        rows.append({"drift_hz_per_s": float(drift), "valid_start_min": lo,
                     "valid_start_max": hi, "valid_start_count": max(0, hi-lo+1)})
    physically_valid = sum(r["valid_start_count"] for r in rows)
    searched = len(drifts)*len(starts)
    return {
        "semantics": "discrete nearest-channel center track plus fixed boxcar radius; not Gaussian-tail or astrophysical exposure completeness",
        "input_frequency_channels": nchannels,
        "legacy_guard_channels_each_side": margin,
        "legacy_common_start_min": int(starts[0]) if len(starts) else None,
        "legacy_common_start_max": int(starts[-1]) if len(starts) else None,
        "legacy_start_channel_count": len(starts),
        "legacy_start_channel_fraction": len(starts)/nchannels,
        "drift_trials": len(drifts),
        "legacy_searched_track_trials": searched,
        "valid_discrete_track_trials_over_full_input": physically_valid,
        "valid_discrete_tracks_omitted_by_common_guard": physically_valid-searched,
        "valid_discrete_track_fraction_searched": searched/physically_valid if physically_valid else None,
        "per_drift": rows,
    }


def catalogue_trace(search: dict, detector: dict, frequencies):
    """Reconstruct all threshold/local-max/NMS/cap decisions and verify parity."""
    scores = search["score_map"]
    width = int(detector["boxcar_width_channels"])
    maxima = scores == maximum_filter(scores, size=(3, width*2+1), mode="nearest")
    peaks = np.argwhere(maxima & (scores >= detector["score_threshold"]))
    ordered = sorted(peaks.tolist(), key=lambda p: (-scores[p[0], p[1]], p[0], p[1]))
    rows, accepted = [], []
    for order, (di, fi) in enumerate(ordered):
        channel = int(search["start_channels"][fi])
        row = {
            "peak_id": f"peak_{order:06d}",
            "start_channel_ascending": channel,
            "start_frequency_hz": float(frequencies[channel]),
            "drift_hz_per_s": float(search["drift_grid_hz_per_s"][di]),
            "robust_score": float(scores[di, fi]),
            "drift_index": di, "start_index": fi,
        }
        suppressor = next((c for c in accepted if abs(channel-c["start_channel_ascending"]) <= 2*width), None)
        row["suppressed_by_peak_id"] = suppressor["peak_id"] if suppressor else None
        if suppressor is None:
            row["uncapped_rank"] = len(accepted)+1
            row["retained_under_legacy_cap"] = len(accepted) < int(detector["max_candidates"])
            accepted.append(row)
        else:
            row["uncapped_rank"] = None
            row["retained_under_legacy_cap"] = False
        rows.append(row)
    # Continuing NMS after the cap gives its counterfactual uncapped output;
    # the capped prefix must reproduce the original, unchanged implementation.
    retained = accepted[:int(detector["max_candidates"])]
    reconstructed = [{"rank": i+1, **{k:r[k] for k in ["start_channel_ascending", "start_frequency_hz", "drift_hz_per_s", "robust_score"]}} for i,r in enumerate(retained)]
    if reconstructed != search["candidates"]:
        raise AssertionError("Catalogue trace does not reproduce immutable legacy output")
    summary = {
        "above_threshold_grid_cells": int(np.count_nonzero(scores >= detector["score_threshold"])),
        "thresholded_local_maxima": len(rows),
        "frequency_suppressed_local_maxima": len(rows)-len(accepted),
        "uncapped_nms_candidates": len(accepted),
        "legacy_cap": int(detector["max_candidates"]),
        "retained_candidates": len(retained),
        "candidates_lost_to_cap": max(0, len(accepted)-len(retained)),
        "catalogue_was_truncated": len(accepted)>len(retained),
        "legacy_output_exactly_reproduced": True,
        "event_grouping_status": "not_implemented; candidates are search maxima, not independent events",
        "cadence_filter_status": "not_applied",
        "llm_status": "not_applied",
    }
    return {"summary": summary, "all_thresholded_local_maxima": rows,
            "uncapped_nms_candidates": accepted, "retained_candidates": retained}


def traced_search(data, frequencies, times, detector):
    result = legacy.detect(data, frequencies, times, detector)
    trace = catalogue_trace(result, detector, frequencies)
    c = coverage(len(frequencies), times, legacy.channel_spacing(frequencies), detector)
    if c["legacy_searched_track_trials"] != result["score_map"].size:
        raise AssertionError("Coverage ledger differs from actual score map")
    return result, trace, c


def path_error(candidate, truth, times, df):
    shift = candidate["start_frequency_hz"]-truth["start_frequency_hz"]
    slope = candidate["drift_hz_per_s"]-truth["drift_hz_per_s"]
    return float(np.max(np.abs(shift+slope*times))/df)


def matching_rows(rows, truth, times, df, tolerance):
    return [r for r in rows if path_error(r,truth,times,df) <= tolerance]


def grid_match(search, truth, times, df, tolerance):
    """Can ANY above-threshold searched track match, before max/suppression?"""
    starts = search["start_channels"]
    truth_start = truth["start_channel_ascending"]
    start_deltas = (starts-truth_start)*df
    end_deltas = start_deltas[None,:]+(search["drift_grid_hz_per_s"][:,None]-truth["drift_hz_per_s"])*times[-1]
    within = (np.abs(start_deltas)[None,:] <= tolerance*df) & (np.abs(end_deltas) <= tolerance*df)
    if not np.any(within):
        return None
    return float(search["score_map"][within].max())


def survival_record(trial_id, truth, frequencies, times, detector, before_search, after_search, after_trace,
                    source_kind, tolerance=3.0):
    """Exclusive first-loss category plus all independently observed stage facts."""
    df = legacy.channel_spacing(frequencies)
    start = truth["start_channel_ascending"]
    radius = detector["boxcar_width_channels"]//2
    shifts = np.rint(truth["drift_hz_per_s"]*times/df).astype(int)
    in_drift = abs(truth["drift_hz_per_s"]) <= detector["max_abs_drift_hz_per_s"]
    discrete_supported = bool(np.all(start+shifts-radius >= 0) and np.all(start+shifts+radius < len(frequencies)))
    nominal_in_common = bool(start >= after_search["start_channels"][0] and start <= after_search["start_channels"][-1])
    best_after = grid_match(after_search,truth,times,df,tolerance)
    in_common_guard = best_after is not None
    best_before = grid_match(before_search,truth,times,df,tolerance)
    threshold = detector["score_threshold"]
    raw = matching_rows(after_trace["all_thresholded_local_maxima"],truth,times,df,tolerance)
    nms = matching_rows(after_trace["uncapped_nms_candidates"],truth,times,df,tolerance)
    kept = matching_rows(after_trace["retained_candidates"],truth,times,df,tolerance)
    facts = [
        ("input_integrity", True, "input_integrity_failure"),
        ("drift_domain", bool(in_drift), "outside_configured_drift_domain"),
        ("discrete_path_support", discrete_supported, "path_or_boxcar_outside_input_band"),
        ("legacy_common_start_guard", in_common_guard, "valid_path_omitted_by_common_guard"),
        ("score_threshold", bool(best_after is not None and best_after >= threshold), "below_score_threshold"),
        ("local_maximum", bool(raw), "no_matching_local_maximum"),
        ("frequency_suppression", bool(nms), "frequency_suppression_loss"),
        ("catalogue_cap", bool(kept), "catalogue_truncation_loss"),
    ]
    first_loss = next((reason for _, passed, reason in facts if not passed),None)
    stages = []
    failed = False
    for name, passed, reason in facts:
        stages.append({"stage":name,"observed_fact":passed,"status":"not_reached" if failed else ("pass" if passed else "fail"),"failure_category":reason if not passed and not failed else None})
        failed = failed or not passed
    stages.extend({"stage":stage,"status":"not_applied","observed_fact":None,"failure_category":None} for stage in ["event_grouping","cadence_filtering","triage"])
    ambiguous = best_before is not None and best_before >= threshold
    return {
        "trial_id":trial_id,"source_kind":source_kind,"truth":truth,
        "recovery_scope":"legacy per-scan candidate catalogue only; event/cadence processing is not evaluated",
        "eligibility_in_configured_drift_domain":bool(in_drift),
        "discrete_signal_path_supported":discrete_supported,
        "common_start_searchable":in_common_guard,
        "nominal_start_in_common_guard":nominal_in_common,
        "searchability_definition":"At least one searched track matches truth within the frozen path tolerance; nominal guard membership also reported.",
        "normalization_status":"row median/MAD applied inside detector; its loss is not separately identifiable from threshold losses in this audit",
        "stages":stages,"first_loss_category":first_loss,
        "best_truth_compatible_score_before":best_before,
        "best_truth_compatible_score_after":best_after,
        "preexisting_compatible_detection":bool(ambiguous),
        "attribution_status":"ambiguous_preexisting_compatible_detection" if ambiguous else "no_above_threshold_compatible_control_track",
        "matching_local_maxima":len(raw),"matching_uncapped_nms":len(nms),"matching_retained":len(kept),
        "compatible_retained":bool(kept),
        "conservative_attributable_recovery":bool(kept and not ambiguous),
        "tolerance_channels":tolerance,
    }


def survival_summary(rows):
    eligible = [r for r in rows if r["eligibility_in_configured_drift_domain"]]
    searchable = [r for r in eligible if r["discrete_signal_path_supported"] and r["common_start_searchable"]]
    categories = {}
    for r in rows:
        key = r["first_loss_category"] or "retained"
        categories[key] = categories.get(key,0)+1
    return {
        "trials":len(rows),"eligible_trials":len(eligible),"legacy_searchable_trials":len(searchable),
        "compatible_retained":sum(r["compatible_retained"] for r in rows),
        "conservatively_attributed_retained":sum(r["conservative_attributable_recovery"] for r in rows),
        "eligible_domain_recovery":sum(r["conservative_attributable_recovery"] for r in eligible)/len(eligible) if eligible else None,
        "legacy_searchable_domain_recovery":sum(r["conservative_attributable_recovery"] for r in searchable)/len(searchable) if searchable else None,
        "first_loss_counts":categories,
        "denominator_warning":"Deterministic engineering cases, not random population samples; no completeness interval or extraterrestrial-origin claim.",
    }
