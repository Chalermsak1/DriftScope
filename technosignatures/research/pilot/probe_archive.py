"""Bounded, read-only archive metadata probes; never download full data files."""
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime,timezone

from .observations import HERE


def main():
    query=urllib.parse.urlencode({"target":"HIP13402","time-start":"57541.68","time-end":"57541.72","limit":"10"})
    attempts=[]
    for base in ["https://seti.berkeley.edu/api/query-files","https://seti.berkeley.edu/opendata/api/query-files"]:
        url=base+"?"+query
        start=time.perf_counter()
        attempt={"url":url,"utc":datetime.now(timezone.utc).isoformat()}
        try:
            with urllib.request.urlopen(url,timeout=15) as response:
                payload=response.read(2_000_001)
                if len(payload)>2_000_000:raise ValueError("Metadata exceeds two-megabyte probe bound")
                attempt.update({"http_status":response.status,"effective_url":response.url,"content_type":response.headers.get("content-type"),"body_bytes":len(payload)})
                try:
                    content=json.loads(payload)
                    attempt["json"]=content
                    attempt["valid_archive_response"]=isinstance(content,dict) and "result" in content and "data" in content
                except (ValueError,UnicodeDecodeError):
                    attempt["body_prefix"]=payload[:160].decode(errors="replace")
                    attempt["valid_archive_response"]=False
        except Exception as exc:
            attempt["failure_type"]=type(exc).__name__
            attempt["failure"]=str(exc)
            attempt["valid_archive_response"]=False
        attempt["elapsed_s"]=time.perf_counter()-start
        attempts.append(attempt)
    result={"purpose":"Check underlying archival metadata independently of candidate-release headers; no full-file acquisition", "api_documentation":"https://github.com/ggroode/bl-opendata/blob/master/README.md","attempts":attempts,"any_valid_archive_response":any(a["valid_archive_response"] for a in attempts)}
    (HERE/"evidence/archive_metadata_probe.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
