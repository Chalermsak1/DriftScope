import io
import json
from pathlib import Path

import pytest
import urllib3

from research.cohort.transport import StrictRangeSource, TransferBudget, VerifiedRangeCache, CoalescedRangeReader
from research.cohort.frame import assemble, freeze_selection, HERE


class Response:
    def __init__(self, url, payload, start, end, **overrides):
        self.url = url; self.status_code = overrides.get('status', 206)
        self.headers = {'Content-Range': f'bytes {start}-{end}/{len(payload)}', 'ETag': '"unit_test"', **overrides.get('headers', {})}
        self.raw = io.BytesIO(payload[start:end+1])
    def __enter__(self): return self
    def __exit__(self, *args): pass


def network(monkeypatch, payload=b'0123456789abcdef', **overrides):
    calls = []
    def get(self, url, headers, **kwargs):
        start, end = map(int, headers['Range'].removeprefix('bytes=').split('-'))
        calls.append((start, end))
        return Response(url, payload, start, end, **overrides)
    monkeypatch.setattr('requests.Session.get', get)
    return calls


def test_budget_is_atomic_and_counts_each_file():
    budget = TransferBudget(10, 6)
    budget.reserve('a', 4); budget.reserve('b', 4)
    with pytest.raises(ValueError): budget.reserve('a', 3)
    assert budget.reserved == 8 and budget.by_file['a'] == 4


@pytest.mark.parametrize('overrides', [{'status': 200}, {'headers': {'ETag': 'W/"weak"'}},
                                      {'headers': {'Content-Range': 'bytes 0-2/999'}},
                                      {'headers': {'Content-Encoding': 'gzip'}}])
def test_invalid_range_protocol_is_rejected(monkeypatch, overrides):
    network(monkeypatch, **overrides)
    source = StrictRangeSource('a', 'https://example.invalid/a', 16, TransferBudget(100, 100))
    with pytest.raises(ValueError): source(0, 3)


def test_entity_change_is_rejected(monkeypatch):
    network(monkeypatch)
    source = StrictRangeSource('a', 'https://example.invalid/a', 16, TransferBudget(100, 100), etag='"different"')
    with pytest.raises(ValueError, match='changed'): source(0, 3)


def test_stream_read_timeout_is_retried_and_budgeted(monkeypatch):
    attempts = []
    def get(self, url, headers, **kwargs):
        response = Response(url, b'0123456789abcdef', 0, 3)
        attempts.append(1)
        if len(attempts) == 1:
            class BrokenStream:
                def read(self, n): raise urllib3.exceptions.ReadTimeoutError(None, url, 'synthetic timeout')
            response.raw = BrokenStream()
        return response
    monkeypatch.setattr('requests.Session.get', get)
    budget = TransferBudget(20, 20)
    source = StrictRangeSource('a', 'https://example.invalid/a', 16, budget)
    assert source(0, 3) == b'0123'
    assert budget.reserved == 8 and len(source.failures) == 1


def test_verified_cache_subranges_and_network_disabled_replay(tmp_path, monkeypatch):
    calls = network(monkeypatch)
    cache = VerifiedRangeCache(tmp_path, 'a', 'https://example.invalid/a', 16, TransferBudget(100, 100))
    assert cache.fetch(0, 15) == b'0123456789abcdef'
    assert cache.fetch(3, 7) == b'34567' and len(calls) == 1
    def disabled(*args, **kwargs): raise AssertionError('HTTP attempted in offline replay')
    monkeypatch.setattr('requests.Session.get', disabled)
    replay = VerifiedRangeCache(tmp_path, 'a', 'https://example.invalid/a', 16, TransferBudget(0, 100), offline=True)
    assert replay.fetch(2, 5) == b'2345'


