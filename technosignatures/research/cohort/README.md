# Prospective C-band cohort pilot

This module advances the conventional pipeline from candidate-selected development cutouts to prospectively selected original observations. It separates **observational source validation** from **synthetic injection recovery**. The approved main study still requires 60 independent components; this archive-index frame has only seven. Passing the access or software checks does not complete representative-cohort sensitivity.

Read [PROTOCOL.md](PROTOCOL.md) before acquisition. Original experiments, approved plans, v2 numerical source, and recorded engineering results are preserved. No LLM is used.

## Selection and estimand

The frozen [selection](evidence/selection.json) contains 12,375 archive-index rows, 251 parent cadence/product proposals and 182 proposals eligible by spectral center. Shared acquisition sessions, raw identities, target identities and coordinate aliases are linked **before** removing ineligible spectral products. Removing a bridge first would falsely create an eighth component; the pre-spectral correction and previous selections are retained. All seven resulting components are selected, with one uniformly selected cadence per component. Their eligible proposal counts, and therefore inverse cadence inclusion weights, are **2, 21, 5, 20, 4, 2, 128** in selection order.

These are cadence/product proposals, some dependent or overlapping, rather than 182 independent observations. One large linked campaign dominates the weighted finite-frame estimate. Seven component backgrounds do not become hundreds of independent groups by injecting more signals. Unknown archive omissions and unidentified dependency links remain limitations.

Random frequency variates are frozen before spectra are inspected. The header-only frequency plan conditions those draws on common available coverage: choose an available 1 GHz stratum uniformly, then an allowed tile-center interval uniformly. The plan preserves provisional frequency fields from the first-stage selection; `frequency_stratum_marginal_probability=1/3` describes that provisional assignment, **not** the conditional available-stratum draw. The operative draw is given by `available_frequency_strata`, `frequency_stratum` and `conditional_frequency_density_per_hz` in the immutable frequency plan. Published numerical weights correct cadence inclusion and unequal placements; they do not turn this conditional frequency design into uniform full-band or sky coverage.

Each chosen tile contains 1,024 channels from every stored integration of an alternating six-scan cadence. No target, tile, integration or cadence is substituted because its spectrum is noisy, masked or difficult to search. Insufficient or failed acquisition prevents the all-cohort runner from silently analyzing a successful subset.

## Data validation and transport

`acquire.py` checks target, MJD, coordinates, GBT identifier, stream count, dtype, resolution and frequency direction against the archive index. It preserves actual scan start times, gaps, original channel indices, source values and masks. Original descending channels are reversed exactly once. Independently read left/right HDF5 hyperslabs must concatenate to the same samples.

HTTP reads require HTTPS, exact 206 ranges, matching content length and a stable strong ETag. Hashed, atomic disk cache records allow offline reconstruction; corrupted or unindexed blocks are rejected. A shared process ledger reserves retry payloads before requests. Budgets are 8 GiB per invocation, 256 MiB per source per invocation, and 48 sources. Resuming a run creates a new transfer ledger, so those limits must not be described as cumulative limits over every interrupted attempt. Two HDF5 processes avoid the interpreter-wide HDF5 lock; each has at most six network workers and 512 KiB coalesced requests in the recorded transport configuration.

Whole original files and their checksums are not verified. An ETag binds range consistency, not astronomical authenticity. Chunk allocation is not independently proved. Exactly zero and nonfinite powers are conservatively masked, without modifying source values; whether zero is an instrument fill or a measured zero remains unresolved. Frequency headers identify a spectral regime, not independently verified receiver hardware or flux calibration.

Source arrays, HTTP blocks and previous private presentation copies are Git-ignored. Published acquisition records contain URLs, header checks, scientific array hashes and explicit failures. A new checkout must acquire its own permitted excerpts.

## Paired experiment

The fixed [evaluation configuration](configs/evaluation.json) specifies six signal families, six continuous peak-power amplitudes and 32 randomized trials per family/amplitude cell, distributed as four or five placements per component. There are **1,152 trials and 1,344 physical signals**; collision companions share a trial. All are development data. Smoke execution uses a distinct seed and only 14 trials; it is not sensitivity evidence for the full matrix.

The baseline arm is the original detector with its unchanged common guard, frequency suppression and 50-candidate limit, followed by the same event/cadence machinery as the new arm. The new arm uses per-drift full support and uncapped local maxima. Its vectorized execution preserves the scalar reference's whole-profile median/MAD normalization, score values, hits, masks, tile ownership and coverage. Exact source-map comparisons are required, not merely similar recovery rates.

