"""Extract all integrations of prospective narrowband tiles from original HDF5."""
import argparse
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import time
import uuid
import multiprocessing
import signal
from urllib.parse import urlsplit, urlunsplit

import h5py
import hdf5plugin
import numpy as np

from research.pilot.observations import plain, separation_deg
from research.pilot.range_access import BoundedRangeReader, exclusive_transfer_lock
from research.conventional.data import Scan, Cadence
from .frame import HERE, write, digest
from .transport import TransferBudget, FileTransferBudget, VerifiedRangeCache, CoalescedRangeReader


def array_hash(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def https_url(url):
    parts = urlsplit(url)
    if parts.scheme not in {'http', 'https'} or parts.hostname != 'bldata.berkeley.edu':
        raise ValueError('Unexpected observational archive origin')
    return urlunsplit(('https', parts.netloc, parts.path, parts.query, ''))


def plan_frequency(frame, selection_path, directory, budget, offline=False):
    """Resolve frozen random variates using HEADERS ONLY, before any data read."""
    path = Path(directory)/'frequency_plan.json'
    if path.exists():
        plan = json.loads(path.read_text())
        if plan['selection_sha256'] != digest(selection_path): raise ValueError('Frequency plan belongs to another frozen selection')
        return plan, 0
    if offline: raise FileNotFoundError('Frozen header-based frequency plan missing')
    config = frame['config']; rows = {r['id']: r for r in frame['rows']}
    definitions = {c['cadence_id']: c for c in frame['cadences']}
    records = {}; network_bytes = 0
    for selected in frame['selection']:
        for archive_id in definitions[selected['cadence_id']]['archive_ids']:
            row = rows[archive_id]
            cache = VerifiedRangeCache(Path(directory)/'range_cache'/str(archive_id), archive_id, https_url(row['url']), row['size'], budget)
            reader = BoundedRangeReader(row['size'], cache.fetch, config['cache_block_bytes'], 8*1024**2)
            try:
                with h5py.File(reader, 'r') as handle:
                    dataset = handle['data']
                    keys = ['source_name', 'src_raj', 'src_dej', 'tstart', 'tsamp', 'nchans', 'fch1', 'foff', 'nbits', 'telescope_id']
                    header = {k: plain(dataset.attrs[k]) for k in keys}
                    if not np.isfinite(header['fch1']) or not -4e-6 <= header['foff'] < 0:
                        raise ValueError('Frequency plan requires validated descending high-resolution header')
                    records[str(archive_id)] = {'header': header, 'shape': list(dataset.shape), 'etag': cache.source.etag or cache.index['etag'],
                                                'status': 'header_read', 'http_requests': cache.source.requests}
            except Exception as exc:
                records[str(archive_id)] = {'status': 'failed', 'failure_type': type(exc).__name__, 'failure': str(exc)}
            network_bytes += cache.source.successful_payload_bytes
            print(f"Header plan {archive_id}: {records[str(archive_id)]['status']}", flush=True)
    selections = []
    for selected in frame['selection']:
        ids = definitions[selected['cadence_id']]['archive_ids']
        current = {**selected}
        if any(records[str(i)]['status'] != 'header_read' for i in ids):
            selections.append({**current, 'frequency_plan_status': 'failed', 'failure': 'one_or_more_headers_unavailable'}); continue
        headers = [records[str(i)]['header'] for i in ids]
        low, high = config['frequency_band_hz']
        low = max(low, max((h['fch1']+h['foff']*(h['nchans']-1))*1e6 for h in headers))
        high = min(high, min(h['fch1']*1e6 for h in headers))
        half_width = (selected['tile_channels']+2)*max(abs(h['foff'])*1e6 for h in headers)/2
        edges = np.linspace(*config['frequency_band_hz'], 4)
        intervals = [(i, max(low, edges[i])+half_width, min(high, edges[i+1])-half_width) for i in range(3)]
        intervals = [(i, a, b) for i, a, b in intervals if b > a]
        if not intervals:
            selections.append({**current, 'frequency_plan_status': 'failed', 'failure': 'no_common_available_analysis_band'}); continue
        k = min(len(intervals)-1, int(selected['frequency_stratum_u']*len(intervals)))
        stratum, lo, hi = intervals[k]
        actual = lo+selected['frequency_within_stratum_u']*(hi-lo)
        selections.append({**current, 'provisional_tile_center_hz': selected['requested_tile_center_hz'],
                           'requested_tile_center_hz': actual, 'frequency_stratum': stratum,
                           'available_frequency_strata': [i for i, _, _ in intervals],
                           'conditional_frequency_density_per_hz': 1/(len(intervals)*(hi-lo)),
                           'common_source_band_hz': [low, high], 'frequency_plan_status': 'frozen_before_spectral_read'})
    plan = {'selection_sha256': digest(selection_path), 'selection': selections, 'headers': records,
            'headers_only_before_spectral_access': True, 'random_variates_frozen_in_selection': True,
            'source_header_network_bytes_this_execution': network_bytes,
            'definition': 'Uniform available frequency stratum, then uniform tile-center interval, conditional on header coverage only.'}
    write(path, plan)
    return plan, network_bytes


def extract_file(row, selection, scan_index, config, directory, budget, offline=False):
    start = time.perf_counter(); directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    record = {'archive_id': row['id'], 'scan_index': scan_index, 'cadence_id': selection['cadence_id'],
              'component_id': selection['component_id'], 'archive_index_row': row, 'transport_url': https_url(row['url']),
              'whole_file_checksum_verified': False, 'offline': offline, 'status': 'incomplete'}
    cache = VerifiedRangeCache(directory/'range_cache'/str(row['id']), row['id'], record['transport_url'],
                               row['size'], budget, offline)
    reader = CoalescedRangeReader(row['size'], cache, config['cache_block_bytes'], config['max_bytes_per_file'],
                                  config['max_prefetch_request_bytes'], config['range_workers'])
    try:
        with h5py.File(reader, 'r') as handle:
            dataset = handle['data']
            keys = ['source_name', 'src_raj', 'src_dej', 'tstart', 'tsamp', 'nchans', 'fch1', 'foff', 'nbits', 'telescope_id']
            header = {k: plain(dataset.attrs[k]) for k in keys}
            checks = {'target_identifier': header['source_name'].strip().casefold() == row['target'].strip().casefold(),
                      'time_agreement': abs(header['tstart']-row['mjd'])*86400 <= 1.1,
                      'pointing_agreement': separation_deg(header['src_raj']*15, header['src_dej'], row['ra'], row['decl'])*3600 <= 1,
                      'GBT': header['telescope_id'] == 6, 'single_power_stream': dataset.ndim == 3 and dataset.shape[1] == 1,
                      'shape_matches_header': dataset.shape[-1] == header['nchans'],
                      'float32_power': dataset.dtype == np.dtype('float32'),
                      'high_spectral_resolution': 0 < abs(header['foff'])*1e6 <= 4,
                      'descending_frequency': header['foff'] < 0, 'positive_integration': header['tsamp'] > 0}
            record.update({'header': header, 'source_shape': list(dataset.shape), 'header_checks': checks,
                           'source_chunks': list(dataset.chunks) if dataset.chunks else None})
            if not all(checks.values()): raise ValueError(f'Original header validation failed: {checks}')
            if not dataset.chunks or dataset.chunks[1] != 1: raise ValueError('Unsupported unchunked/multi-stream source; no full-file fallback')
            center = int(np.rint((selection['requested_tile_center_hz']/1e6-header['fch1'])/header['foff']))
            first = center-selection['tile_channels']//2; stop = first+selection['tile_channels']
            if not 0 <= first < stop <= dataset.shape[2]: raise ValueError('Preselected tile lies outside source spectrum')
            frequency = (header['fch1']+header['foff']*np.arange(first, stop))[::-1]*1e6
            low, high = config['frequency_band_hz']
            if frequency[0] < low or frequency[-1] > high: raise ValueError('Tile outside the declared C-band analysis interval')
            # Native hyperslab selection uses the dataset index without the
            # costly whole-index enumeration observed in chunk-info APIs on
            # these original files. Range budgets still apply to EVERY read.
            print(f"Source {row['id']}: reading bounded hyperslab", flush=True)
            record['read_strategy'] = 'Native HDF5 hyperslabs with coalesced verified HTTP block reads'
            # All stored time integrations, never a selected crop of successful scans.
            raw = np.asarray(dataset[:, 0, first:stop])
            # Zero recorded powers cannot establish whether a sample is a
            # measured zero or an HDF5/instrument fill. Mask conservatively,
            # preserve the original array and retain that loss in denominators.
            usable = np.isfinite(raw) & (raw != 0)
            power, usable = raw[:, ::-1].copy(), usable[:, ::-1].copy()
            times = np.arange(raw.shape[0])*header['tsamp']
            # Independent hyperslab concatenation detects selection/order errors.
            middle = first+(stop-first)//2
            joined = np.concatenate([dataset[:, 0, first:middle], dataset[:, 0, middle:stop]], axis=1)
            if not np.array_equal(joined, raw, equal_nan=True): raise AssertionError('Independent HDF5 hyperslabs disagree')
            destination = directory/('offline_tiles' if offline else 'tiles')/f"{row['id']}.npz"
            destination.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(destination, power_ascending=power, frequency_hz=frequency, time_s=times, usable=usable)
            hashes = {k: array_hash(a) for k, a in [('power', power), ('frequency', frequency), ('time', times), ('usable', usable)]}
            record.update({'status': 'acquired', 'original_channel_slice_half_open': [first, stop], 'excerpt_shape': list(power.shape),
                           'all_stored_time_integrations_extracted': True, 'chunk_allocation_metadata_verified': False,
                           'zero_power_samples_conservatively_masked': int(np.count_nonzero(raw == 0)),
                           'mask_definition': 'finite nonzero recorded power; zero measurement versus fill is unresolved, source values unchanged',
                           'usable_sample_count': int(usable.sum()), 'sample_count': int(usable.size),
                           'usable_fraction': float(usable.mean()), 'scientific_array_sha256': hashes,
                           'tile_relative_path': str(destination.relative_to(directory)), 'tile_file_sha256': digest(destination),
                           'independent_hyperslab_check_passed': True})
    except Exception as exc:
        record.update({'failure_type': type(exc).__name__, 'failure': str(exc), 'status': 'failed'})
    record.update({'range_bytes_accessed': reader.fetched_bytes, 'successful_network_payload_bytes': cache.source.successful_payload_bytes,
                   'http_requests': cache.source.requests, 'http_failures': cache.source.failures,
                   'verified_cached_reads': cache.verified_hits, 'cache_index_sha256': digest(cache.path) if cache.path.exists() else None,
                   'wall_s': time.perf_counter()-start})
    print(f"Source {row['id']}: {record['status']}, {reader.fetched_bytes/1024**2:.1f} MiB accessed, {cache.source.successful_payload_bytes/1024**2:.1f} MiB new", flush=True)
    return record


def validate_cadence(records, frame):
    if len(records) != 6 or any(r['status'] != 'acquired' for r in records):
        return {'passed': False, 'reason': 'one_or_more_source_files_unavailable_or_invalid'}
    headers = [r['header'] for r in records]; config = frame['config']
    on_limit, off_limit = frame['geometry']['on_max_pairwise_arcsec'], frame['geometry']['off_min_pairwise_arcsec']
    ons = headers[::2]; offs = headers[1::2]
    checks = {'same_on_identifiers': len({h['source_name'].strip().casefold() for h in ons}) == 1,
              'on_geometry': all(separation_deg(a['src_raj']*15, a['src_dej'], b['src_raj']*15, b['src_dej'])*3600 <= on_limit for a in ons for b in ons),
              'off_geometry': all(separation_deg(a['src_raj']*15, a['src_dej'], b['src_raj']*15, b['src_dej'])*3600 >= off_limit for a in ons for b in offs),
              'nonoverlapping_integrations': all((b['header']['tstart']-a['header']['tstart'])*86400 >= a['source_shape'][0]*a['header']['tsamp']-0.001 for a, b in zip(records, records[1:])),
              'same_frequency_grid': all(r['scientific_array_sha256']['frequency'] == records[0]['scientific_array_sha256']['frequency'] for r in records),
              'same_time_resolution': all(h['tsamp'] == headers[0]['tsamp'] for h in headers),
              'every_scan_has_recorded_samples': all(r['usable_sample_count'] > 0 for r in records)}
    return {'passed': all(checks.values()), 'checks': checks,
            'represented_exposure_s': sum(r['excerpt_shape'][0]*r['header']['tsamp'] for r in records),
            'on_recorded_sample_count': sum(r['usable_sample_count'] for r in records[::2]),
            'total_recorded_sample_count': sum(r['usable_sample_count'] for r in records)}


def _process_task(arguments):
    row, selected, i, config, directory, ledger, offline = arguments
    try:
        if selected['frequency_plan_status'] != 'frozen_before_spectral_read': raise ValueError(selected['failure'])
        with exclusive_transfer_lock(Path(directory)/'range_cache'/str(row['id'])/'source.lock'):
            result = extract_file(row, selected, i, config, directory, FileTransferBudget(ledger), offline)
    except Exception as exc:
        result = {'archive_id': row['id'], 'cadence_id': selected['cadence_id'], 'component_id': selected['component_id'],
                  'scan_index': i, 'status': 'failed', 'failure_type': type(exc).__name__, 'failure': str(exc),
                  'successful_network_payload_bytes': 0}
    write(Path(directory)/'file_records'/f"{row['id']}.json", result)
    return result


def acquire(selection_path, directory=HERE/'data', offline=False, executor='threads', network_workers=None, request_bytes=None):
    frame = json.loads(Path(selection_path).read_text()); config = frame['config']
    config = dict(config)
    if network_workers is not None:
        if not 1 <= network_workers <= 8: raise ValueError('Network worker bound is 1..8 per source')
        config['range_workers'] = network_workers
    if request_bytes is not None:
        if not config['cache_block_bytes'] <= request_bytes <= 8*1024**2: raise ValueError('Invalid coalesced request size')
        config['max_prefetch_request_bytes'] = request_bytes
    if len(frame['selection'])*6 > config['max_spectral_file_count']: raise ValueError('Frozen batch exceeds file-count budget')
    rows = {r['id']: r for r in frame['rows']}; cadences = {c['cadence_id']: c for c in frame['cadences']}
    ledger = Path(directory)/'transfer_runs'/f'{uuid.uuid4().hex}.json'
    budget = FileTransferBudget.create(ledger, 0 if offline else config['max_batch_network_bytes'], config['max_bytes_per_file'])
    with exclusive_transfer_lock(Path(directory)/'acquisition.lock'):
        plan, header_bytes = plan_frequency(frame, selection_path, directory, budget, offline)
        tasks = [(rows[archive_id], selected, i) for selected in plan['selection']
                 for i, archive_id in enumerate(cadences[selected['cadence_id']]['archive_ids'])]
        def one(task):
            row, selected, i = task
            try:
                if selected['frequency_plan_status'] != 'frozen_before_spectral_read': raise ValueError(selected['failure'])
                return extract_file(row, selected, i, config, directory, budget, offline)
            except Exception as exc:
                return {'archive_id': row['id'], 'cadence_id': selected['cadence_id'], 'component_id': selected['component_id'],
                        'scan_index': i, 'status': 'failed', 'failure_type': type(exc).__name__, 'failure': str(exc),
                        'successful_network_payload_bytes': 0}
        if executor == 'processes':
            arguments = [(row, selected, i, config, str(directory), str(ledger), offline) for row, selected, i in tasks]
            with ProcessPoolExecutor(max_workers=config['scan_workers'], mp_context=multiprocessing.get_context('spawn')) as pool:
                try: records = list(pool.map(_process_task, arguments))
                except BaseException:
                    budget.cancel()
                    raise
        else:
            with ThreadPoolExecutor(max_workers=config['scan_workers']) as pool:
                records = list(pool.map(one, tasks))
    grouped = []
    for selected in plan['selection']:
        pieces = [r for r in records if r['cadence_id'] == selected['cadence_id']]
        grouped.append({'selection': selected, 'source_records': pieces, 'cadence_validation': validate_cadence(pieces, frame)})
    return {'selection_sha256': digest(selection_path), 'frequency_plan_sha256': digest(Path(directory)/'frequency_plan.json'),
            'frequency_plan': plan, 'offline': offline, 'cadences': grouped,
            'selected_cadences': len(frame['selection']), 'acquired_complete_cadences': sum(c['cadence_validation']['passed'] for c in grouped),
            'selected_components': len({s['component_id'] for s in frame['selection']}),
            'complete_acquired_components': len({c['selection']['component_id'] for c in grouped if c['cadence_validation']['passed']}),
            'files_attempted': len(records), 'files_acquired': sum(r['status'] == 'acquired' for r in records),
            'http_payload_bytes_reserved_including_retry_attempts': budget.reserved,
            'successful_network_payload_bytes': header_bytes+sum(r['successful_network_payload_bytes'] for r in records),
            'max_batch_network_bytes': config['max_batch_network_bytes'],
            'transport_runtime_settings': {'executor': executor, 'network_workers_per_source': config['range_workers'],
                                           'max_request_bytes': config['max_prefetch_request_bytes'],
                                           'shared_budget_ledger': str(ledger.relative_to(directory))},
            'main_60_component_gate_passed': False, 'receiver_hardware_identity_verified': False,
            'scope': 'Full stored time support within prospectively selected narrow frequency tiles; not full original bandwidth or a finalized representative-sensitivity study.'}


def load_cadence(record, directory=HERE/'data'):
    if not record['cadence_validation']['passed']: raise ValueError('Cannot load an incomplete/invalid cadence as valid observational evidence')
    selected = record['selection']; scans = []
    for r in record['source_records']:
        path = Path(directory)/r['tile_relative_path']
        if digest(path) != r['tile_file_sha256']: raise ValueError('Acquired tile checksum mismatch')
        with np.load(path, allow_pickle=False) as data:
            arrays = {k: data[k].copy() for k in data.files}
        for key, name in [('power_ascending', 'power'), ('frequency_hz', 'frequency'), ('time_s', 'time'), ('usable', 'usable')]:
            if array_hash(arrays[key]) != r['scientific_array_sha256'][name]: raise ValueError('Scientific tile hash mismatch')
        h = r['header']; i = r['scan_index']
        session = next(p for p in urlsplit(r['archive_index_row']['url']).path.split('/') if p.startswith('AGBT')) if '/pipeline/AGBT' in r['archive_index_row']['url'] else 'release_campaign_bl_tess_C'
        scans.append(Scan(f"{selected['cadence_id']}_scan_{i}", arrays['power_ascending'], arrays['frequency_hz'], arrays['time_s'],
                          h['tstart'], 'ON' if i % 2 == 0 else 'OFF', h['source_name'].strip().casefold(),
                          session, r['archive_index_row']['url'].split('.gpuspec.')[0].split('.rawspec.')[0],
                          'GBT_C_spectral_regime_hardware_unverified', arrays['usable'], h['src_raj']*15, h['src_dej']))
    return Cadence(selected['cadence_id'], tuple(scans), candidate_selected=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection', type=Path, default=HERE/'evidence/selection.json')
    p.add_argument('--output', type=Path)
    p.add_argument('--data', type=Path, default=HERE/'data')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--executor', choices=['threads', 'processes'], default='processes')
    p.add_argument('--network-workers', type=int, default=6)
    p.add_argument('--request-bytes', type=int, default=524288)
    args = p.parse_args(); target = args.output or HERE/'evidence'/('acquisition_offline.json' if args.offline else 'acquisition.json')
    def interrupted(signum, frame): raise KeyboardInterrupt('Acquisition cancellation requested')
    signal.signal(signal.SIGTERM, interrupted)
    result = acquire(args.selection, args.data, args.offline, args.executor, args.network_workers, args.request_bytes); write(target, result)
    print(json.dumps({k: v for k, v in result.items() if k != 'cadences'}, indent=2), flush=True)
    if result['acquired_complete_cadences'] != result['selected_cadences']: raise SystemExit(1)


if __name__ == '__main__': main()
