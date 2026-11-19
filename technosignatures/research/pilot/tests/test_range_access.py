"""Offline HDF5 range-reader correctness and bounded-I/O invariants."""
import io
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from research.pilot.range_access import BoundedRangeReader,HTTPRangeSource,exclusive_transfer_lock


def test_extraction_lock_rejects_concurrent_writer_and_releases(tmp_path):
    path=tmp_path/"exclusive.lock"
    with exclusive_transfer_lock(path):
        with pytest.raises(RuntimeError,match="already running"):
            with exclusive_transfer_lock(path):pass
    with exclusive_transfer_lock(path):pass


def test_seek_read_cache_and_readinto():
    payload=bytes(range(200))
    calls=[]
    def fetch(lo,hi):calls.append((lo,hi));return payload[lo:hi+1]
    reader=BoundedRangeReader(len(payload),fetch,block_bytes=16,max_bytes=128)
    assert reader.read(5)==payload[:5]
    reader.seek(14)
    target=bytearray(10)
    assert reader.readinto(target)==10
    assert bytes(target)==payload[14:24]
    reader.seek(0)
    assert reader.read(24)==payload[:24]
    assert len(calls)==2
    reader.seek(-5,2)
    assert reader.read()==payload[-5:]
    assert reader.read(1)==b""


def test_range_budget_stops_fetch_before_excess():
    calls=[]
    def fetch(lo,hi):calls.append((lo,hi));return b"x"*(hi-lo+1)
    reader=BoundedRangeReader(1000,fetch,block_bytes=16,max_bytes=32)
    reader.read(32)
    with pytest.raises(ValueError,match="budget"):
        reader.read(1)
    assert len(calls)==2


def test_bad_response_length_is_rejected():
    reader=BoundedRangeReader(100,lambda a,b:b"short",block_bytes=16,max_bytes=32)
    with pytest.raises(ValueError,match="length"):
        reader.read(1)


def test_hdf5_metadata_and_excerpt_match_in_memory_reference():
    buffer=io.BytesIO()
    expected=np.arange(160,dtype=np.float32).reshape(10,16)
    with h5py.File(buffer,"w") as h:
        ds=h.create_dataset("data",data=expected,chunks=(2,16),compression="gzip")
        ds.attrs["tsamp"]=1.25
    payload=buffer.getvalue()
    reader=BoundedRangeReader(len(payload),lambda lo,hi:payload[lo:hi+1],block_bytes=256,max_bytes=65536)
    with h5py.File(reader,"r") as h:
        assert h["data"].shape==(10,16)
        assert h["data"].attrs["tsamp"]==1.25
        np.testing.assert_array_equal(h["data"][2:4,5:10],expected[2:4,5:10])
    assert reader.fetched_bytes<=len(payload)


@pytest.mark.parametrize("status,content_range",[(200,"bytes 0-3/100"),(206,"bytes 0-4/100")])
def test_http_range_semantics_must_be_exact(monkeypatch,status,content_range):
    class Response:
        headers={"Content-Range":content_range,"ETag":"stable"}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n):return b"abcd"
    response=Response();response.status=status
    monkeypatch.setattr("urllib.request.urlopen",lambda *a,**k:response)
    with pytest.raises(ValueError):HTTPRangeSource("https://example.invalid/data",100)(0,3)


def test_entity_change_is_rejected(monkeypatch):
    class Response:
        status=206
        headers={"Content-Range":"bytes 0-3/100","ETag":"changed"}
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,n):return b"abcd"
    monkeypatch.setattr("urllib.request.urlopen",lambda *a,**k:Response())
    with pytest.raises(ValueError,match="entity changed"):
        HTTPRangeSource("https://example.invalid/data",100,etag="old")(0,3)


def test_persistent_source_reuses_session_and_preserves_range_checks(monkeypatch):
    calls=[];sessions=[]
    class Response:
        status_code=206
        def __init__(self,headers):
            a,b=(int(v) for v in headers['Range'].split('=')[1].split('-'))
            self.headers={'Content-Range':f'bytes {a}-{b}/100','ETag':'stable'}
            self.raw=io.BytesIO(bytes(range(a,b+1)))
        def __enter__(self):return self
        def __exit__(self,*args):return False
    class Session:
        def __init__(self):sessions.append(self)
        def get(self,url,headers,stream,timeout):
            calls.append(headers['Range'])
            assert stream and timeout==15
            return Response(headers)
    monkeypatch.setattr('requests.Session',Session)
    source=HTTPRangeSource('https://example.invalid/data',100,persistent=True)
    assert source(0,3)==bytes(range(4))
    assert source(4,7)==bytes(range(4,8))
    assert len(sessions)==1
    assert calls==['bytes=0-3','bytes=4-7']


def test_transient_timeout_is_recorded_and_retried(monkeypatch):
    import requests
    calls=[]
    class Response:
        status_code=206
        headers={'Content-Range':'bytes 0-3/100','ETag':'stable'}
        raw=io.BytesIO(b'abcd')
        def __enter__(self):return self
        def __exit__(self,*args):return False
    class Session:
        def get(self,*args,**kwargs):
            calls.append(1)
            if len(calls)==1:raise requests.exceptions.ReadTimeout('simulated transient timeout')
            return Response()
    monkeypatch.setattr('requests.Session',Session)
    source=HTTPRangeSource('https://example.invalid/data',100,persistent=True)
    assert source(0,3)==b'abcd'
    assert len(calls)==2
    assert len(source.failures)==1
    assert source.failures[0]['failure_type']=='ReadTimeout'
