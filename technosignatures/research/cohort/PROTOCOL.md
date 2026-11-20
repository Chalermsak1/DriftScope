# Prospective C-band spectral access and sensitivity pilot

This development amendment is fixed in `configs/access.json` before inspecting the selected spectral arrays. Earlier experiments, plans, source observations and results remain preserved. The main 60-component study is not replaced by this access pilot.

## Instrument geometry

The [GBT specifications](https://gbtdocs.readthedocs.io/en/latest/references/gbt.html) give the approximate Gregorian FWHM as `12.60 / frequency_GHz` arcminutes. Observatory [pointing guidance](https://gbtdocs.readthedocs.io/en/latest/how-tos/general_guides/point-focus.html) relates tracking tolerance to beam width. The [C-band documentation](https://gbtdocs.readthedocs.io/en/latest/references/receivers/c-band.html) identifies the receiver regime. These support replacing an inherited one-arcsecond engineering limit with a frequency-aware criterion.

The declared spectral range is 4.5–7.5 GHz. Require maximum pairwise ON-coordinate separation of at most 0.1 times the narrowest beam in that range: **10.08 arcseconds**. Require every OFF coordinate to be at least three times the broadest beam from every ON coordinate: **504 arcseconds**. Under an illustrative Gaussian main beam, a displacement of 0.1 FWHM corresponds to a response ratio of approximately 0.973. This is a protocol design calculation, not a measured calibration or a guarantee about actual beam sidelobes, transmitter direction, weather, or source extent. The source-coordinate agreement against each archive index row remains one arcsecond.

The previous one-arcsecond audit is retained. The new criterion is not tuned against detection outcomes; it is a documented development selection amendment supported by instrument angular scales. Hardware receiver identity, observing logs, pointing corrections and flux calibration are not independently established by a spectral frequency header.

## Sampling and resource contract

- Query fixed calendar years 2016–2025 using telescope/frequency/product metadata only. Preserve complete API responses, query saturation/failure status and response hashes. An incomplete API frame is not called representative.
- Form six-scan alternating ON/OFF proposals using `.gpuspec.0000.h5` and `.rawspec.0000.h5` product names, with high spectral resolution independently required from source headers. Link shared raw IDs, acquisition sessions, target identities and coordinate aliases before sampling. Republished TESS files lacking original session directories form one conservative campaign component.
- Freeze a random component order, select up to eight components for the access batch, and choose one cadence uniformly within each. The completed metadata frame yielded only seven components, so the pre-waveform access plan was expanded to include all seven; the earlier four-component metadata selection is retained. Record two-stage inclusion probabilities and weights. No validation or locked-test partition is opened.
- Select one 1,024-channel frequency tile per cadence without examining its spectra. Freeze random uniform variates first; use source headers only to determine common available frequency coverage. Select uniformly among intersecting 1-GHz strata, then uniformly inside the selected available interval. Preserve unavailable band coverage, selection density and the original provisional center. A separate immutable frequency plan is saved before spectral extraction. Do not choose apparently clean or previously successful regions.
- Acquire every stored integration of all six scans. Preserve source channel indices, descending/ascending conversion, actual MJD gaps, dtype and source-value masks. Nonfinite and exactly zero powers are conservatively unusable; zero measurement versus instrument/HDF5 fill is unresolved. Source arrays are unchanged and mask losses remain in denominators. Chunk-allocation metadata is not claimed verified. Retain inaccessible/invalid selections and technical failures; never silently replace them with easier spectra.
- Limit successful/attempted HTTP payload reservations to **8 GiB per acquisition invocation**, at most **256 MiB per file per invocation** and **48 source files**. These are extraction limits, not the multi-terabyte sizes of full originals. Retain counters for resumed invocations separately rather than pretending the allowance bounds cumulative interrupted traffic. Use stable-ETag HTTPS byte ranges, resumable hashed caches and an exclusive acquisition lock. Whole-file archive checksums remain unverified.
- Downloaded observations, range caches and generated numerical source arrays remain outside Git. Publish code, metadata/provenance, experiment ledgers, scientific summaries and figures.

## Evaluation contract

The first multi-group sensitivity experiment is exploratory and conditional on the acquired finite frame and predeclared injection distribution. It must report all selected/acquired/failed cadences, actual independent groups, original sample/axis hashes, coverage/masks, ambiguity bounds and every loss stage.

Keep physical-signal count separate from trial count. Compare arms on identical injected arrays and no-injection controls. Report full-declared and searchable-domain denominators. Keep conditional-placement uncertainty separate from acquisition-component uncertainty, and retain paired outcomes in resampling. A small number of successful components does not establish the main study's precision, generalization or noninferiority criteria.

No LLM, confirmed-origin classification, transmitter-prevalence constraint, or claim of a finalized representative sensitivity study is authorized by passing this pilot alone.
