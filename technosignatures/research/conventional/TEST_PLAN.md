# Scientific test strategy

The architecture and testing-strategy skills were used to structure this work. Acceptance targets are scientific behaviors and loss denominators, not a line-coverage percentage.

| Component | Verification type | Required behavior |
|---|---|---|
| Observation adapter | Contract/metamorphic | Descending-axis reversal preserves samples and masks; GHz origins cannot conceal irregular channels; immutable arrays; nonfinite usable data rejected. |
| Masks and geometry | Independent numerical reference | Enumerate each valid boxcar sample using scalar loops; compare every support cell, masked count, and score against the tiled implementation. |
| Tiling | Metamorphic | Core widths 1, 5, 13, 32 and oversized tiles produce equivalent whole-band scores; signed tracks crossing tile boundaries remain detected. |
| Coverage | Regression/integration | Search all 489,730 physically valid original-fixture discrete tracks, including the 99,326 omitted by the old common guard. |
| Resource failure | Negative contract | Refuse an oversized score map before returning any partial catalogue; zero noise scale is a technical error, not a clean observation. |
| Candidate truncation | Synthetic stress | Eighty known tracks can all recover one to one; no silent top-50 limit. Candidate maxima and physical signals have different denominators. |
| Event grouping | Constructed adversarial paths | Compatible duplicates group; transitive bridges do not merge distinct endpoints; crossing tracks remain separate. |
| Assignment | Independent combinatorial examples | Maximize recovery before minimizing error; one event cannot recover two signals; stage ancestry cannot reuse a parent hit; inactive intermittent support cannot match. |
| Cadence timing | Synthetic integration | One global chirp remains coherent across actual scan gaps; fitted slope is correct; OFF arrays remain identical in ON-only injections. |
| Cadence filtering | Challenge integration | Equal/weak OFF leakage is measured; incomplete or masked OFF coverage escalates; intermittent ON response causes an explicit strict-policy loss while review-safe retains. |
| Injection physics | Analytic and adaptive-integral comparison | Integrated Gaussian power and centroid agree with limiting cases; midpoint quadrature converges to an independent SciPy adaptive integral; shams are exact; original arrays remain unchanged. |
| Injection design | Arithmetic/determinism | Full manifest records 1,152 trials / 1,344 physical signals with reproducible full parameters; edges remain sampled. |
| Acquisition graph | Leakage adversaries | Shared raw, target, session and coordinate aliases connect transitively; quotas cannot split a component; missing linkage blocks certification. |
| Sampling frame | Mocked protocol | Saturated responses are bisected; exhausted budgets/network errors mark incompleteness; two-stage selection probabilities and weights are correct. |
| Header source check | Fake HDF5 byte source | Case-normalized names, target coordinates, timestamps, dimensions and resolutions are verified without reading spectral samples; bad headers fail. |
| Statistical denominators | Hand calculations | Eligible/searchable/ambiguous/failed signals use the intended denominators; invalid weights rejected. |
| Statistical uncertainty | Deterministic resampling | Whole groups and paired outcomes remain intact; one group yields unresolved environmental uncertainty; degenerate intervals do not imply no future risk. |
| Evaluation leakage | Negative contract | Development runner rejects wrong-observation manifests and validation/test partitions. |
| Experiment execution | Real observations plus controlled additions | Execute old regression scenarios, the 48-trial conditional set, four real-cadence cases and convergence checks; record every signal and source-array hash. |
| Reproduction | Complete repeat | Stable scientific JSON and exact score/power-array hashes match; historical experiment and approved-plan files remain identical. |

The full regression run also includes the earlier 53 baseline/pilot tests, including actual original-archive excerpt identity and offline range-cache reconstruction. Those require locally acquired proof/cache assets and are separate from the new offline-capable test suite.

## Known gaps after this development milestone

- No representative multi-session source-sample acquisition or population-completeness interval.
- No production survey-scale streaming, optimized turboSETI/hyperseti comparison, or matched false-alarm/workload calibration.
- No exhaustive crowded-source association/deblending guarantee.
- No verified beam response, channelizer-response comparison, voltage simulator, or full six-family randomized pilot execution.
- No frozen validation-selected comparator, locked scientific cohort, reviewer study, or LLM evaluation.

These gaps remain explicit scientific gates; passing software tests does not close them.
