"""Real-observation Load -> Inject -> Detect experiment.

The detector accepts data, frequency/time axes, and search settings only.
Injection truth is used by evaluation AFTER both blind searches have finished.
All input/output paths in the config are relative to this project directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import maximum_filter, uniform_filter1d

MAD_TO_SIGMA = 1.482602218505602


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def robust_sigma(values: np.ndarray, axis=None, keepdims=False):
    center = np.median(values, axis=axis, keepdims=True)
    return MAD_TO_SIGMA * np.median(np.abs(values - center), axis=axis, keepdims=keepdims)


def channel_spacing(frequencies: np.ndarray) -> float:
    """Estimate spacing over the full band to reduce GHz subtraction roundoff."""
    return float((frequencies[-1] - frequencies[0]) / (len(frequencies) - 1))


def fetch_dataset(dataset: dict, destination: Path) -> None:
    """Download only when missing, use TLS, verify bytes, replace atomically."""
    if destination.exists():
        if sha256(destination) != dataset["sha256"]:
            raise ValueError("Existing observation checksum mismatch; refusing to overwrite it")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        req = urllib.request.Request(dataset["url"], headers={"User-Agent": "technosignature-pipeline/1"})
        with urllib.request.urlopen(req, timeout=45) as response, temporary.open("wb") as output:
            total = 0
            while block := response.read(65536):
                total += len(block)
                if total > 10 * 1024 * 1024:
                    raise ValueError("Unexpectedly large sample (>10 MiB); aborting download")
                output.write(block)
        if sha256(temporary) != dataset["sha256"]:
            raise ValueError("Downloaded observation checksum mismatch")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def load_observation(path: Path, dataset: dict):
    """Read real SIGPROC power data with blimpy; normalize frequency order only."""
    from blimpy import Waterfall
    from astropy.time import Time

    if sha256(path) != dataset["sha256"]:
        raise ValueError("Observation checksum mismatch")
    wf = Waterfall(str(path))
    header = wf.header
    if int(header["nifs"]) != 1:
        raise ValueError("This experiment expects a single stored intensity stream")
    data = np.asarray(wf.data[:, 0, :], dtype=np.float64).copy()
    if list(data.shape) != dataset["expected_shape"]:
        raise ValueError(f"Unexpected observation shape: {data.shape}")
    if not np.isfinite(data).all():
        raise ValueError("Observation contains non-finite values")
    source = header["source_name"]
    if isinstance(source, bytes):
        source = source.decode()
    if source != dataset["expected_source_name"]:
        raise ValueError(f"Unexpected source: {source}")
    frequencies = (float(header["fch1"]) + np.arange(data.shape[1]) * float(header["foff"])) * 1e6
    original_descending = bool(frequencies[1] < frequencies[0])
    if original_descending:
        frequencies = frequencies[::-1].copy()
        data = data[:, ::-1].copy()
    dt = float(header["tsamp"])
    times = np.arange(data.shape[0], dtype=np.float64) * dt
    metadata = {
        "source_name": source,
        "telescope_id": int(header["telescope_id"]),
        "telescope": "Green Bank Telescope" if int(header["telescope_id"]) == 6 else "unresolved",
        "rawdatafile": str(header.get("rawdatafile", "")),
        "shape_time_frequency": list(data.shape),
        "start_mjd": float(header["tstart"]),
        "start_utc": Time(float(header["tstart"]), format="mjd", scale="utc").isot,
        "time_resolution_s": dt,
        "frequency_resolution_hz": float(abs(header["foff"]) * 1e6),
        "frequency_first_center_hz": float(frequencies[0]),
        "frequency_last_center_hz": float(frequencies[-1]),
        "elapsed_first_to_last_sample_s": float(times[-1]),
        "total_integration_s": float(data.shape[0] * dt),
        "original_frequency_descending": original_descending,
        "intensity_units": "uncalibrated recorded power (arbitrary units)",
        "sample_time_convention": "start of integration; matches SETIGEN frame times",
        "observation_description": "Small C-band diagnostic observation cutout in the Sagittarius B2 direction",
    }
    return data, frequencies, times, metadata


def inject_signal(before: np.ndarray, frequencies: np.ndarray, times: np.ndarray, config: dict):
    """Add exactly one deterministic Gaussian line to a copy, using SETIGEN."""
    import setigen as stg

    df = channel_spacing(frequencies)
    dt = float(times[1] - times[0])
    channel = int(config["start_channel_ascending"])
    if not 0 <= channel < before.shape[1]:
        raise ValueError("Injection starting channel outside observation")
    center0 = float(frequencies[channel])
    drift = float(config["drift_hz_per_s"])
    fwhm = float(config["fwhm_channels"]) * df
    if fwhm <= 0 or config["peak_amplitude_in_background_sigma"] <= 0:
        raise ValueError("Injection width and amplitude must be positive")
    centers = center0 + drift * times
    sigma_f = fwhm / (2 * np.sqrt(2 * np.log(2)))
    if centers.min() - 6 * sigma_f < frequencies[0] or centers.max() + 6 * sigma_f > frequencies[-1]:
        raise ValueError("Injection would approach/cross frequency boundaries")
    row_sigmas = robust_sigma(before, axis=1)
    background_sigma = float(np.median(row_sigmas))
    if not background_sigma > 0:
        raise ValueError("Cannot estimate nonzero background noise")
    amplitude = float(config["peak_amplitude_in_background_sigma"] * background_sigma)
    # Work in relative Hz internally: passing a GHz origin with a rounded
    # adjacent-channel spacing accumulates sub-Hz coordinate error across a band.
    relative_frequencies = np.arange(before.shape[1], dtype=np.float64) * df
    relative_start = channel * df
    frame = stg.Frame.from_data(df=df, dt=dt, fch1=0.0, ascending=True, data=before.copy())
    frame.add_signal(
        stg.constant_path(f_start=relative_start, drift_rate=drift),
        stg.constant_t_profile(level=amplitude),
        stg.gaussian_f_profile(width=fwhm),
        stg.constant_bp_profile(level=1),
    )
    after = np.asarray(frame.data, dtype=np.float64).copy()
    delta = after - before
    # Independent closed-form validation of the injector, not used by detection.
    relative_centers = relative_start + drift * times
    expected = amplitude * np.exp(-0.5 * ((relative_frequencies[None, :] - relative_centers[:, None]) / sigma_f) ** 2)
    error = float(np.max(np.abs(delta - expected)))
    np.testing.assert_allclose(delta, expected, rtol=1e-7, atol=amplitude * 1e-7)
    truth = {
        **config,
        "number_of_injected_tracks": 1,
        "start_frequency_hz": center0,
        "end_frequency_hz": float(centers[-1]),
        "fwhm_hz": fwhm,
        "background_sigma_power": background_sigma,
        "peak_amplitude_power": amplitude,
        "maximum_sampled_delta_power": float(delta.max()),
        "closed_form_max_abs_error_power": error,
        "profile": "constant-amplitude Gaussian in frequency; center f(t)=f0+drift*t",
        "injection_domain": "additive detected power; no voltages, phase, or stochastic transmitter noise",
        "time_frequency_integration": "sampled at channel centers and integration starts; no intra-integration drift smearing",
        "randomness": "none; fixed observation and deterministic injection",
        "coordinate_handling": "relative Hz inside SETIGEN; absolute Hz restored for truth reporting",
    }
    return after, delta, truth


def detect(data: np.ndarray, frequencies: np.ndarray, times: np.ndarray, config: dict):
    """Blind brute-force incoherent dedoppler search, no access to injection truth.

    Subtract each row median, divide by row MAD sigma; sum a 3-channel
    boxcar along nearest-channel linear drift tracks; robustly standardize
    each resulting frequency profile across the common valid start band.
    Scores are descriptive robust Z scores, NOT Gaussian false-alarm SNRs.
    """
    data = np.asarray(data, dtype=np.float64)
    if data.ndim != 2 or data.shape != (len(times), len(frequencies)):
        raise ValueError("Data/axis shape mismatch")
    if len(times) < 2 or len(frequencies) < 3 or not np.isfinite(data).all():
        raise ValueError("Need finite data with >=2 times and >=3 channels")
    if times[0] != 0 or not np.allclose(np.diff(times), times[1] - times[0]):
        raise ValueError("Times must start at zero and be uniformly increasing")
    df = channel_spacing(frequencies)
    if df <= 0 or times[-1] <= 0 or not np.allclose(np.diff(frequencies), df):
        raise ValueError("Axes must be uniformly increasing")
    width = int(config["boxcar_width_channels"])
    max_drift = float(config["max_abs_drift_hz_per_s"])
    grid_error = float(config["max_endpoint_grid_error_channels"])
    if width < 1 or width % 2 != 1 or max_drift <= 0 or grid_error <= 0:
        raise ValueError("Need odd positive boxcar width and positive drift/grid settings")
    # Adjacent trials move the endpoint <=grid_error channels; the nearest trial
    # therefore misses an interior true drift by at most grid_error/2 channels.
    max_step = grid_error * df / times[-1]
    half_trials = int(np.ceil(max_drift / max_step))
    drifts = np.linspace(-max_drift, max_drift, 2 * half_trials + 1)
    max_shift = int(np.ceil(max_drift * times[-1] / df))
    margin = max_shift + width // 2 + 1
    starts = np.arange(margin, data.shape[1] - margin)
    if starts.size < 32:
        raise ValueError("Search leaves too few edge-safe start channels")
    medians = np.median(data, axis=1, keepdims=True)
    sigmas = robust_sigma(data, axis=1, keepdims=True)
    if np.any(sigmas <= 0):
        raise ValueError("At least one time row has zero robust scale")
    standardized = (data - medians) / sigmas
    smoothed = uniform_filter1d(standardized, size=width, axis=1, mode="constant") * width
    scores = np.empty((len(drifts), len(starts)), dtype=np.float64)
    row_indices = np.arange(data.shape[0])[:, None]
    for i, drift in enumerate(drifts):
        offsets = np.rint(drift * times / df).astype(int)
        integrated = np.sum(smoothed[row_indices, starts[None, :] + offsets[:, None]], axis=0)
        scale = float(robust_sigma(integrated))
        if not scale > 0:
            raise ValueError("Degenerate drift-integrated profile")
        scores[i] = (integrated - np.median(integrated)) / scale
    # Local maxima plus frequency NMS: avoids listing one drift ridge many times.
    maxima = (scores == maximum_filter(scores, size=(3, width * 2 + 1), mode="nearest"))
    peaks = np.argwhere(maxima & (scores >= float(config["score_threshold"])))
    ordered = sorted(peaks.tolist(), key=lambda p: (-scores[p[0], p[1]], p[0], p[1]))
    selected = []
    for di, fi in ordered:
        channel = int(starts[fi])
        if any(abs(channel - c["start_channel_ascending"]) <= 2 * width for c in selected):
            continue
        selected.append({
            "rank": len(selected) + 1,
            "start_channel_ascending": channel,
            "start_frequency_hz": float(frequencies[channel]),
            "drift_hz_per_s": float(drifts[di]),
            "robust_score": float(scores[di, fi]),
        })
        if len(selected) >= int(config["max_candidates"]):
            break
    return {
        "candidates": selected,
        "score_map": scores,
        "drift_grid_hz_per_s": drifts,
        "start_channels": starts,
        "settings": {
            **config,
            "number_of_drift_trials": len(drifts),
            "drift_grid_spacing_hz_per_s": float(drifts[1] - drifts[0]),
            "searched_start_channel_min": int(starts[0]),
            "searched_start_channel_max": int(starts[-1]),
            "searched_track_count": int(scores.size),
            "valid_start_channels": len(starts),
            "maximum_score": float(scores.max()),
            "score_definition": "per-drift median/MAD standardized incoherent track power",
            "false_alarm_probability": "not calibrated; correlated trials and real interference",
        },
    }


def evaluate(before_search: dict, after_search: dict, truth: dict, times: np.ndarray, df: float, config: dict):
    """Match recovered tracks to truth only AFTER blind candidate generation."""
    def errors(candidate):
        delta = candidate["start_frequency_hz"] - truth["start_frequency_hz"]
        delta_drift = candidate["drift_hz_per_s"] - truth["drift_hz_per_s"]
        return float(np.max(np.abs(delta + delta_drift * times)) / df)

    matched_after = [c for c in after_search["candidates"] if errors(c) <= config["max_track_error_channels"]]
    matched_before = [c for c in before_search["candidates"] if errors(c) <= config["max_track_error_channels"]]
    best = matched_after[0] if matched_after else None
    top_match = bool(best is not None and best["rank"] == 1)
    return {
        "recovered": bool(best is not None),
        "matched_candidate": best,
        "top_candidate_matches_injection": top_match,
        "matched_track_max_error_channels": errors(best) if best else None,
        "matched_start_frequency_error_hz": best["start_frequency_hz"] - truth["start_frequency_hz"] if best else None,
        "matched_drift_error_hz_per_s": best["drift_hz_per_s"] - truth["drift_hz_per_s"] if best else None,
        "matching_candidates_before_injection": len(matched_before),
        "matching_candidates_after_injection": len(matched_after),
        "candidate_count_before": len(before_search["candidates"]),
        "candidate_count_after": len(after_search["candidates"]),
        "matching_tolerance_channels": config["max_track_error_channels"],
        "passes_recovery_check": bool(best and not matched_before and (top_match or not config["require_top_candidate_match"])),
        "interpretation": "One deterministic software recovery check, not an extraterrestrial detection or sensitivity survey",
    }


def save_candidates(path: Path, candidates: list):
    fields = ["rank", "start_channel_ascending", "start_frequency_hz", "drift_hz_per_s", "robust_score"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candidates)


def plot_results(output: Path, before, after, delta, frequencies, times, truth, before_search, after_search):
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "figure.facecolor": "white"})
    df = channel_spacing(frequencies)
    dt = times[1] - times[0]
    x = (frequencies - frequencies[0]) / 1000
    extent = [x[0] - df / 2000, x[-1] + df / 2000, -dt / 2, times[-1] + dt / 2]
    lo, hi = np.percentile(before, [1, 99.5])
    # The exact same scale is used on BOTH observations; no autoscale after injection.
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.8), layout="constrained", sharey=True)
    for ax, array, title in zip(axes[:2], [before, after], ["Before | real observation", "After | one injected track"]):
        im = ax.imshow(array, origin="lower", aspect="auto", extent=extent, vmin=lo, vmax=hi, cmap="magma", interpolation="nearest")
        ax.set_title(title)
    figure.colorbar(im, ax=axes[:2], label="Recorded power [arbitrary units]", shrink=0.8)
    imdelta = axes[2].imshow(delta, origin="lower", aspect="auto", extent=extent, cmap="viridis", vmin=0, vmax=delta.max(), interpolation="nearest")
    axes[2].set_title("Difference | after minus before")
    figure.colorbar(imdelta, ax=axes[2], label="Added power [arbitrary units]", shrink=0.8)
    for ax in axes:
        ax.set_xlabel(f"Frequency offset [kHz] from {frequencies[0] / 1e6:.9f} MHz")
    axes[0].set_ylabel("Elapsed time [s]")
    figure.suptitle("Load → Inject → Detect | DIAG_SGR_B2, Green Bank Telescope", fontsize=15)
    figure.savefig(output / "spectrogram_comparison.png", dpi=180)
    figure.savefig(output / "spectrogram_comparison.pdf", metadata={"CreationDate": None, "ModDate": None})
    plt.close(figure)

    track = truth["start_frequency_hz"] + truth["drift_hz_per_s"] * times
    center_index = int(np.argmin(np.abs(frequencies - np.mean(track))))
    left, right = max(0, center_index - 55), min(len(frequencies), center_index + 56)
    zoom_extent = [x[left] - df / 2000, x[right - 1] + df / 2000, -dt / 2, times[-1] + dt / 2]
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.8), layout="constrained", sharey=True)
    for ax, array, title in zip(axes, [before, after], ["Before | same frequency window", "After | truth and recovered track"]):
        im = ax.imshow(array[:, left:right], origin="lower", aspect="auto", extent=zoom_extent, vmin=lo, vmax=hi, cmap="magma", interpolation="nearest")
        ax.set_title(title)
        ax.set_xlabel(f"Frequency offset [kHz]\nReference: {frequencies[0] / 1e6:.9f} MHz")
    axes[1].plot((track - frequencies[0]) / 1000, times, color="cyan", lw=1.5, label="Injected truth")
    if after_search["candidates"]:
        recovered = after_search["candidates"][0]
        path = recovered["start_frequency_hz"] + recovered["drift_hz_per_s"] * times
        axes[1].plot((path - frequencies[0]) / 1000, times, "--", color="lime", lw=1.3, label="Blind rank-1 recovery")
    axes[1].legend(loc="upper left", fontsize=8)
    axes[0].set_ylabel("Elapsed time [s]")
    figure.colorbar(im, ax=axes, label="Recorded power [arbitrary units]", shrink=0.85)
    figure.savefig(output / "spectrogram_zoom.png", dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained", sharey=True)
    maximum = max(before_search["score_map"].max(), after_search["score_map"].max())
    for ax, search, title in zip(axes, [before_search, after_search], ["Blind search | before", "Blind search | after"]):
        grid = search["drift_grid_hz_per_s"]
        chans = search["start_channels"]
        im = ax.imshow(search["score_map"], origin="lower", aspect="auto", extent=[x[chans[0]], x[chans[-1]], grid[0], grid[-1]], vmin=0, vmax=maximum, cmap="viridis", interpolation="nearest")
        ax.set_title(title)
        ax.set_xlabel(f"Track start frequency offset [kHz]\nReference: {frequencies[0] / 1e6:.9f} MHz")
    axes[1].plot((truth["start_frequency_hz"] - frequencies[0]) / 1000, truth["drift_hz_per_s"], marker="x", color="red", ms=8, label="Truth (evaluation only)")
    axes[1].legend(fontsize=8)
    axes[0].set_ylabel("Trial drift rate [Hz/s]")
    figure.colorbar(im, ax=axes, label="Robust score (not calibrated false-alarm SNR)", shrink=0.85)
    figure.savefig(output / "detection_search.png", dpi=180)
    plt.close(figure)


def write_report(path: Path, results: dict):
    o, t, e = results["observation"], results["injection_truth"], results["evaluation"]
    candidate = e["matched_candidate"] or {}
    status = "PASS" if results["all_checks_passed"] else "FAIL"
    report = f"""# Load → Inject → Detect: experiment report

