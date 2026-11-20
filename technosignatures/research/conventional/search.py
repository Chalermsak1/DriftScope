"""Per-drift support, halo tiles, global score normalization, and uncapped hits.

All valid starts for one drift contribute to the SAME median/MAD profile.
Tiles partition start-channel ownership, never statistical normalization.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.ndimage import maximum_filter

from .data import Scan


def mad_sigma(values, axis=None):
    med = np.median(values, axis=axis, keepdims=axis is not None)
    return 1.482602218505602*np.median(np.abs(values-med), axis=axis)


@dataclass(frozen=True)
class SearchConfig:
    max_abs_drift_hz_per_s: float = 4.0
    max_endpoint_grid_error_channels: float = 0.5
    boxcar_width_channels: int = 3
    score_threshold: float = 10.0
    tile_core_channels: int = 256
    max_score_cells: int = 20_000_000

    def __post_init__(self):
        numeric = (self.max_abs_drift_hz_per_s, self.max_endpoint_grid_error_channels, self.score_threshold)
        if not all(np.isfinite(x) and x > 0 for x in numeric):
            raise ValueError("Search bounds, grid error, and threshold must be finite positive values")
        if (not isinstance(self.boxcar_width_channels, int) or self.boxcar_width_channels < 1
                or self.boxcar_width_channels % 2 != 1):
            raise ValueError("Boxcar width must be an odd positive integer")
        if not isinstance(self.tile_core_channels, int) or self.tile_core_channels < 1 or self.max_score_cells < 1:
            raise ValueError("Invalid tile/memory budget")


@dataclass
class SearchResult:
    scan: Scan
    config: SearchConfig
    drift_grid: np.ndarray
    scores: np.ndarray
    hits: list[dict]
    coverage: dict
    tiles: list[dict]

    @property
    def drift_step(self):
        return float(self.drift_grid[1]-self.drift_grid[0])


def search(scan: Scan, config: SearchConfig = SearchConfig()):
    nt, nf = scan.power.shape
    radius = config.boxcar_width_channels//2
    span = scan.time_s[-1]
    half = int(np.ceil(config.max_abs_drift_hz_per_s*span/(config.max_endpoint_grid_error_channels*scan.df)))
    ndrift = 2*half+1
    if ndrift*nf > config.max_score_cells:
        raise ValueError("Search exceeds explicit score-map budget; no partial catalogue returned")
    drifts = np.linspace(-config.max_abs_drift_hz_per_s, config.max_abs_drift_hz_per_s, ndrift)
    standardized = np.zeros_like(scan.power)
    for i in range(nt):
        row = scan.power[i, scan.usable[i]]
        if len(row) < 3 or not (scale := float(mad_sigma(row))) > 0:
            raise ValueError("Too few usable samples or zero pre-search noise scale")
        standardized[i, scan.usable[i]] = (row-np.median(row))/scale
    scores = np.full((ndrift, nf), np.nan)
    rows = np.arange(nt)[:, None]
    per_drift = []
    cores = [(i, min(i+config.tile_core_channels, nf)) for i in range(0, nf, config.tile_core_channels)]
    max_shift = int(np.ceil(config.max_abs_drift_hz_per_s*span/scan.df))
    tiles = [{"core_start": lo, "core_stop_exclusive": hi,
              "halo_start": max(0, lo-max_shift-radius),
              "halo_stop_exclusive": min(nf, hi+max_shift+radius)} for lo, hi in cores]
    for di, drift in enumerate(drifts):
        shifts = np.rint(drift*scan.time_s/scan.df).astype(int)
        lo, hi = max(0, radius-int(shifts.min())), min(nf, nf-radius-int(shifts.max()))
        starts = np.arange(lo, max(lo, hi))
        usable_starts, integrated_parts = [], []
        for core, tile in zip(cores, tiles):
            owner = starts[(starts >= core[0]) & (starts < core[1])]
            if not owner.size:
                continue
            local = owner[None, :]+shifts[:, None]-tile["halo_start"]
            data = standardized[:, tile["halo_start"]:tile["halo_stop_exclusive"]]
            mask = scan.usable[:, tile["halo_start"]:tile["halo_stop_exclusive"]]
            values = np.zeros(len(owner))
            valid = np.ones(len(owner), bool)
            for box in range(-radius, radius+1):
                values += np.sum(data[rows, local+box], axis=0)
                valid &= np.all(mask[rows, local+box], axis=0)
            usable_starts.append(owner[valid]); integrated_parts.append(values[valid])
        usable = np.concatenate(usable_starts) if usable_starts else np.array([], dtype=int)
        integrated = np.concatenate(integrated_parts) if integrated_parts else np.array([])
        scale = float(mad_sigma(integrated)) if len(integrated) >= 3 else 0.0
        evaluated = len(usable) if scale > 0 else 0
        if evaluated:
            scores[di, usable] = (integrated-np.median(integrated))/scale
        per_drift.append({"drift_hz_per_s": float(drift), "physical_track_trials": len(starts),
                          "masked_track_trials": len(starts)-len(usable), "evaluated_track_trials": evaluated,
                          "unscorable_track_trials": len(usable)-evaluated,
                          "profile_scale": scale, "valid_start_min": lo, "valid_start_stop_exclusive": max(lo, hi)})
    finite = np.isfinite(scores)
    maxima_input = np.where(finite, scores, -np.inf)
    maxima = maxima_input == maximum_filter(maxima_input, size=(3, config.boxcar_width_channels*2+1), mode="constant", cval=-np.inf)
    peaks = np.argwhere(finite & maxima & (scores >= config.score_threshold))
    ordered = sorted(peaks.tolist(), key=lambda p: (-scores[p[0], p[1]], p[0], p[1]))
    step = float(drifts[1]-drifts[0])
    hits = [{"hit_id": f"{scan.scan_id}_d{di:05d}_c{channel:08d}", "scan_id": scan.scan_id,
             "start_channel_ascending": channel, "start_frequency_hz": float(scan.frequency_hz[channel]),
             "drift_hz_per_s": float(drifts[di]), "robust_score": float(scores[di, channel]),
             "drift_index": di, "drift_grid_spacing_hz_per_s": step,
             "reference_time_after_scan_start_s": scan.dt/2,
             "time_support_start_s": 0.0, "time_support_end_s": float(span)} for di, channel in ordered]
    physical = sum(r["physical_track_trials"] for r in per_drift)
    evaluated = int(finite.sum())
    coverage = {"definition": "nearest-channel linear path plus complete boxcar at every stored integration",
                "physical_track_trials": physical, "evaluated_track_trials": evaluated,
                "masked_track_trials": sum(r["masked_track_trials"] for r in per_drift),
                "unscorable_track_trials": sum(r["unscorable_track_trials"] for r in per_drift),
                "physical_fraction_evaluated": evaluated/physical if physical else None,
                "above_threshold_cells": int(np.count_nonzero(finite & (scores >= config.score_threshold))),
                "local_maximum_hits": len(hits), "candidate_cap": None, "catalogue_truncated": False,
                "sample_exposure_s": nt*scan.dt,
                "usable_time_bandwidth_hz_s": int(scan.usable.sum())*scan.dt*scan.df,
                "scan_gaps_counted_as_exposure": False, "per_drift": per_drift,
                "frequency_reference": "midpoint of first stored integration; time_s remains integration-start metadata",
                "score_definition": "whole-valid-profile per-drift median/MAD track-power standardization; descriptive, not false-alarm probability"}
    assert physical == evaluated+coverage["masked_track_trials"]+coverage["unscorable_track_trials"]
    return SearchResult(scan, config, drifts, scores, hits, coverage, tiles)


def forced_measurement(result: SearchResult, start_frequency_hz, drift_hz_per_s, tolerance_channels=3.0):
    """Inspect a predicted path, including subthreshold power; missing is not absent."""
    scan = result.scan
    if not np.isfinite(start_frequency_hz) or not np.isfinite(drift_hz_per_s):
        raise ValueError("Non-finite forced track")
    if abs(drift_hz_per_s) > result.config.max_abs_drift_hz_per_s:
        return {"status": "outside_drift_domain", "score": None}
    di = int(np.argmin(np.abs(result.drift_grid-drift_hz_per_s)))
    channel = int(np.rint((start_frequency_hz-scan.frequency_hz[0])/scan.df))
    if not 0 <= channel < len(scan.frequency_hz):
        return {"status": "outside_frequency_domain", "score": None}
    error = np.max(np.abs(scan.frequency_hz[channel]-start_frequency_hz+(result.drift_grid[di]-drift_hz_per_s)*scan.time_s))/scan.df
    if error > tolerance_channels:
        return {"status": "no_compatible_grid_track", "score": None, "max_path_error_channels": float(error)}
    score = result.scores[di, channel]
    return {"status": "searched" if np.isfinite(score) else "masked_or_unsupported_or_unscorable",
            "score": float(score) if np.isfinite(score) else None, "drift_index": di, "start_channel": channel,
            "max_path_error_channels": float(error)}
