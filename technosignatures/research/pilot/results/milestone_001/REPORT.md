# Complete-cadence access pilot and pipeline-loss audit

This report separates real observational access, blind native searches, injections into real data, and fully synthetic engineering stress tests.

## Observational access

- Eight checksum-pinned released cutouts inspected; 6 distinct six-scan sequences, not eight independent cadences.
- Structural checks: True; 48 scan/header records inspected.
- Duplicate scan-sequence cutouts: [['mlc4', 'mlc5'], ['mlc3', 'mlc8']].
- Conservative target/UTC-day proxy groups: [['mlc1', 'mlc7'], ['mlc2'], ['mlc3', 'mlc8'], ['mlc4', 'mlc5'], ['mlc6']].
- Access establishes six released scan records in narrow candidate-selected frequency intervals. Full original bandwidth/integration counts and telescope logs have not been independently acquired.
- Frequency centers are reconstructed from the original header lattice under blimpy half-open slicing; the absolute convention has a disclosed one-channel uncertainty.
- The pilot is L-band; the original C-band fixture is a separate engineering control. Neither is a representative population cohort.

## Original reference coverage

- Common valid starts: 764/1024 = 74.609375%.
- Original searched track trials: 390,404.
- Discrete per-drift boxcar-valid trials in the input: 489,730.
- Valid discrete trials omitted by the common guard: 99,326.
- These counts measure the detector's discrete path/boxcar domain, not Gaussian-tail signal support or an astrophysical selection volume.

## Blind native observational searches

No native peak is labeled extraterrestrial or automatically labeled terrestrial interference.

| Scan | Role | Raw local maxima | Uncapped NMS | Cap losses | Retained |
|---|---|---:|---:|---:|---:|
| 0 | ON | 0 | 0 | 0 | 0 |
| 1 | OFF | 0 | 0 | 0 | 0 |
| 2 | ON | 2 | 1 | 0 | 1 |
| 3 | OFF | 0 | 0 | 0 | 0 |
| 4 | ON | 0 | 0 | 0 | 0 |
| 5 | OFF | 0 | 0 | 0 | 0 |

Every local maximum is recorded, including its suppressor or uncapped rank. The traced capped prefix exactly reproduces the unchanged original detector. Score maps can be regenerated from pinned data/config/code; their numerical hashes are retained rather than duplicating large arrays.

## Synthetic survival experiments

- Original-real-background engineering cases: 10; outcomes: {'retained': 4, 'below_score_threshold': 2, 'valid_path_omitted_by_common_guard': 3, 'outside_configured_drift_domain': 1}.
- Fully synthetic 80-line stress test: {'retained': 50, 'catalogue_truncation_loss': 30}.
- Synthetic cap audit: 97 uncapped candidates; 47 discarded by the original cap.
- Two-track suppression stress test: {'retained': 2}.
- One global chirp injected into the real selected cadence: 3 ON-scan pieces; 3 conservatively attributable per-scan recoveries. OFF arrays remain unchanged.
- Actual MJD scan gaps are used for the global chirp; its frequency is never reset at a new ON scan.
- These are deterministic engineering scenarios, not a randomized completeness survey. No confidence interval or transmitter-origin inference is assigned to these fractions.

## Signal-loss records

Each injected track records domain eligibility, discrete path support, compatible searched-track availability, threshold survival, local-maximum survival, frequency suppression, and cap survival. It retains a first-loss category and checks the no-injection control for ambiguous attribution.

Event grouping, cadence filtering, and triage are explicitly `not_applied`. Median/MAD normalization occurs inside the baseline; its loss cannot be separately identified from threshold/noise effects in this audit. The current work does not claim those later milestones are complete.

## Reproduction and status

Run from project root:

```bash
.venv/bin/python -m research.pilot.acquire
.venv/bin/python -m research.pilot.run
.venv/bin/python -m pytest -q tests research/pilot/tests --junitxml=research/pilot/evidence/tests.xml
.venv/bin/python -m research.pilot.verify
```

Final test/repeat evidence is stored separately in `research/pilot/evidence/verification.json`; this scientific report is generated before that final verification and should be read with it.

The original project manifest is verified before and after execution. No original source/data/result is overwritten. Acquisition timing is in `evidence/network_transfer.json`; CPU timing and memory are in `profile.json`.

Next work: validate source cutouts against independently obtained raw-file excerpts if possible, construct a representative complete-cadence cohort, and implement overlap-aware search/event grouping and physically integrated injection before a sensitivity claim. No LLM has been introduced.
