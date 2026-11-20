"""Strict, budgeted HTTPS ranges with resumable verified disk caching."""
from collections import OrderedDict, defaultdict
import hashlib
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlparse

import requests
import urllib3
import fcntl

from .frame import write
from research.pilot.range_access import BoundedRangeReader


class TransferBudget:
    def __init__(self, total_bytes, per_file_bytes):
        if total_bytes < 0 or per_file_bytes < 0: raise ValueError('Negative transfer budget')
        self.limit = int(total_bytes); self.per_file_limit = int(per_file_bytes)
        self.reserved = 0; self.by_file = defaultdict(int); self.lock = threading.Lock()

    def reserve(self, key, nbytes):
        with self.lock:
            if nbytes < 1 or self.reserved+nbytes > self.limit or self.by_file[key]+nbytes > self.per_file_limit:
                raise ValueError('HTTP payload reservation exceeds batch or per-file budget')
            self.reserved += nbytes; self.by_file[key] += nbytes


class FileTransferBudget:
    """One atomic payload ledger shared by independent HDF5 reader processes."""
    def __init__(self, path):
        self.path = Path(path); self.lock = threading.RLock()

    @classmethod
    def create(cls, path, total, per_file):
        write(path, {'limit': total, 'per_file_limit': per_file, 'reserved': 0, 'by_file': {}, 'cancelled': False})
        return cls(path)

    @property
    def reserved(self): return json.loads(self.path.read_text())['reserved']

    def update(self, key=None, nbytes=None, cancel=False):
        with self.lock, self.path.with_suffix('.lock').open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            data = json.loads(self.path.read_text())
            if cancel: data['cancelled'] = True
            else:
                current = data['by_file'].get(str(key), 0)
                if data['cancelled'] or nbytes < 1 or data['reserved']+nbytes > data['limit'] or current+nbytes > data['per_file_limit']:
                    raise ValueError('Acquisition cancelled or shared payload budget exceeded')
                data['reserved'] += nbytes; data['by_file'][str(key)] = current+nbytes
            write(self.path, data)
            fcntl.flock(handle, fcntl.LOCK_UN)

    def reserve(self, key, nbytes): self.update(key, nbytes)
    def cancel(self): self.update(cancel=True)


class StrictRangeSource:
    def __init__(self, key, url, size, budget, etag=None):
        if urlparse(url).scheme != 'https': raise ValueError('Spectral transport requires HTTPS')
        self.key = str(key); self.url = url; self.size = int(size); self.budget = budget
        self.etag = etag; self.lock = threading.Lock(); self.local = threading.local()
        self.requests = []; self.failures = []; self.successful_payload_bytes = 0

    def __call__(self, start, end):
        if not 0 <= start <= end < self.size: raise ValueError('Invalid archive byte range')
        for attempt in range(3):
            self.budget.reserve(self.key, end-start+1)
            try:
                return self._read(start, end)
            except (requests.RequestException, urllib3.exceptions.HTTPError, OSError) as exc:
                with self.lock:
                    self.failures.append({'start': start, 'end': end, 'attempt': attempt+1,
                                          'failure_type': type(exc).__name__, 'failure': str(exc)})
                if attempt == 2: raise
                time.sleep(0.25*(attempt+1))

    def _read(self, start, end):
        if not hasattr(self.local, 'session'): self.local.session = requests.Session()
        headers = {'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'}
        with self.lock:
            if self.etag: headers['If-Range'] = self.etag
        with self.local.session.get(self.url, headers=headers, stream=True, timeout=(10, 45)) as response:
            if urlparse(response.url).scheme != 'https': raise ValueError('Archive redirected spectral data to non-HTTPS')
            if response.status_code != 206: raise ValueError(f'Archive did not honor Range: HTTP {response.status_code}')
            expected = f'bytes {start}-{end}/{self.size}'
            if response.headers.get('Content-Range') != expected: raise ValueError('Incorrect Content-Range')
            if response.headers.get('Content-Encoding', 'identity').lower() != 'identity': raise ValueError('Unexpected transfer encoding')
            etag = response.headers.get('ETag')
            if not etag or etag.startswith('W/'): raise ValueError('Strong stable ETag required')
            with self.lock:
                if self.etag is not None and self.etag != etag: raise ValueError('Archive entity changed')
                self.etag = etag
            length = end-start+1
            value = response.raw.read(length+1)
            if len(value) != length: raise ValueError('Incorrect range payload length')
            with self.lock:
                self.successful_payload_bytes += len(value)
                self.requests.append({'start': start, 'end': end, 'content_range': expected, 'etag': etag,
                                      'status': response.status_code, 'effective_url': response.url})
            return value


