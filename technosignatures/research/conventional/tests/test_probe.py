"""Fake HDF5 bytes test metadata validation, never astronomical evidence."""
import h5py
import numpy as np
import pytest

from research.conventional.probe_cohort import probe


@pytest.mark.parametrize('bad_header', [False, True])
def test_header_probe_validates_pointing_time_shape_without_spectral_reads(tmp_path, monkeypatch, bad_header):
    payloads, rows = {}, []
    for i in range(6):
        file = tmp_path/f'fake{i}.h5'
        role_on = i % 2 == 0
        name, ra = ('A', 30.) if role_on else (f'A_OFF_{i}', 33.)
        mjd = 59000+i*50/86400
        with h5py.File(file, 'w') as f:
            d = f.create_dataset('data', data=np.zeros((16, 1, 16), dtype=np.float32))
            for k, v in dict(source_name=name.lower(), src_raj=ra/15, src_dej=0., tstart=mjd+(1 if bad_header and i == 3 else 0),
                             tsamp=1., nchans=16, fch1=6000., foff=-1e-6, nbits=32, telescope_id=6).items(): d.attrs[k] = v
        url = f'https://example.invalid/fake{i}.h5'
        payloads[url] = file.read_bytes()
        rows.append({'id': i, 'url': url, 'target': name, 'ra': ra, 'decl': 0., 'mjd': mjd, 'size': len(payloads[url]), 'md5sum': 'unit_test_unverified'})
    class FakeSource:
        def __init__(self, url, size, persistent=False):
            self.payload = payloads[url]; self.etag = 'unit_test_etag'; self.requests = []; self.failures = []
        def __call__(self, start, end):
            self.requests.append({'start': start, 'end': end})
            return self.payload[start:end+1]
    monkeypatch.setattr('research.conventional.probe_cohort.HTTPRangeSource', FakeSource)
    frame = {'rows': rows, 'cadences': [{'cadence_id': 'synthetic_metadata', 'archive_ids': list(range(6))}],
             'development_access_sample': [{'cadence_id': 'synthetic_metadata', 'sampling_weight': 1.}]}
    result = probe(frame)
    assert result['actual_cadence_headers_validated'] is (not bad_header)
    assert not result['spectral_samples_acquired'] and not result['representative_sensitivity_ready']
    assert result['range_bytes_accessed'] <= result['max_total_byte_budget']
