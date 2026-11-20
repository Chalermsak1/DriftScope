"""Validated in-memory observations. True masks mean usable recorded samples."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import numpy as np


@dataclass(frozen=True)
class Scan:
    scan_id: str
    power: np.ndarray
    frequency_hz: np.ndarray
    time_s: np.ndarray
    start_mjd: float
    role: str
    target: str
    session_id: str
    raw_id: str
    receiver: str
    usable: np.ndarray | None = None
    ra_deg: float | None = None
    dec_deg: float | None = None

    def __post_init__(self):
        data = np.array(self.power, dtype=np.float64, copy=True)
        freq = np.array(self.frequency_hz, dtype=np.float64, copy=True)
        times = np.array(self.time_s, dtype=np.float64, copy=True)
        mask = np.ones(data.shape, bool) if self.usable is None else np.array(self.usable, dtype=bool, copy=True)
        if data.ndim != 2 or freq.ndim != 1 or times.ndim != 1 or data.shape != (len(times), len(freq)):
            raise ValueError("Observation shape/axes disagree")
        if mask.shape != data.shape or len(times) < 2 or len(freq) < 3:
            raise ValueError("Need matching sample mask, >=2 integrations, >=3 channels")
        if not np.isfinite(freq).all() or not np.isfinite(times).all() or not np.isfinite(data[mask]).all():
            raise ValueError("Non-finite axes or usable power")
        if np.all(np.diff(freq) < 0):
            freq, data, mask = freq[::-1].copy(), data[:, ::-1].copy(), mask[:, ::-1].copy()
        df = float(np.median(np.diff(freq)))
        # Relative tolerance against GHz origins must never hide irregular channels.
        atol = max(abs(df)*1e-7, abs(np.spacing(freq).max())*4)
        if df <= 0 or not np.allclose(np.diff(freq), df, rtol=0, atol=atol):
            raise ValueError("Frequency axis must be a uniform monotonic channel lattice")
        if times[0] != 0 or times[1] <= 0 or not np.allclose(np.diff(times), times[1], rtol=1e-10, atol=1e-10):
            raise ValueError("Scan times must start at zero and increase uniformly")
        if not np.isfinite(self.start_mjd) or self.role not in {"ON", "OFF"}:
            raise ValueError("Need a finite MJD and explicit ON/OFF role")
        if (self.ra_deg is None) != (self.dec_deg is None):
            raise ValueError('Pointing RA/Dec must both be supplied or explicitly unavailable')
        if self.ra_deg is not None and (not np.isfinite(self.ra_deg) or not np.isfinite(self.dec_deg)
                                       or not 0 <= self.ra_deg < 360 or not -90 <= self.dec_deg <= 90):
            raise ValueError('Invalid pointing coordinates')
        for name in ("scan_id", "target", "session_id", "raw_id", "receiver"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"Missing {name}; unknown provenance must be explicit")
        for name, value in (("power", data), ("frequency_hz", freq), ("time_s", times), ("usable", mask)):
            value.flags.writeable = False
            object.__setattr__(self, name, value)

    @property
    def df(self):
        return float(np.median(np.diff(self.frequency_hz)))

    @property
    def dt(self):
        return float(self.time_s[1])

    def with_power(self, power):
        return replace(self, power=power)


@dataclass(frozen=True)
class Cadence:
    cadence_id: str
    scans: tuple[Scan, ...]
    candidate_selected: bool = True

    def __post_init__(self):
        if not self.scans or len({s.scan_id for s in self.scans}) != len(self.scans):
            raise ValueError("Need nonempty cadence with unique scan IDs")
        on = [s for s in self.scans if s.role == "ON"]
        if not on or len({s.target for s in on}) != 1:
            raise ValueError("ON pointings must identify one target")
        if any(s.role == "OFF" and s.target == on[0].target for s in self.scans):
            raise ValueError("OFF target equals ON target")
        if len({s.receiver for s in self.scans}) != 1:
            raise ValueError("Mixed receiver regimes in one cadence")
        for a, b in zip(self.scans, self.scans[1:]):
            gap = (b.start_mjd-a.start_mjd)*86400-a.power.shape[0]*a.dt
            if gap < -0.001:
                raise ValueError("Scans reordered or overlapping")

    @property
    def offsets_s(self):
        return np.array([(s.start_mjd-self.scans[0].start_mjd)*86400 for s in self.scans])

    @property
    def complete(self):
        return [s.role for s in self.scans] == ["ON", "OFF", "ON", "OFF", "ON", "OFF"]


def release_cadences(path: Path):
    """Read only the existing checksum-pinned release; preserve actual scan gaps."""
    from research.pilot.observations import load_release, inspect_cadence
    release, spec = load_release(Path(path))
    cadences = []
    for key, item in sorted(release.items()):
        meta, power, freq, _ = inspect_cadence(key, item)
        if not meta["passes_structural_cadence_checks"]:
            raise ValueError(f"Invalid released cadence {key}")
        scans = []
        for i, m in enumerate(meta["scans"]):
            header = item["all_header"][i]
            raw = str(header.get("rawdatafile", f"{m['source_name']}:{m['start_mjd']:.12f}"))
            scans.append(Scan(f"{key}_scan_{i}", power[i], freq, np.arange(power.shape[1])*m["integration_s"],
                              m["start_mjd"], m["role"], m["source_name"],
                              f"GBT_UTC_day_{int(m['start_mjd'])}", raw,
                              "GBT_L_candidate_release", ra_deg=m['ra_deg'], dec_deg=m['dec_deg']))
        cadences.append(Cadence(key, tuple(scans), candidate_selected=True))
    return cadences, spec
