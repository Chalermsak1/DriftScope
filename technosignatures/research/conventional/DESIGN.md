# ADR: conventional detection, cadence association, and cohort evaluation

**Status:** Implemented development decisions; not a frozen confirmatory analysis protocol.

The original approved plan and statistical analysis plan remain unchanged. This document records the implementation choices and amendments for the new module. Development data may inform these choices; no validation/test outcome was opened.

## 1. Search coverage and score comparability

The old detector searches a single rectangular band of starting channels guarded against the worst drift in either direction. That removes valid paths for smaller drifts and for tracks moving away from an input edge.

For drift `d`, let `shift[t] = rint(d * time[t] / df)` and let `r` be the boxcar radius. The discrete physically valid start interval is:

```text
lo = max(0, r - min(shift))
hi_exclusive = min(nfreq, nfreq - r - max(shift))
```

Every required `(time, channel)` boxcar sample must additionally be usable. Physical paths, masked paths, evaluated paths, and numerically unscorable paths are separate counts, with the invariant:

```text
physical = masked + evaluated + unscorable
```

Each tile owns a disjoint core of starting channels. Its read halo extends by the worst signed drift excursion plus boxcar radius. Thus a track crossing a tile boundary is evaluated by exactly one owner while reading all required samples. No overlap hit deduplication is needed because ownership is unique.

Normalization has two levels: row median/MAD over all usable scan channels; then integrated-profile median/MAD over all usable starts at that drift. Tile cores share this global profile normalization. Independent tile normalization was rejected because it changes score scales at boundaries and can make whole-band/tiled catalogues disagree.

V2 removes both the legacy starting-frequency NMS and candidate cap. It emits every thresholded local maximum, then separately groups events. The score-map memory budget is checked before search; exceeding it aborts without a partial catalogue. This development implementation retains a score map and is not claimed to stream a production-scale survey.

Score distributions change when the normalization domain expands. The old and new arms are compared as complete algorithms; no measured recovery change is attributed exclusively to channel coverage. Robust scores remain descriptive quantities, not calibrated Gaussian significances or false-alarm probabilities.

## 2. Event grouping and signal assignment

Two hits are compatible only if their model frequencies agree within the configured physical corridor over the full scan support. The strongest remaining hit anchors a group. Every new member must be compatible with every existing member, not only the anchor or a nearest neighbor.

This complete-link rule avoids single-link chaining, where A matches B and B matches C although A and C describe different paths. Crossing tracks that agree briefly but diverge elsewhere remain separate. A stronger line is not permitted to suppress all nearby starting frequencies irrespective of drift.

The representative is an actual strongest hit; no truth-guided centroid is constructed. Every hit has exactly one event membership, including aliases. Some partial-overlap aliases remain separate by design; reducing event count aggressively would require additional validated deblending assumptions.

Recovery uses maximum-cardinality, then minimum-path-error bipartite assignment. Dummy unmatched columns have an explicit penalty larger than any possible sum of valid assignment costs. Invalid pairs are more expensive still. An intermittent truth with no active samples has no admissible real match. That last condition was added after an integration run caught an invalid infinity at JSON serialization.

To keep the per-signal stage ledger coherent, grouped-event assignments reserve their actual parent hits first. Remaining truths are assigned to remaining hits. The unconstrained maximum raw-hit recovery is also reported, because this ancestry-preserving allocation can differ from independent raw-stage optimization. No single hit or event is reused to claim two physical signals.

## 3. Cadence association over actual timestamps

Scan times remain integration-start metadata. For the integrated-power v2 experiments, a candidate frequency is referenced to the midpoint of the first integration; relative sample spacing is unchanged. This avoids interpreting a time-averaged drifting profile's frequency as an instantaneous integration-start value. Physical truth matching uses integration midpoints. The original sampled-power regression cases retain their original numerical start-coordinate convention and are reported separately.

ON scan events are linked through actual elapsed times derived from MJD. Missing scan gaps are never replaced with samples or counted as observed exposure.

The initial implementation used drift-grid spacing as a local slope uncertainty. A synthetic test showed this was insufficient: a short-scan event could have an imprecise representative slope while remaining within the allowed path corridor. That gate split one genuine global chirp.

The replacement requires a common straight line to lie within the frequency corridor at both endpoints of every associated event. Endpoint strips define a feasible interval in drift. For two endpoints with `t_j > t_i`:

```text
(f_j - e_j - f_i - e_i) / (t_j - t_i) <= drift
drift <= (f_j + e_j - f_i + e_i) / (t_j - t_i)
```

All endpoint pairs are intersected, including within-scan pairs. At a feasible slope, all intercept intervals must overlap. A clipped least-squares slope/intercept selects a feasible representative. Associations are deterministic, score ordered, and contain at most one ON event per scan. This is a conservative development associator, not a globally optimized multi-source hypothesis tracker; all unassociated ON events seed their own associations and remain visible.

