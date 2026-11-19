"""Scientific invariants and detector recovery tests; no network required."""
import inspect
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pipeline as p


@pytest.fixture
def config():
    return json.loads((ROOT / "config.json").read_text())


@pytest.fixture
def observation(config):
    return p.load_observation(ROOT / config["dataset"]["path"], config["dataset"])


def test_real_observation_hash_header_and_frequency_reversal(config, observation):
    from blimpy import Waterfall
    data, frequencies, times, metadata = observation
    raw = Waterfall(str(ROOT / config["dataset"]["path"]))
    assert metadata["source_name"] == "DIAG_SGR_B2"
    assert metadata["telescope_id"] == 6
    assert np.all(np.diff(frequencies) > 0)
    np.testing.assert_array_equal(data, raw.data[:, 0, ::-1])
    np.testing.assert_allclose(np.diff(times), metadata["time_resolution_s"])


def test_corrupt_observation_is_rejected(tmp_path, config):
    path = tmp_path / "broken.fil"
    path.write_bytes(b"not the real observation")
    with pytest.raises(ValueError, match="checksum"):
        p.load_observation(path, config["dataset"])


def test_single_injection_preserves_input_and_matches_closed_form(config, observation):
    before, frequencies, times, _ = observation
    original = before.copy()
    after, delta, truth = p.inject_signal(before, frequencies, times, config["injection"])
    np.testing.assert_array_equal(before, original)
    np.testing.assert_allclose(after - before, delta, rtol=0, atol=0)
    df = p.channel_spacing(frequencies)
    relative_frequencies = np.arange(len(frequencies)) * df
    centers = truth["start_channel_ascending"] * df + truth["drift_hz_per_s"] * times
    sigma = truth["fwhm_hz"] / np.sqrt(8 * np.log(2))
    expected = truth["peak_amplitude_power"] * np.exp(-0.5 * ((relative_frequencies[None, :] - centers[:, None]) / sigma) ** 2)
    np.testing.assert_allclose(delta, expected, rtol=1e-7, atol=truth["peak_amplitude_power"] * 1e-7)
    # Every integration contains one connected bright spectral feature.
    bright = delta > 0.01 * delta.max(axis=1, keepdims=True)
    for row in bright:
        indices = np.flatnonzero(row)
        assert len(indices) >= 2
        assert np.all(np.diff(indices) == 1)


@pytest.mark.parametrize("drift", [1.0, -1.35, 0.0])
def test_blind_recovery_for_positive_negative_and_zero_drift(config, observation, drift):
    before, frequencies, times, _ = observation
    settings = {**config["injection"], "drift_hz_per_s": drift}
    after, _, truth = p.inject_signal(before, frequencies, times, settings)
    before_search = p.detect(before, frequencies, times, config["detector"])
    after_search = p.detect(after, frequencies, times, config["detector"])
    result = p.evaluate(before_search, after_search, truth, times, p.channel_spacing(frequencies), config["evaluation"])
    assert result["passes_recovery_check"], result
    assert result["top_candidate_matches_injection"]


def test_detector_interface_excludes_truth():
    assert list(inspect.signature(p.detect).parameters) == ["data", "frequencies", "times", "config"]


def test_shifted_frequency_axis_produces_shifted_detection(config, observation):
    before, frequencies, times, _ = observation
    after, _, _ = p.inject_signal(before, frequencies, times, config["injection"])
    base = p.detect(after, frequencies, times, config["detector"])["candidates"][0]
    shifted = p.detect(after, frequencies + 1e6, times, config["detector"])["candidates"][0]
    assert shifted["start_frequency_hz"] - base["start_frequency_hz"] == pytest.approx(1e6)
    assert shifted["drift_hz_per_s"] == base["drift_hz_per_s"]
    assert shifted["robust_score"] == base["robust_score"]


def test_no_spurious_detection_in_seeded_noise(config, observation):
    before, frequencies, times, _ = observation
    surrogate = np.random.default_rng(20261119).normal(size=before.shape)
    assert p.detect(surrogate, frequencies, times, config["detector"])["candidates"] == []


def test_refuse_out_of_band_injection(config, observation):
    before, frequencies, times, _ = observation
    settings = {**config["injection"], "start_channel_ascending": 1023}
    with pytest.raises(ValueError, match="boundaries"):
        p.inject_signal(before, frequencies, times, settings)


def test_invalid_detector_axes_rejected(config, observation):
    before, frequencies, times, _ = observation
    with pytest.raises(ValueError, match="increasing"):
        p.detect(before, frequencies[::-1], times, config["detector"])


def test_zero_noise_scale_rejected(config, observation):
    before, frequencies, times, _ = observation
    with pytest.raises(ValueError, match="zero robust scale"):
        p.detect(np.ones_like(before), frequencies, times, config["detector"])


def test_saved_run_numeric_evidence_and_manifest(config):
    output = ROOT / "results" / "run_001"
    if not (output / "results.json").exists():
        pytest.skip("Run pipeline.py first to verify the saved experiment")
    result = json.loads((output / "results.json").read_text())
    assert result["all_checks_passed"]
    before = np.load(output / "before.npz")["power"]
    after = np.load(output / "after.npz")["power"]
    delta = np.load(output / "injected_signal.npy", allow_pickle=False)
    np.testing.assert_array_equal(after - before, delta)
    for name, entry in json.loads((output / "artifact_manifest.json").read_text()).items():
        assert p.sha256(output / name) == entry["sha256"]
