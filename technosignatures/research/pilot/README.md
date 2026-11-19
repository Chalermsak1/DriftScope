# Executed access pilot and pipeline-loss accounting

This research extension preserves the original `pipeline.py`, source observation, recorded results, and approved plan. It executes observational access checks and traces the conventional detector's losses before any LLM development.

Start with the [current combined milestone report](evidence/MILESTONE_REPORT.md), [current milestone status](evidence/milestone_status.json), and [final test/reproduction evidence](evidence/verification.json). The generated [per-stage experiment report](results/milestone_001/REPORT.md) is supplemented by the subsequent original-source checks. Scope and incomplete gates are explicit; structural cadence validation is not a claim of representative population coverage.

## What is executed

1. Acquire a commit- and checksum-pinned observational candidate release linked by the paper's official project page.
2. Validate eight released six-scan cutouts, including timestamps, ON/OFF labels, coordinates, frequency/time resolution, finite samples, and original frequency direction.
3. Identify repeated scan sequences and shared target/day groups before treating cutouts as independent data.
4. Search all six scans of `mlc1` with the unchanged conventional baseline; retain every thresholded local maximum and its suppression/cap decision.
5. Audit the original fixture's searched domain against per-drift discrete track support.
6. Run ten declared signal-survival cases in the original real observation, with an unchanged no-injection control.
7. Run an 80-line fully synthetic truncation fixture and a two-track fully synthetic suppression fixture. Track signals separately from candidate maxima.
8. Inject one global chirp across the actual timestamps of three ON scans, preserving the observing gaps and unchanged OFF arrays.
9. Query original archive file metadata, distinguish resolution products, inspect HDF5 headers with bounded byte ranges, and independently compare full-time frequency excerpts with the release. Consult `archive_excerpts.json` for the actual acquisition result; no full-file checksum is claimed verified.
10. Run the test suite and a complete same-environment numerical repeat. Verification covers scientific JSON and all NPZ arrays, not identical timing or image bytes.

## Reproduce in the existing workspace

From the project root:

```bash
.venv/bin/python -m research.pilot.acquire
.venv/bin/python -m research.pilot.run
.venv/bin/python -m pytest -q tests research/pilot/tests --junitxml=research/pilot/evidence/tests.xml
.venv/bin/python -m research.pilot.verify
```

The existing workspace contains the acquired release, source excerpts and verified range cache. In a fresh copy without that cache, first follow the independent archive-validation commands below before running the full test suite: the source-provenance tests deliberately fail if source extraction evidence or offline range reconstruction is unavailable.

The experiment uses the original pinned environment in `requirements.lock`; no extra dependencies were installed. `acquire` checks the existing source checksum and only downloads when needed. `--refresh` explicitly repeats the measured transfer while rejecting a corrupted existing file. Downloaded source bytes are never accepted without the pinned checksum and expected git-blob hash.

All new code and outputs are under `research/`. The experiment creates/updates only the new milestone directory, not `run_001`. To preserve a reference execution while trying another output location:

```bash
.venv/bin/python -m research.pilot.run --output research/pilot/results/my_new_run
```

## Reproduce independent archive validation

These are bounded read-only network operations, separate from the offline experiment:

```bash
.venv/bin/python -m research.pilot.probe_archive
.venv/bin/python -m research.pilot.crosscheck_archive --range-metadata
.venv/bin/python -m research.pilot.archive_excerpts
```

The exact official archive route was discovered from the portal/documentation. One route returned 404; the working route is `/opendata/api/query-files`. The API may redirect to HTTP. Resulting metadata identify files to inspect; they are not accepted as proof of spectral-product identity without HDF5 header/sample checks. Some archive-index timestamps differ from the actual HDF5 header by one second; source headers and sample equality resolve the correspondence.

`archive_excerpts` selects the high-frequency-resolution `.gpuspec.0000.h5` product for each scan, reads every stored integration over the released frequency interval, and checks bitwise equality with the published scientific array. Each original file is limited to 256 MiB of accessed range blocks per execution; all six together are limited to 1.5 GiB per execution. This is not a bound on cumulative network traffic across interrupted/repeated attempts. If a server ignores Range, returns the wrong offsets/size, changes ETag, or exceeds the budget, extraction fails and records the failure. Downloaded blocks are hashed and cached, so interrupted extraction can resume without discarding completed verified ranges. An operating-system file lock prevents concurrent extraction processes from sharing the cache.

After successful acquisition:

```bash
.venv/bin/python -m research.pilot.archive_excerpts --offline
```

