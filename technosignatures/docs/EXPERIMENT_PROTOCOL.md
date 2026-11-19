# Initial experimental protocol

## Objective

Validate the mechanics, coordinate conventions, integrity checks, independent detection, saved evidence, and repeatability of one Load → Inject → Detect experiment before introducing an LLM.

This is an engineering/scientific validation milestone. It is not a blinded astronomical discovery study or a claim of a novel algorithm.

## Fixed inputs

`config.json` specifies the sample's immutable URL, SHA-256, expected target/shape, one injection, detector search domain, and recovery tolerance. These settings were selected before the first successful recovery. Initial execution exposed a packaging dependency incompatibility and frequency-coordinate roundoff; the fixes preserved the intended experiment settings. The amplitude was not tuned after measuring recovery.

The 131 kB SIGPROC file is a real C-band observational cutout from SETIGEN's tests. Its header identifies DIAG_SGR_B2 and the GBT; its upstream introduction commit describes it as a C-band observation. See `data/PROVENANCE.md` for traceability and limitations.

## Load

1. Verify SHA-256 before reading scientific data.
2. Use `blimpy.Waterfall` to read the SIGPROC header and power array.
3. Verify the target, 32×1024 shape, one intensity stream, and finite power values.
4. Convert to float64; reverse the frequency axis if the original spacing is negative.
5. Construct physical frequency and elapsed-time axes from the header, preserving uncalibrated power values.
6. Record MJD, UTC start, original raw-file identifier, telescope ID, spacing, duration, and orientation.

The time of row 0 is the start of the first integration. Row 31 is at 44.3813287253 s; the observation integrates for 45.8129844907 s. These are different quantities and are reported separately.

## Inject

Inject a single power track into a COPY of the observation:

`S(t, f) = A exp[-(f - f0 - drift*t)^2 / (2 sigma_f^2)]`

with:

- Initial ascending channel: 360.
- Drift: +1.0 Hz/s.
- Frequency FWHM: 2 channels, approximately 2.793967725 Hz.
- `sigma_f = FWHM / sqrt(8 ln 2)`.
- Constant amplitude: 8 times the median of the original per-row MAD noise scales.
- MAD noise scale: `1.4826022185 × median(abs(row - median(row)))`.
- No random generator or synthetic background.

SETIGEN generates the signal in relative-frequency coordinates. This avoids amplifying cancellation error when adjacent channel centers are expressed around 6.664 GHz. Absolute Hz are restored in truth/evaluation and plots. Channel spacing for numerical work is estimated over the full available band rather than by subtracting just two adjacent GHz-valued frequencies; the header spacing is separately recorded.

An independently evaluated Gaussian verifies every injected pixel against the intended model. The original array must remain bitwise unchanged. The difference must be finite and nonnegative within floating-point tolerance. The signal center plus six frequency standard deviations must stay within the band for every sample.

This is a sampled detected-power injection. It does not simulate phase, raw voltages, transmitter noise, channel response in detail, or drift smearing within one integration. Such effects belong in later sensitivity experiments.

## Detect (independent of truth)

The detector signature is `detect(data, frequencies, times, config)`. It receives no injection parameters, signal-only array, or difference image. Both the original and modified observation go through exactly the same procedure.

1. Normalize each time row using its own median and MAD scale. This is robust location/scale normalization, not a complete bandpass calibration.
2. Sum a 3-channel boxcar at each time sample.
3. Search trial slopes from −4 to +4 Hz/s. Choose a fixed grid so adjacent trials differ by at most 0.5 channel at the final sample.
4. For each slope, calculate nearest-channel shifts `round(drift*t/df)` and sum boxcar power over time for all valid starting channels.
5. Use a common starting-channel region with enough margin for every tested drift, so no track wraps around the band or receives a different integration count.
6. At each trial slope, subtract the median integrated power across start channels and divide by its MAD scale. This yields the reported robust score.
7. Select local maxima with score ≥10; suppress peaks within six starting channels of an already-ranked peak; retain at most 50 candidates.

For this observation, the configured search has 511 drift trials and 764 starting channels: 390,404 correlated track trials. Drift step is approximately 0.0156863 Hz/s. This score and threshold are not equivalent to turboSETI SNR or a calibrated false-alarm probability.

The baseline can produce secondary peaks whose trial tracks partially cross the same injected line. It does not count independent emitters. Single-track recovery uses the candidate rank and full-track agreement, not the total number of candidates.

## Evaluate only after both searches

The candidate path is `f_recovered(t)=f_start_recovered+drift_recovered*t`. Calculate the maximum absolute difference from injected truth over all observed samples, in channels.

Acceptance criteria:

- Raw checksum and input metadata verified.
- Original power array unchanged.
- Exactly one signal declared and its power shape independently verified.
- A post-injection candidate above threshold matches truth within three channels over the whole observation.
- The matching candidate is rank 1.
- No above-threshold pre-injection candidate matches that truth track within the same tolerance.
- Numerical arrays, search maps, candidate CSVs, and scientific JSON repeat exactly in a second complete run in the same environment.
- Tests cover drift sign, zero drift, coordinate transformations, corrupted inputs, boundary rejection, degenerate noise estimates, and the saved manifest.

The three-channel tolerance allows the width of the boxcar signal and coarse nearest-channel integration. It was configured before the successful run. Report actual parameter errors rather than just a Boolean pass.

## Figures

- Full-band before/after/difference: shared 1st–99.5th percentile power limits from the ORIGINAL observation for the first two panels. The injected track may saturate this display scale. Difference has its own explicitly labeled scale.
- Zoom: same physical window and intensity limits in both panels, truth and recovered track overlaid after detection only.
- Search maps: same score color scale before and after, with drift and starting-frequency axes.

## Reproducibility and audit trail

- `config.json`: machine-readable fixed protocol.
- `requirements.lock`: exact installed versions; Python/platform in `environment.json`.
- Input SHA-256 and pipeline source SHA-256 in the scientific result.
- Per-artifact SHA-256 and byte count in `artifact_manifest.json`.
- All numerical arrays and candidate lists retained.
- `verify_reproduction.py`: complete repeat, exact array comparisons and byte comparisons for results/config/candidates.
- `pytest`: automated scientific invariants and software failure cases.

No claim of cross-platform bit identity is made. The complete environment is version-pinned but not containerized or wheel-hash locked. Source-code changes deliberately alter the source hash and must be followed by a new reference run.

## Future research gate

Proceed to a separate sensitivity study before evaluating LLMs: multiple observations and observing sessions; injections spanning strengths, slopes, widths, intermittency and off-grid values; realistic instrumental response and drift smearing; event-level candidate grouping; review-burden metrics; and appropriate controls. A useful null result or upper limit requires a documented searched volume and calibrated detection efficiency, which this one-signal experiment does not provide.