**Status: {status}.** Real observation loaded, one synthetic power track injected, and an independent baseline search evaluated.

## Observation and provenance

- Target label: `{o['source_name']}`; telescope: {o['telescope']} (SIGPROC ID {o['telescope_id']}).
- Start: {o['start_utc']} UTC (MJD {o['start_mjd']:.10f}).
- Array: {o['shape_time_frequency'][0]} integrations × {o['shape_time_frequency'][1]} frequency channels.
- Integration: {o['time_resolution_s']:.9f} s; total duration: {o['total_integration_s']:.6f} s.
- Channel spacing: {o['frequency_resolution_hz']:.9f} Hz.
- Center-frequency range: {o['frequency_first_center_hz']/1e6:.9f}–{o['frequency_last_center_hz']/1e6:.9f} MHz.
- Original descending frequency order reversed into ascending order; power values otherwise unchanged.
- Raw observation SHA-256: `{results['input_sha256']}`.
- Frozen source: {results['config']['dataset']['url']}
- This is a compact archival diagnostic cutout, not a complete ON/OFF observing cadence.

## Injection (ground truth)

- Exactly one Gaussian narrowband track, constant amplitude, positive linear drift.
- Start: {t['start_frequency_hz']/1e6:.9f} MHz; ascending channel {t['start_channel_ascending']}.
- Drift: {t['drift_hz_per_s']:.9f} Hz/s; FWHM: {t['fwhm_hz']:.9f} Hz.
- Peak power: {t['peak_amplitude_power']:.6f} arbitrary units = {t['peak_amplitude_in_background_sigma']:.1f} × pre-injection median row MAD sigma.
- Additive sampled power model, not a phase-coherent voltage simulation. No random numbers are drawn.
- Independent analytic Gaussian check max error: {t['closed_form_max_abs_error_power']:.6g} power units.

