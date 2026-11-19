"""Acquire full-time narrowband excerpts from six original archive HDF5 files.

Uses verified HTTP byte ranges with per-file budgets, never full-file download.
Compares every fetched scientific sample with the published candidate release.
After acquisition, --offline reproduces extraction from hashed cached ranges.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import time
import threading
from pathlib import Path

import h5py
import hdf5plugin
import numpy as np

from .observations import HERE,load_release,inspect_cadence,plain,digest
from .range_access import BoundedRangeReader,HTTPRangeSource,exclusive_transfer_lock


def _run(offline=False):
    cross=json.loads((HERE/"evidence/archive_crosscheck.json").read_text())
    release,_=load_release();item=release["mlc1"]
    meta,*_=inspect_cadence("mlc1",item)
    destination=HERE/"data/archive_excerpts"
    destination.mkdir(exist_ok=True)
    def extract(scan):
        started=time.perf_counter();index=scan["scan_index"]
        rows=[r for r in scan.get("archive_rows",[]) if r["url"].endswith(".gpuspec.0000.h5")]
        if len(rows)!=1:raise ValueError(f"Scan {index}: need one high-frequency-resolution product, got {len(rows)}")
        row=rows[0];directory=HERE/"data/range_cache"/str(row["id"])
        directory.mkdir(parents=True,exist_ok=True)
        source_meta_path=directory/"source.json"
        previous=json.loads(source_meta_path.read_text()) if source_meta_path.exists() else None
        if previous and (previous["url"]!=row["url"] or previous["size"]!=row["size"]):raise ValueError("Range cache source changed")
        source=HTTPRangeSource(row["url"],row["size"],previous["etag"] if previous else None,persistent=True)
        cache_manifest_path=directory/"ranges.json"
        cached=json.loads(cache_manifest_path.read_text()) if cache_manifest_path.exists() else {}
        network_bytes=0
        cache_lock=threading.Lock()
        verified_memory={}
        def containing_cached_name(lo,hi):
            with cache_lock: names=list(cached)
            for name in names:
                begin,end=(int(v) for v in name.removesuffix('.bin').split('-'))
                if begin<=lo and hi<=end:return name,begin
            return None
        def fetch(lo,hi):
            nonlocal network_bytes
            name=f"{lo:012d}-{hi:012d}.bin";path=directory/name
            if path.exists():
                if name not in cached or digest(path)!=cached[name]["sha256"]:raise ValueError("Cached range hash missing/mismatched")
                return path.read_bytes()
            containing=containing_cached_name(lo,hi)
            if containing:
                parent_name,parent_begin=containing
                with cache_lock:
                    if parent_name not in verified_memory:
                        value=(directory/parent_name).read_bytes()
                        if hashlib.sha256(value).hexdigest()!=cached[parent_name]['sha256']:raise ValueError('Containing cache block checksum mismatch')
                        verified_memory[parent_name]=value
                    return verified_memory[parent_name][lo-parent_begin:hi-parent_begin+1]
            if offline:raise FileNotFoundError(f"Required cached range missing: {name}")
            value=source(lo,hi)
            with cache_lock:
                temporary=path.with_suffix(".part")
                temporary.write_bytes(value);temporary.replace(path)
                network_bytes+=len(value)
                cached[name]={"sha256":hashlib.sha256(value).hexdigest(),"bytes":len(value)}
                source_meta_path.write_text(json.dumps({"url":row["url"],"size":row["size"],"etag":source.etag},indent=2)+"\n")
                temporary=cache_manifest_path.with_suffix(".part")
                temporary.write_text(json.dumps(cached,indent=2,sort_keys=True)+"\n")
                temporary.replace(cache_manifest_path)
            return value
        # Fine blocks avoid transferring MiB for tiny scattered metadata nodes.
        # Large data reads are prefetched as coalesced runs below, not as one
        # HTTP request per fine block. Older verified larger blocks are reused.
        reader=BoundedRangeReader(row["size"],fetch,block_bytes=65536,max_bytes=256*1024*1024)
        record={"scan_index":index,"url":row["url"],"archive_id":row["id"],"archive_file_bytes":row["size"],"archive_reported_md5":row["md5sum"],"whole_original_file_checksum_verified":False,"range_byte_budget":reader.max_bytes}
        try:
            with h5py.File(reader,"r") as h:
                ds=h["data"];attrs=plain(dict(ds.attrs));header=item["all_header"][index]
                fields=["source_name","telescope_id","nbits","nchans","fch1","foff","tsamp","tstart"]
                header_checks={k:attrs.get(k)==plain(header[k]) for k in fields}
                if not all(header_checks.values()):raise ValueError(f"Source header differs: {header_checks}")
                lo,hi=item["freq"]
                first=int(np.rint((hi-attrs["fch1"])/attrs["foff"]))
                stop=int(np.rint((lo-attrs["fch1"])/attrs["foff"]))
                if not 0<=first<stop<=ds.shape[2]:raise ValueError("Invalid source channel slice")
                # Identify exactly which stored chunks hold the excerpt, then
                # prefetch their existing reader blocks concurrently OUTSIDE
                # HDF5 callbacks. This avoids serial network I/O under h5py's
                # global lock. Data selection and decompression stay unchanged.
                required=set()
                if ds.chunks:
                    for t in range(0,ds.shape[0],ds.chunks[0]):
                        for fc in range(first//ds.chunks[2],(stop-1)//ds.chunks[2]+1):
                            info=ds.id.get_chunk_info_by_coord((t,0,fc*ds.chunks[2]))
                            if info.byte_offset is None:continue
                            begin=info.byte_offset//reader.block_bytes
                            end=(info.byte_offset+info.size-1)//reader.block_bytes
                            required.update(range(begin,end+1))
                    required.update(reader.cache)
                    potential=sum(min(row['size'],(idx+1)*reader.block_bytes)-idx*reader.block_bytes for idx in required)
                    if potential>reader.max_bytes:raise ValueError("Prefetch plan exceeds per-file range budget")
                    missing=[idx for idx in sorted(required) if not containing_cached_name(idx*reader.block_bytes,min(row['size'],(idx+1)*reader.block_bytes)-1)]
                    runs=[]
                    for idx in missing:
                        if runs and idx==runs[-1][-1]+1 and len(runs[-1])*reader.block_bytes<8*1024*1024:runs[-1].append(idx)
                        else:runs.append([idx])
                    ranges=[(r[0]*reader.block_bytes,min(row['size'],(r[-1]+1)*reader.block_bytes)-1) for r in runs]
                    with ThreadPoolExecutor(max_workers=3) as pool:
                        list(pool.map(lambda pair:fetch(*pair),ranges))
                    record["prefetched_reader_blocks"]=len(required)
                # All stored integrations, rather than a selected time crop.
                data=ds[:,0,first:stop]
                published=item["data"][index,:,0,:]
                equal=data.dtype==published.dtype and data.shape==published.shape and np.array_equal(data,published)
                if not equal:raise ValueError(f"Scientific excerpt differs from release: shapes {data.shape}/{published.shape}")
                freq=(attrs["fch1"]+attrs["foff"]*np.arange(first,stop))[::-1]*1e6
                path=destination/f"scan_{index}.npz"
                np.savez_compressed(path,power_ascending=data[:,::-1],frequency_hz=freq,time_s=np.arange(data.shape[0])*attrs["tsamp"])
                record.update({"header_checks":header_checks,"source_shape":list(ds.shape),"excerpt_shape":list(data.shape),"original_channel_slice_half_open":[first,stop],"entire_stored_time_axis_acquired":True,"every_scientific_sample_bitwise_equals_release":True,"axis_convention_confirmed_by_raw_slice":True,"header":attrs,"excerpt_npz_sha256":digest(path)})
        except Exception as exc:
            record.update({"failure_type":type(exc).__name__,"failure":str(exc)})
        record.update({"range_bytes_accessed":reader.fetched_bytes,"new_network_bytes":network_bytes,"http_requests":source.requests,"http_failures":source.failures,"wall_s":time.perf_counter()-started,"offline":offline})
        print(f"Archive scan {index+1}/6: {'MATCH' if record.get('every_scientific_sample_bitwise_equals_release') else record.get('failure')} | {reader.fetched_bytes/1024**2:.1f} MiB accessed",flush=True)
        return record
    with ThreadPoolExecutor(max_workers=2) as executor:records=list(executor.map(extract,cross["scans"]))
    success=all(r.get("every_scientific_sample_bitwise_equals_release",False) for r in records)
    result={"mode":"offline_cached_ranges" if offline else "bounded_archive_extraction","all_six_scientific_excerpts_bitwise_match":success,"all_stored_time_samples_acquired_for_selected_frequency_slice":success,"full_original_bandwidth_acquired":False,"representative_cohort_gate_passed":False,"range_bytes_accessed":sum(r["range_bytes_accessed"] for r in records),"new_network_bytes":sum(r["new_network_bytes"] for r in records),"sum_original_archive_file_bytes":sum(r["archive_file_bytes"] for r in records),"records":records,"scientific_limit":"Only an all-six PASS confirms source/sample identity for the selected complete six-scan narrowband cadence. No full-band survey, representative population sensitivity, or verification of whole archive file MD5 checksums is claimed."}
    path=HERE/"evidence"/("archive_excerpts_offline.json" if offline else "archive_excerpts.json")
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
    return result


def run(offline=False):
    with exclusive_transfer_lock(HERE/"data/archive_extraction.lock"):
        return _run(offline)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--offline",action="store_true")
    result=run(parser.parse_args().offline)
    raise SystemExit(0 if result["all_six_scientific_excerpts_bitwise_match"] else 1)
