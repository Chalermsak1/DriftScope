# Completed C-band access and sensitivity pilot — 20 November 2026

The complete-cadence access pilot and the reduced-cohort development experiment are reproducible. **Representative-cohort sensitivity is still incomplete: seven linked components are available against the approved target of 60.** No LLM or extraterrestrial-origin claim is introduced.

## Observational evidence

All **42 prospectively selected original files** yielded seven valid six-scan cadences. The extracted arrays contain **983,040 usable recorded-power samples** across **960 stored integrations**, with 17,523.4666 seconds of summed ON/OFF exposure, including 8,761.7333 ON seconds. Every stored integration is retained within one preselected 1,024-channel tile per cadence, approximately 2.86 kHz wide. Gaps are not counted as exposure. These cells are not 983,040 independent observing environments.

All source-header and cadence checks pass. Independent left/right HDF5 hyperslabs concatenate to the same samples. Offline reconstruction consumes zero network bytes and reproduces every power, frequency, integration-start-time and mask array. Source arrays remain unchanged; analysis uses immutable floating-point copies. Every accelerated-search score map matches the scalar reference byte for byte across all 42 scans, with identical hits, coverage and tiles. Whole-original checksums, receiver hardware and calibrated flux sensitivity remain unverified.

The frozen archive frame has 12,375 indexed rows, 251 parent cadence/product proposals and 182 frequency-eligible proposals in seven linked components. Linkage precedes frequency filtering, preserving dependency bridges. All seven components are selected, with one cadence each. The component proposal counts/weights are 2, 21, 5, 20, 4, 2 and 128; the largest contributes 70.33% of total design weight. The [catalogue audit](catalogue_coverage_audit.json) verifies frame/canonical-response hashes for 88 queries, including 39 saturated parents resolved by bisection. Completeness is conditional on these queries. All archived effective metadata-query URLs use HTTP after redirects, so hashes establish retained-record integrity rather than authenticated catalogue provenance; source byte ranges separately enforce HTTPS.

## Experimental evidence and the correction

Each full matrix has **1,152 trials and 1,344 physical signals**: six families × six amplitudes × 32 randomized placements per cell, allocated as four or five placements across each component. Collision companions share a trial and benchmark weight. One companion is outside the declared starting-frequency domain; it remains recorded, leaving 1,343 eligible signals. Both full versions finish with zero technical failures.

The first evaluator independently assigned local and cadence events. Its conservative result was 521 new versus 544 legacy review-safe recoveries, with weighted rates **34.0832% versus 38.4275%**. It identified 45 ancestry/assignment conflicts. That result and exact implementation are preserved at revision `df4486e` and in the [v1 report](MILESTONE_REPORT_V1.md).

The [v2 amendment](matching_amendment_v2.json), declared before v2 outcomes, fixes post-search attribution. It admits a global assignment only when the cadence event has a compatible actual local parent and hit, maximizes one-to-one matching cardinality before minimizing path error, and reserves those ancestors before assigning remaining local stages. Missing/reused parents are structural failures. The rows now retain hit/event/cadence IDs, path errors and active-integration counts.

All 1,152 injection parameter sets, allocations, source inputs and detection settings are identical between versions. Native-control scientific records and every recorded per-trial injection/blind-output metric match exactly. Blind search, grouping and cadence algorithms did not change. **All 45 former ancestry-conflict signals have a valid retained chain under v2.** This is a development correction after viewing v1 results, not an independent confirmatory experiment or a change in physical detector sensitivity.

## Corrected benchmark results

| Conservative outcome | Unweighted recoveries / 1,343 eligible signals | Cadence/design-weighted recovery |
|---|---:|---:|
| Complete-support search, review-safe | 566 | 39.6786% |
| Legacy search + same downstream review-safe rules | 544 | 38.4275% |
| Complete-support search, strict-policy retention | 433 | 28.0718% |
| Legacy search + same downstream strict-policy retention | 421 | 29.0252% |

These are benchmark averages over the declared injection distribution, not transmitter-prevalence or sky-completeness estimates. Raw and weighted strict results differ in ordering because component weights differ substantially. The new arm is not uniformly better under both policies. Strict-policy retention includes coverage-unknown escalation: 52 of the 433 new retained signals and 76 of the 421 legacy retained signals are escalated rather than fully passing the strict gates. The remaining 381 and 345 respectively have a `retain` decision. These totals must not be described as confirmed three-ON/OFF-clean events.

The review-safe weighted difference is **+1.2511 percentage points**. Exploratory 95% percentile intervals are **+0.5259 to +2.1576 points** under conditional placement resampling, and **+0.8566 to +2.6667 points** under whole-component resampling. There are 10,000 paired replicates for each procedure. Seven components, a dominant weight, one cadence per component, and development after v1 outcomes prevent confirmatory superiority/noninferiority claims. The component bootstrap is not a design-based confidence interval for every catalogue cadence; within-component cadence-selection variance is unidentifiable here.

