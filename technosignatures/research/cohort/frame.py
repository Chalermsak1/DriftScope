"""Freeze a detector-independent sampling frame before spectral access."""
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from astropy.time import Time
import numpy as np

from research.conventional.archive import collect_frame
from research.conventional.cohort import components
from research.pilot.observations import separation_deg

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.part')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')
    temporary.replace(path)


def assemble(rows, config, center_filter=True):
    streams = defaultdict(list)
    excluded, records = [], []
    on_limit = config['on_tolerance_fwhm_fraction']*config['beam_fwhm_arcsec_times_ghz']/(config['frequency_band_hz'][1]/1e9)
    off_limit = config['off_min_fwhm_multiple']*config['beam_fwhm_arcsec_times_ghz']/(config['frequency_band_hz'][0]/1e9)
    for row in rows:
        if row.get('telescope') != 'GBT' or not row.get('url', '').endswith(('.gpuspec.0000.h5', '.rawspec.0000.h5')): continue
        if center_filter and not config['frequency_band_hz'][0]/1e6 <= float(row['center_freq']) <= config['frequency_band_hz'][1]/1e6:
            excluded.append({'archive_ids': [row['id']], 'reasons': ['product_center_outside_declared_spectral_regime']}); continue
        sessions = [s for s in PurePosixPath(urlparse(row['url']).path).parts if s.startswith('AGBT')]
        if not sessions:
            # A republished campaign without original session IDs is one
            # conservative linkage unit, never one independent group per tile.
            parts = PurePosixPath(urlparse(row['url']).path).parts
            if 'bl_tess' in parts: sessions = ['release_campaign_bl_tess_C']
            else:
                excluded.append({'archive_ids': [row['id']], 'reasons': ['unknown_acquisition_session']}); continue
        streams[(sessions[0], float(row['center_freq']))].append(row)
    for (session, center), values in sorted(streams.items()):
        unique = {}
        for row in sorted(values, key=lambda r: r['id']):
            key = (row['target'].strip().casefold(), float(row['mjd']))
            if key in unique:
                excluded.append({'archive_ids': [row['id']], 'reasons': ['duplicate_product_at_same_target_and_time']})
            else: unique[key] = row
        ordered = sorted(unique.values(), key=lambda r: (r['mjd'], r['id']))
        for i in range(len(ordered)-5):
            scans = ordered[i:i+6]; target = scans[0]['target'].strip().casefold()
            if any(s['target'].strip().casefold() != target for s in scans[::2]): continue
            if any(s['target'].strip().casefold() == target for s in scans[1::2]): continue
            gaps = np.diff([r['mjd'] for r in scans])*86400
            on_sep = [separation_deg(a['ra'], a['decl'], b['ra'], b['decl'])*3600 for a in scans[::2] for b in scans[::2]]
            off_sep = [separation_deg(a['ra'], a['decl'], b['ra'], b['decl'])*3600 for a in scans[::2] for b in scans[1::2]]
            reasons = []
            if target.endswith('_off'): reasons.append('explicit_off_primary')
            if np.any(gaps <= 0) or np.any(gaps > 1800): reasons.append('nonchronological_or_excessive_scan_gap')
            if max(on_sep) > on_limit: reasons.append('on_pairwise_pointing_exceeds_beam_fraction')
            if min(off_sep) < off_limit: reasons.append('off_pointing_inside_declared_beam_separation')
            evidence = {'archive_ids': [r['id'] for r in scans], 'target': scans[0]['target'],
                        'max_pairwise_on_separation_arcsec': max(on_sep), 'min_on_off_separation_arcsec': min(off_sep)}
            if reasons:
                excluded.append({**evidence, 'reasons': reasons}); continue
            records.append({**evidence, 'cadence_id': 'cohort_'+'_'.join(str(r['id']) for r in scans),
                            'target_ids': [target], 'session_ids': [session],
                            'raw_ids': [r['url'].split('.gpuspec.')[0].split('.rawspec.')[0] for r in scans]
                                       +[f"GBT_acquisition_{float(r['mjd'])*86400:.0f}_{r['target'].strip().casefold()}" for r in scans],
                            'on_pointings': [{'ra_deg': r['ra'], 'dec_deg': r['decl']} for r in scans[::2]],
                            'candidate_selected': False, 'headers_validated': False, 'samples_acquired_and_verified': False,
                            'receiver_verified': False, 'receiver': 'GBT_C_spectral_regime_hardware_unverified',
                            'center_frequency_mhz': center, 'full_original_bytes': sum(r['size'] for r in scans)})
    return records, excluded, {'on_max_pairwise_arcsec': on_limit, 'off_min_pairwise_arcsec': off_limit}