## Blind detector and recovery

Detector: row median/MAD normalization, {results['config']['detector']['boxcar_width_channels']}-channel boxcar, incoherent nearest-channel sums over linear drift tracks, then per-drift robust profile standardization. It receives no truth coordinates or delta array.

- Search range: ±{results['config']['detector']['max_abs_drift_hz_per_s']} Hz/s over {results['search_after']['number_of_drift_trials']} trial drift rates.
- Search size: {results['search_after']['searched_track_count']:,} track trials.
- Detection threshold: robust score ≥{results['config']['detector']['score_threshold']}; this is a descriptive threshold, not a calibrated false-alarm probability.
- Before: {e['candidate_count_before']} retained candidate(s); after: {e['candidate_count_after']}.
- Candidates are search maxima, not distinct sources. One injected line can create secondary peaks when other trial tracks partially overlap it; full-track truth matching determines which candidate is recovered.
- Injection matched: **{e['recovered']}**; top candidate matches: **{e['top_candidate_matches_injection']}**.
- Recovered start: {candidate.get('start_frequency_hz', float('nan'))/1e6:.9f} MHz.
- Recovered drift: {candidate.get('drift_hz_per_s', float('nan')):.9f} Hz/s.
- Recovered robust score: {candidate.get('robust_score', float('nan')):.4f}.
- Maximum recovered-versus-injected track error: {e['matched_track_max_error_channels']} channels (allowed ≤{e['matching_tolerance_channels']}).
- Matching candidate(s) before injection: {e['matching_candidates_before_injection']}.

