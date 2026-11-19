# Statistical analysis plan

Version 1.0 · proposed design · 19 November 2026

This document specifies how the research questions in [RESEARCH_PLAN.md](RESEARCH_PLAN.md) should be estimated. It is not a report of new experimental results. Freeze a dated version and its hash after the calibration/access pilot and before opening the locked test outcomes. Changes afterward are labeled amendments or exploratory analyses.

## 1. Populations and estimands

There are three different target populations:

1. The finite, declared observation benchmark plus a specified random injection distribution.
2. Future observing sessions from a particular telescope/receiver regime.
3. Human review of native event workloads under a particular interface and reviewer cohort.

An estimate for one does not automatically apply to the others. Independent placement draws on fixed backgrounds can characterize a conditional injection distribution; they do not provide equally many independent observing environments.

Primary technical estimand: paired difference in end-to-end injected-signal retention between the selected assisted workflow and the strongest validation-selected conventional comparator, over the locked core benchmark distribution. The event pool is fixed when isolating triage; full-chain recovery is also reported from all injections.

Primary productivity estimand: relative reduction in mean active review time for a fixed, probability-sampled native-event workload, comparing the selected assisted interface against the conventional interface. Report evidence correctness, final-action distributions, and injected-case behavior alongside time.

The proposed thresholds are a one-percentage-point noninferiority margin for automated retention and a 30% review-time reduction point estimate with a 95% confidence interval excluding zero benefit. They are operational design choices. Validate their relevance with a domain mentor before freezing them.

## 2. Denominators and notation

For injection i, let:

- `E_i`: signal lies in the predeclared eligible physical/search domain.
- `V_i`: its support intersects the reported searchable, unmasked exposure under the protocol.
- `D_i`: the candidate generator recovers it.
- `G_i`: event grouping preserves it.
- `C_i`: cadence processing preserves it.
- `T_i`: automated triage retains/escalates it.

Eligibility is fixed from physical parameters and metadata, not from whether a detector happened to find it. A signal family cannot be retrospectively excluded because the chosen algorithm performs poorly on it. Masks and unsupported regions are recorded, not removed after observing failure. Explicit out-of-range challenge sets are reported separately from the frozen primary domain.

Report:

- Searchable-domain recovery: `sum(w_i E_i V_i D_i G_i C_i T_i) / sum(w_i E_i V_i)`.
- Full-declared-domain recovery: `sum(w_i E_i V_i D_i G_i C_i T_i) / sum(w_i E_i)`, with nonsearchable cases counted as unrecovered for that declared domain.
- Generation efficiency: `sum(w_i E_i V_i D_i) / sum(w_i E_i V_i)`.
- Conditional triage survival: retained generated injection events divided by all generated injection events reaching that comparison boundary.
- Exposure/coverage fraction: separate time-frequency/path-aware ledger, not a claim that edge-channel fraction alone captures every slope's coverage.

Use the same baseline candidate-generation boundary for paired triage comparisons. If comparing different detectors, use each detector's entire injection-to-outcome chain. An unknown native event is never automatically assigned a negative label merely because it was unmodified.

## 3. Cohort and split construction

Construct a graph linking overlapping raw data, shared acquisition sessions, and shared targets. Assign connected components, not patches, to development/validation/test partitions. Record components, session counts, target counts, cadence counts, receiver, resolution, and interference summaries.

Proposed main target: 60 independent components, divided 30/10/20. If component connectivity prevents that scale, revise sampling or narrow the generalization claim before freezing. Stratification must not break linkage constraints.

Use development data to build/fix models, prompts, image rendering, event definitions, and injection settings. Use validation data to select exactly one conventional comparator and one assisted workflow, including thresholds and retention policies. Access the locked test for the finalized primary comparison once. Subsequent adjustments require new independent evaluation data or an explicitly exploratory label.

The current DIAG_SGR_B2 cutout remains a regression fixture and development example. It is excluded from the locked scientific test.

## 4. Trial matrix and allocation

The pilot contains six signal families × six amplitude levels × 32 randomized placements = 1,152 trials. The planned main injection benchmark contains six × six × 200 = 7,200 trials, before additional multi-signal/out-of-range challenge sets.

Allocate placements across independent test groups, time/frequency positions, and predeclared interference strata. With 20 test groups, the nominal 200 placements per family/amplitude cell can be balanced at ten per group. Balance is a design aid, not proof that conditions are exchangeable.