OFF scans are inspected at the predicted path using the uncensored score map. A missing above-threshold hit is not automatically recorded as no signal. Unsupported/masked/out-of-drift/unscorable paths have explicit unknown status. Forced scores are compared with a separately configured OFF evidence threshold; the threshold is an engineering setting, not an origin probability.

Two policies operate on the same feature records:

- **Review-safe:** retain every ON-supported cadence event, escalating OFF coincidence, missing persistence, and incomplete coverage.
- **Strict experimental:** require three ON events and no OFF evidence; reject measured OFF coincidence or missing persistence, and escalate unknown coverage rather than treating it as absence.

The strict rule is measured as a comparison, including loss of ON-intermittent and OFF-response injections. Neither policy labels unresolved native data as extraterrestrial or terrestrial.

## 4. Integrated injections and development sensitivity

Gaussian profiles are analytically averaged over rectangular channel bins using normal CDF differences. Midpoint quadrature averages the moving profile and temporal modulation over each actual integration. The peak amplitude refers to the continuous Gaussian before bin/time averaging, in units of a fixed pre-injection local power-noise estimate.

Noise is estimated from the median of row MAD scales over ON scans in a fixed ±64-channel starting-position window. The window, estimate, absolute amplitude, width, responses, time quadrature, and complete parameters are saved. The detector receives neither this window nor truth.

The simulator supports linear, broadened, intermittent, amplitude-modulated, curved, and paired collision cases. ON/OFF response factors are illustrative controlled parameters; no calibrated telescope beam is implied. Spectral/time averaging does not model voltages, transmitter stochasticity, channelizer sidelobes, or calibrated flux.

The complete six-family design contains 1,152 trial executions but 1,344 physical signals because collision trials contain two tracks. These units are recorded separately. The current executed sensitivity development set is 48 continuous-linear trials on one fixed real background. Placements include band edges, fractional channel phase, and both drift signs; failed and unsearchable placements remain in the ledger.

The old capped detector and v2 receive the same injected arrays. No-injection controls are searched independently. Compatible native outcomes create an ambiguous attribution flag, with conservative and optimistic bounds. The single-scan sensitivity endpoint is grouped events; separate cadence engineering cases quantify later-stage losses without pretending that a one-scan observation is a complete cadence.

## 5. Cohort construction and uncertainty

Metadata frames use a predeclared calendar/telescope/frequency query. Saturated responses are recursively split in time under a request/response budget. A saturated parent page cannot stand in for an unqueried child interval. Query completeness refers only to the API responses, not an independently verified full archive inventory.

Cadence proposals require alternating target identities, plausible time ordering, the inherited pointing-separation criteria, and the correct high-frequency-resolution product. Explicit `_OFF` names cannot become primary ON targets in shifted ABABAB windows. Headers still validate actual integrations, axes, and pointings; metadata pattern matching alone does not complete acquisition.

Shared raw identifiers, session identifiers, ON target names, and ON coordinate aliases within one arcsecond create graph edges. Connected components are indivisible split units. Missing linkage blocks certification. Candidate-selected release/regression data are restricted to development. Split quotas never justify breaking a component.

Selection samples components equally, then one cadence within each selected component. The inclusion probability is the product of those stages; inverse probabilities are recorded. This is a finite-frame sampling design, not a claim of extraterrestrial source prevalence.

The initial C-band calendar-week query was empty. A separately documented full-2018 C-band feasibility frame was queried. Name/role checks reduced initial sequence proposals; the first real header probe then exposed ON pointing variations above the inherited one-arcsecond criterion. Geometry is now checked before metadata sampling, and every rejected sequence is retained. This development amendment used metadata/header integrity only, without detector or sensitivity outcomes.

**The inherited one-arcsecond ON threshold has not been justified against C-band pointing accuracy or beam coupling.** It is intentionally conservative and currently excludes many otherwise plausible sequences. No inference that those observations are unusable is warranted. A scientifically representative cohort requires an instrument-specific definition and analysis of resulting selection coverage before freezing.

Representative sensitivity readiness additionally requires a sufficiently broad component count, verified source headers and samples, a single verified receiver regime, a complete specified frame, and candidate-independent selection. Frequency center alone is insufficient receiver verification.

Statistics retain distinct eligible and searchable denominators. Paired acquisition-component bootstrap samples entire components, preserving within-component outcomes and weights. With one group, observing-environment uncertainty is unresolved and no population interval is generated. Degenerate bootstrap percentiles are not promoted to a zero-width future-risk interval. The main 60-component target and 30/10/20 split remain unachieved and unfrozen.
