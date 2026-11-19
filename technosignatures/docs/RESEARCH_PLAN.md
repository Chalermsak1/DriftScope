# Research plan: preserving signal recovery while reducing radio SETI review burden

Version 1.0 · 19 November 2026 · Asia/Bangkok

Status: proposed research programme, grounded in the completed first experiment. Proposed thresholds, sample sizes, budgets, and schedules below are design choices, not measured performance or established field standards. The existing experiment and its evidence remain unchanged.

## 1. Scientific objective

Develop an independently reproducible method that reduces the human effort required to assess narrowband radio candidates while measuring and limiting preventable loss of plausible signals throughout the search pipeline.

The central question is:

> Under a fixed observing dataset and review budget, can evidence-grounded AI assistance improve candidate assessment while preserving the recovery of independently injected signals across realistic interference and signal conditions?

The first scientific product is a measured selection function and an account of where signals disappear. A language model becomes useful only if it improves a defined part of that process. Successful outcomes include an effective conventional method, a useful AI assistant, or a well-supported negative result about AI assistance.

Extraterrestrial technology has no confirmed training set. An unusual signal, a recovered injection, and a confirmed extraterrestrial transmitter are different evidential categories. The project can measure the first two. Confirmation of the third requires observational evidence beyond this benchmark.

The search is initially limited to narrowband drifting radio emission in one telescope/receiver configuration. It cannot optimize the search for all possible technology or determine the probability that extraterrestrial life exists.

## 2. What the existing experiment establishes

The project already contains a real C-band diagnostic cutout labeled DIAG_SGR_B2, an unchanged source file with a pinned checksum, one deterministic Gaussian power injection, an independent drift search, thirteen passing tests, and nine exact repeat-run comparisons. The strongest recovered candidate has drift +1.01961 Hz/s for injected +1.00000 Hz/s, maximum path error 0.623 channel, and robust score 42.54. These facts are recorded in [the completed report](../results/run_001/REPORT.md).

This establishes functional software, not a population estimate of detection efficiency. In particular:

| Current property | Consequence for the research plan |
|---|---|
| One 45.8-second observation, 32×1024 samples | It cannot represent diverse observing sessions or interference conditions. |
| Deliberately strong, deterministic injection | It does not locate the detection threshold or characterize weak-signal losses. |
| Gaussian power samples without integration smearing | Physical realism must be expanded and independently checked. |
| 764 of 1024 possible start channels searched | Current common-band search coverage is 74.609%; masked/edge coverage must enter the denominator. |
| At most 50 candidates retained | This cap can silently remove injected signals in crowded data unless truncation is recorded. |
| Frequency-only suppression within six channels | Nearby independent signals may merge; secondary peaks from one signal may remain. |
| Three post-injection search maxima | A hit, an event, and a distinct source must be represented separately. |
| No complete ON/OFF cadence | The experiment cannot assess sky localization or cadence-based interference rejection. |
| Score is median/MAD standardized track power | Its threshold is not a Gaussian significance, false-alarm probability, or turboSETI SNR. |

These are expected limits of the first milestone. They now become explicit research tasks.

## 3. Contribution and related-work position

Signal injection and AI filtering already have substantial precedents. SETIGEN provides injection tools; Ma et al. demonstrate a deep-learning search; Choza et al. investigate sensitivity and search-pipeline effects. See [the evidence register](LITERATURE_AND_NOVELTY.md).

The proposed contribution is therefore a specific combination to be tested for originality: a reproducible loss audit through detection, grouping, cadence processing, and AI triage, paired with expert review-time measurements under an explicit signal-retention constraint. The novelty review must compare the exact proposed outputs with existing papers and released code before a publication claim is made.

The programme has two separable deliverables:

1. **Methods benchmark:** physically checked injections, session-held-out observations, event-level recovery, coverage accounting, and calibrated limits on what the benchmark establishes.
2. **Decision-support experiment:** a controlled comparison of conventional, learned, and language-model review assistance using the same cases, with cost and failure analyses.

The second deliverable is conditional on the first. A duplicate or non-informative benchmark is redesigned before expensive model development.

## 4. Scientific questions and hypotheses

