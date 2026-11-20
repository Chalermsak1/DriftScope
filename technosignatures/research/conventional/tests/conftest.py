"""All generated observations here are explicitly synthetic test fixtures."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from research.conventional.data import Scan, Cadence


@pytest.fixture
def make_scan():
    def make(seed=1, nt=16, nf=256, dt=1.0, offset=0.0, role="ON", scan_id="s0", mask=None):
        return Scan(scan_id, 20+np.random.default_rng(seed).normal(size=(nt, nf)),
                    1e9+np.arange(nf, dtype=float), np.arange(nt)*dt, 59000+offset/86400,
                    role, "A" if role == "ON" else "OFF_"+scan_id, "synthetic_session", "synthetic_raw_"+scan_id,
                    "SYNTHETIC_TEST_ONLY", mask)
    return make


@pytest.fixture
def synthetic_cadence(make_scan):
    return Cadence("synthetic", tuple(make_scan(seed=i+1, scan_id=f"s{i}", offset=50*i,
                                                role="ON" if i % 2 == 0 else "OFF") for i in range(6)), False)


@pytest.fixture
def signal_parameters():
    return {"trial_id": "synthetic_case", "family": "continuous_linear", "start_channel": 80.0,
            "drift_hz_per_s": 0.08, "peak_power_sigma": 30.0, "fwhm_channels": 2.0,
            "curvature_hz_per_s2": 0.0, "off_response": 0.0}
