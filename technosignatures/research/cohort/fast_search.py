"""Vectorized execution of the validated per-drift, globally normalized search."""
import numpy as np
from scipy.ndimage import maximum_filter

from research.conventional.search import SearchConfig, SearchResult, mad_sigma


def search(scan, config=SearchConfig(), drift_batch=16):
    nt, nf = scan.power.shape; radius = config.boxcar_width_channels//2
    half = int(np.ceil(config.max_abs_drift_hz_per_s*scan.time_s[-1]/(config.max_endpoint_grid_error_channels*scan.df)))
    drifts = np.linspace(-config.max_abs_drift_hz_per_s, config.max_abs_drift_hz_per_s, 2*half+1)
    if len(drifts)*nf > config.max_score_cells: raise ValueError('Search exceeds explicit score-map budget')
    if drift_batch < 1: raise ValueError('Positive drift batch required')
    standardized = np.zeros_like(scan.power)
    for i in range(nt):
        row = scan.power[i, scan.usable[i]]
        if len(row) < 3 or not (scale := float(mad_sigma(row))) > 0: raise ValueError('Too few usable samples or zero pre-search noise scale')
        standardized[i, scan.usable[i]] = (row-np.median(row))/scale
    max_shift = int(np.ceil(config.max_abs_drift_hz_per_s*scan.time_s[-1]/scan.df))
    cores = [(i, min(i+config.tile_core_channels, nf)) for i in range(0, nf, config.tile_core_channels)]
    tiles = [{'core_start': lo, 'core_stop_exclusive': hi, 'halo_start': max(0, lo-max_shift-radius),
              'halo_stop_exclusive': min(nf, hi+max_shift+radius)} for lo, hi in cores]
    scores = np.full((len(drifts), nf), np.nan); per_drift = []
    time_indices = np.arange(nt)[None, :, None]
    for begin in range(0, len(drifts), drift_batch):
        trial = drifts[begin:begin+drift_batch]
        shifts = np.rint(trial[:, None]*scan.time_s[None, :]/scan.df).astype(int)
        lower = np.maximum(0, radius-shifts.min(axis=1)); upper = np.minimum(nf, nf-radius-shifts.max(axis=1))
        origins = np.arange(nf)[None, :]
        physical = (origins >= lower[:, None]) & (origins < upper[:, None])
        usable = physical.copy(); values = np.zeros((len(trial), nf))
        for lo, hi in cores:
            indices = np.arange(lo, hi)[None, None, :]+shifts[:, :, None]
            for box in range(-radius, radius+1):
                clipped = np.clip(indices+box, 0, nf-1)
                values[:, lo:hi] += np.sum(standardized[time_indices, clipped], axis=1)
                usable[:, lo:hi] &= np.all(scan.usable[time_indices, clipped], axis=1)
            # NumPy uses a different reduction order for a one-column physical
            # owner. Match the reference's pairing exactly at such tiny edges.
            single = np.flatnonzero(physical[:, lo:hi].sum(axis=1) == 1)
            for j in single:
                owner = int(np.flatnonzero(physical[j, lo:hi])[0])+lo
                positions = owner+shifts[j, :, None]
                value = 0.0
                for box in range(-radius, radius+1):
                    value += float(np.sum(standardized[np.arange(nt)[:, None], positions+box], axis=0)[0])
                values[j, owner] = value
        # Keep row-wise median/MAD identical to the scalar scientific reference;
        # vectorize the expensive track integration, not the statistical definition.
        for j, drift in enumerate(trial):
            integrated = values[j, usable[j]]
            scale = float(mad_sigma(integrated)) if len(integrated) >= 3 else 0.0
            evaluated = len(integrated) if scale > 0 else 0
            if evaluated: scores[begin+j, usable[j]] = (integrated-np.median(integrated))/scale
            count = int(physical[j].sum())
            per_drift.append({'drift_hz_per_s': float(drift), 'physical_track_trials': count,
                              'masked_track_trials': count-int(usable[j].sum()), 'evaluated_track_trials': evaluated,
                              'unscorable_track_trials': int(usable[j].sum())-evaluated, 'profile_scale': scale,
                              'valid_start_min': int(lower[j]), 'valid_start_stop_exclusive': max(int(lower[j]), int(upper[j]))})
    finite = np.isfinite(scores); maximum_input = np.where(finite, scores, -np.inf)
    maxima = maximum_input == maximum_filter(maximum_input, size=(3, config.boxcar_width_channels*2+1), mode='constant', cval=-np.inf)
    peaks = np.argwhere(finite & maxima & (scores >= config.score_threshold))
    ordered = sorted(peaks.tolist(), key=lambda p: (-scores[p[0], p[1]], p[0], p[1]))
    step = float(drifts[1]-drifts[0])
    hits = [{'hit_id': f'{scan.scan_id}_d{di:05d}_c{channel:08d}', 'scan_id': scan.scan_id,
             'start_channel_ascending': channel, 'start_frequency_hz': float(scan.frequency_hz[channel]),
             'drift_hz_per_s': float(drifts[di]), 'robust_score': float(scores[di, channel]), 'drift_index': di,
             'drift_grid_spacing_hz_per_s': step, 'reference_time_after_scan_start_s': scan.dt/2,
             'time_support_start_s': 0.0, 'time_support_end_s': float(scan.time_s[-1])} for di, channel in ordered]
    physical_count = sum(r['physical_track_trials'] for r in per_drift); evaluated = int(finite.sum())
    coverage = {'definition': 'nearest-channel linear path plus complete boxcar at every stored integration',
                'physical_track_trials': physical_count, 'evaluated_track_trials': evaluated,
                'masked_track_trials': sum(r['masked_track_trials'] for r in per_drift),
                'unscorable_track_trials': sum(r['unscorable_track_trials'] for r in per_drift),
                'physical_fraction_evaluated': evaluated/physical_count if physical_count else None,
                'above_threshold_cells': int(np.count_nonzero(finite & (scores >= config.score_threshold))),
                'local_maximum_hits': len(hits), 'candidate_cap': None, 'catalogue_truncated': False,
                'sample_exposure_s': nt*scan.dt, 'usable_time_bandwidth_hz_s': int(scan.usable.sum())*scan.dt*scan.df,
                'scan_gaps_counted_as_exposure': False, 'per_drift': per_drift,
                'frequency_reference': 'midpoint of first stored integration; time_s remains integration-start metadata',
                'score_definition': 'whole-valid-profile per-drift median/MAD track-power standardization; descriptive, not false-alarm probability'}
    assert physical_count == evaluated+coverage['masked_track_trials']+coverage['unscorable_track_trials']
    return SearchResult(scan, config, drifts, scores, hits, coverage, tiles)
