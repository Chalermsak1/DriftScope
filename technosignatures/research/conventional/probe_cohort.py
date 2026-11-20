"""Bounded header-only source check of a preselected metadata cadence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np

from research.pilot.range_access import BoundedRangeReader, HTTPRangeSource
from research.pilot.observations import plain, separation_deg
from .cohort import propose_metadata_cadences, components, readiness, sample_components


def refine_frame(path):
    source = json.loads(Path(path).read_text())
    rejected = []
    records = propose_metadata_cadences(source['rows'], rejected)
    return {'parent_frame_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'rows': source['rows'], 'cadences': records, 'linkage': components(records),
            'selection_amendment': 'Development corrections: exclude explicit _OFF primary names, link coordinate aliases, and enforce the existing 1-arcsec ON / 1-arcmin OFF geometry in the metadata frame. Added metadata geometry after the initial header-only probe failed ON agreement; no waveform or sensitivity outcome informed selection.',
            'rejected_metadata_sequences': rejected,
            'pointing_tolerance_limit': '1 arcsec is the inherited conservative engineering criterion, not a receiver-calibrated beam-response or pointing-accuracy requirement. Assess its suitability before freezing a scientific cohort; failed proposals remain in the audit.',
            'frame_complete': source['frame_complete_with_respect_to_unsaturated_api_queries'],
            'readiness': readiness(records, source['frame_complete_with_respect_to_unsaturated_api_queries']),
            'development_access_sample': sample_components(records, 4, source['config']['seed']) if records else []}


def probe(frame, max_bytes_per_file=8*1024**2):
    if not frame['development_access_sample']: raise ValueError('No preselected metadata cadence')
    selected = frame['development_access_sample'][0]
    cadence = next(c for c in frame['cadences'] if c['cadence_id'] == selected['cadence_id'])
    rows = {r['id']: r for r in frame['rows']}
    records = []
    for index, archive_id in enumerate(cadence['archive_ids']):
        row = rows[archive_id]
        source = HTTPRangeSource(row['url'], row['size'], persistent=True)
        def fetch(lo, hi):
            value = source(lo, hi)
            if not source.etag: raise ValueError('Archive omitted ETag; cannot validate entity stability')
            return value
        reader = BoundedRangeReader(row['size'], fetch, block_bytes=65536, max_bytes=max_bytes_per_file)
        record = {'archive_id': archive_id, 'url': row['url'], 'index_mjd': row['mjd'], 'full_file_bytes': row['size'],
                  'archive_md5_not_verified': row['md5sum'], 'whole_file_checksum_verified': False}
        try:
            with h5py.File(reader, 'r') as handle:
                dataset = handle['data']; header = plain(dict(dataset.attrs))
                keep = ['source_name', 'src_raj', 'src_dej', 'tstart', 'tsamp', 'nchans', 'fch1', 'foff', 'nbits', 'telescope_id']
                header = {k: header[k] for k in keep}
                checks = {'target_name_casefolded': header['source_name'].strip().casefold() == row['target'].strip().casefold(),
                          'index_time_within_1_1_seconds': abs(header['tstart']-row['mjd'])*86400 <= 1.1,
                          'pointing_within_1_arcsec': separation_deg(header['src_raj']*15, header['src_dej'], row['ra'], row['decl']) <= 1/3600,
                          'GBT': header['telescope_id'] == 6,
                          'shape_channels_match': dataset.ndim == 3 and dataset.shape[-1] == header['nchans'] and dataset.shape[1] == 1,
                          'positive_time_resolution': header['tsamp'] > 0,
                          'negative_channel_spacing': header['foff'] < 0}
                record.update({'header': header, 'shape': list(dataset.shape), 'dtype': str(dataset.dtype),
                               'chunks': list(dataset.chunks) if dataset.chunks else None,
                               'checks': checks, 'header_checks_passed': all(checks.values())})
        except Exception as exc:
            record.update({'failure_type': type(exc).__name__, 'failure': str(exc), 'header_checks_passed': False})
        record.update({'range_bytes_accessed': reader.fetched_bytes, 'http_requests': source.requests,
                       'byte_budget': max_bytes_per_file, 'http_failures': source.failures})
        records.append(record)
        print(f"Cohort header {index+1}/6: {archive_id}, pass={record['header_checks_passed']}, bytes={reader.fetched_bytes}", flush=True)
    complete = all(r['header_checks_passed'] for r in records)
    cadence_checks = {}
    if complete:
        headers = [r['header'] for r in records]
        cadence_checks['nonoverlapping_actual_integrations'] = all((b['tstart']-a['header']['tstart'])*86400 >= a['shape'][0]*a['header']['tsamp']-0.001 for a, b in zip(records, headers[1:]))
        cadence_checks['same_lattice_and_resolution'] = all(all(h[k] == headers[0][k] for k in ['nchans', 'fch1', 'foff', 'tsamp']) for h in headers)
        cadence_checks['on_pointings_agree'] = all(separation_deg(h['src_raj']*15, h['src_dej'], headers[0]['src_raj']*15, headers[0]['src_dej']) <= 1/3600 for h in headers[::2])
        cadence_checks['off_pointings_distinct'] = all(separation_deg(h['src_raj']*15, h['src_dej'], headers[0]['src_raj']*15, headers[0]['src_dej']) > 1/60 for h in headers[1::2])
    return {'utc': datetime.now(timezone.utc).isoformat(), 'selection': selected, 'cadence_id': cadence['cadence_id'],
            'records': records, 'all_six_header_checks_passed': complete, 'cadence_checks': cadence_checks,
            'actual_cadence_headers_validated': complete and all(cadence_checks.values()),
            'range_bytes_accessed': sum(r['range_bytes_accessed'] for r in records),
            'max_total_byte_budget': 6*max_bytes_per_file, 'spectral_samples_acquired': False,
            'target_identifier_matching': 'trim whitespace and casefold only; original names preserved, pointing agreement independently required',
            'representative_sensitivity_ready': False,
            'limitation': 'Header-only access feasibility on one preselected candidate-independent archive proposal; no spectral-data or receiver-hardware validation and no sensitivity measurement.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frame', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--metadata-only', action='store_true')
    args = p.parse_args()
    frame = refine_frame(args.frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.metadata_only:
        result = frame
    else:
        result = probe(frame)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'records', 'rows', 'cadences', 'linkage'}}, indent=2))
    if not args.metadata_only and not result['actual_cadence_headers_validated']: raise SystemExit(1)


if __name__ == '__main__': main()