The corrected [curves](../results/pilot_v2/cohort_sensitivity.png), [cell results](../results/pilot_v2/sensitivity_cells.json), [uncertainty](../results/pilot_v2/uncertainty.json) and [predetermined before/after spectrogram](../results/pilot_v2/cohort_before_after.png) are retained. Both sides of each spectrogram use common intensity limits; OFF scans receive zero synthetic addition. The example was chosen by design order, not by recovery success.

## Coverage, losses and actual search stress

The complete-support search evaluates **6,077,016 valid discrete full-scan tracks**, compared with **5,692,140** under the legacy common guard: **384,876 additional tracks**. No selected source samples are masked or unscorable. This is completeness only for the declared nearest-channel linear path/boxcar model within these tiles; it excludes full observing bandwidth, arbitrary morphologies and partial-time searches.

| Exclusive first loss, before policy veto | New arm | Legacy arm |
|---|---:|---:|
| Outside declared starting domain | 1 | 1 |
| Unsearched/unavailable support | 28 | 58 |
| Below threshold | 692 | 680 |
| Frequency suppression or assignment | 0 | 6 |
| Catalogue cap or assignment | 0 | 3 |
| Grouping or assignment | 1 | 0 |
| Cadence association | 52 | 50 |
| Ambiguous attribution | 4 | 2 |
| Retained before strict veto | 566 | 544 |

The three legacy `catalogue_truncation_or_assignment` cases are assignment losses: actual candidate-cap truncation is zero throughout these controls and injection trials. Stage labels retain `or_assignment`; they are not isolated causal ablations. Strict persistence removes a further 133 new and 123 legacy signals. No OFF-coincidence veto is triggered in this matrix. Review-safe retention means review eligibility, not a technological-origin classification.

The uninjected controls yield **zero candidates at threshold 10 in either arm**. This does not establish a zero false-alarm rate, validate a high-RFI review burden, or establish OFF-veto sensitivity. The separate explicitly synthetic crowding regression reconstructs 85 uncapped legacy candidates, a 50-candidate prefix and 35 cap losses. Candidate/association counts are not independent transmitters.

Remaining association/grouping losses, and the intermittent case that exits the band during an active scan, remain traceable rather than silently removed. Matching scores are descriptive median/MAD statistics, not calibrated Gaussian significances or origin probabilities.

## Verification and reproducibility

**159 tests pass**, with zero failures, errors or skips. Adversarial ancestry tests cover a closer but incoherent alias, duplicate-parent prevention, inactive truth, missing/reused parents and inconsistent actual hits. Controlled interruption/resume and bounded concurrency reproduce scientific ledgers on synthetic integration fixtures.

A fresh full v2 execution reproduces **11 top-level scientific JSON/JSONL files and all 1,152 trial checkpoints exactly**, including checkpoint IDs. The v1 matrix independently passes the same full-repeat requirement. Repeated executions do not increase independent sample size. See [v2 repeat verification](repeat_verification_v2.json), [v1 verification](repeat_verification.json), [delivery validation](delivery_validation.json), and [JUnit](tests_complete_pipeline.xml).

All 63 installed distributions match `requirements.lock` on the recorded Python 3.11.16/macOS ARM64 environment. This is not a clean-install or cross-platform reproduction claim; PNG bytes and wall time are outside the exact scientific comparison. The original 31-file experiment and eight-file approved plan remain unchanged. [Execution notes](EXECUTION_NOTES.md) retain the intermediate console-log collision; scientific files and both independent repeats are unaffected.

Quadrature diagnostics use one separately seeded placement per family/component. The largest observed 32-versus-128 time-sampling difference is **1.41084% of continuous peak** at an intermittent edge; other audited families are below 0.012%. These are observed diagnostics, not exhaustive error bounds. The injector models additive detected power with rectangular channels/time integration; beam/voltage response, stochastic transmitter noise and flux conversion are not calibrated.

## Open main-study gates

The 60-component target remains unmet: at least 53 additional qualifying linked components are needed under the current design, without splitting existing dependencies to inflate the count. Additional cadences within components, more prospectively selected frequency tiles, independently verified receiver/observing logs, realistic RFI/OFF tests and calibrated physical sensitivity remain necessary. API completeness is not independently established sky/archive completeness. All current data are development data; locked tests remain untouched.

The conventional pipeline now has reproducible multi-group evidence and detailed losses, but the representative sensitivity assessment is not finalized. LLM development remains gated. Follow the [module guide](../README.md) and [backlog status](../BACKLOG_STATUS.md) for reproduction and the remaining engineering work.
