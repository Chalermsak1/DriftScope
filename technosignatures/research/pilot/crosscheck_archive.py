"""Cross-check six released scan headers against official archive metadata.

No full observational file is downloaded. Optionally read bounded HDF5
metadata from the first timestamp-exact archive match using --range-metadata.
"""
import argparse
import json
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone

import h5py
import hdf5plugin
from .observations import HERE,load_release,inspect_cadence,plain
from .range_access import HTTPRangeSource,BoundedRangeReader


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--range-metadata",action="store_true")
    args=parser.parse_args()
    release,_=load_release()
    meta,*_=inspect_cadence("mlc1",release["mlc1"])
    def query(scan):
        mjd=scan["start_mjd"]
        params={"target":scan["source_name"],"time-start":str(mjd-3/86400),"time-end":str(mjd+3/86400),"limit":"20"}
        url="https://seti.berkeley.edu/opendata/api/query-files?"+urllib.parse.urlencode(params)
        result={"scan_index":scan["scan_index"],"role":scan["role"],"released_source":scan["source_name"],"released_mjd":mjd,"query_url":url}
        try:
            with urllib.request.urlopen(url,timeout=15) as response:
                payload=response.read(2_000_001)
                if len(payload)>2_000_000:raise ValueError("Response over metadata budget")
                data=json.loads(payload)
                result["effective_query_url"]=response.url
            if data.get("result")!="success":raise ValueError("Archive did not return success")
            rows=[r for r in data.get("data",[]) if r.get("target")==scan["source_name"] and r.get("file_type")=="HDF5"]
            for r in rows:r["released_timestamp_difference_s"]=(float(r["mjd"])-mjd)*86400
            exact=[r for r in rows if abs(r["released_timestamp_difference_s"])<=0.002]
            result.update({"archive_rows":rows,"timestamp_exact_matches":exact,"has_timestamp_exact_archive_match":bool(exact)})
        except Exception as exc:result.update({"failure_type":type(exc).__name__,"failure":str(exc),"has_timestamp_exact_archive_match":False})
        return result
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=3) as executor:scans=list(executor.map(query,meta["scans"]))
    evidence={"utc":datetime.now(timezone.utc).isoformat(),"scans":scans,"all_six_have_timestamp_exact_archive_match":all(s["has_timestamp_exact_archive_match"] for s in scans),"timestamp_tolerance_s":0.002,"query_wall_s":time.perf_counter()-started,"limit":"API matching is metadata evidence only; it does not establish bit identity between released cutouts and source files. Multiple resolution products can share timestamps. Archive queries may redirect to HTTP; GitHub release remains independently checksum-pinned."}
    if args.range_metadata and scans[0].get("archive_rows"):
        probes=[]
        # Inspect all first-scan resolution products; timestamp equality alone
        # cannot identify the source of a spectral excerpt.
        for row in sorted(scans[0]["archive_rows"],key=lambda r:r["url"]):
            probe={"url":row["url"],"archive_id":row["id"],"archive_size":row["size"],"archive_reported_md5":row["md5sum"],"whole_file_checksum_verified":False}
            source=HTTPRangeSource(row["url"],row["size"])
            reader=BoundedRangeReader(row["size"],source,max_bytes=8*1024*1024)
            try:
                with h5py.File(reader,"r") as handle:
                    ds=handle["data"]
                    attrs=plain(dict(ds.attrs))
                    probe.update({"data_shape":list(ds.shape),"dtype":str(ds.dtype),"chunks":list(ds.chunks) if ds.chunks else None,"compression":ds.compression,"attributes":attrs})
                    released=meta["scans"][0]["header"]
                    probe["released_header_comparison"]={key:{"released":released.get(key),"archive":attrs.get(key),"equal":released.get(key)==attrs.get(key)} for key in ["source_name","telescope_id","nbits","nchans","fch1","foff","tsamp","tstart"]}
                    probe["released_resolution_and_time_exactly_match"]=all(probe["released_header_comparison"][k]["equal"] for k in ["nbits","foff","tsamp","tstart"])
            except Exception as exc:probe.update({"failure_type":type(exc).__name__,"failure":str(exc)})
            probe.update({"fetched_bytes":reader.fetched_bytes,"range_requests":source.requests,"byte_budget":reader.max_bytes})
            cache_dir=HERE/"evidence/range_metadata_cache"
            cache_dir.mkdir(exist_ok=True)
            for index,value in reader.cache.items():(cache_dir/f"id_{row['id']}_block_{index:08d}.bin").write_bytes(value)
            probes.append(probe)
        evidence["first_scan_resolution_product_probes"]=probes
        evidence["any_probed_product_matches_released_resolution_and_time"]=any(p.get("released_resolution_and_time_exactly_match",False) for p in probes)
    (HERE/"evidence/archive_crosscheck.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps({"all_six_matches":evidence["all_six_have_timestamp_exact_archive_match"],"exact_match_counts":[len(s.get("timestamp_exact_matches",[])) for s in scans],"resolution_product_probes":evidence.get("first_scan_resolution_product_probes"),"query_wall_s":evidence["query_wall_s"]},indent=2))


if __name__=="__main__":main()