Both arms see the same injected arrays and uninjected controls. OFF scans with zero added response reuse identical control searches. No detector receives injection truth, a difference image, a family label or a desired recovery position. Truth is used afterward for one-to-one candidate/event matching and coherent ancestry checks. Local-maximum, suppression, cap, grouping, association, ambiguity and policy decisions remain distinct. Audit compatibility at successive stages is not a proof of unique physical attribution; category names retain `or_assignment` where matching competition can contribute.

Unsearched support and technical failures remain explicit. Full declared-domain recovery and per-arm searchable-domain recovery use separate denominators. Conservative recovery excludes compatible native control events and overlapping companions; optimistic compatibility is also saved. Review-safe retention means a candidate merits review, not that it is extraterrestrial. Strict filtering is experimental and can reject intermittent signals or signals visible in OFF scans. Robust detection scores are descriptive and are not calibrated Gaussian significances or false-alarm probabilities.

The injector adds detected power, analytically integrates a Gaussian across rectangular channels, and averages over 32 midpoint samples per stored integration. Peak amplitude is specified before bin/time averaging in units of a pre-injection local ON-scan MAD estimate. It does not simulate voltages, calibrated telescope response or stochastic transmitter self-noise. Intermittent interval edges are sampled numerically; 32/64/128 convergence diagnostics on separately seeded source placements quantify observed differences, rather than claiming exact time integration.

Trial checkpoints are written atomically. At most two trials execute concurrently; results are emitted in the frozen design order. Resume verifies source, config, data and design hashes before reusing a checkpoint. A wall-time stop leaves an incomplete run and preserves checkpoints, including any bounded in-flight work. It does not produce a completed sensitivity claim.

## Uncertainty

Weights are inverse cadence inclusion divided by placements in that component/cell and physical companions in the trial. This keeps family/amplitude cells equally weighted despite four/five allocations and avoids giving collisions twice the benchmark weight.

The placement bootstrap resamples whole trials within component/family/amplitude strata and keeps companion signals and paired pipeline outcomes together. The separate component bootstrap resamples whole linked environments. Both use 10,000 replicates. Degenerate bootstrap bounds are explicitly unresolved. Seven components trigger a few-group warning; neither procedure establishes the approved main study's precision or noninferiority criteria. Conditional Clopper–Pearson diagnostics apply only to independent single-signal placements within one fixed component/cell, never pooled collision companions or independent observing environments.

## Reproduction

Use the Python 3.11 environment and pinned `requirements.lock` described in the repository README. Run from `technosignatures/`, preferably in a separate checkout to preserve reference artifacts.

```bash
# The published selection and API responses are frozen; do not overwrite them.
.venv/bin/python -m research.cohort.acquire
.venv/bin/python -m research.cohort.acquire --offline
.venv/bin/python -m research.cohort.verify --offline research/cohort/evidence/acquisition_offline.json --source-checks --output research/cohort/evidence/source_verification.json
.venv/bin/python -m pytest -q research/cohort/tests --junitxml=research/cohort/evidence/tests_local.xml
.venv/bin/python -m research.cohort.run --smoke --output research/cohort/results/smoke_local
.venv/bin/python -m research.cohort.run --output research/cohort/results/pilot_local
# Only after an interruption, with unchanged source/config/input/design:
.venv/bin/python -m research.cohort.run --resume --output research/cohort/results/pilot_local
.venv/bin/python -m research.cohort.run --output research/cohort/results/reproduction/pilot_repeat
.venv/bin/python -m research.cohort.verify --reference research/cohort/results/pilot_local --repeat research/cohort/results/reproduction/pilot_repeat --output research/cohort/evidence/repeat_local.json
```

Acquisition requires the archive to remain reachable and to retain the selected source bytes. Offline reconstruction requires a complete verified cache. The original pilot integration tests separately require their historical release and range cache; the new cohort unit fixtures do not substitute for those observations.

To reconstruct the metadata selection without network, write to a **new** destination with `python -m research.cohort.frame --offline --output <new-selection.json>`. Creation timestamps will differ; selected IDs, component membership, probabilities and random draws should agree. Avoid refreshing metadata after seeing outcomes while calling it the same prospective selection.

Result ledgers include every trial and physical signal, native control coverage, losses, ambiguity bounds, separate uncertainties and a predetermined spectrogram example. No curve or visualization establishes extraterrestrial origin or full observing-band completeness.