Peak-amplitude multipliers initially `[0.25,0.5,1,2,4,8]` multiply a recorded pre-injection robust local power-noise estimate. They are not observed detector SNRs. Development-only calibration may replace this grid to span the sensitivity transition; freeze the replacement with the same methods for all compared arms. Keep weak and failed injections in the completeness calculation.

Use documented pseudo-random seed streams for background selection, parameter generation, rendering perturbations, and analysis resampling. Store the full parameter manifest; a seed alone is insufficient when generators or software versions change. Do not give truth manifests or class-revealing identifiers to triage models.

## 5. Recovery matching and attribution

Match candidate/event paths to injection support over actual timestamps. For narrow continuous tracks, use maximum or predeclared quantile path error in physical Hz, with tolerance tied to channel resolution, injected width, and search resolution. For intermittent cases, require specified support overlap and timing agreement. Curved cases use their actual path, not a forced linear truth label.

Freeze tolerances using development examples and resolution arguments. Report continuous path/frequency/drift errors so a broad tolerance cannot hide poor localization. Do not change tolerance to rescue a test outcome.

Multi-signal cases require one-to-one assignment between injected signals and recovered events under the frozen matching cost/threshold. A single recovered event cannot count as recovery of two nearby injections. Secondary hits from one line are grouped before event-level recovery is counted.

Run the same no-injection background through the same pipeline. A pre-existing matching background event makes attribution ambiguous. Preserve such crowded cases; report a conservative recovery estimate treating unresolvable attribution as failure and an optimistic bound counting compatible outcomes, plus the ambiguous fraction. Do not select only empty spectral neighborhoods and then claim performance in crowded data.

## 6. Primary comparisons and uncertainty

Compute paired per-injection outcomes for the assisted and conventional workflows. Let `Delta = recovery_assisted - recovery_comparator`. The proposed technical criterion is a lower 95% confidence bound for Delta of at least −0.01 on the declared benchmark, together with complete failure and coverage accounting.

Provide two uncertainty views:

1. Conditional placement uncertainty for the specified finite benchmark/injection distribution, using methods appropriate to how placements were randomized.
2. Observing-environment uncertainty, resampling whole independent acquisition components while preserving within-component paired cases, weighting, and all stages. Use at least 10,000 paired group-bootstrap replicates as a planned analysis, and report the number of independent groups and sensitivity to group definition.

Report receiver/family/amplitude/interference-stratum results and the macro-average across prespecified signal strata. Also report an exposure-weighted view where sampling weights are justified. Weights are benchmark definitions; no weights are described as alien-transmitter prevalence.

Bootstrap intervals can degenerate when every observed outcome is identical or events are extremely rare. A zero-width resampling interval is not evidence of zero future risk. Add exact binomial bounds only when independent Bernoulli assumptions are defensible for the claimed population; otherwise label uncertainty unresolved, show group-level outcomes, and gather more independent data or narrow the claim. Do not substitute the number of reused cutouts for independent sessions.

If subgroup sizes are too small, report intervals and insufficient precision rather than interpreting a nonsignificant difference as equivalence. A proposed loss alarm of more than three percentage points in a core stratum triggers investigation, even when the overall average meets its criterion; it is an engineering alarm rather than a new confirmatory hypothesis test.

## 7. Rare-loss sample-size reasoning

For n independent trials with zero missed injected signals, the one-sided 95% upper bound on the loss probability is:

`q_upper = 1 - 0.05^(1/n)`.

Thus at least 299 independent zero-loss trials are needed to bound the loss below 1% under that simple model. With only 80 independent zero-loss trials, the upper bound is about 3.68%. This is why the proposed human-review injection sample cannot establish a 99% human-retention guarantee.

These calculations are conditional illustrations, not the power analysis for the clustered main experiment. Correlation, variable difficulty, or limited acquisition diversity changes what may be inferred. Several thousand placements across twenty groups do not establish a one-percent upper bound for arbitrary future sessions.

After the pilot, estimate paired discordance rates and between-group variation. Simulate the planned allocation to estimate the probability of excluding a one-percentage-point degradation under several true effects and failure-clustering scenarios. Select a fixed sample size before the test. If sufficient precision is infeasible, explicitly choose a wider claim/retention policy or keep the workflow in ranking/summary mode.

For individual completeness cells, 200 independent Bernoulli trials have a worst-case normal-approximation 95% half-width of roughly 6.93 percentage points. Clustering can increase uncertainty. A 7,200-case total does not imply sub-percent precision in every amplitude/morphology cell.

## 8. Review workload and native events

