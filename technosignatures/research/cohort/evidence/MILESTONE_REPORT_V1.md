# Completed access pilot and first full sensitivity matrix

All **42 selected source files** yielded seven complete cadences: **983,040 usable recorded-power samples**, 960 stored integrations, and 17,523.4666 seconds of summed ON/OFF exposure within the selected narrow frequency tiles. Every header/cadence validation passed. Offline reconstruction uses zero network bytes and reproduces all scientific arrays. All 42 accelerated-search score maps match the scalar reference byte for byte, with identical hits and coverage.

The first full matrix executed **1,152 randomized trials / 1,344 physical signals** with zero technical failures. One companion lies outside the declared starting-frequency domain, leaving 1,343 eligible signals. A fresh full execution reproduces all 13 top-level scientific record/check comparisons and every one of the 1,152 trial checkpoints exactly. The original 31-file experiment and eight-file approved plan remain unchanged. **154 full-suite tests pass.** See [delivery validation](delivery_validation_v1.json), [source verification](source_verification.json), [repeat verification](repeat_verification.json), and [JUnit](tests_pilot_v1.xml).

| Conservative outcome | Unweighted recoveries | Cadence/design-weighted recovery |
|---|---:|---:|
| New review-safe | 521 | 34.0832% |
| Legacy + same downstream review-safe | 544 | 38.4275% |
| New strict experimental | 402 | 24.4046% |
| Legacy + same downstream strict | 421 | 29.0252% |

The new-minus-legacy review-safe difference is **−4.3443 percentage points**. Exploratory 95% percentile intervals are −6.8173 to −1.9142 points conditional on the selected backgrounds/placements, and −5.7454 to +0.6556 points under whole-component resampling. These are not confirmatory main-study confidence statements or a design-based variance estimate for all catalogue cadences.

The new arm evaluates **6,077,016** valid discrete full-scan tracks, compared with **5,692,140** under the legacy common guard: **384,876 additional tracks**. No selected source samples were masked or unscorable. Nevertheless, greater geometric coverage does not establish higher end-to-end recovery. First-loss counts include 28 new versus 58 legacy unsearched signals, but the conservative new evaluator records **45 cadence ancestry/assignment conflicts**. There are also 53 association losses in each arm, 692 versus 680 below-threshold losses, and other separately recorded grouping/suppression/ambiguity losses. These are stage observations, not isolated causal effects of individual code changes.

The uninjected controls produce zero candidates at threshold 10 in both arms, and no native cap truncation. This does not establish a zero false-alarm rate or validate behavior in high-RFI environments. The separate synthetic crowding regression demonstrates 85 uncapped legacy candidates, a 50-candidate prefix and 35 cap losses.

The matching audit found that independent local and cadence assignments may select different aliases of the same injected profile. Requiring a recorded parent prevents fabricated survival chains but can conservatively undercount feasible chains. The first single-cadence smoke originally counted six new recoveries; after this guard it counts five, equal to the legacy arm. Both records remain available. A subsequent joint ancestry assignment correction must be documented as development after these outcomes and evaluated on the same fixed arrays; the v1 result must remain preserved.

The main **60-component gate remains false**: only seven linked components exist in this frame, with one cadence each. One component contains 128 of 182 eligible proposals and contributes about 70% of the total design weight. Placement replication does not create independent observing environments or identify within-component cadence variation. Whole originals/checksums, receiver hardware, calibrated flux sensitivity, full-band/sky completeness and locked-test evaluation remain unverified. No LLM or extraterrestrial-origin claim is introduced.

Numerical quadrature checks cover one separately seeded placement per family/component. The largest observed 32-versus-128 time-sampling difference is 1.41084% of continuous peak for an intermittent edge; all other audited families are below 0.012%. These are observed diagnostics, not exhaustive integration error bounds.

The source manifest inside `results/pilot_v1/` identifies the exact implementation for this historical experiment. Reproduce at its corresponding Git revision rather than silently substituting a later evaluator. See [execution notes](EXECUTION_NOTES.md) for the retained console-log collision; the independent scientific records and exact numerical repeat are unaffected.
