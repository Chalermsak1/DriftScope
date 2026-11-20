"""Execute conditional development trials with full loss and attribution ledgers."""
from dataclasses import asdict
import numpy as np

import pipeline as legacy
from research.pilot.accounting import catalogue_trace
from .data import Cadence
from .events import group_events, match_tracks, track_values, hierarchical_matches
from .injection import inject
from .search import SearchConfig, search
from .statistics import summary, paired_cluster_interval, first_loss


def _matching_grid(result, truth):
    scan = result.scan
    times = scan.time_s+scan.dt/2
    target = track_values(truth, times)
    candidates = np.flatnonzero(np.abs(scan.frequency_hz-target[0]) <= 3*scan.df)
    best = None
    for start in candidates:
        paths = scan.frequency_hz[start]+result.drift_grid[:, None]*scan.time_s[None, :]
        compatible = np.max(np.abs(paths-target[None, :]), axis=1) <= 3*scan.df
        values = result.scores[compatible, start]
        finite = values[np.isfinite(values)]
        if len(finite):
            best = max(best, float(finite.max())) if best is not None else float(finite.max())
    return best


def evaluate_single_scan(scan, design, config=SearchConfig(), component_id="development_fixture", subsamples=32,
                         source_kind="development_background_provenance_as_supplied"):
    """Paired immutable legacy versus v2; a single background is NOT a cohort.

    The single-scan experiment does not apply cadence filtering. Its terminal
    retention field is explicitly the event boundary; cadence experiments are
    executed and reported separately by run.py.
    """
    if design['cadence_id'] != scan.scan_id or any(t.get('cadence_id') != scan.scan_id for t in design['trials']):
        raise ValueError('Injection manifest belongs to a different observation')
    if any(t.get('partition', 'development') != 'development' for t in design['trials']):
        raise ValueError('This development runner must not access validation/locked-test outcomes')
    if len({t['trial_id'] for t in design['trials']}) != len(design['trials']):
        raise ValueError('Duplicate trial identifiers')
    cadence = Cadence(scan.scan_id, (scan,), candidate_selected=True)
    before = search(scan, config)
    before_events = group_events(before)["events"]
    legacy_config = {k: v for k, v in asdict(config).items() if k not in {"tile_core_channels", "max_score_cells"}}
    legacy_config["max_candidates"] = 50
    native_legacy = legacy.detect(scan.power, scan.frequency_hz, scan.time_s, legacy_config)
    rows, trials = [], []
    physical_times = scan.time_s+scan.dt/2
    for parameters in design["trials"]:
        truth_list = []
        try:
            after_cadence, truth_list, injection = inject(cadence, parameters, subsamples)
            altered = after_cadence.scans[0]
            result = search(altered, config)
            grouped = group_events(result)
            ancestry = hierarchical_matches(truth_list, [{**h, "epoch_s": scan.dt/2} for h in result.hits],
                                            [{**e, "epoch_s": scan.dt/2} for e in grouped["events"]], physical_times, scan.df)
            matched_hits = {r["truth_id"]: r for r in ancestry['hits']}
            matched_events = {r["truth_id"]: r for r in ancestry['events']}
            native_matches = {r["truth_id"]: r for r in match_tracks(truth_list, [{**e, "epoch_s": scan.dt/2} for e in before_events], physical_times, scan.df)}
            legacy_result = legacy.detect(altered.power, altered.frequency_hz, altered.time_s, legacy_config)
            legacy_trace = catalogue_trace(legacy_result, legacy_config, altered.frequency_hz)
            legacy_events = [{**e, "event_id": f"legacy_{i}", "epoch_s": scan.dt/2} for i, e in enumerate(legacy_result["candidates"])]
            legacy_native_events = [{**e, "event_id": f"legacy_native_{i}", "epoch_s": scan.dt/2} for i, e in enumerate(native_legacy["candidates"])]
            legacy_matches = {r["truth_id"]: r for r in match_tracks(truth_list, legacy_events, physical_times, scan.df)}
            legacy_native_matches = {r["truth_id"]: r for r in match_tracks(truth_list, legacy_native_events, physical_times, scan.df)}
            for truth in truth_list:
                tid = truth["truth_id"]
                grid_score = _matching_grid(result, truth)
                eligible = bool(scan.frequency_hz[0] <= truth["start_frequency_hz"] <= scan.frequency_hz[-1]
                                and abs(truth["drift_hz_per_s"]) <= config.max_abs_drift_hz_per_s)
                generated = matched_hits[tid]["matched_id"] is not None
                event_retained = matched_events[tid]["matched_id"] is not None
                ambiguous = native_matches[tid]["matched_id"] is not None
                old_ambiguous = legacy_native_matches[tid]["matched_id"] is not None
                row = {"trial_id": parameters["trial_id"], "truth_id": tid, "component_id": component_id,
                       "family": parameters["family"], "peak_power_sigma": parameters["peak_power_sigma"], "weight": 1.0,
                       "eligible": eligible, "searchable": grid_score is not None,
                       "best_compatible_grid_score": grid_score, "generated": generated, "grouped": event_retained,
                       "cadence_retained": event_retained, "terminal_boundary": "single_scan_grouped_events; cadence_not_applied",
                       "raw_assignment_constrained_by_grouped_recovery": True,
                       "ambiguity_native_match": native_matches[tid], "ambiguous_native_match": ambiguous,
                       "legacy_ambiguous_native_match": old_ambiguous,
                       "new_retained_conservative": eligible and event_retained and not ambiguous,
                       "legacy_retained_conservative": eligible and legacy_matches[tid]["matched_id"] is not None and not old_ambiguous,
                       "new_retained_optimistic": eligible and event_retained,
                       "legacy_retained_optimistic": eligible and legacy_matches[tid]["matched_id"] is not None,
                       "hit_match": matched_hits[tid], "event_match": matched_events[tid], "legacy_match": legacy_matches[tid],
                       "source_kind": source_kind, "failure_type": None}
                row["first_loss"] = first_loss(row)
                rows.append(row)
            trials.append({"trial_id": parameters["trial_id"], "injection": injection, "truths": truth_list,
                           "v2_hit_count": len(result.hits), "v2_event_count": grouped["event_count"],
                           "recovery_assignment_audit": {k: v for k, v in ancestry.items() if k not in {'hits', 'events'}},
                           "legacy_retained_candidates": len(legacy_result["candidates"]),
                           "legacy_uncapped_candidates": legacy_trace["summary"]["uncapped_nms_candidates"],
                           "legacy_candidates_lost_to_cap": legacy_trace["summary"]["candidates_lost_to_cap"]})
        except Exception as exc:
            if not truth_list:
                raise RuntimeError(f"Trial {parameters['trial_id']} failed before truth allocation; execution incomplete") from exc
            for truth in truth_list:
                row = {"trial_id": parameters["trial_id"], "truth_id": truth["truth_id"], "component_id": component_id,
                       "family": parameters["family"], "peak_power_sigma": parameters["peak_power_sigma"], "weight": 1.0,
                       "eligible": bool(scan.frequency_hz[0] <= truth["start_frequency_hz"] <= scan.frequency_hz[-1]
                                        and abs(truth["drift_hz_per_s"]) <= config.max_abs_drift_hz_per_s),
                       "searchable": False, "generated": False, "grouped": False, "cadence_retained": False,
                       "ambiguous_native_match": False, "new_retained_conservative": False, "legacy_retained_conservative": False,
                       "new_retained_optimistic": False, "legacy_retained_optimistic": False,
                       "failure_type": type(exc).__name__, "failure": str(exc)}
                row["first_loss"] = first_loss(row); rows.append(row)
    assert len(rows) == design["signal_count"]
    if len({r["truth_id"] for r in rows}) != len(rows): raise AssertionError("Duplicate trial/signal outcomes")
    by_amplitude = []
    for family in sorted({r["family"] for r in rows}):
        for amplitude in sorted({r["peak_power_sigma"] for r in rows if r["family"] == family}):
            cell = [r for r in rows if r["family"] == family and r["peak_power_sigma"] == amplitude]
            by_amplitude.append({"family": family, "peak_power_sigma": amplitude,
                                 "conservative": summary(cell), "optimistic": summary(cell, conservative=False),
                                 "paired": paired_cluster_interval(cell, "legacy_retained_conservative", "new_retained_conservative")})
    return {"scope": "conditional development-background injection recovery, not representative-cohort sensitivity",
            "representative_cohort_gate_passed": False, "signal_rows": rows, "trial_details": trials,
            "by_family_amplitude": by_amplitude, "conservative": summary(rows), "optimistic": summary(rows, conservative=False),
            "paired": paired_cluster_interval(rows, "legacy_retained_conservative", "new_retained_conservative"),
            "technical_failure_signal_count": sum(bool(r.get("failure_type")) for r in rows),
            "score_configuration": asdict(config), "time_matching": "physical injection paths at integration midpoints; candidate frequency reference is first midpoint",
            "cadence_filtering_applied": False,
            "stage_assignment": "event representatives reserved first, remaining hits matched one to one; unconstrained raw maximum reported separately"}