| ID | Question | Testable outcome |
|---|---|---|
| RQ1 | Where does the pipeline lose injected signals? | Recovery at every stage, stratified by amplitude, width, drift, intermittency, frequency position, and background. |
| RQ2 | How much do realism and normalization change apparent sensitivity? | Paired recovery differences between simple and instrument-aware injections; cross-check of amplitude conventions. |
| RQ3 | Can conventional improvements reduce review burden? | Compare event grouping, cadence features, and a small feature model before using an LLM. |
| RQ4 | Does an LLM provide additional value? | Review effort and retained-signal recovery versus the strongest validation-selected non-LLM comparator. |
| RQ5 | Does additional context help? | Controlled metadata-only, image-only, joint-input, and evidence-retrieval ablations. |
| RQ6 | How stable is performance on unfamiliar data? | Separate held-out-session, held-out-target, held-out-morphology, and optional new-receiver evaluations. |

Primary AI hypothesis: a selected assistance workflow yields at least 30% lower mean active review time on the locked benchmark, with a positive confidence-bound time benefit and no more than a one-percentage-point loss in paired automated injection retention relative to the selected comparator. These are proposed decision criteria. Their evidential scope is the declared benchmark distribution; a broader deployment claim requires broader independent observations.

The primary scientific comparison has a meaningful negative outcome: AI adds no benefit, or its measured retention/cost trade-off is worse. We then retain the better conventional workflow and report the boundary conditions.

## 5. Measurement model: coverage, detection, and survival

Represent a possible signal by parameters theta: frequency, amplitude, width, drift and curvature, modulation/duty cycle, timing, and apparent response in different pointings. Let x describe the observing conditions.

Within the declared signal/observation domain:

`P(final retained | theta,x) = P(candidate generated | theta,x) × P(final retained | generated,theta,x)`.

The second term includes grouping, cadence decisions, triage, technical failures, and review policy. Its value cannot repair a zero first term. Report both terms, their product measured directly, and the additional fraction of the original frequency/time domain that was searchable.

Do not infer an extraterrestrial discovery rate from these quantities without a justified transmitter population model. Benchmark weights describe a chosen test distribution, not a distribution of alien civilizations.

Define units before counting:

- **Scan:** one contiguous telescope observation.
- **Cadence:** an associated sequence of ON/OFF scans, using actual pointing and timestamps.
- **Hit:** one thresholded drift/frequency maximum.
- **Event:** grouped compatible hits associated with a putative track across a scan/cadence.
- **Injection trial:** one synthetic signal or explicitly declared multi-signal scenario applied to an immutable background.
- **Independence group:** connected observations sharing acquisition sessions, targets, or overlapping raw data; used for split construction.

Every injection gets a stage ledger: input accepted → searchable support → preprocessed → generated as a hit → preserved through grouping → preserved through cadence filtering → sent for review → retained/escalated/rejected. Store the first loss reason and every later applicable decision. Never count only the signals that reached the model when reporting end-to-end completeness.

## 6. Data strategy and access feasibility

