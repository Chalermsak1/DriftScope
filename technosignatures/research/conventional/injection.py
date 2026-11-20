"""Detected-power Gaussian injections averaged over bins and integration time.

This is a boxcar-channel power model, not a voltage/instrument/beam simulator.
Continuous peak amplitude is defined BEFORE bin/time averaging, in units of
the documented pre-injection local recorded-power noise estimate.
"""
from dataclasses import replace
import numpy as np
from scipy.special import ndtr

from .data import Cadence
from .search import mad_sigma

FAMILIES = ("continuous_linear", "broadened_narrowband", "intermittent", "amplitude_modulated", "curved_drift", "collision_or_crowded")
AMPLITUDES = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)


def integrated_gaussian(frequencies, times, dt, truth, amplitude, subsamples):
    if not isinstance(subsamples, int) or subsamples < 1 or dt <= 0:
        raise ValueError("Positive integration interval and integer quadrature count required")
    if not np.isfinite(amplitude) or amplitude < 0 or not np.isfinite(truth['fwhm_hz']) or truth["fwhm_hz"] <= 0:
        raise ValueError("Invalid amplitude or Gaussian width")
    if any(not np.isfinite(truth[k]) for k in ['start_frequency_hz', 'drift_hz_per_s']):
        raise ValueError('Non-finite signal path')
    if truth.get('modulation_period_s', 1) <= 0:
        raise ValueError('Modulation period must be positive')
    df = float(np.median(np.diff(frequencies)))
    sigma = truth["fwhm_hz"]/(2*np.sqrt(2*np.log(2)))
    result = np.zeros((len(times), len(frequencies)))
    for j in range(subsamples):
        t = np.asarray(times)+(j+0.5)*dt/subsamples
        relative = t-float(truth.get("epoch_s", 0.0))
        # Work relative to the first channel to avoid GHz cancellation inside profiles.
        centers = ((truth["start_frequency_hz"]-frequencies[0])+truth["drift_hz_per_s"]*relative
                   +0.5*truth.get("curvature_hz_per_s2", 0.0)*relative**2)
        weight = np.ones(len(t))
        if "active_intervals_s" in truth:
            weight[:] = 0
            for start, stop in truth["active_intervals_s"]:
                weight[(t >= start) & (t < stop)] = 1
        if "modulation_period_s" in truth:
            weight *= 1+0.5*np.sin(2*np.pi*t/truth["modulation_period_s"]+truth.get("modulation_phase", 0.0))
        offset = (frequencies-frequencies[0])[None, :]-centers[:, None]
        profile = sigma*np.sqrt(2*np.pi)/df*(ndtr((offset+df/2)/sigma)-ndtr((offset-df/2)/sigma))
        result += amplitude*weight[:, None]*profile/subsamples
    return result


def parameter_manifest(cadence_id, nchannels, span_s, df, seed, placements=32, families=FAMILIES, amplitudes=AMPLITUDES, max_drift=4.0):
    if placements < 1 or nchannels < 3 or not all(np.isfinite(v) and v > 0 for v in [span_s, df, max_drift]):
        raise ValueError("Invalid injection design dimensions")
    if not families or not amplitudes or any(f not in FAMILIES for f in families) or any(not np.isfinite(a) or a <= 0 for a in amplitudes):
        raise ValueError("Unknown family or invalid amplitude grid; zero-amplitude shams are separate controls")
    rng = np.random.default_rng(seed)
    trials = []
    for family in families:
        for amplitude in amplitudes:
            for _ in range(placements):
                # Sampling is over the declared band, INCLUDING edges/masks, never
                # a post-detection selection of clean or successfully searched starts.
                trials.append({"trial_id": f"trial_{len(trials):06d}", "cadence_id": cadence_id,
                               "family": family, "peak_power_sigma": float(amplitude),
                               "start_channel": float(rng.uniform(0, nchannels-1)),
                               "drift_hz_per_s": float(rng.uniform(-max_drift, max_drift)),
                               "fwhm_channels": 6.0 if family == "broadened_narrowband" else 2.0,
                               "curvature_hz_per_s2": float(rng.choice([-1, 1])*4*df/span_s**2) if family == "curved_drift" else 0.0,
                               "active_intervals_s": [[0.25*span_s, 0.75*span_s]] if family == "intermittent" else None,
                               "modulation_period_s": span_s/2 if family == "amplitude_modulated" else None,
                               "modulation_phase": float(rng.uniform(0, 2*np.pi)), "off_response": 0.0,
                               "collision_offset_channels": 5.0 if family == "collision_or_crowded" else None})
    return {"version": "integrated-power-design-v1", "cadence_id": cadence_id, "seed": seed,
            "trials": trials, "trial_count": len(trials), "signal_count": sum(2 if t["family"] == "collision_or_crowded" else 1 for t in trials),
            "truth_access": "injector and post-search evaluator only", "placements_include_edges_and_masks": True,
            "status": "generated_design_not_a_claim_of_execution"}


