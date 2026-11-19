"""Bounded HTTP range reads for HDF5 metadata/excerpts, not whole-file hashes.

Every response must be 206 with exact Content-Range and a stable entity tag.
The reader aborts if the server ignores Range or the byte budget is exceeded.
"""
import io
import fcntl
import threading
from contextlib import contextmanager
import urllib.request


@contextmanager
def exclusive_transfer_lock(path):
    """OS-released lock: concurrent extraction processes must not share cache."""
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another archive extraction is already running") from None
        try:
            yield
        finally:
            fcntl.flock(handle,fcntl.LOCK_UN)


class BoundedRangeReader(io.RawIOBase):
    def __init__(self,size,fetch,block_bytes=65536,max_bytes=8*1024*1024):
        self.size=int(size);self.fetch=fetch;self.block_bytes=int(block_bytes)
        self.max_bytes=int(max_bytes);self.position=0;self.cache={};self.fetched_bytes=0

    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        target=offset if whence==0 else self.position+offset if whence==1 else self.size+offset if whence==2 else None
        if target is None or target<0:raise ValueError("Invalid seek")
        self.position=int(target)
        return self.position

    def read(self,size=-1):
        if self.position>=self.size:return b""
        length=self.size-self.position if size is None or size<0 else min(int(size),self.size-self.position)
        if length<0:raise ValueError("Negative read")
        if length>self.max_bytes:raise ValueError("Requested read exceeds byte budget")
        if length==0:return b""
        start=self.position;stop=start+length
        chunks=[]
        for index in range(start//self.block_bytes,(stop-1)//self.block_bytes+1):
            lo=index*self.block_bytes;hi=min(self.size,lo+self.block_bytes)
            if index not in self.cache:
                if self.fetched_bytes+hi-lo>self.max_bytes:raise ValueError("Total range-read budget exceeded")
                value=self.fetch(lo,hi-1)
                if len(value)!=hi-lo:raise ValueError("Range response length mismatch")
                self.cache[index]=value;self.fetched_bytes+=len(value)
            chunks.append(self.cache[index][max(0,start-lo):min(hi,stop)-lo])
        self.position=stop
        return b"".join(chunks)

    def readinto(self,buffer):
        value=self.read(len(buffer));buffer[:len(value)]=value;return len(value)


class HTTPRangeSource:
    def __init__(self,url,size,etag=None,persistent=False):
        self.url=url;self.size=int(size);self.etag=etag;self.requests=[]
        self.persistent=persistent;self._local=threading.local();self.failures=[]

    def __call__(self,start,end):
        import requests
        import urllib3
        for attempt in range(1,4):
            try:
                return self._read_range(start,end)
            except (OSError,requests.exceptions.RequestException,urllib3.exceptions.HTTPError) as exc:
                self.failures.append({"start":start,"end":end,"attempt":attempt,"failure_type":type(exc).__name__,"failure":str(exc)})
                if attempt==3:raise

    def _read_range(self,start,end):
        headers={"Range":f"bytes={start}-{end}","Accept-Encoding":"identity"}
        if self.persistent:
            import requests
            if not hasattr(self._local,'session'):self._local.session=requests.Session()
            response=self._local.session.get(self.url,headers=headers,stream=True,timeout=15)
            response.status=response.status_code
            response.read=response.raw.read
        else:
            request=urllib.request.Request(self.url,headers=headers)
            response=urllib.request.urlopen(request,timeout=15)
        with response:
            if response.status!=206:raise ValueError(f"Server ignored Range: HTTP {response.status}")
            content_range=response.headers.get("Content-Range","")
            if content_range!=f"bytes {start}-{end}/{self.size}":raise ValueError(f"Wrong Content-Range: {content_range}")
            etag=response.headers.get("ETag")
            if self.etag is not None and etag!=self.etag:raise ValueError("Archive entity changed during reads")
            if self.etag is None:self.etag=etag
            value=response.read(end-start+2)
            if len(value)!=end-start+1:raise ValueError("Unexpected response length")
            self.requests.append({"start":start,"end":end,"content_range":content_range,"etag":etag,"http_status":response.status})
            return value
