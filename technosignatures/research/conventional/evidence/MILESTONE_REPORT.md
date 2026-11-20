# Conventional pipeline development: validated increment

**Status: PASS for the executed development scope, with open scientific gates.**

The new module implements coverage remediation, path-based event grouping, timestamp-aware cadence association/filtering, and cohort/sensitivity infrastructure. Representative-cohort sensitivity is not complete: the current source-sample cohort does not meet the approved acquisition, independence, receiver, or frozen-analysis requirements.

## 1. Evidence and preservation

- **115 tests passed**, zero failures, errors, or skips: [tests_final.xml](tests_final.xml).
- **17 complete-repeat comparisons passed**, including exact score/power-array hashes: [verification.json](verification.json).
- The 31 original experiment files and eight approved-plan files match their recorded hashes.
- All 139 pre-existing local project files were checked for byte preservation after work/testing; see [delivery validation](delivery_validation.json).
- Existing Python 3.11/macOS ARM64 pinned environment; no new dependencies and no fresh environment installation claim.
- No LLM, locked test access, astrophysical detection, or population sensitivity estimate.

The [development log](DEVELOPMENT_LOG.md) retains failures and their corrections. The [design record](../DESIGN.md), [schemas](../SCHEMAS.md), and [test strategy](../TEST_PLAN.md) explain the implementation and scientific limits.

## 2. Coverage remediation

| Quantity on original real regression observation | Historical detector | V2 |
|---|---:|---:|
| Evaluated discrete linear boxcar paths | 390,404 | 489,730 |
| All physically valid discrete paths for this grid | 489,730 | 489,730 |
| Valid discrete paths omitted by a common guard | 99,326 | 0 |
| Candidate cap | 50 | None |

The new search uses each drift's own valid starting interval and excludes paths whose full time/boxcar footprint intersects a mask. Tile cores own starting channels uniquely, while halos supply all drift-crossing samples. Per-drift score normalization uses the whole usable profile, so tile boundaries do not define separate statistics.

The whole-band/tile score maps agree at absolute tolerance `2e-12`, with identical hit IDs. Additional scalar-enumeration tests cover several tile widths, signed drift, masked samples, and every score/support cell on small observations.

These are **discrete search-domain** counts. They do not establish all-morphology sensitivity or the fraction of extraterrestrial signals detectable. Expanding the normalization domain changes scores; equal thresholds across arms do not equate false-alarm rates.

The original ten sampled-power scenarios retain their original convention and are separate from the physically integrated trials. V2 additionally recovers `low_common_guard`, `high_common_guard`, and `low_edge_inside_input`, while the weak/intermediate examples remain below recovery and the out-of-drift challenge remains unrecovered. Seven of the ten deterministic cases recover in v2 versus four previously; this is an engineering check, not an estimated population rate.

Evidence: [coverage_remediation.json](../results/development_v2/coverage_remediation.json), [coverage figure](../results/development_v2/coverage_comparison.png).

## 3. Grouping and truncation

On the original fully synthetic 80-line stress fixture:

| Quantity | Result |
|---|---:|
| Known physical injected tracks | 80 |
| Legacy retained physical signals, one-to-one matched | 50 |
| V2 thresholded local-max hits | 506 |
| V2 grouped events | 187 |
| V2 recovered physical signals, one-to-one matched | 80 |

Hit count, event count, and physical-signal recovery are distinct. V2 retains partial-overlap aliases, so 187 events do not imply 187 sources. Complete-link grouping prevents tested transitive merges and preserves divergent/crossing paths; it does not claim general deblending optimality.

The supplementary nearby/opposite-drift two-line fixture recovers **2/2 physical tracks** in both v2 and the old arm. Its two executions are identical; no gain is inferred where the comparator already succeeds. There are 20 v2 hits and nine events in that case, again illustrating residual aliases.

Evidence: [crowded_stress.json](../results/development_v2/crowded_stress.json), [paired_end_to_end.json](paired_end_to_end.json).

## 4. Conditional sensitivity development

Executed 48 continuous-linear trials on the original real development cutout: six amplitude levels and eight randomized placements at each level. Full parameters and seeds are saved; placements include fractional channel phase, both drift signs, and edges. Every signal has an outcome row. The two arms receive identical time/channel-integrated additions.

| Continuous peak amplitude / local power sigma | Eligible trials | Searchable v2 trials | Legacy retained | V2 retained |
|---:|---:|---:|---:|---:|
| 0.25 | 8 | 8 | 0 | 0 |
| 0.5 | 8 | 8 | 0 | 0 |
| 1 | 8 | 8 | 0 | 0 |
| 2 | 8 | 7 | 4 | 5 |
| 4 | 8 | 7 | 5 | 7 |
| 8 | 8 | 7 | 5 | 7 |
| **Total** | **48** | **45** | **14** | **19** |

V2 full-declared-domain recovery is 19/48 (39.58%); searchable-domain recovery is 19/45 (42.22%). Three physically declared placements lack compatible searched support and remain failures in the full-domain denominator. The other 26 misses occur at generation; none is silently excluded. There are zero technical-failure outcomes and zero terminal native-match ambiguities in this set.

The paired point difference versus the historical arm is +5/48, or +10.42 percentage points, **on this fixed development experiment only**. There is one acquisition component. The group-uncertainty routine therefore returns no observing-environment interval. No per-cell conditional-placement interval has yet been supplied in this increment; eight placements per cell are insufficient for a precise curve, and these point summaries do not establish statistical superiority or representative completeness.

