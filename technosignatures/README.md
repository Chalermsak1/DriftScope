# Technosignature research: Load → Inject → Detect

This project implements and executes the initial experimental milestone: load one real radio observation, inject exactly one deterministic synthetic narrowband track, detect it with a conventional blind search, and save the complete numerical evidence and before/after figures. No LLM is used.

The scope is a reproducible software recovery experiment. It does not claim an extraterrestrial detection or a completed sensitivity study.

## Start here

- Experiment report: [results/run_001/REPORT.md](results/run_001/REPORT.md)
- Before/after/difference figure: [results/run_001/spectrogram_comparison.png](results/run_001/spectrogram_comparison.png)
- Close view: [results/run_001/spectrogram_zoom.png](results/run_001/spectrogram_zoom.png)
- Blind search maps: [results/run_001/detection_search.png](results/run_001/detection_search.png)
- Machine-readable result: [results/run_001/results.json](results/run_001/results.json)
- Repeat-run verification: [results/reproducibility.json](results/reproducibility.json)
- Scientific method and acceptance criteria: [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md)
- Data origin: [data/PROVENANCE.md](data/PROVENANCE.md)

## Reproduce in the existing environment

Run the following commands from this directory:

```bash
.venv/bin/python pipeline.py
.venv/bin/python -m pytest -q --junitxml=results/tests.xml
.venv/bin/python verify_reproduction.py
```

The first command overwrites generated artifacts in `results/run_001`; it never modifies the original observation. To preserve a previous run:

```bash
.venv/bin/python pipeline.py --output results/my_new_run
```

The command exits with status 0 only if all recovery/integrity checks pass. An unexpected file checksum, target, shape, non-finite power value, missing signal recovery, or pre-existing truth-matching candidate causes a failure or a nonzero exit.

## Rebuild the environment

Tested with CPython 3.11 on macOS ARM64. `requirements.lock` contains exact versions of the complete installed dependency set; it is a version lock, not a wheel-hash or container lock. Cross-platform floating-point bit identity is not guaranteed.

With `uv`:

```bash
uv --cache-dir .uv-cache venv --python python3.11 .venv
uv --cache-dir .uv-cache pip install --python .venv/bin/python -r requirements.lock
.venv/bin/python pipeline.py --download
```

Or with standard Python tooling:

```bash
python3.11 -m venv .venv
.venv/bin/python -m ensurepip --upgrade
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python pipeline.py --download
```

The raw sample is already included (131,466 bytes). `--download` only fetches it if missing, from a commit-pinned HTTPS URL, verifies SHA-256, and replaces a temporary file atomically. A corrupted existing file is rejected rather than silently replaced. After dependencies and data are present, the experiment and tests run without network access.

`blimpy==2.0.31` depends on the deprecated `pkg_resources` API. This environment explicitly pins `setuptools==80.9.0`. The deprecation warning is expected; removing that pin can break imports. Scientific-package installation is confined to `.venv` and project-local caches.

## Layout

```text
config.json                  Frozen observation, injection, search, and recovery settings
pipeline.py                  Loader, SETIGEN injection, blind detector, evaluation, plots, report
verify_reproduction.py       Second complete run and equality checks
requirements.in              Direct dependencies and compatibility constraint
requirements.lock            Exact tested versions, including transitive dependencies
tests/test_pipeline.py        Recovery, sign, units, integrity, boundaries, and saved-output tests
data/raw/sample.fil          Unmodified real SIGPROC observation
data/PROVENANCE.md           Metadata, origin, hash, attribution, and caveats
docs/EXPERIMENT_PROTOCOL.md  Scientific specification and limitations
results/run_001/             Complete experiment outputs
results/reproducibility.json Independent-run comparison summary
results/tests.xml            Machine-readable test results
```

## Configuration and independence

The injector reads only `config["injection"]`; the detector reads only `config["detector"]`. The detector receives the full before or after observation and its physical axes. It does not receive the injection frequency, drift, signal-only array, or difference image. Truth matching and overlays are performed only after both searches finish.

All search settings are explicit in `config.json`. This implementation uses an inspectable brute-force incoherent dedoppler baseline; it is not turboSETI and does not claim to reproduce turboSETI's score normalization or optimizations.

The `start_channel_ascending` convention means channel 0 is the lowest frequency after reversing the source file's descending-frequency order. Frequencies are in Hz, time is in seconds, drift in Hz/s, and intensity is uncalibrated recorded power. The injection operates in relative frequency coordinates internally to avoid precision loss from GHz origins; reporting retains absolute frequencies.

## Reading the evidence

The before and after observations use identical intensity limits. The difference image has a separate scale and is a visualization/validation artifact, never detector input. In the full-band view the narrow injected track is small; the zoom figure resolves it.

The detector produces a robust score standardized by median/MAD across possible start frequencies at each trial drift. A score of 10 or 42 is not a calibrated Gaussian significance or a probability of extraterrestrial origin. Real backgrounds, correlated search trials, and candidate suppression prevent that interpretation.

One injected track can produce multiple secondary search maxima because incorrect trial tracks partially overlap it. Candidate count is not source count. The saved candidate catalogue retains these effects rather than hiding them. Recovery is evaluated by comparing the recovered and injected track over the full time span.

## Next milestone

Before introducing an LLM, freeze a broader injection-recovery protocol: multiple independent observations; positive/negative/off-grid drift; amplitude and bandwidth sweeps; held-out observing sessions; realistic drift smearing; and an empirically characterized false-positive/review burden. Confirm scientific relevance and related work with a technosignature researcher before treating the method as a publication contribution.