This reconstructs the excerpt from local hashed range blocks without network access. Whole original HDF5 files are many gigabytes; the pipeline does not download them in full, and therefore does not claim to verify their full-file MD5 values. The archive-provided MD5 values are retained as provenance fields only.

## Evidence map

| Artifact | Meaning |
|---|---|
| `configs/source.json` | Immutable source URL, commit, sizes, SHA-256, git-blob hash, source-selection rule, and data-use attribution note. |
| `configs/audit.json` | Frozen engineering cases, signal strengths/drifts/positions, matching tolerance, and synthetic noise seeds. |
| `evidence/network_transfer.json` | Measured release transfer, public timing/size/status facts, TLS verification policy, checksum. |
| `evidence/archive_metadata_probe.json` | Successful/failed archive query routes and original file index records. |
| `evidence/archive_crosscheck.json` | Six scan timestamp queries plus original HDF5 resolution-product comparisons. |
| `evidence/archive_excerpts.json` | Original HDF5 range/sample acquisition and per-scan bitwise comparisons. |
| `evidence/archive_excerpts_offline.json` | Cached-range reconstruction evidence after the offline verification command. |
| `results/milestone_001/observational_manifest.json` | All released headers, physical axes, gap/exposure accounting, and cadence checks. |
| `results/milestone_001/access_summary.json` | Duplicate sequences, conservative grouping proxy, and population-gate limitations. |
| `native_scan_*_catalogue.json` | Every thresholded local maximum, suppressor, uncapped rank, and retained/capped state. |
| `*_coverage.json` | Common-guard coverage and the valid discrete path count at each trial drift. |
| `fixture_survival.json` | Signal-level survival and exclusive first-loss category for ten injections in the real C-band fixture. |
| `fully_synthetic_crowded_fixture*.json` | Candidate-count and physical-signal-count truncation evidence, clearly marked fully synthetic. |
| `cadence_injection_survival.json` | One chirp's three ON-scan pieces and unchanged OFF arrays; no cadence rejection algorithm is implied. |
| `profile.json` | Actual baseline runtime and process peak RSS; not a forecast of a population-scale study. |
| `evidence/tests.xml` | Current automated test results. |
| `evidence/verification.json` | Repeat comparisons, code/test hashes, and preservation of original experiment and approved documents. |
| `evidence/development_log.json` | Failures, corrected assumptions, source-access findings, and scope. |

## How to read the loss ledger

The detector is unmodified. `accounting.py` reconstructs its full threshold/local-maximum catalogue, continues its frequency-suppression rule without a cap, and verifies that the capped prefix exactly equals the original output. This isolates cap losses without falsely treating an improved detector as the original.

For each injection, the evaluator checks domain eligibility, discrete path support, availability of a truth-compatible searched track, score threshold, local maximum, frequency suppression, and cap survival. Downstream stages are `not_reached` after an earlier failure; unimplemented event/cadence/triage stages are `not_applied`. The no-injection control identifies ambiguous attribution from pre-existing compatible detections.

Coverage uses the detector's discrete nearest-channel path and boxcar footprint. It is not coverage of all Gaussian tails or a calibrated astrophysical selection function. A compatible track may start near a nominally excluded center within the frozen matching tolerance; both nominal guard membership and actual compatible-track availability are recorded.

Candidate peaks are not distinct injected signals. In the measured 80-line fixture, 475 local maxima become 97 candidates after frequency suppression. The cap discards 47 candidate peaks and loses 30 of the 80 injected physical tracks. Tests explicitly check these different units.

## Limits and unfinished work

- Candidate-selected release data do not establish a representative RFI/background population or a locked test cohort.
- Shared scan sequences and target/day groups prevent treating eight cutouts as eight independent sessions.
- Original archive excerpt validation, when passed, covers a narrow spectral interval across all stored integrations of six scans; it does not constitute a full-band survey or calibration audit.
- The C-band fixture and L-band cadence are separate engineering cases and are not pooled as a sensitivity estimate.
- Sampled-power injections omit intra-integration smearing, channel-response integration, transmitter noise, and calibrated beam response.
- The selected ON-only response is an illustrative controlled injection; it does not prove that a real signal absent in OFF is extraterrestrial.
- Event grouping, full cadence veto/filtering, overlapping tiled search, representative sensitivity curves, and LLM evaluation remain separate unfinished milestones.
- Deterministic scenario fractions are engineering outcomes. No confidence interval for population completeness or extraterrestrial-origin probability is claimed.

The next implementation milestone is overlap-aware search coverage and event grouping, after the current access/provenance checks and loss audits are validated. The current code already exposes the uncapped catalogue needed to quantify that change.
