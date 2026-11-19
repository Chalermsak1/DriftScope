"""Checksum-pinned observational release access with explicit cadence validation.

The upstream release is a legacy pickle containing numpy arrays and Astropy
angles. Only the exact pinned file and explicitly whitelisted constructors
are accepted. Exported scientific arrays use non-object NPZ, never pickle.
"""
from __future__ import annotations

import io
import json
import pickle
from pathlib import Path
from dataclasses import dataclass
import hashlib

import numpy as np
from astropy.coordinates import Angle
import astropy.units.core as unit_core

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain(value):
    if isinstance(value, Angle):
        return {"degrees": float(value.degree), "original": str(value)}
    if isinstance(value, np.ndarray):
        return [plain(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported metadata: {type(value)}")


class RestrictedReleaseUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        allowed = {
            ("numpy.core.numeric", "_frombuffer"): np._core.numeric._frombuffer,
            ("numpy.core.multiarray", "_reconstruct"): np._core.multiarray._reconstruct,
            ("numpy.core.multiarray", "scalar"): np._core.multiarray.scalar,
            ("numpy", "dtype"): np.dtype,
            ("numpy", "ndarray"): np.ndarray,
            ("builtins", "bytes"): bytes,
            ("astropy.coordinates.angles", "Angle"): Angle,
            **{("astropy.units.core", n): getattr(unit_core, n)
               for n in ("Unit", "CompositeUnit", "_recreate_irreducible_unit", "IrreducibleUnit")},
        }
        if (module, name) not in allowed:
            raise pickle.UnpicklingError(f"Unapproved global: {module}.{name}")
        return allowed[(module, name)]


def load_release(path: Path = HERE / "data/upstream/top_8_data.pkl"):
    spec = json.loads((HERE / "configs/source.json").read_text())
    payload = path.read_bytes()
    if len(payload) != spec["bytes"] or hashlib.sha256(payload).hexdigest() != spec["sha256"]:
        raise ValueError("Unrecognized observational release: size/checksum mismatch")
    blob = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
    if blob != spec["git_blob_sha1"]:
        raise ValueError("Upstream git blob mismatch")
    release = RestrictedReleaseUnpickler(io.BytesIO(payload)).load()
    if set(release) != {f"mlc{i}" for i in range(1, 9)}:
        raise ValueError("Unexpected released cadence keys")
    return release, spec


def separation_deg(ra1, dec1, ra2, dec2):
    # Stable spherical angular distance, including RA wrap and polar pointings.
    r1, d1, r2, d2 = np.deg2rad([ra1, dec1, ra2, dec2])
    a = np.sin((d2-d1)/2)**2 + np.cos(d1)*np.cos(d2)*np.sin((r2-r1)/2)**2
    return float(np.rad2deg(2*np.arcsin(np.sqrt(np.clip(a, 0, 1)))))


def inspect_cadence(key: str, item: dict):
    data = np.asarray(item["data"])
    headers = item["all_header"]
    bounds = np.asarray(item["freq"], dtype=float)
    if data.ndim != 4 or data.shape[0] != 6 or data.shape[2] != 1 or len(headers) != 6:
        raise ValueError(f"{key}: unexpected six-scan array/header structure")
    if bounds.shape != (2,) or not np.isfinite(bounds).all() or bounds[0] >= bounds[1]:
        raise ValueError(f"{key}: invalid released frequency bounds")
    nt, nf = data.shape[1], data.shape[3]
    mjds = np.array([float(h["tstart"]) for h in headers])
    offsets = (mjds - mjds[0]) * 86400.0
    tsamps = np.array([float(h["tsamp"]) for h in headers])
    foffs = np.array([float(h["foff"]) for h in headers])
    names = [str(h["source_name"]) for h in headers]
    ras = [float(h["src_raj"].degree) for h in headers]
    decs = [float(h["src_dej"].degree) for h in headers]
    separations = [separation_deg(ras[0], decs[0], ra, dec) for ra, dec in zip(ras, decs)]
    durations = tsamps * nt
    gaps = offsets[1:] - (offsets[:-1] + durations[:-1])
    df = float(abs(foffs[0]) * 1e6)
    # The release provides a frequency interval of N*df, not N channel centers.
    # Reconstruct the half-open blimpy slice on the ORIGINAL header lattice.
    # This convention is separately checked; one-channel ambiguity is disclosed.
    upper, lower = bounds[1], bounds[0]
    original_first = float(headers[0]["fch1"])
    upper_index = int(np.rint((upper - original_first) / foffs[0]))
    lower_index = int(np.rint((lower - original_first) / foffs[0]))
    lattice = original_first + foffs[0] * np.arange(upper_index, lower_index)
    lattice_error = max(abs(lattice[0]-upper), abs((original_first + foffs[0]*lower_index)-lower))*1e6 if len(lattice) else float("inf")
    frequencies = lattice[::-1] * 1e6
    checks = {
        "six_scans_and_six_headers": True,
        "finite_power": bool(np.isfinite(data).all()),
        "positive_time_resolution": bool(np.all(tsamps > 0)),
        "chronological_order": bool(np.all(np.diff(mjds) > 0)),
        "no_overlapping_integrations": bool(np.all(gaps >= -0.001)),
        "same_time_resolution": bool(np.allclose(tsamps, tsamps[0], rtol=1e-9, atol=0)),
        "same_channel_spacing": bool(np.allclose(foffs, foffs[0], rtol=1e-9, atol=0)),
        "descending_original_frequency": bool(np.all(foffs < 0)),
        "frequency_interval_matches_cutout_shape": bool(abs((upper-lower)*1e6 - nf*df) < 0.01),
        "reconstructed_frequency_shape": len(lattice) == nf,
        "frequency_bounds_on_header_lattice": bool(lattice_error < 0.01),
        "same_telescope": all(int(h["telescope_id"]) == 6 for h in headers),
        "same_original_frequency_lattice": all(abs(float(h["fch1"])-original_first) < 1e-9 for h in headers),
        "on_target_names_consistent": names[0] == names[2] == names[4],
        "off_target_names_differ": all(names[i] != names[0] for i in (1, 3, 5)),
        "on_coordinates_agree_within_1_arcsec": all(separations[i] <= 1/3600 for i in (0, 2, 4)),
        "off_coordinates_distinct_over_1_arcmin": all(separations[i] > 1/60 for i in (1, 3, 5)),
    }
    scans = []
    for i, h in enumerate(headers):
        scans.append({
            "scan_index": i,
            "role": "ON" if i % 2 == 0 else "OFF",
            "source_name": names[i],
            "start_mjd": float(mjds[i]),
            "elapsed_start_s": float(offsets[i]),
            "sample_count": nt,
            "integration_s": float(tsamps[i]),
            "represented_duration_s": float(durations[i]),
            "ra_deg": ras[i], "dec_deg": decs[i],
            "separation_from_first_on_deg": separations[i],
            "header": plain(h),
        })
    metadata = {
        "cadence_id": key,
        "source_type": "real_observational_candidate_cutout",
        "checks": checks,
        "passes_structural_cadence_checks": all(checks.values()),
        "shape": list(data.shape),
        "released_frequency_bounds_mhz": bounds.tolist(),
        "channel_spacing_hz": df,
        "frequency_bounds_lattice_error_hz": float(lattice_error),
        "frequency_axis_convention": "Descending header lattice, upper bound included/lower excluded as in blimpy half-open slicing; reverse to ascending. Extraction code not supplied in release; absolute channel-center convention is an explicit reconstruction assumption.",
        "frequency_axis_absolute_systematic_uncertainty_hz": df,
        "gaps_between_represented_scans_s": gaps.tolist(),
        "represented_exposure_s": float(durations.sum()),
        "elapsed_span_s": float(offsets[-1]+durations[-1]),
        "scans": scans,
        "limitations": [
            "Candidate-selected, narrow frequency cutout; not a representative background cohort.",
            "Six released scan records are present; full original files and all original integration counts have not been independently acquired.",
            "Represented exposure is sample_count*tsamp; do not count scan gaps as observed exposure.",
            "Pointing separation checks verify distinct directions, not beam attenuation or an extraterrestrial origin.",
            "Source timestamps/pointings are inherited headers; no independent telescope-log audit.",
            "L-band pilot differs from the original C-band fixture; they are not pooled for sensitivity estimates.",
        ],
    }
    return metadata, data[:, :, 0, ::-1].astype(np.float64), frequencies, offsets


if __name__ == "__main__":
    release, _ = load_release()
    for key, item in release.items():
        m, _, _, _ = inspect_cadence(key, item)
        print(json.dumps({"cadence": key, "passed": m["passes_structural_cadence_checks"], "failed": [k for k,v in m["checks"].items() if not v], "sources": [s["source_name"] for s in m["scans"]], "starts": [s["elapsed_start_s"] for s in m["scans"]], "gaps": m["gaps_between_represented_scans_s"]}))