## Verification

```json
{json.dumps(results['checks'], indent=2)}
```

## Artifacts

- `spectrogram_comparison.png` / `.pdf`: original, injected, and difference views. Before and after use identical intensity limits.
- `spectrogram_zoom.png`: close view, with truth/recovered tracks overlaid only for evaluation.
- `detection_search.png`: before/after blind score maps using identical color limits.
- `before.npz`, `after.npz`, `injected_signal.npy`: numerical power arrays and physical axes.
- `candidates_before.csv`, `candidates_after.csv`: independently generated candidate lists.
- `search_before.npz`, `search_after.npz`: complete searched score maps and trial axes.
- `results.json`, `environment.json`, `artifact_manifest.json`: machine-readable evidence, versions, and checksums.

## Limits and interpretation

This validates plumbing for one deliberately strong, deterministic injected signal. It does not measure completeness, precision on extraterrestrial signals, or scientific novelty. Unknown features in the original observation are not labeled extraterrestrial or automatically labeled RFI. The source file carries observational metadata; its full upstream raw-data acquisition chain has not been independently audited.

Scores use real correlated/non-Gaussian backgrounds, a correlated drift grid, and a simple noise estimator; no Gaussian p-value is claimed. The Gaussian injector is sampled at channel centers/integration starts, omits intra-integration drift smearing and signal self-noise, and does not represent every transmitter morphology. The detector searches a restricted drift/bandwidth family and excludes edge channels. Candidate suppression merges nearby start-frequency peaks and is adequate for this single-track experiment only.