Use the public [Breakthrough Listen archive](https://breakthroughinitiatives.org/opendatasearch) and associated [data-release documentation](https://seti.berkeley.edu/listen2019/overview.html) as candidate sources. Access to a suitably diverse complete-cadence cohort has not yet been verified for this project.

Prefer one GBT receiver initially. C-band preserves continuity with the current sample; if complete C-band cadences are insufficient or acquisition is impractical, select a better documented receiver before validation/test assignment. Keep receivers separate rather than treating a change of receiver as ordinary random variation.

Build two sampling frames:

1. Randomly/stratifiably selected frequency-time regions from complete cadences, chosen without reference to injection location or detector successes. These support selection-function measurements.
2. Native candidate events selected from an unmodified archive search. These support realistic review-burden measurements. Preserve sampling probabilities when enriching rare difficult cases.

Do not use only visually clean backgrounds. Stratify by interference occupancy, bandpass position, missing data, scan quality, receiver, date, and time resolution. Include crowded regions as a declared stress stratum; retain an account of masked regions rather than quietly dropping them.

Proposed scale:

| Stage | Data target | Permitted conclusion |
|---|---|---|
| Access pilot | 4–8 complete cadences spanning at least 4 acquisition groups, plus current fixture | Feasibility, loader/cadence validation, runtime, no generalization claim. |
| Main study target | At least 60 disjoint independence groups; 30 development, 10 validation, 20 test; commonly 1–3 cadences per group | Receiver-specific benchmark estimates with explicit cluster uncertainty. |
| Reduced study | Fewer groups if access fails | Exploratory results; narrow scope; precision and operational claims reduced accordingly. |
| External extension | New receiver or independent acquisition campaign | Separate transportability result, not silently pooled into the primary estimate. |

The group count is a target subject to archive feasibility, not an assertion that those data have been downloaded. If shared targets/sessions create one giant connected group, downselect or revise the generalization question before splitting. Never break those dependencies just to achieve a preferred split ratio.

Record immutable URLs/identifiers, hashes, byte counts, pointing, receiver, frequency/time axes, acquisition group, target, cadence associations, masks, and original licenses/citations in a manifest. Validate units, channel direction, scan time gaps, data truncation, calibration state, and whether OFF pointings could contain source response.

Data acquisition is a major resource gate: a small derived cutout does not imply a cheap archive download. Confirm whether server-side cutouts or authenticated scientific collaboration can provide the required portions; do not assume HTTP range support or efficient remote HDF5 slicing. Download one complete example and measure transfer, disk, and parsing cost before forecasting the cohort.

## 7. Injection design and physical realism

Keep the existing analytic injection as a fixed regression fixture. For scientific trials, inject before every preprocessing operation whose losses are being measured. Simulate in detected power for the main benchmark, then validate a limited subset against a more detailed channel-integrated or voltage-based construction.

Signal families:

| Family | Key variables | Purpose |
|---|---|---|
| Continuous linear narrowband | Positive, negative, zero, near-zero, off-grid slopes; random channel phase | Core search domain and grid losses. |
| Wider/broadened narrowband | Widths spanning fractions to several channels | Bandwidth mismatch. |
| Intermittent | Random onset, gaps, short durations, partial ON coverage | Avoid assuming signals persist for every scan. |
| Modulated amplitude | Smooth fluctuations and controlled bursts | Sensitivity to normalization and persistence rules. |
| Curved drift | Quadratic frequency path and controlled deviation from a linear model | Explicit out-of-model stress test. |
| Collision/crowding | Injection near another native line; two synthetic tracks in a separate challenge set | Grouping, suppression, and candidate-cap failures. |

Use a drift range in physical Hz/s and a dimensionless drift measure `abs(drift)*integration_time/channel_width`. Choose ranges after checking each observation's resolution. Include cases just beyond configured search bounds to measure handling of out-of-domain cases; do not include unsearchable cases in a misleading in-domain recall figure.

Randomize fractional-channel starting position, slope phase, time origin, and placement across usable and explicitly masked/edge regions. Match a single physical frequency path across all scan timestamps; do not restart a chirp at each ON scan. Inject normally into ON pointings with the appropriate apparent response, and test source leakage into OFF pointings separately using a justified beam-response approximation. Strict absence in OFF is evidence, not a universal law.

Specify amplitude as recorded peak/integrated power relative to a documented pre-injection local noise estimate. Do not label this quantity detector SNR. Preserve both the noise estimate and absolute added power, and compare normalizations across packages. Physical flux/EIRP conversion requires receiver calibration and is a later optional analysis.

Integrate frequency profiles over channel bins and frequency paths over integrations, using convergence checks on numerical subsampling. Account for the instrumental bandpass consistently in the chosen injection domain. Include a sinc-squared or measured response comparison; avoid claiming that a Gaussian power addition fully represents the instrument.

Proposed pilot matrix: six families × six amplitude levels × 32 randomized placements = 1,152 trials. The current one-background version can debug the machinery, but population estimates require placements across independent observational groups. Initial amplitude multipliers `[0.25, 0.5, 1, 2, 4, 8]` refer to pre-injection robust power sigma. Calibration data may replace this grid once, to span the transition from missed to reliably recovered signals; freeze it before the test set.

Proposed locked evaluation: six families × six amplitude levels × 200 placements = 7,200 trials, allocated across test groups and interference strata. Count statistical independence appropriately: 7,200 placements on a small number of backgrounds are not 7,200 independent observing environments. Add separate, explicitly labeled multi-signal and out-of-range challenge sets.

Use at least two independently implemented synthesis checks for the core family. A model trained and tested on one simulator's artifacts can appear scientifically effective while learning the generator.

## 8. Baseline development and comparison arms

Preserve `pipeline.py` and `run_001` as the fixed first milestone. Put research changes in a new module/config series so historical evidence remains valid.

Baseline work first addresses denominators, not model complexity:

1. Replace fixed shape/target assumptions with a separately validated loader adapter.
2. Maintain precise axes from header reference plus offsets; support gaps without inventing samples.
3. Search overlapping frequency tiles with sufficient drift/width margins; record exposure and deduplicate overlaps.
4. Stream hit catalogues or explicitly report truncation; separate display limits from detection limits.
5. Group compatible tracks using their paths and time support, not starting frequency alone; test preservation of nearby distinct signals.
6. Measure losses from every mask, normalization, suppression rule, and cadence decision.
7. Compare an established implementation such as turboSETI with the transparent local reference. Hyperseti is an optional accelerator if compatible hardware and access are available. Freeze versions, settings, and score definitions separately.

Proposed arms:

| Arm | Role |
|---|---|
| B0 | Transparent local drift-search reference, expanded for integrity/coverage. |
| B1 | Established narrowband detector plus explicit event grouping and cadence rules. |
| B2 | B1 plus small metadata/feature classifier or ranker. |
| B3 | B1 plus compact image/cadence classifier if labels and compute justify it. |
| L1 | Text LLM using the same measured metadata/features as B2. |
| L2 | Multimodal LLM using the same measurements plus standardized cadence images. |
| L3 | Selected LLM plus a frozen, cited instrument/RFI reference collection, only if L2 justifies the added work. |

Do not train every arm at full scale. Screen B0/B1/B2 first, then a small L1/L2 pilot; add B3/L3 only if the learning question remains unresolved. The comparator for the primary AI claim is the strongest non-LLM workflow selected on validation data under the same retention and resource constraints.

Separate candidate generation from candidate triage. When comparing triage, use the same event pool. When comparing full systems, run the entire detection-to-retention chain and expose differences in generated events. A union catalogue can support diagnostic comparisons but cannot retrospectively rescue an arm's end-to-end misses.

## 9. AI interface and evidence grounding

The model receives a fixed candidate packet: unique opaque case ID, physical units, scan timestamps, pointing roles, receiver/resolution, measured track parameters with uncertainties, ON/OFF power summaries, mask flags, standardized images if applicable, and approved reference excerpts if applicable.

It does not receive injection labels, before/after difference images, simulator settings, truth-derived crops, file names containing class information, or test-set answers. Crop construction must be equally available for native and injected events, with randomized/controlled placement so centering cannot reveal labels. Images use consistent axes and comparable scaling across the cadence; audit resizing, downsampling, and clipping for line removal.

Structured decisions are `retain`, `escalate`, or `reject_supported_interference`. A proposed rejection requires cited measured evidence and a machine-checkable reason; unresolved cases remain available for review. Model self-reported confidence is not a calibrated probability of origin. Invalid outputs, timeouts, unavailable evidence, and out-of-domain inputs default to retain/escalate and count toward cost and burden.

Tool-based calculations should produce numerical features; the LLM interprets those features. Validate every quoted frequency, drift, time, pointing relation, and evidence reference. Retain a source-linked case report and a structured event log. Evaluate faithful factual claims rather than using stylistic persuasiveness or purported internal reasoning as evidence.

Freeze model identifiers/weights, prompt text, image renderer, decoding settings, reference collection, and retry policy. Quantify variability with repeated pilot calls even when temperature is zero; retain primary and replicate outputs. Do not use an LLM judge as the sole ground-truth labeler.

## 10. Labels, controls, and reference judgments

Keep origin, morphology, and review action as separate fields. Useful labels include known synthetic injection, independently supported terrestrial/instrumental origin, unresolved native event, and insufficient information. An unmodified archive tile is not certified to contain no extraterrestrial emission.

Synthetic positives evaluate recovery of a specified signal family. Simulated RFI evaluates a specified interference model. Independently documented RFI provides a limited real-origin control. Native unresolved events measure workload and reviewer disagreement; they do not provide a clean binary confusion matrix for alien versus terrestrial origin.

Obtain two independent expert assessments for a selected native-event subset, with adjudication and evidence records. Reviewers should be blinded to injection status and model identity where feasible. A single-developer labeling pass is a development aid and must not be described as expert consensus.

Controls include amplitude-zero sham cases processed through the same file/render path; on/off label permutations as a diagnostic stress test; wrong-unit and missing-metadata cases; mirrored axes with consistent physical metadata; nearby-line collisions; and injected cases with plausible response in OFF scans. Diagnostic controls are not silently pooled with natural operational data.

## 11. Evaluation, confidence, and decision gates

The detailed estimands, weighting, interval handling, and sample-size reasoning are in [STATISTICAL_ANALYSIS_PLAN.md](STATISTICAL_ANALYSIS_PLAN.md).

Primary measurements:

- End-to-end injection recovery and conditional triage survival, reported separately.
- Active human review time per fixed native-event workload; reviewer accuracy/retention as companion outcomes.
- Candidate/event review burden per searched exposure, with bytes, time-bandwidth coverage, and masks recorded.
- Measured CPU/GPU runtime, memory, inference calls/tokens, failures, and latency.
- Frequency/drift/path errors, factual-error rates, and abstention/escalation rates.

Report recovery curves and 50%/90% recovery amplitudes where identifiable. Report native unresolved-event burden instead of calling all retained native events false positives. Report sensitivity at fixed review budgets as well as review effort at fixed retention requirements.

Proposed gates:

| Gate | Evidence required | Action if unmet |
|---|---|---|
| G0: existing fixture | Hashes, thirteen tests, exact repeat run | Repair the fixture before expansion. Already passed for the current version. |
| G1: data viability | Complete cadences, provenance, independent groups, realistic transfer/storage estimate | Reduce scope or request a research collaboration; no generalization claim from one fixture. |
| G2: trustworthy benchmark | Injection convergence, masks/edges accounted for, no hidden cap, grouped split, complete stage ledger | Continue baseline engineering; no AI performance claim. |
| G3: conventional reference | Established/local comparison, pilot sensitivity curves, frozen comparator and operating point | Fix sensitivity/normalization problems first. |
| G4: AI screening | Small held-out development pilot suggests additional value; evidence validation works | Stop AI branch or keep summaries only; preserve conventional result. |
| G5: locked test | Paired retention lower bound ≥−0.01; review-time reduction point estimate ≥30% and 95% lower benefit bound >0; no undisclosed exclusions | Report null/inconclusive result; no automated rejection. |
| G6: external/operational | Independent observing conditions, failure accounting, limited expert-observed use | Scope claims to the locked benchmark and use retain/escalate defaults. |

Subgroup losses are not concealed by a favorable global average. A proposed additional engineering alarm is a loss point estimate worse than three percentage points in a preregistered core stratum; investigate regardless of global success. Sparse strata remain uncertain even if no misses occur. Passing a benchmark gate does not certify performance on unobserved telescope conditions.

The first usable mode should rank candidates and provide verified summaries while preserving the complete event archive. Automatic rejection is a separate, higher-evidence decision. It is not necessary to achieve useful review-time savings.

## 12. Controlled human review study

Use a frozen event set after technical validation. Compare the selected conventional review interface with the selected AI-assisted interface. Keep plotting, available measurements, and navigation comparable; isolate the assistant's contribution.

Planning target: 240 event cases, comprising 160 native cases sampled with recorded probabilities and 80 injected cases used to monitor gross missed-signal behavior. Each case is reviewed in both conditions by different reviewers; four reviewers each assess approximately 120 case-condition assignments. Use randomized condition/order blocks and a shared training set excluded from analysis. Do not show a reviewer both versions of the same underlying event or near-duplicate injection family.

This yields 480 reviews, not 480 independent observing sessions. At an assumed one to two active minutes per review, direct review time is approximately 8–16 reviewer-hours, plus training, breaks, and adjudication. Plan 16–30 total reviewer-hours. Pilot timing must replace these assumptions.

Measure active time, final action, evidence correctness, escalation, and changes from an initial assessment. Analyze case/reviewer effects and acquisition grouping. Review-time savings only count when retention and evidence-quality requirements are also met. Eighty injected human-study cases cannot establish a 99% human-retention guarantee; that part of the study is exploratory unless expanded.

If expert reviewers cannot be recruited, complete the software benchmark and postpone the human-productivity claim. A solo timing experiment can debug instrumentation but is not the main study.

## 13. Software and data architecture

Use small explicit components with versioned contracts:

```text
Archive manifest → immutable raw files → loader/axes/quality audit
                                       ↓
                     original branch / injected copy + hidden truth ledger
                                       ↓
                  identical preprocessing and candidate generation
                                       ↓
                   hit catalogue → event grouping → cadence features
                                       ↓
                conventional / learned / LLM assistance comparisons
                                       ↓
                  review actions + costs + stage-loss audit + reports
```

Proposed records: `Observation`, `Cadence`, `ExposureMask`, `SplitGroup`, `InjectionTruth`, `Hit`, `Event`, `CandidatePacket`, `ModelRun`, `ReviewDecision`, and `StageOutcome`. Use a stable experiment ID and hashes to join them. Truth access is restricted by interface separation, not a misleading claim that a solo investigator has never seen the test data.

Outputs should include observation/split manifests, signal parameter manifests, raw and deduplicated event catalogues, every rejection/truncation reason, frozen configs, environment versions, renderer version, model requests/responses, reviewer assignments, metrics with intervals, and a publication-ready figure set. Never overwrite `run_001` or treat a changed score definition as the same experiment version.

Test coverage targets are scientific behaviors, not an arbitrary line-coverage percentage. See the backlog and statistical plan for input-integrity, metamorphic, integration, benchmark, and repeat-run checks.

## 14. Resource strategy

Assumptions: one Python-capable researcher; existing local CPU machine; no assumed GPU, paid API credit, or telescope allocation; intermittent domain-expert feedback. These are planning assumptions to refine after the access pilot.

| Resource | Proposed initial bound | Scaling rule |
|---|---|---|
| Raw acquisition | Measure one cadence; pilot allowance up to 20 GB | Reassess before a cohort download; projected full downloads can exceed derived-cutout size by orders of magnitude. |
| Main retained working data | Aim for 50–200 GB of selected tiles/products | Increase only after access/storage feasibility and scoped research value are established. |
| Baseline compute | CPU pilot and profiled batches | Estimate from measured seconds per MHz×scan×trial grid, not file count alone. |
| Injection experiment | 1,152 pilot and proposed 7,200 locked cases | Generate lazily; store seeds/parameters and necessary audit examples, not duplicate entire raw files. |
| AI pilot | 100–300 candidate packets, at most two model variants initially | Compare benefit before selecting a full inference budget. |
| Inference cost | Provider-neutral formula; no paid run assumed | `N_calls × (input_tokens×input_rate + output_tokens×output_rate)`, with image charges, retries, and repeated runs added. |
| Expert effort | Short design review plus 16–30 reviewer-hours for the proposed study | If unavailable, narrow claims and postpone human-effectiveness evaluation. |

The transparent detector costs approximately the number of trial drifts × valid start channels × time samples. It is appropriate as a reference but is not automatically suitable for a large archive. Profile, tile, stream, and compare established optimized code before committing compute.

Use staged scope to maximize information gained per cost: fix losses → establish data/realism → measure conventional performance → screen AI → run one locked comparison. Model training from scratch and broad parameter/model sweeps are outside the initial programme.

## 15. Schedule and responsibilities

A working schedule is 24–32 weeks at roughly 15–20 researcher-hours per week, or about 360–640 researcher-hours. Access and reviewer delays can extend elapsed time. These ranges are planning estimates, not a commitment that all gates pass within a date.

| Weeks | Work package | Deliverable and gate |
|---|---|---|
| 1–2 | Scope, related-work matrix, archive access pilot, expert critique | Research charter and data feasibility memo; G1 decision. |
| 3–5 | Loader/axes, coverage and cap accounting, event grouping, cadence assembly | Versioned baseline and complete loss ledger; G2 engineering evidence. |
| 6–8 | Realistic injector, physical checks, stratified pilot | Convergence report and amplitude/drift pilot curves. |
| 9–11 | Established comparator, feature ranker, benchmark statistical design | Frozen comparator, cohort, split manifest, and preregistered analysis; G3. |
| 12–14 | Small AI pilot and evidence/rendering ablations on development data | Select one workflow or terminate AI branch; G4. |
| 15–18 | Finalized preparation and one locked technical evaluation | Recovery/burden/cost results and failure audit; G5 technical decision. |
| 19–22 | Expert review study if resources exist | Time/quality study with uncertainty; otherwise document deferred endpoint. |
| 23–26 | External challenge data, robustness, replication | Restricted generalization statement; G6. |
| 23–32 | Independent reproduction, paper/dataset preparation, and contingency alongside any external extension | Reproducible release and defensible manuscript; optional external work can extend the schedule. |

The researcher owns implementation, manifests, analysis, and evidence. A domain mentor checks physical assumptions, data/cadence interpretation, and the scientific claim. Independent reviewers assess native events. A second analyst, if available, checks analysis code and reproduces a locked subset. These are proposed human roles; no collaborators have been contacted or committed.

## 16. Risks and response rules

| Risk | Early evidence | Response |
|---|---|---|
| Data cannot support independent complete cadences | Manifest/access pilot fails | Restrict to methods fixture or obtain a suitable collaboration; revise claim. |
| Simulator artifacts drive model success | Cross-generator/held-out-morphology degradation | Improve physical checks and report conditional scope. |
| Candidate cap or grouping hides losses | High occupancy, truncation, collision tests | Remove hidden truncation, retain raw hits, fix event definitions. |
| Cleaner removes weak signals | Pre/postprocessing injection ledger | Change cleaning or accept/document lower coverage. |
| Apparently excellent accuracy reflects class balance | Native workload and weighted burden disagree | Use conditional recovery, native burden, and deployment weights. |
| LLM makes plausible incorrect claims | Evidence-validation audit | Remove unsupported fields, increase escalation, use factual summaries only. |
| Inference variability or service changes | Replicate outputs or version changes | Cache/version runs; qualify reproducibility and avoid mixing versions. |
| Review-time benefit is learning or interface bias | Order/reviewer effects | Counterbalance, standardize interface, preserve blinded case assignments. |
| Statistical precision insufficient | Wide grouped intervals, few independent sessions | Report inconclusive; gather new groups or narrow the claim. |
| No gain over a small conventional model | Validation trade-off dominated | Stop model expansion; publish the benchmark/negative result if informative. |

## 17. Immediate two-week execution package

The next implementation begins with measurement integrity rather than adding an LLM:

1. Freeze the current fixture and retain its manifest as completed evidence.
2. Build a metadata-only archive cohort manifest and validate one complete cadence's accessibility and size.
3. Specify the searchable frequency/time mask and stage-outcome schema; test the existing 74.609% start-channel coverage against that ledger.
4. Separate full hit/event output from display/top-k limits and quantify secondary-peak/nearby-signal behavior.
5. Assemble one cadence using physical timestamps and ON/OFF roles; verify a synthetic path across scan gaps.
6. Implement the 1,152-case pilot manifest and converged injection options, with a hidden truth interface; keep single-background results explicitly developmental.
7. Run a small profiled subset, select a feasible full pilot budget, and record failures before scaling.
8. Obtain a narrow scientific-method critique from a technosignature researcher using a concrete design and sample plots.

At the end of this package, the project should know what data it can use, what it actually searches, which losses it can measure, and what the next experiment will cost.

## 18. Completion criteria and scientific claims

A completed methods study includes the cohort/splits, validated signal families, coverage and stage-loss accounting, comparator results, uncertainty, and independent reproduction. An AI-effectiveness claim additionally requires the frozen comparison, cost/failure evidence, and reviewer study appropriate to its wording.

Use conclusions of the form: “On this receiver-specific held-out benchmark and declared injection distribution, method X changed recovery by Y and review time by Z, with the reported uncertainty.”

Do not infer that a fluent report validates a signal, that simulated recall is the probability of finding extraterrestrials, that no confirmed detections means every rejected native event was interference, or that a null result constrains civilization prevalence without calibrated coverage and population assumptions.

The full plan is effective if it identifies the cheapest defensible path to improved search performance, including the decision to stop an unhelpful AI branch.
