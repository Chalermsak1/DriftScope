# Conventional pipeline development v2

This module develops four linked capabilities: representative-cohort evaluation infrastructure, coverage remediation, event grouping, and cadence filtering. It preserves `pipeline.py`, `results/run_001`, the approved plans, and the earlier pilot records.

**Scientific scope:** executable development work and conditional injection experiments. The representative-cohort sensitivity gate remains open. Neither candidate-selected release data nor the original regression observation provide a representative population sensitivity estimate. No LLM or locked-test evaluation is introduced.

## Read the evidence

- [Current milestone report](evidence/MILESTONE_REPORT.md) and [validation status](evidence/milestone_status.json).
- [Final tests](evidence/tests_final.xml) and [complete development repeat](evidence/verification.json).
- [Development summary](results/development_v2/summary.json).
- [Coverage and legacy regression comparison](results/development_v2/coverage_remediation.json).
- [80-line synthetic stress test](results/development_v2/crowded_stress.json).
- [Conditional sensitivity ledger](results/development_v2/conditional_sensitivity.json).
- [Real-cadence engineering cases](results/development_v2/cadence_cases.json).
- [Archive sampling-frame audit](evidence/archive_frame_2018_refined.json) and [original-source header probe](evidence/cohort_header_probe.json).
- [Scientific decisions and development amendments](DESIGN.md), [record contracts](SCHEMAS.md), and [test strategy](TEST_PLAN.md).

## Installation and offline tests

From the `technosignatures/` project directory, use the existing pinned Python 3.11 environment described in its README. No dependency was added for v2.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pytest -q tests research/conventional/tests
```

These tests use the bundled original observation plus explicitly synthetic fixtures. They do not require the candidate release, an archive connection, or the large HTTP range cache. They cover algorithms and scientific invariants; they are not sensitivity measurements on synthetic metadata.

To reproduce the full historical-pilot integration suite as well, follow `research/pilot/README.md` to acquire and validate the release and archive cache, then run:

```bash
.venv/bin/python -m pytest -q tests research/pilot/tests research/conventional/tests \
  --junitxml=research/conventional/evidence/tests_local.xml
```

The historical archive offline-extraction test regenerates its pilot excerpt/evidence files. Use a separate working copy if preserving those exact historical records. The publication validation backed up and restored these files and checked preservation afterward.

## Execute the development evidence package

Acquire the independently licensed pilot source from its pinned origin using the existing downloader. Its source bytes and derived observational arrays remain outside Git.

```bash
.venv/bin/python -m research.pilot.acquire
.venv/bin/python -m research.conventional.run \
  --release-path research/pilot/data/upstream/top_8_data.pkl \
  --output research/conventional/results/my_development_run
```

The runner refuses to overwrite a nonempty output directory. It executes:

1. Whole-band/tile equivalence, exact discrete-support coverage accounting, and all ten original sampled-power regression scenarios.
2. An uncapped 80-line fully synthetic stress experiment with one-to-one recovery.
3. Gaussian channel integration and time-subsampling convergence checks.
4. A generated six-family × six-amplitude × 32-placement design, explicitly **not executed** as the full pilot.
5. Forty-eight randomized continuous-linear trials on the original real development observation, paired against the frozen legacy detector. There are eight placements per amplitude and one acquisition component.
6. Four integrated-power injection cases on the real `mlc1` six-scan cadence: persistent ON-only, weak OFF response, equal OFF response, and first-ON-only intermittency.
7. Cohort linkage and eligibility checks on all eight existing candidate-selected cutouts.

The local sensitivity curve ends at the grouped single-scan event boundary. Cadence filtering is evaluated separately on the four explicitly declared cadence cases. Those results are not pooled across receivers or presented as end-to-end cohort completeness.

To require a complete same-environment repeat:

```bash
.venv/bin/python -m research.conventional.verify \
  --reference research/conventional/results/my_development_run \
  --release-path research/pilot/data/upstream/top_8_data.pkl \
  --tests research/conventional/evidence/tests_local.xml \
  --output research/conventional/evidence/verification_local.json
```

Verification rejects changed reference source files, reruns into a temporary directory, compares every stable scientific JSON record and exact score/power-array hash, and checks the original experiment/plan manifests. Timing and image bytes are excluded. It does not perform a fresh dependency installation or repeat archive network acquisition.

## Build and inspect a candidate-independent sampling frame

```bash
.venv/bin/python -m research.conventional.archive \
  --config research/conventional/configs/archive_frame_2018.json \
  --output research/conventional/evidence/archive_frame_local.json
.venv/bin/python -m research.conventional.probe_cohort \
  --frame research/conventional/evidence/archive_frame_local.json \
  --metadata-only \
  --output research/conventional/evidence/archive_frame_refined_local.json
.venv/bin/python -m research.conventional.probe_cohort \
  --frame research/conventional/evidence/archive_frame_local.json \
  --output research/conventional/evidence/header_probe_local.json
```

The frame query uses telescope, calendar interval, and center-frequency metadata, without candidate detections, RFI scores, or injection positions. Saturated queries are bisected until unsaturated or the explicit request budget is exhausted. An incomplete query frame cannot pass readiness. Every query response, canonical response hash, failed request, rejection, inclusion probability, and selected component is recorded.

The header probe selects the first deterministic sampled proposal and reads headers only, with at most 8 MiB per original file / 48 MiB per execution. It requires HTTP ranges and ETag stability, compares archive metadata with the actual HDF5 header, and checks six-scan timing and pointing geometry. It does not acquire spectral samples, verify whole-file MD5, or infer receiver hardware from center frequency alone.

The inherited 1-arcsecond ON-pointing criterion is intentionally reported as a development assumption. Its suitability for a receiver-specific study has not been established. Failed proposals remain recorded; do not interpret them as proof of bad telescope data. A scientific cohort requires an instrument-justified pointing/beam criterion frozen before evaluation.

## Limits and next gates

- The new detector searches all valid **discrete linear boxcar tracks** under its declared mask and resource budget. This is not completeness for Gaussian tails, all morphologies, or a full astronomical survey.
- Global per-drift score normalization differs from the old common-guard normalization. Equal numeric thresholds do not establish equal false-alarm rates; an established comparator and native workload calibration remain necessary.
- Complete-link grouping prevents specified bridge/crossing failures. Partial-overlap aliases and ambiguous crowded associations remain possible. The ledger distinguishes hits, representatives, and physical injected signals.
- The default review-safe cadence policy retains/escalates every ON-supported cadence event. The strict policy is a separately measured experimental persistence/OFF veto, with losses retained in evidence. OFF coincidence is not an origin label.
- A rectangular channel/time Gaussian power model and convergence on specified cases do not validate the full instrumental response or all six signal families. The generated 1,152-trial design is not an executed sensitivity study.
- One real development background supports a conditional recovery measurement. The statistics module refuses an observing-environment interval from one independent component and labels degenerate resampling as unresolved.
- Actual source samples from a sufficiently broad, independent cohort, finalized receiver/pointing definitions, resource forecasts, validation comparator selection, and protocol/split freezing remain required before representative sensitivity or a locked comparison.

Failures and their corrections are retained in `evidence/DEVELOPMENT_LOG.md`. Local partial outputs are preserved under ignored `results/failed_attempts/`; they are not promoted to the validated reference.
