"""Publish milestone status only after source, tests and repeats all pass."""
import json
from pathlib import Path

from .observations import HERE,ROOT,digest
from .run import preserved_original


def main():
    evidence=HERE/"evidence";out=HERE/"results/milestone_001"
    verify=json.loads((evidence/"verification.json").read_text())
    archive=json.loads((evidence/"archive_excerpts.json").read_text())
    offline=json.loads((evidence/"archive_excerpts_offline.json").read_text())
    summary=json.loads((out/"summary.json").read_text())
    assert verify["all_checks_passed"]
    assert archive["all_six_scientific_excerpts_bitwise_match"]
    assert offline["all_six_scientific_excerpts_bitwise_match"] and offline["new_network_bytes"]==0
    preserved_original()
    status={
        "milestone":"complete-six-scan-narrowband-access-and-legacy-loss-accounting",
        "status":"PASS_WITH_DECLARED_SCIENTIFIC_SCOPE",
        "completed":{
            "release_access":"8 real observational cutouts, 48 scan/header records; six distinct scan sequences; five conservative target/day groups",
            "independent_source_access":"One complete six-scan cadence over the selected 4096-channel interval, all stored integrations acquired from original HDF5 sources",
            "source_sample_identity":"All six original archive excerpts bitwise match the published release; raw frequency slice convention confirmed for mlc1",
            "legacy_search_loss_audit":"Exact reconstruction of threshold, local maxima, frequency suppression and catalogue cap",
            "signal_survival":"Ten engineering cases on the original real fixture; an eighty-line fully synthetic truncation fixture; a two-track synthetic fixture; one global chirp across three real ON scans",
            "reproducibility":"All scientific JSON/arrays repeated; original experiment and approved plan preserved; raw excerpts reproduced offline with HTTP disabled in tests"
        },
        "tests":verify["tests"],"repeat_comparisons_passed":verify["repeat_check_count"],
        "preservation":verify["preservation"],
        "work_package_status":{
            "R01":"PARTIAL: closest-source/code review advanced; recent primary-paper lead still unavailable; novelty not established",
            "R02":"PASS for bounded candidate-release/one-cadence access pilot; representative cohort selection remains open",
            "R03":"PASS for one complete six-scan narrowband cadence with original-source sample identity; not a full-band acquisition",
            "R04":"PASS: coverage and candidate-cap effects measured with executable tests",
            "R05":"PASS for existing implemented detector stages; later-stage schemas/statuses explicitly not-applied",
            "R06":"PARTIAL: release and archive-HDF5 excerpt access implemented; production general-purpose loader remains future work",
            "R07":"NOT COMPLETE: overlap-aware search remediation not implemented",
            "R08":"NOT COMPLETE: path/time event grouping not implemented",
            "R09":"PARTIAL: actual cadence timing/pointings and global injection checked; no cadence-veto algorithm validated",
            "R10":"NOT COMPLETE: sampled Gaussian power only; physical integration/smearing awaits separate validation",
            "R11":"NOT COMPLETE: ten-case audit and stress fixtures executed; full 1152-case morphology pilot not executed",
            "R12":"PARTIAL: weak/off-grid/guard/collision cases audited; broader physical and OFF-leakage challenge sets remain",
            "R13":"PARTIAL: current CPU/memory/transfer profiling recorded; main sensitivity-study resource forecast remains open"
        },
        "open_gates":{
            "representative_multi_session_cohort":False,
            "full_original_bandwidth_acquired":False,
            "whole_original_hdf5_md5_verified":False,
            "population_completeness_estimated":False,
            "llm_introduced":False
        },
        "next_milestone":"Overlap-aware search coverage and loss-aware event grouping; representative cohort acquisition continues separately.",
        "range_bytes_accessed_successful_execution":archive["range_bytes_accessed"],
        "new_network_bytes_successful_execution":archive["new_network_bytes"],
        "sum_full_archive_file_bytes_not_downloaded_in_full":archive["sum_original_archive_file_bytes"],
        "network_measurement_limit":"Successful-execution counters exclude earlier interrupted transfer traffic; cached disk footprint and restart audit are separate evidence."
    }
    (evidence/"milestone_status.json").write_text(json.dumps(status,indent=2,sort_keys=True)+"\n")
    lines=["# Original-source cadence validation addendum","", "**PASS for the stated narrowband, six-scan access scope.** This addendum augments the experiment report; it does not turn a candidate-selected pilot into a representative sensitivity study.","", "## Independent source evidence", "", "The official archive index was queried for all six HIP13402 cadence pointings. Timestamp matching alone initially selected a different resolution product. Bounded HDF5-header reads identified the actual high-frequency-resolution files, whose attributes match the release. Narrow frequency excerpts spanning every stored integration were then acquired from each original file and compared to the published release.","", "| Scan | Archive ID | Stored integrations | Excerpt channels | Every float32 sample equal | Accessed MiB |", "|---|---:|---:|---:|---|---:|"]
    for r in archive["records"]:
        lines.append(f"| {r['scan_index']} | {r['archive_id']} | {r['excerpt_shape'][0]} | {r['excerpt_shape'][1]} | {r['every_scientific_sample_bitwise_equals_release']} | {r['range_bytes_accessed']/1024**2:.2f} |")
    lines.extend(["",f"The original files total {archive['sum_original_archive_file_bytes']/1e9:.3f} GB; they were not downloaded in full. The successful execution accessed {archive['range_bytes_accessed']/1024**2:.2f} MiB of range blocks. Its new-network counter is {archive['new_network_bytes']/1024**2:.2f} MiB and excludes earlier interrupted traffic. All six excerpts also reproduced from the local hash-verified cache with HTTP disabled.","", "The selected frequency interval is about 11.6 kHz. This establishes all stored time samples in that interval, not the original full-bandwidth coverage. HTTP status 206, exact Content-Range and stable ETag are required. Excerpt hashes and cached-range hashes are recorded; whole-file archive MD5 values are provenance fields and have **not** been verified.","", "The raw slice confirms the reconstructed channel-center convention for mlc1. Other released cutouts retain their disclosed reconstruction uncertainty. Absolute receiver frequency calibration and telescope observing logs have not been independently audited. Source DIMENSION_LABELS text is inherited; the numeric layout is checked against dataset shape, nchans, and the released arrays rather than inferred from label text alone.","", "## Validation and limitations","",f"- Current suite: {verify['tests']['tests']} tests, {verify['tests']['failures']} failures, {verify['tests']['errors']} errors, {verify['tests']['skipped']} skips.",f"- Complete numerical experiment repeat: {verify['repeat_check_count']} matching scientific JSON/array comparisons.",f"- Preserved: {verify['preservation']['original_manifest_files_verified']} original experiment files and {verify['preservation']['approved_plan_manifest_files_verified']} approved-plan files.","- The initial test failure, transfer restarts, cache quarantine, and I/O corrections remain documented. No detection method or signal strength was tuned in response to those test corrections.","- No event grouping, cadence rejection, population uncertainty estimate, or LLM was introduced.","", "See `milestone_status.json` for per-work-package completion and partial/open gates."])
    (evidence/"CADENCE_SOURCE_VALIDATION.md").write_text("\n".join(lines)+"\n")
    paths=[p for p in sorted(HERE.rglob('*')) if p.is_file() and not any(part in {'__pycache__','range_cache','range_metadata_cache','reproduction'} for part in p.relative_to(HERE).parts) and p.name!='milestone_manifest.json']
    manifest={str(p.relative_to(ROOT)):{"sha256":digest(p),"bytes":p.stat().st_size} for p in paths}
    (evidence/"milestone_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"status":status['status'],"tests":status['tests'],"repeat_checks":status['repeat_comparisons_passed'],"source_cadence_scans_verified":len(archive['records'])},indent=2))


if __name__=="__main__":main()
