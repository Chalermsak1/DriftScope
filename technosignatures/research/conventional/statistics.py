"""Explicit domain denominators, paired cluster resampling, ambiguity bounds."""
from __future__ import annotations

import numpy as np

STAGES = ("eligible", "searchable", "generated", "grouped", "cadence_retained")


def first_loss(record):
    if record.get("failure_type"):
        return "technical_failure:"+record["failure_type"]
    for stage in STAGES:
        if not record[stage]: return stage
    return "retained"


def summary(rows, outcome="cadence_retained", conservative=True):
    if not rows:
        return {"signal_count": 0, "full_declared_domain_recovery": None, "searchable_domain_recovery": None}
    weights = np.array([r.get("weight", 1.0) for r in rows], float)
    if not np.isfinite(weights).all() or np.any(weights <= 0):
        raise ValueError("Finite positive benchmark weights required")
    eligible = np.array([r["eligible"] for r in rows], bool)
    searchable = eligible & np.array([r["searchable"] for r in rows], bool)
    retained = eligible & np.array([r[outcome] for r in rows], bool)
    if np.any(retained & ~searchable):
        raise ValueError("A recovered signal cannot be outside its declared searchable support")
    ambiguous = np.array([r.get("ambiguous_native_match", False) for r in rows], bool)
    if conservative: retained &= ~ambiguous
    full_denominator = float(weights[eligible].sum())
    search_denominator = float(weights[searchable].sum())
    numerator = float(weights[retained].sum())
    return {"signal_count": len(rows), "eligible_count": int(eligible.sum()), "searchable_count": int(searchable.sum()),
            "eligible_weight": full_denominator, "searchable_weight": search_denominator, "retained_weight": numerator,
            "full_declared_domain_recovery": numerator/full_denominator if full_denominator else None,
            "searchable_domain_recovery": numerator/search_denominator if search_denominator else None,
            "ambiguous_signal_count": int(ambiguous.sum()), "ambiguity_policy": "count ambiguous as unrecovered" if conservative else "compatible outcomes counted optimistically",
            "first_loss_counts": {reason: sum(first_loss(r) == reason for r in rows) for reason in sorted({first_loss(r) for r in rows})}}


def paired_cluster_interval(rows, left, right, seed=20261121, replicates=10000):
    """Resample whole acquisition components; retain paired outcomes and weights."""
    if replicates < 1000:
        raise ValueError("At least 1000 exploratory replicates required; default approved analysis uses 10000")
    eligible = [r for r in rows if r["eligible"]]
    ids = sorted({r["component_id"] for r in eligible})
    if not eligible:
        return {"point_difference": None, "interval_95": None, "component_count": 0, "status": "no_eligible_signals"}
    weights = np.array([r.get("weight", 1.0) for r in eligible], float)
    if not np.isfinite(weights).all() or np.any(weights <= 0): raise ValueError("Invalid cluster weights")
    delta = np.array([int(r[right])-int(r[left]) for r in eligible], float)
    point = float(np.average(delta, weights=weights))
    if len(ids) < 2:
        return {"point_difference": point, "interval_95": None, "component_count": len(ids),
                "status": "unresolved_observing_environment_uncertainty_single_component"}
    numerator, denominator = [], []
    for component in ids:
        selected = np.array([r["component_id"] == component for r in eligible])
        numerator.append(float(np.dot(weights[selected], delta[selected])))
        denominator.append(float(weights[selected].sum()))
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(ids), size=(replicates, len(ids)))
    estimates = np.asarray(numerator)[draws].sum(axis=1)/np.asarray(denominator)[draws].sum(axis=1)
    interval = np.quantile(estimates, [0.025, 0.975]).tolist()
    degenerate = interval[0] == interval[1]
    return {"point_difference": point, "interval_95": None if degenerate else interval,
            "empirical_percentiles_95": interval, "component_count": len(ids), "replicates": replicates, "seed": seed,
            "status": "degenerate_resampling_future_risk_unresolved" if degenerate else "exploratory_group_percentile_bootstrap",
            "few_components_warning": len(ids) < 20, "estimator": "paired eligible-signal weighted rate difference; right minus left"}
