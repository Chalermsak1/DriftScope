# Observation provenance

## File and upstream evidence

- Local path: `raw/sample.fil`.
- Repository: [Bryan Brzycki / setigen](https://github.com/bbrzycki/setigen).
- Immutable source: https://raw.githubusercontent.com/bbrzycki/setigen/7ba8324848eb91bd18a2233f467271020a950f40/tests/assets/sample.fil
- Introduction commit: [7ba8324848eb91bd18a2233f467271020a950f40](https://github.com/bbrzycki/setigen/commit/7ba8324848eb91bd18a2233f467271020a950f40), dated 2019-08-05.
- Upstream commit description: “Replace voyager with lighter weight cband obs 32x1024”.
- Bytes: 131,466.
- SHA-256: `ee0ed0df43990a4653a05eed914401836c0a0de154897afa2c05ddd7f8128ea5`.
- Downloaded for this project on 2026-11-19, Asia/Bangkok.

## Header metadata read from the actual file

- SIGPROC source name: `DIAG_SGR_B2` (Sagittarius B2 direction, diagnostic label).
- Telescope ID: 6 (Green Bank Telescope in the SIGPROC convention).
- Original raw-file identifier: `blc13_guppi_58465_61957_DIAG_SGR_B2_0066.0000.raw`.
- Start MJD: 58465.717094907406 = 2018-12-13 17:12:37 UTC.
- 32 integrations × 1 stored intensity stream × 1024 channels; 32-bit floating-point stored power.
- Time sample: 1.431655765333332 s; total integration time 45.81298449066662 s.
- Original channel spacing: −1.3969838619232178 Hz.
- Channel-center frequency range after reversal: approximately 6663.998570759–6663.999999873 MHz.

The upstream history and header identify an observational cutout, not a freshly simulated background. This project preserves the downloaded bytes and verifies the hash on every load. The stored array is converted to float64 and reversed into increasing-frequency order; no background synthesis or denoising replaces the observation.

The full raw acquisition/calibration chain has not been independently verified. This is a small diagnostic cutout, not a full target observation or an ON/OFF sequence. Its intensity is not calibrated in Jy, and the pipeline does not infer transmitter power or astrophysical origin from it.

## Attribution

The sample is distributed in the SETIGEN repository. Its repository license notice is preserved in `SETIGEN_LICENSE.txt`; this is not a claim of ownership over the upstream observation. The injection uses the installed SETIGEN package. Please cite the upstream software/data appropriately in any future publication, including [Brzycki et al., Setigen: Simulating Radio Technosignatures for SETI](https://arxiv.org/abs/2203.09668), and establish publication-specific data attribution with the data producers.

## Download notes

The older Berkeley Voyager HTTPS endpoint had a certificate-name mismatch during source discovery. It was not used, and TLS verification was not disabled. The experiment uses the smaller immutable SETIGEN-hosted observational cutout described above.
