"""Reacquire the pinned 12.6 MB source and record measured transfer evidence.

Run from the project root: python -m research.pilot.acquire [--refresh]
Uses curl's TLS verification and rejects unknown bytes before replacement.
"""
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .observations import HERE, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    spec = json.loads((HERE/"configs/source.json").read_text())
    destination = HERE/"data/upstream/top_8_data.pkl"
    if destination.exists() and digest(destination) != spec["sha256"]:
        raise ValueError("Existing source corrupted; refusing to overwrite")
    started = time.perf_counter()
    evidence = {"url":spec["url"],"commit":spec["commit"],"utc":datetime.now(timezone.utc).isoformat()}
    if destination.exists() and not args.refresh:
        evidence.update({"mode":"verified_cached_source","network_transfer_performed":False})
    else:
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary = destination.with_suffix(".download")
        command = ["curl","-fL","--max-time","60","--max-filesize","20000000","--silent","--show-error","--write-out","%{json}",spec["url"],"-o",str(temporary)]
        result = subprocess.run(command,text=True,capture_output=True)
        evidence.update({"mode":"network_download","network_transfer_performed":True,"curl_exit_code":result.returncode,"curl_stderr":result.stderr})
        try:
            metrics = json.loads(result.stdout) if result.stdout else {}
            # Retain relevant public transfer facts, not local interface/IP or
            # large certificate dumps emitted by some curl versions.
            evidence["curl_metrics"] = {k:metrics[k] for k in ["http_code","url_effective","size_download","time_total","speed_download","num_redirects","ssl_verify_result","exitcode"] if k in metrics}
            if result.returncode:
                raise RuntimeError(f"Download failed: {result.stderr}")
            if temporary.stat().st_size != spec["bytes"] or digest(temporary) != spec["sha256"]:
                raise ValueError("Downloaded source differs from pinned size/checksum")
            temporary.replace(destination)
        except Exception as exc:
            evidence["failure"] = str(exc)
            (HERE/"evidence/acquisition_failure.json").write_text(json.dumps(evidence,indent=2)+"\n")
            raise
        finally:
            temporary.unlink(missing_ok=True)
    evidence.update({"elapsed_wall_s":time.perf_counter()-started,"bytes":destination.stat().st_size,"sha256":digest(destination),"tls_verification_disabled":False})
    path = HERE/"evidence"/("network_transfer.json" if evidence["network_transfer_performed"] else "cached_access.json")
    path.write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps({k:v for k,v in evidence.items() if k!='curl_metrics'},indent=2))


if __name__ == "__main__":
    main()