Measure native retained-event counts per searched time-bandwidth exposure and per complete cadence, distinguishing duplicated hits, grouped events, escalations, and independently supported interference. Record truncated catalogues, masked volume, unavailable scans, and technical failures.

Do not calculate alien/terrestrial precision using all native events as negatives. A true false-positive rate can be estimated only for a clearly defined reference-negative subset with defensible labels, and its limited scope must be named. Use “native review burden” for the operational count whose origin is unknown.

For ranking methods, show recovery at fixed review budgets, e.g. top 10/50/100 events per declared workload, only where meaningful for actual catalogue size. Count all unreviewed generated injections as not reviewed at that budget, and distinguish this from permanent rejection. Do not hide an upstream top-50 truncation inside a downstream top-50 comparison.

## 9. Human-review analysis

The proposed study has 240 cases (160 native and 80 injected), each seen under two conditions by different reviewers, giving 480 assignments across four reviewers. Assign case-condition pairs using blocked randomization; a reviewer never sees another rendering/condition of the same underlying event. Group near-duplicates together when assigning reviewers.

The primary time endpoint is the mean active review time on the native workload; injected cases are companion checks and do not set the benchmark's native prevalence. If native cases are enriched for difficulty, use recorded selection probabilities for the main workload estimate and show the unweighted challenge result separately.

Calculate `time_reduction = 1 - mean_time_assisted / mean_time_conventional`. Estimate uncertainty using case/acquisition-aware paired or mixed-effect analysis with reviewer as an explicit factor, preserving the randomized assignment structure. Four reviewers do not support a universal statement about all astronomers; use the observed cohort scope and report reviewer-specific effects.

Predefine active timing, pause handling, maximum session duration, missing-data rules, and technical interruptions in a pilot. Report timeouts and failed assistance both as system failures and in workload/cost accounting; do not drop slow failed requests. Show end-to-end elapsed latency separately from active reviewer time.

Adjudicate evidence correctness and review actions independently of fluent prose. Faster review with materially poorer evidence or loss of detectable test signals does not satisfy the usefulness criterion. When unresolved-native labels prevent a definitive correctness judgment, report agreement and escalation rather than inventing origin truth.

## 10. Model calibration, factuality, and abstention

If a small model produces class/retention probabilities, calibrate them using validation data and a named procedure. Evaluate calibration against the actual labeled task, not against extraterrestrial-origin probability. An LLM confidence number is not presumed calibrated.

Score evidence claims against measured features: units, frequency, slope, pointing role, scan time, presence/absence and reference citations. Separate numerical error, unsupported inference, incorrect citation, invalid schema, and missing information. Use domain-expert adjudication for ambiguous claims. Report automation failure and retain/escalate defaults in the denominator.

Show risk-versus-coverage curves for any selective classifier, including the review cost of abstention. Pure ranking/summary assistance may retain all events; that protects automated retention by design but does not establish human decision quality. Human effects require their own evidence.

## 11. Ablations and multiplicity

Predeclare one primary assisted workflow/comparator pair. Metadata-only versus image-only versus joint input, retrieval, prompt variations, held-out signal families, alternate normalizations, and alternate grouping rules are secondary analyses unless separately powered and preregistered.

Select model/prompt/threshold combinations on development/validation only. Report the full screened variant count and selection rule. Do not choose the winner on the locked test. If making multiple confirmatory secondary tests, specify a correction such as Holm before evaluation; otherwise label them exploratory with intervals rather than selectively presenting favorable p-values.

## 12. Failure handling and release tables

Report a complete trial flow: selected observations, unavailable/corrupt files, eligible/searchable injections, preprocessing failures, hits, events, cadence losses, triage decisions, model failures, and reviewer assignments. Reasons are mutually interpretable and preserve the first failure stage.

Required final tables/figures:

1. Cohort, independent groups, split composition, masks, and searched exposure.
2. Injection-parameter coverage and simulator checks.
3. Stage-by-stage loss table for all arms.
4. Completeness curves/heatmaps with uncertainty and ambiguous-attribution bounds.
5. Recovery versus review budget and native burden versus recovery.
6. Native review-time effect with reviewer/case uncertainty and evidence-quality outcomes.
7. Runtime, memory, inference cost, failures, and latency.
8. Subgroup and held-out-domain failure analysis.
9. Reproduction checks and all deviations from the frozen analysis plan.

No transmitter-prevalence upper limit is included in the initial project. Such a result would additionally require calibrated flux sensitivity, beam/distance/time coverage, a specified transmitter population, and an explicit likelihood for zero confirmed detections.
