# Scientific record contracts

Version: conventional v2 development. JSON is written with `allow_nan=False`; unknown/unsupported quantities are `null` or named statuses, never infinity or invented zero measurements.

## Observation boundary

`Scan` contains immutable, copied power/frequency/time/mask arrays and explicit ID, MJD, ON/OFF role, target, acquisition-session ID, raw-data ID, receiver regime, and optional RA/Dec. Coordinates must be both supplied or both unavailable. A true sample mask means usable recorded data. Masked nonfinite values are permitted; nonfinite usable samples are rejected.

Frequency axes are converted to ascending order together with power and mask. Uniformity is checked against channel spacing and floating-point resolution, not a permissive relative tolerance against GHz origins. Within a scan, integrations must be uniformly spaced and start at relative time zero. Cadences preserve chronological actual MJD starts, missing exposure, and represented scan roles.

## Search boundary

`SearchResult` holds:

- Validated source scan and frozen search settings.
- Drift grid and full score map; unsupported/masked/unscorable cells are NaN internally only.
- Every above-threshold local maximum, with deterministic ID, frequency, slope, score, grid index, and time-reference convention.
- Physical, masked, evaluated and unscorable trial counts per drift.
- Tile core and halo intervals, usable time-bandwidth exposure, and uncapped catalogue status.

Stored experiment records hash score-array bytes together with the recorded shape and settings. Numerical array hashes support exact same-environment repeat checks; no hash is represented as an astrophysical calibration.

## Event boundary

An event references an actual representative hit and all member hit IDs. Membership is total and unique. Event count, hit count, injected physical-signal count, and trial count remain distinct. Grouping receives no truth and applies no cap. Recovery assignment is a separate evaluator with truth access.

`match_tracks` records one truth ID, zero/one matched output ID, and continuous maximum path error in channel units. Matching uses only active truth support where declared. No active support means unmatched. Multi-signal assignments are one to one; unmatched columns are explicit. Ancestry-constrained and unconstrained raw-hit matching totals are both available.

## Cadence boundary

Each cadence association records global frequency/drift reference, feasible slope interval, endpoint-fit residual, member ON event IDs, and every represented scan's elapsed start, pointing role, associated events, forced score/status, and OFF evidence.

The same association carries two separate policy outcomes, `review_safe` and `strict_experimental`. The strict policy is not silently applied as the default. Unknown or unsearched OFF support cannot become a numerical zero or an absence label. Input ON events are all assigned exactly once, including those that do not persist across scans.

## Truth and experiment boundary

An injection manifest contains full randomized parameters and seed, family, amplitude convention, fractional starting channel, physical slope/curvature, modulation/intermittency, width, OFF response, and collision companion definition. Trial and signal counts are independently recorded. Hidden truth is passed only to injection and post-search evaluation, not to search/grouping/cadence feature construction.

Signal rows contain `eligible`, `searchable`, `generated`, `grouped`, `cadence_retained`, component ID, weight, ambiguous native match, continuous match errors, and first-loss stage. The one-scan development engine explicitly labels its terminal field as grouped events with cadence not applied. Actual cadence cases carry policy-specific signal-survival rows.

Post-injection technical failures remain counted as failed signal outcomes. A failure before truth allocation aborts the execution as incomplete; no completed sensitivity report is issued. Failed execution logs and local partial outputs are retained.

## Cohort and analysis boundary

Metadata records include cadence ID; target/session/raw link sets; coordinate aliases; source-header/sample/receiver verification flags; candidate-selection status; and original archive identifiers/byte counts. Component assignments, inclusion probabilities and weights, partition proposals, incomplete-frame status, and rejection reasons are explicit.

The representative readiness gate is independent of whether a detector finds anything. Cohort selection never reads injection recovery or detection score. The development runner rejects validation/test-labelled manifests. A proposed split is not a locked split or permission to open test outcomes.

Summary rates retain both `eligible_weight` and `searchable_weight`. Unresolved ambiguity has conservative/optimistic views. Bootstrap output records component count, seed, replicate count, paired estimand, few-group warning, and unresolved/degenerate states. No rate or bootstrap interval is interpreted as extraterrestrial-origin probability or a transmitter-prevalence bound.