def inject(cadence: Cadence, parameters, subsamples=32):
    first = cadence.scans[0]
    center = float(parameters["start_channel"])
    if not 0 <= center < len(first.frequency_hz) or parameters["peak_power_sigma"] < 0:
        raise ValueError("Start outside declared band or negative amplitude")
    if not np.isfinite(parameters["off_response"]) or not 0 <= parameters["off_response"] <= 1:
        raise ValueError("OFF response must lie in [0,1]")
    sigma_values = []
    local_lo, local_hi = max(0, int(center)-64), min(len(first.frequency_hz), int(center)+65)
    for scan in cadence.scans:
        if scan.role != "ON": continue
        for row, mask in zip(scan.power[:, local_lo:local_hi], scan.usable[:, local_lo:local_hi]):
            if mask.sum() >= 3:
                sigma_values.append(float(mad_sigma(row[mask])))
    noise = float(np.median(sigma_values)) if sigma_values else 0.0
    if not np.isfinite(noise) or noise <= 0:
        raise ValueError("Cannot estimate local pre-injection recorded-power noise")
    truth = {"truth_id": parameters["trial_id"]+"_signal_0", "epoch_s": 0.0,
             "start_frequency_hz": float(first.frequency_hz[0]+center*first.df),
             "drift_hz_per_s": parameters["drift_hz_per_s"], "fwhm_hz": parameters["fwhm_channels"]*first.df,
             "curvature_hz_per_s2": parameters.get("curvature_hz_per_s2", 0.0)}
    for key in ("active_intervals_s", "modulation_period_s", "modulation_phase"):
        if parameters.get(key) is not None: truth[key] = parameters[key]
    truths = [truth]
    if parameters.get("collision_offset_channels") is not None:
        truths.append({**truth, "truth_id": parameters["trial_id"]+"_signal_1",
                       "start_frequency_hz": truth["start_frequency_hz"]+parameters["collision_offset_channels"]*first.df,
                       "drift_hz_per_s": -truth["drift_hz_per_s"]})
    scans = []
    for scan, offset in zip(cadence.scans, cadence.offsets_s):
        response = 1.0 if scan.role == "ON" else parameters["off_response"]
        delta = sum((integrated_gaussian(scan.frequency_hz, scan.time_s+offset, scan.dt, t,
                                        noise*parameters["peak_power_sigma"]*response, subsamples) for t in truths), np.zeros_like(scan.power))
        scans.append(scan.with_power(scan.power+delta))
    return replace(cadence, scans=tuple(scans)), truths, {
        "noise_estimate_power": noise, "noise_definition": "median row MAD sigma over ON scans, fixed +/-64-channel window around sampled starting position; masked samples excluded",
        "noise_channel_window_half_open": [local_lo, local_hi],
        "continuous_peak_power_before_bin_time_averaging": noise*parameters["peak_power_sigma"],
        "time_midpoint_subsamples": subsamples, "frequency_bin_integration": "analytic Gaussian CDF",
        "off_response": parameters["off_response"], "beam_calibrated": False,
        "physical_limit": "additive detected power, rectangular channel/time response; no voltages, stochastic transmitter noise, calibrated beam, or flux conversion"}
