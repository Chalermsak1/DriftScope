# First code publication

This repository publishes the existing research implementation and evidence without changing the original experiment or approved plan. The preserved project is under `technosignatures/`; run its Python commands from that directory.

## Included

- Conventional load/inject/detect pipeline, configuration, dependency version lock, and tests.
- Original baseline observation, numerical outputs, candidate tables, reports, and spectrograms.
- Approved research/statistical documents and execution backlog.
- Cadence metadata validation, bounded archive access, exact legacy-detector tracing, coverage accounting, truncation audits, and signal-survival experiments.
- Historical scientific JSON, figures, source-validation records, test evidence, development failures, and explicit incomplete gates.

## Downloaded and generated assets

The following are intentionally outside Git:

- `technosignatures/research/pilot/data/`: the third-party candidate release, original-archive excerpts, HTTP-range blocks, and acquisition locks.
- Pilot numerical `.npz` exports in `research/pilot/results/milestone_001/`, including observational exports and reproducible synthetic fixtures.
- Python environments, package caches, temporary/reproduction runs, and archive metadata caches.

The pinned candidate payload is 12,613,542 bytes. Its SHA-256, upstream commit, source URL, attribution, selection bias, and unresolved redistribution-license status are documented in [source.json](technosignatures/research/pilot/configs/source.json). The original archive files are accessed using bounded byte ranges; they are not downloaded in full.

[omitted_assets.json](publication_evidence/omitted_assets.json) records the selected local assets excluded from this snapshot. It is not an inventory of cache blocks. Acquisition requires external services to remain available and can transfer substantially more data than the small candidate release; consult the pilot README for budgets and failure behavior.

## Fresh-checkout pilot reproduction

After creating the Python environment using the root README, run from `technosignatures/`:

```bash
.venv/bin/python -m research.pilot.acquire
.venv/bin/python -m research.pilot.run
.venv/bin/python -m research.pilot.probe_archive
.venv/bin/python -m research.pilot.crosscheck_archive --range-metadata
.venv/bin/python -m research.pilot.archive_excerpts
.venv/bin/python -m research.pilot.archive_excerpts --offline
.venv/bin/python -m pytest -q tests research/pilot/tests --junitxml=research/pilot/evidence/tests.xml
.venv/bin/python -m research.pilot.verify
```

These commands regenerate the omitted pilot arrays and the archive cache. Acquisition commands verify checksums and source correspondence. Provenance tests deliberately fail if the required acquisition evidence/cache is absent; a newly cloned repository is not immediately ready for the full 53-test suite. The baseline 13-test suite requires no pilot download.

`research.pilot.run`, archive validation, pytest with the documented XML destination, and `research.pilot.verify` update pilot outputs/evidence in place. Use a separate checkout to preserve the published reference records while reproducing. The original baseline source and recorded `results/run_001` are preserved by these pilot commands.

## Manifests and evidence scope

`PROJECT_MANIFEST.json` and `research/planning/manifest.json` verify the preserved original experiment and approved plan. Their referenced files are included byte for byte.

Git attributes disable line-ending conversion for the preserved project. Original CSV CRLF endings and trailing blanks in the archived upstream HTML are retained as source-record bytes; publication whitespace checks exclude those three historical records.

The historical pilot `milestone_manifest.json` and result `artifact_manifest.json` describe the complete local experiment, including downloaded/generated assets excluded from Git. They are retained as research records, not presented as a list of Git-tracked files. Missing entries from those manifests are expected until the acquisition and generation steps run. Reproduced execution timing and NPZ container bytes need not match historical file hashes; the pilot verifier compares the scientific arrays and stable JSON instead.

The publication-specific [validation record](publication_evidence/validation.json) records the checks executed for this upload, and `publication_evidence/snapshot_manifest.json` hashes the published snapshot. That snapshot manifest excludes itself. Historical verification records describe the original run; they do not claim a clean dependency installation or a fresh network acquisition during publication.

No broad license for the project's own code is selected by this publication. Existing third-party notices and attribution are retained.