The frozen old detector and new complete algorithm have different profile-normalization domains and candidate handling. This comparison does not isolate the causal contribution of any individual stage and does not replace a validation-selected established comparator.

The generated full design contains **1,152 unexecuted trials / 1,344 physical signals** across six families. Collision trials contain two signals. Generating that manifest is not execution of the full pilot or main study.

Evidence: [conditional_sensitivity.json](../results/development_v2/conditional_sensitivity.json), [executed manifest](../results/development_v2/executed_development_design.json), [curve](../results/development_v2/conditional_recovery.png).

## 5. Physical integration

Gaussian power is integrated analytically over channel bins, then averaged in time by midpoint quadrature. Independent tests verify total profile power, drift-dependent centroid, a SciPy adaptive-integral reference, exact shams, and source-array immutability.

At the configured maximum drifts, relative peak differences for 64 versus 128 time subsamples were approximately `3.97e-5` for the C-band fixture and `9.76e-5` for the L-band engineering regime, below the declared `1e-3` criterion. The executed 32-subsample values also differ from 64-subsample values by approximately `1.59e-4` and `3.91e-4` in those specified checks. These checks validate the declared Gaussian rectangular-bin model, not an instrument-specific response or all six signal families.

Evidence: [integration_convergence.json](../results/development_v2/integration_convergence.json).

## 6. Real-cadence association and filtering

Four controlled additions were executed on the real, previously candidate-selected `mlc1` six-scan cutout. Actual MJD-derived gaps and ON/OFF roles are preserved. Native/no-injection controls were processed first. Signal truth is used only after blind search, grouping, association, and policy decisions.

| Engineering case | Review-safe | Strict experimental policy | Measured reason |
|---|---|---|---|
| Persistent ON-only chirp | Retain | Retain | Three coherent ON events; OFF forced scores below threshold |
| Same chirp with 0.1 OFF response | Retain | Retain | Actual added OFF response remains below the configured evidence threshold |
| Same chirp with equal OFF response | Retain/escalate | Reject | OFF coincidence detected |
| First ON scan only | Retain/escalate | Reject | Missing three-ON persistence |

The strict rule's two losses are visible at the cadence stage. The safe policy retains all four specified cases; that deterministic observation is not a universal retention guarantee. Matching error is approximately 0.437 channels for the persistent global chirp and 0.586 channels over active support for the first-ON case.

The weak OFF example is instructive: its OFF forced scores are approximately 3.27, 2.30, and 1.31, below the threshold of six. Passing the strict rule therefore does not establish physically zero OFF response or extraterrestrial origin. The equal-OFF scores are approximately 29.49, 24.86, and 24.76 and do trigger the rule.

Unit tests additionally cover subthreshold forced evidence, missing/unsupported/masked OFF coverage, and the inactive-support matching defect found during integration. Unknown coverage escalates rather than being counted as absence.

Evidence: [cadence_cases.json](../results/development_v2/cadence_cases.json), [before/after spectrograms](../results/development_v2/integrated_cadence_before_after.png).

## 7. Representative-cohort access and remaining gates

The first independent seven-day C-band metadata window was empty. The separately documented fixed-2018 frame returned **102 archive rows**. Initial name/time patterns produced 27 possible sequences in six linked acquisition/target groups. Current metadata checks retain **two proposals / two components**, with 25 rejected sequences and reasons preserved.

The initial selected AND_X proposal failed the inherited one-arcsecond ON consistency criterion. After adding the same geometry to metadata selection, the selected AND_XI proposal passed every actual source-header and six-scan integrity check. The successful probe accessed **393,216 bytes (384 KiB)** of bounded ranges. The original source files are much larger; no full-file checksum or spectral-sample acquisition is claimed.

The strict one-arcsecond criterion is an unvalidated C-band engineering assumption and excludes many plausible sequences with small coordinate variations. This selection coverage must be assessed against instrument pointing/beam knowledge before defining a scientific cohort. Its failures do not demonstrate corrupted or unusable observations.

The earlier eight candidate-selected released cutouts form five conservative connected components under the available target/session/raw linkage and remain development data. They do not repair the representative-cohort gate.

Still required for representative sensitivity:

1. A justified receiver/pointing/exposure definition and broader candidate-independent sampling frame.
2. Acquired and verified spectral samples from sufficiently many independent complete cadences; the main target remains 60 components.
3. Data-volume, processing-memory, and transfer feasibility for that cohort.
4. Conditional-placement intervals plus environment-aware uncertainty on actual independent groups.
5. Established comparator/workload calibration, complete morphology/realism checks, and a frozen grouped split/protocol before locked outcomes.

Evidence: [refined frame](archive_frame_2018_refined.json), [successful source-header probe](cohort_header_probe.json), [failed proposal](cohort_header_probe_pointing_failure.json).

## 8. Operational limits and next increment

The successful development execution took approximately **100.09 seconds** and reached approximately **2.11 GB process peak RSS** in the recorded environment. This is an observed development run, not an isolated performance benchmark or a cohort-scale forecast. Streaming and tighter process-memory control remain future work.

This increment validates the stated implementation and controlled cases. It does not close representative sensitivity, production-scale searching/deblending, all-morphology injection physics, statistical precision, or locked-evaluation gates. See [the execution delta](../BACKLOG_STATUS.md) for concrete next milestones.
