"""Synthetic HDF5 fixtures independently validate the observational adapter."""
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

from research.cohort.frame import HERE, write
from research.cohort.acquire import acquire, load_cadence
from research.cohort.verify import compare_acquisitions
from test_transport_frame import Response


@pytest.mark.parametrize('zero_sample', [False, True])
def test_complete_cadence_acquisition_and_offline_reconstruction(tmp_path, monkeypatch, zero_sample):
    config = json.loads((HERE/'configs/access.json').read_text())
    config.update(tile_channels=16, max_bytes_per_file=4*1024**2, max_batch_network_bytes=20*1024**2,
                  cache_block_bytes=1024, max_prefetch_request_bytes=4096)
    payloads, rows = {}, []
    originals = {}
    for i in range(6):
        target, ra = ('A', 30.) if i % 2 == 0 else ('A_OFF', 32.)
        filename = tmp_path/f'{i}.h5'; mjd = 59000+i*30/86400
        original = np.arange(4*128, dtype=np.float32).reshape(4, 1, 128)+1000+i
        if zero_sample: original[1, 0, 64] = 0
        with h5py.File(filename, 'w') as f:
            d = f.create_dataset('data', data=original, chunks=(1, 1, 32), compression='gzip')
            for k, v in dict(source_name=target, src_raj=ra/15, src_dej=0., tstart=mjd, tsamp=2., nchans=128,
                             fch1=6000., foff=-1e-6, nbits=32, telescope_id=6).items(): d.attrs[k] = v
        url = f'https://bldata.berkeley.edu/pipeline/AGBT_TEST/file{i}.rawspec.0000.h5'
        payloads[url] = filename.read_bytes(); originals[i] = original
        rows.append({'id': i, 'target': target, 'ra': ra, 'decl': 0., 'mjd': mjd, 'size': len(payloads[url]), 'url': url})
    calls = []
    def get(self, url, headers, **kwargs):
        a, b = map(int, headers['Range'].removeprefix('bytes=').split('-')); calls.append((url, a, b))
        return Response(url, payloads[url], a, b)
    monkeypatch.setattr('requests.Session.get', get)
    selected = {'cadence_id': 'synthetic_unit', 'component_id': 'synthetic_component', 'requested_tile_center_hz': 6e9,
                'tile_channels': 16, 'frequency_stratum_u': 0.4, 'frequency_within_stratum_u': 0.5, 'partition': 'development'}
    frame = {'config': config, 'rows': rows, 'selection': [selected],
             'cadences': [{'cadence_id': 'synthetic_unit', 'archive_ids': list(range(6))}],
             'geometry': {'on_max_pairwise_arcsec': 10.08, 'off_min_pairwise_arcsec': 504.}}
    selection_path = tmp_path/'selection.json'; write(selection_path, frame)
    directory = tmp_path/'download'
    online = acquire(selection_path, directory)
    assert online['acquired_complete_cadences'] == 1 and online['files_acquired'] == 6
    assert online['frequency_plan']['headers_only_before_spectral_access']
    for record in online['cadences'][0]['source_records']:
        a, b = record['original_channel_slice_half_open']
        with np.load(directory/record['tile_relative_path'], allow_pickle=False) as exported:
            np.testing.assert_array_equal(exported['power_ascending'], originals[record['archive_id']][:, 0, a:b][:, ::-1])
            if zero_sample: assert not exported['usable'][1, b-1-64]
    cadence = load_cadence(online['cadences'][0], directory)
    assert cadence.complete and not cadence.candidate_selected
    def disabled(*args, **kwargs): raise AssertionError('Offline acquisition attempted HTTP')
    monkeypatch.setattr('requests.Session.get', disabled)
    offline = acquire(selection_path, directory, offline=True)
    assert offline['successful_network_payload_bytes'] == 0 and offline['acquired_complete_cadences'] == 1
    a = online['cadences'][0]['source_records']; b = offline['cadences'][0]['source_records']
    assert all(x['scientific_array_sha256'] == y['scientific_array_sha256'] for x, y in zip(a, b))
    online_path, offline_path = tmp_path/'online.json', tmp_path/'offline.json'
    write(online_path, online); write(offline_path, offline)
    assert compare_acquisitions(online_path, offline_path)['all_checks_passed']
    offline['cadences'][0]['source_records'][0]['scientific_array_sha256']['power'] = 'corrupted_synthetic_fixture'
    write(offline_path, offline)
    with pytest.raises(AssertionError): compare_acquisitions(online_path, offline_path)
