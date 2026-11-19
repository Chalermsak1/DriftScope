# Load → Inject → Detect: experiment report

**Status: PASS.** Real observation loaded, one synthetic power track injected, and an independent baseline search evaluated.

## Observation and provenance

- Target label: `DIAG_SGR_B2`; telescope: Green Bank Telescope (SIGPROC ID 6).
- Start: 2018-12-13T17:12:37.000 UTC (MJD 58465.7170949074).
- Array: 32 integrations × 1024 frequency channels.
- Integration: 1.431655765 s; total duration: 45.812984 s.
- Channel spacing: 1.396983862 Hz.
- Center-frequency range: 6663.998570759–6663.999999873 MHz.
- Original descending frequency order reversed into ascending order; power values otherwise unchanged.
- Raw observation SHA-256: `ee0ed0df43990a4653a05eed914401836c0a0de154897afa2c05ddd7f8128ea5`.
- Frozen source: https://raw.githubusercontent.com/bbrzycki/setigen/7ba8324848eb91bd18a2233f467271020a950f40/tests/assets/sample.fil
- This is a compact archival diagnostic cutout, not a complete ON/OFF observing cadence.

## Injection (ground truth)

- Exactly one Gaussian narrowband track, constant amplitude, positive linear drift.
- Start: 6663.999073673 MHz; ascending channel 360.
- Drift: 1.000000000 Hz/s; FWHM: 2.793967725 Hz.
- Peak power: 1835011.947387 arbitrary units = 8.0 × pre-injection median row MAD sigma.
- Additive sampled power model, not a phase-coherent voltage simulation. No random numbers are drawn.
- Independent analytic Gaussian check max error: 4.65661e-10 power units.

## Blind detector and recovery

Detector: row median/MAD normalization, 3-channel boxcar, incoherent nearest-channel sums over linear drift tracks, then per-drift robust profile standardization. It receives no truth coordinates or delta array.

- Search range: ±4.0 Hz/s over 511 trial drift rates.
- Search size: 390,404 track trials.
- Detection threshold: robust score ≥10.0; this is a descriptive threshold, not a calibrated false-alarm probability.
- Before: 0 retained candidate(s); after: 3.
- Candidates are search maxima, not distinct sources. One injected line can create secondary peaks when other trial tracks partially overlap it; full-track truth matching determines which candidate is recovered.
- Injection matched: **True**; top candidate matches: **True**.
- Recovered start: 6663.999073673 MHz.
- Recovered drift: 1.019607843 Hz/s.
- Recovered robust score: 42.5391.
- Maximum recovered-versus-injected track error: 0.6229292657938883 channels (allowed ≤3.0).
- Matching candidate(s) before injection: 0.

## Verification

```json
{
  "input_checksum_verified": true,
  "shape_matches_protocol": true,
  "original_array_unchanged": true,
  "all_output_power_finite": true,
  "delta_nonnegative_with_roundoff_tolerance": true,
  "exactly_one_injection_declared": true,
  "analytic_injection_verified": true,
  "injection_detected_above_threshold": true,
  "top_candidate_matches_injection": true,
  "no_matching_preinjection_candidate": true,
  "recovery_check_passed": true
}
```

## Artifacts

- `spectrogram_comparison.png` / `.pdf`: original, injected, and difference views. Before and after use identical intensity limits.
- `spectrogram_zoom.png`: close view, with truth/recovered tracks overlaid only for evaluation.
- `detection_search.png`: before/after blind score maps using identical color limits.
- `before.npz`, `after.npz`, `injected_signal.npy`: numerical power arrays and physical axes.
- `candidates_before.csv`, `candidates_after.csv`: independently generated candidate lists.
- `search_before.npz`, `search_after.npz`: complete searched score maps and trial axes.
- `results.json`, `environment.json`, `artifact_manifest.json`: machine-readable evidence, versions, and checksums.

## Limits and interpretation

This validates plumbing for one deliberately strong, deterministic injected signal. It does not measure completeness, precision on extraterrestrial signals, or scientific novelty. Unknown features in the original observation are not labeled extraterrestrial or automatically labeled RFI. The source file carries observational metadata; its full upstream raw-data acquisition chain has not been independently audited.

Scores use real correlated/non-Gaussian backgrounds, a correlated drift grid, and a simple noise estimator; no Gaussian p-value is claimed. The Gaussian injector is sampled at channel centers/integration starts, omits intra-integration drift smearing and signal self-noise, and does not represent every transmitter morphology. The detector searches a restricted drift/bandwidth family and excludes edge channels. Candidate suppression merges nearby start-frequency peaks and is adequate for this single-track experiment only.

The next research stage is a preregistered multi-injection sensitivity study and independent observations, before any LLM evaluation.