def test_adjacent_reads_coalesce_without_changing_bytes_or_budget(tmp_path, monkeypatch):
    calls = network(monkeypatch)
    cache = VerifiedRangeCache(tmp_path, 'a', 'https://example.invalid/a', 16, TransferBudget(32, 32))
    reader = CoalescedRangeReader(16, cache, 4, 16, 8, 2)
    assert reader.read(16) == b'0123456789abcdef'
    assert sorted(calls) == [(0, 7), (8, 15)] and reader.fetched_bytes == 16
    reader.seek(3); assert reader.read(5) == b'34567' and len(calls) == 2


def test_cache_corruption_and_unindexed_payload_are_not_accepted(tmp_path, monkeypatch):
    network(monkeypatch)
    cache = VerifiedRangeCache(tmp_path, 'a', 'https://example.invalid/a', 16, TransferBudget(100, 100))
    cache.fetch(0, 15)
    path = next(tmp_path.glob('*.bin')); path.write_bytes(b'x'*16)
    replay = VerifiedRangeCache(tmp_path, 'a', 'https://example.invalid/a', 16, TransferBudget(0, 100), offline=True)
    with pytest.raises(ValueError, match='checksum'): replay.fetch(0, 15)
    other = tmp_path/'other'; other.mkdir(); (other/'00000000000000-00000000000003.bin').write_bytes(b'0123')
    unknown = VerifiedRangeCache(other, 'a', 'https://example.invalid/a', 16, TransferBudget(0, 100), offline=True)
    with pytest.raises(ValueError, match='Unindexed'): unknown.fetch(0, 3)


def metadata_rows(offsets=(0., 4., 8.), suffix='rawspec', session='AGBT_TEST'):
    rows = []
    for i in range(6):
        on = i % 2 == 0
        rows.append({'id': i, 'target': 'A' if on else 'A_OFF', 'mjd': 59000+i/1000,
                     'ra': 30+offsets[i//2]/3600 if on else 32., 'decl': 0., 'center_freq': 6000.,
                     'url': f'https://bldata.berkeley.edu/pipeline/{session}/file{i}.{suffix}.0000.h5', 'size': 1000, 'telescope': 'GBT'})
    return rows


def config(): return json.loads((HERE/'configs/access.json').read_text())


def test_beam_relative_rule_and_new_product_preserve_realistic_pointing_variation():
    records, excluded, geometry = assemble(metadata_rows(), config())
    assert len(records) == 1 and not excluded
    assert geometry['on_max_pairwise_arcsec'] == pytest.approx(10.08)
    assert geometry['off_min_pairwise_arcsec'] == pytest.approx(504.)


def test_pairwise_on_check_cannot_hide_opposite_offsets():
    records, rejected, _ = assemble(metadata_rows((0., 8., -8.)), config())
    assert not records and 'on_pairwise_pointing_exceeds_beam_fraction' in rejected[0]['reasons']


def test_tess_release_is_one_conservative_component_and_selection_repeats():
    rows = metadata_rows()
    for row in rows: row['url'] = row['url'].replace('/pipeline/AGBT_TEST/', '/bl_tess/c_band/')
    first = freeze_selection(rows, config(), True, {})
    second = freeze_selection(rows, config(), True, {})
    assert first['selection'] == second['selection']
    assert first['linkage']['component_count'] == 1
    assert first['cadences'][0]['session_ids'] == ['release_campaign_bl_tess_C']
    assert not first['selection_used_detector_or_injection_outcomes']


def test_ineligible_bridge_must_not_split_independence_components():
    rows = []
    for block, (session, target, center, ra) in enumerate([('AGBT_A', 'A', 6000, 30), ('AGBT_A', 'B', 7900, 60), ('AGBT_B', 'B', 6000, 60)]):
        current = metadata_rows(offsets=(0, 0, 0), session=session)
        for i, row in enumerate(current):
            row.update(id=block*10+i, mjd=row['mjd']+block, center_freq=center,
                       target=target if i % 2 == 0 else target+'_OFF', ra=ra if i % 2 == 0 else ra+2)
        rows.extend(current)
    result = freeze_selection(rows, config(), True, {})
    assert len(result['cadences']) == 2 and len(result['linkage_parent_cadences']) == 3
    assert result['linkage']['component_count'] == 1
    assert len(result['selection']) == 1