def freeze_selection(rows, config, frame_complete, input_hashes):
    records, excluded, geometry = assemble(rows, config)
    # Determine dependencies on the PARENT catalogue. Removing an out-of-band
    # product must not sever an acquisition/target bridge and invent independence.
    parent_records, _, _ = assemble(rows, config, center_filter=False)
    parent_graph = components(parent_records)
    eligible_ids = {r['cadence_id'] for r in records}
    groups = []
    for group in parent_graph['components']:
        eligible = sorted(set(group['cadence_ids']) & eligible_ids)
        if eligible: groups.append({**group, 'cadence_ids': eligible, 'parent_cadence_ids': group['cadence_ids']})
    graph = {'components': groups, 'component_count': len(groups), 'cadence_count': len(records),
             'parent_cadence_count': len(parent_records), 'edges': parent_graph['edges'],
             'dependency_links_computed_before_frequency_eligibility_filter': True}
    rng = np.random.default_rng(config['seed'])
    permutation = rng.permutation(len(graph['components'])).tolist()
    chosen_count = min(config['sampling_components'], len(permutation))
    selections = []
    offset = int(rng.integers(3))
    for position, index in enumerate(permutation[:chosen_count]):
        group = graph['components'][index]
        cadence_id = group['cadence_ids'][int(rng.integers(len(group['cadence_ids'])))]
        stratum = (position+offset) % 3
        low, high = config['frequency_band_hz']
        width = (high-low)/3
        frequency = float(rng.uniform(low+stratum*width+4096, low+(stratum+1)*width-4096))
        pi = (chosen_count/len(permutation))/len(group['cadence_ids'])
        selections.append({'cadence_id': cadence_id, 'component_id': group['component_id'],
                           'component_inclusion_probability': chosen_count/len(permutation),
                           'conditional_cadence_probability': 1/len(group['cadence_ids']),
                           'cadence_inclusion_probability': pi, 'sampling_weight': 1/pi,
                           'frequency_stratum': stratum, 'requested_tile_center_hz': frequency,
                           'frequency_stratum_u': float(rng.random()), 'frequency_within_stratum_u': float(rng.random()),
                           'frequency_stratum_marginal_probability': 1/3,
                           'tile_channels': config['tile_channels'], 'partition': 'development'})
    return {'version': config['version'], 'frozen_at_utc': datetime.now(timezone.utc).isoformat(), 'config': config,
            'input_frame_sha256': input_hashes, 'rows': sorted(rows, key=lambda r: r['id']), 'cadences': records,
            'rejected_sequences': excluded, 'geometry': geometry, 'linkage': graph, 'selection': selections,
            'linkage_parent_cadences': parent_records,
            'component_random_order': [graph['components'][i]['component_id'] for i in permutation],
            'metadata_api_frame_complete': frame_complete, 'sky_inventory_completeness_independently_verified': False,
            'selection_used_detector_or_injection_outcomes': False, 'spectral_samples_examined_before_selection': False,
            'main_60_component_gate_passed': False,
            'scope': 'Finite archive-index frame and prospective access/development sample. Inclusion weights do not represent transmitter prevalence.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=HERE/'configs/access.json')
    p.add_argument('--output', type=Path, default=HERE/'evidence/selection.json')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--refresh-incomplete', action='store_true')
    args = p.parse_args(); config = json.loads(args.config.read_text())
    if args.output.exists(): raise FileExistsError('Selection already frozen; use a new output file')
    rows, hashes = {}, {}; complete = True
    for year in config['years']:
        path = HERE/f'evidence/frames/{year}.json'
        if path.exists() and args.refresh_incomplete:
            old = json.loads(path.read_text())
            if not old['frame_complete_with_respect_to_unsaturated_api_queries']:
                saved = path.parent/'attempts'/f'{year}-{digest(path)[:16]}.json'
                write(saved, old); path.unlink()
        if not path.exists():
            if args.offline: raise FileNotFoundError(path)
            query = {**config['archive_query'], 'start_mjd': float(Time(f'{year}-01-01').mjd),
                     'stop_mjd': float(Time(f'{year+1}-01-01').mjd), 'seed': config['seed']}
            frame = collect_frame(query); write(path, frame)
        frame = json.loads(path.read_text()); hashes[str(year)] = digest(path)
        complete &= frame['frame_complete_with_respect_to_unsaturated_api_queries']
        for row in frame['rows']:
            if row['id'] in rows and rows[row['id']] != row: raise ValueError('Conflicting archive index rows')
            rows[row['id']] = row
        print(f"Metadata {year}: {len(frame['rows'])} rows; complete={frame['frame_complete_with_respect_to_unsaturated_api_queries']}", flush=True)
    result = freeze_selection(list(rows.values()), config, complete, hashes)
    write(args.output, result)
    print(json.dumps({'frame_rows': len(rows), 'cadence_proposals': len(result['cadences']),
                      'components': result['linkage']['component_count'], 'selected': len(result['selection']), 'metadata_complete': complete}, indent=2))


if __name__ == '__main__': main()