The next research stage is a preregistered multi-injection sensitivity study and independent observations, before any LLM evaluation.
"""
    path.write_text(report)


def run(config_path: Path = ROOT / "config.json", output: Path = ROOT / "results" / "run_001", download=False):
    config_path, output = Path(config_path).resolve(), Path(output).resolve()
    config = json.loads(config_path.read_text())
    input_path = ROOT / config["dataset"]["path"]
    if download:
        fetch_dataset(config["dataset"], input_path)
    if not input_path.exists():
        raise FileNotFoundError("Observation missing. Run with --download.")
    output.mkdir(parents=True, exist_ok=True)
    before, frequencies, times, observation = load_observation(input_path, config["dataset"])
    immutable_copy = before.copy()
    after, delta, truth = inject_signal(before, frequencies, times, config["injection"])
    # Explicit blind boundary: no truth or injected-only difference enters detect().
    before_search = detect(before, frequencies, times, config["detector"])
    after_search = detect(after, frequencies, times, config["detector"])
    evaluation = evaluate(before_search, after_search, truth, times, channel_spacing(frequencies), config["evaluation"])
    checks = {
        "input_checksum_verified": sha256(input_path) == config["dataset"]["sha256"],
        "shape_matches_protocol": list(before.shape) == config["dataset"]["expected_shape"],
        "original_array_unchanged": bool(np.array_equal(before, immutable_copy)),
        "all_output_power_finite": bool(np.isfinite(after).all()),
        "delta_nonnegative_with_roundoff_tolerance": bool(delta.min() >= -np.finfo(float).eps * abs(after).max()),
        "exactly_one_injection_declared": truth["number_of_injected_tracks"] == 1,
        "analytic_injection_verified": truth["closed_form_max_abs_error_power"] < truth["peak_amplitude_power"] * 1e-7,
        "injection_detected_above_threshold": evaluation["recovered"],
        "top_candidate_matches_injection": evaluation["top_candidate_matches_injection"],
        "no_matching_preinjection_candidate": evaluation["matching_candidates_before_injection"] == 0,
        "recovery_check_passed": evaluation["passes_recovery_check"],
    }
    results = {
        "experiment_id": config["experiment_id"],
        "config": config,
        "input_sha256": sha256(input_path),
        "source_code_sha256": sha256(Path(__file__)),
        "observation": observation,
        "injection_truth": truth,
        "search_before": before_search["settings"],
        "search_after": after_search["settings"],
        "evaluation": evaluation,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    for name, values in [("before", before), ("after", after)]:
        np.savez_compressed(output / f"{name}.npz", power=values, frequency_hz=frequencies, time_s=times)
    np.save(output / "injected_signal.npy", delta, allow_pickle=False)
    for label, search in [("before", before_search), ("after", after_search)]:
        save_candidates(output / f"candidates_{label}.csv", search["candidates"])
        np.savez_compressed(output / f"search_{label}.npz", score=search["score_map"], drift_hz_per_s=search["drift_grid_hz_per_s"], start_channels=search["start_channels"])
    write_json(output / "results.json", results)
    write_json(output / "config.json", config)
    packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    write_json(output / "environment.json", {"python": sys.version, "platform": platform.platform(), "packages": dict(sorted(packages.items()))})
    plot_results(output, before, after, delta, frequencies, times, truth, before_search, after_search)
    write_report(output / "REPORT.md", results)
    artifacts = {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file() and p.name != "artifact_manifest.json"}
    write_json(output / "artifact_manifest.json", artifacts)
    print(json.dumps({"output": str(output), "all_checks_passed": results["all_checks_passed"], "evaluation": evaluation}, indent=2))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "run_001")
    parser.add_argument("--download", action="store_true", help="Fetch checksum-pinned public sample if missing")
    args = parser.parse_args()
    result = run(args.config, args.output, args.download)
    raise SystemExit(0 if result["all_checks_passed"] else 1)


if __name__ == "__main__":
    main()
