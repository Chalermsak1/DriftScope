# Original-source cadence validation addendum

**PASS for the stated narrowband, six-scan access scope.** This addendum augments the experiment report; it does not turn a candidate-selected pilot into a representative sensitivity study.

## Independent source evidence

The official archive index was queried for all six HIP13402 cadence pointings. Timestamp matching alone initially selected a different resolution product. Bounded HDF5-header reads identified the actual high-frequency-resolution files, whose attributes match the release. Narrow frequency excerpts spanning every stored integration were then acquired from each original file and compared to the published release.

| Scan | Archive ID | Stored integrations | Excerpt channels | Every float32 sample equal | Accessed MiB |
|---|---:|---:|---:|---|---:|
| 0 | 72259 | 16 | 4096 | True | 53.56 |
| 1 | 72261 | 16 | 4096 | True | 53.94 |
| 2 | 72263 | 16 | 4096 | True | 55.06 |
| 3 | 72265 | 16 | 4096 | True | 55.19 |
| 4 | 72267 | 16 | 4096 | True | 53.69 |
| 5 | 72269 | 16 | 4096 | True | 55.06 |

The original files total 92.245 GB; they were not downloaded in full. The successful execution accessed 326.50 MiB of range blocks. Its new-network counter is 3.12 MiB and excludes earlier interrupted traffic. All six excerpts also reproduced from the local hash-verified cache with HTTP disabled.

The selected frequency interval is about 11.6 kHz. This establishes all stored time samples in that interval, not the original full-bandwidth coverage. HTTP status 206, exact Content-Range and stable ETag are required. Excerpt hashes and cached-range hashes are recorded; whole-file archive MD5 values are provenance fields and have **not** been verified.

The raw slice confirms the reconstructed channel-center convention for mlc1. Other released cutouts retain their disclosed reconstruction uncertainty. Absolute receiver frequency calibration and telescope observing logs have not been independently audited. Source DIMENSION_LABELS text is inherited; the numeric layout is checked against dataset shape, nchans, and the released arrays rather than inferred from label text alone.

## Validation and limitations

- Current suite: 53 tests, 0 failures, 0 errors, 0 skips.
- Complete numerical experiment repeat: 47 matching scientific JSON/array comparisons.
- Preserved: 31 original experiment files and 8 approved-plan files.
- The initial test failure, transfer restarts, cache quarantine, and I/O corrections remain documented. No detection method or signal strength was tuned in response to those test corrections.
- No event grouping, cadence rejection, population uncertainty estimate, or LLM was introduced.

See `milestone_status.json` for per-work-package completion and partial/open gates.