class VerifiedRangeCache:
    def __init__(self, directory, key, url, size, budget, offline=False, memory_bytes=16*1024**2):
        self.directory = Path(directory); self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory/'index.json'; self.offline = offline
        self.lock = threading.RLock(); self.memory = OrderedDict(); self.memory_bytes = int(memory_bytes)
        self.verified_hits = 0; self.cached_bytes_returned = 0
        if self.path.exists():
            self.index = json.loads(self.path.read_text())
            if self.index['url'] != url or self.index['size'] != size: raise ValueError('Cache source identity changed')
        else:
            self.index = {'url': url, 'size': size, 'etag': None, 'ranges': {}}
        self.source = StrictRangeSource(key, url, size, budget, self.index['etag'])

    def containing(self, lo, hi):
        with self.lock:
            for name, record in self.index['ranges'].items():
                if record['start'] <= lo and hi <= record['end']: return name, record
        return None

    def fetch(self, lo, hi):
        found = self.containing(lo, hi)
        if found:
            name, record = found
            with self.lock:
                if name not in self.memory:
                    value = (self.directory/name).read_bytes()
                    if len(value) != record['bytes'] or hashlib.sha256(value).hexdigest() != record['sha256']:
                        raise ValueError('Cached range checksum mismatch')
                    self.memory[name] = value
                    while sum(len(v) for v in self.memory.values()) > self.memory_bytes and len(self.memory) > 1:
                        self.memory.popitem(last=False)
                self.memory.move_to_end(name)
                value = self.memory[name][lo-record['start']:hi-record['start']+1]
                self.verified_hits += 1; self.cached_bytes_returned += len(value)
                return value
        name = f'{lo:014d}-{hi:014d}.bin'; target = self.directory/name
        if target.exists(): raise ValueError('Unindexed cache payload exists; not accepted as verified data')
        if self.offline: raise FileNotFoundError(f'Required verified range missing: {name}')
        value = self.source(lo, hi)
        record = {'start': lo, 'end': hi, 'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
        with self.lock:
            temp = target.with_suffix('.part'); temp.write_bytes(value); temp.replace(target)
            self.index['ranges'][name] = record; self.index['etag'] = self.source.etag
            write(self.path, self.index)
        return value

    def prefetch(self, block_indices, block_bytes, file_size, max_request_bytes, workers):
        from concurrent.futures import ThreadPoolExecutor
        missing = [i for i in sorted(block_indices) if not self.containing(i*block_bytes, min((i+1)*block_bytes, file_size)-1)]
        runs = []
        for i in missing:
            if runs and i == runs[-1][-1]+1 and len(runs[-1])*block_bytes < max_request_bytes: runs[-1].append(i)
            else: runs.append([i])
        ranges = [(run[0]*block_bytes, min((run[-1]+1)*block_bytes, file_size)-1) for run in runs]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda pair: self.fetch(*pair), ranges))
        return {'required_blocks': len(block_indices), 'new_coalesced_ranges': len(ranges)}


class CoalescedRangeReader(BoundedRangeReader):
    """Preserve fine block accounting while fetching adjacent misses together."""
    def __init__(self, size, cache, block_bytes, max_bytes, request_bytes, workers):
        super().__init__(size, cache.fetch, block_bytes, max_bytes)
        self.disk_cache = cache; self.request_bytes = request_bytes; self.workers = workers

    def read(self, size=-1):
        if self.position >= self.size: return b''
        length = self.size-self.position if size is None or size < 0 else min(int(size), self.size-self.position)
        if length < 0 or length > self.max_bytes: raise ValueError('Requested read exceeds explicit budget')
        if length:
            stop = self.position+length
            missing = {i for i in range(self.position//self.block_bytes, (stop-1)//self.block_bytes+1) if i not in self.cache}
            potential = self.fetched_bytes+sum(min(self.size, (i+1)*self.block_bytes)-i*self.block_bytes for i in missing)
            if potential > self.max_bytes: raise ValueError('Coalesced read exceeds cumulative unique-byte budget')
            self.disk_cache.prefetch(missing, self.block_bytes, self.size, self.request_bytes, self.workers)
        return super().read(size)
