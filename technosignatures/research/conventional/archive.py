"""Bounded detector-independent archive frame; saturated queries are bisected."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request

from .cohort import propose_metadata_cadences, components, readiness, sample_components


def collect_frame(config, fetch=None):
    attempts, rows = [], {}
    complete = True
    budget = config["max_requests"]

    def http_get(url):
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = response.read(config["max_response_bytes"]+1)
            if len(payload) > config["max_response_bytes"]:
                raise ValueError("Metadata response exceeds configured byte budget")
            return json.loads(payload), response.url

    fetch = fetch or http_get

    def visit(start, stop):
        nonlocal complete
        if len(attempts) >= budget:
            complete = False
            return
        query = {"target": "", "telescopes": "GBT", "file-types": "HDF5",
                 "time-start": start, "time-end": stop,
                 "freq-start": config["frequency_start_mhz"], "freq-end": config["frequency_stop_mhz"], "limit": config["query_limit"]}
        url = config["api_url"]+"?"+urllib.parse.urlencode(query)
        attempt = {"url": url, "time_start_mjd": start, "time_stop_mjd": stop}
        attempts.append(attempt)
        try:
            content, effective = fetch(url)
            if content.get("result") != "success" or not isinstance(content.get("data"), list):
                raise ValueError("Archive did not return a successful row list")
            data = content["data"]
            attempt.update({"effective_url": effective, "row_count": len(data),
                            "response_sha256": hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest(),
                            "canonical_response": content})
            if len(data) >= config["query_limit"]:
                attempt["saturated"] = True
                if (stop-start)*86400 <= 2 or len(attempts) >= budget:
                    complete = False
                else:
                    middle = (start+stop)/2
                    visit(start, middle); visit(middle, stop)
                # Saturated parent rows are not an unbiased substitute for failed child queries.
                return
            for row in data:
                if (row.get("telescope") == "GBT" and start <= float(row["mjd"]) <= stop
                        and config["frequency_start_mhz"] <= float(row["center_freq"]) <= config["frequency_stop_mhz"]):
                    if row["id"] in rows and rows[row["id"]] != row:
                        raise ValueError("Conflicting archive metadata for the same file ID")
                    rows[row["id"]] = row
        except Exception as exc:
            complete = False
            attempt.update({"failure_type": type(exc).__name__, "failure": str(exc)})

    if config["start_mjd"] >= config["stop_mjd"] or budget < 1 or config["query_limit"] < 2:
        raise ValueError("Invalid frame/query bounds")
    visit(config["start_mjd"], config["stop_mjd"])
    ordered = sorted(rows.values(), key=lambda r: r["id"])
    rejected = []
    records = propose_metadata_cadences(ordered, rejected)
    return {"collected_at_utc": datetime.now(timezone.utc).isoformat(), "config": config,
            "selection": "calendar-window, telescope and frequency metadata only; no candidate outcomes, RFI scores, or injection locations",
            "frame_complete_with_respect_to_unsaturated_api_queries": complete,
            "archive_index_completeness_independently_verified": False,
            "attempts": attempts, "rows": ordered, "cadences": records,
            'rejected_metadata_sequences': rejected,
            "linkage": components(records), "development_access_sample": sample_components(records, 4, config["seed"]) if records else [],
            "readiness": readiness(records, complete),
            "spectral_data_downloaded": False,
            "limitation": "A finite convenience calendar frame, metadata proposals only. API result completeness is not an independent audit of the whole archive, full cadences, receiver identity, or data accessibility."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).parent/"configs/archive_frame.json")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent/"evidence/archive_frame.json")
    args = parser.parse_args()
    result = collect_frame(json.loads(args.config.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"metadata_rows": len(result["rows"]), "cadence_proposals": len(result["cadences"]),
                      "complete_queries": result["frame_complete_with_respect_to_unsaturated_api_queries"], "readiness": result["readiness"]}, indent=2))
    raise SystemExit(0 if result["frame_complete_with_respect_to_unsaturated_api_queries"] else 1)


if __name__ == "__main__": main()
