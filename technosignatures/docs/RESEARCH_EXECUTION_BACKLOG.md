# Research execution backlog

Version 1.0 · all tasks below are planned unless explicitly marked complete. Priority denotes order/value, not a claim that the task has already run.

## Work packages and acceptance evidence

| ID | Priority | Task | Depends on | Acceptance evidence |
|---|---|---|---|---|
| R00 | Done | Preserve existing Load → Inject → Detect milestone | — | `run_001`, checksum, 13 tests, 9 repeat comparisons; already complete. |
| R01 | P0 | Read closest primary papers/code and resolve recent overlap lead | R00 | Contribution matrix; bounded claim; source access limits recorded. |
| R02 | P0 | Query archive metadata and select a feasible one-receiver access pilot | R00 | Manifest of proposed files, cadence links, sizes, licenses, and selection rule. |
| R03 | P0 | Acquire and validate one complete ON/OFF cadence | R02 | Hashes, header/axis/pointing/time audit, transfer/disk/runtime measurement. |
| R04 | P0 | Audit current channel coverage and candidate-cap behavior | R00 | Current 764/1024 starting-channel coverage reproduced; explicit cap/truncation tests. |
| R05 | P0 | Specify stage-outcome, hit, event, exposure and truth schemas | R03,R04 | Versioned record contracts; loss denominators reconstructible from records. |
| R06 | P0 | Generalize loader in a new research module | R03,R05 | Multiple shapes, channel orders, cadence gaps, corruption/non-finite checks; fixture unchanged. |
| R07 | P0 | Implement overlap-aware tiled search and complete hit output | R04,R06 | Whole-band/tile equivalence on a small case; no double counting or silent caps. |
| R08 | P0 | Implement path/time-aware event grouping | R05,R07 | Single-line secondary hits grouped; nearby/two-line cases preserved; grouping losses measured. |
| R09 | P0 | Implement cadence assembly/features | R03,R06,R08 | Actual timestamps and pointing roles preserved; chirp across gaps verified. |
| R10 | P0 | Implement channel/time-integrated injection options | R06 | Analytic limiting cases and numerical convergence; power/width/time conventions recorded. |
| R11 | P0 | Build versioned randomized injection manifests | R05,R10 | Hidden truth path; fixed seeds/parameters; 1,152-case pilot manifest arithmetic checked. |
| R12 | P0 | Test weak/off-grid/edge/collision and OFF-leakage cases | R08,R09,R11 | Complete stage ledger for every trial; ambiguous attribution retained. |
| R13 | P0 | Profile a small pilot and set access/compute bounds | R07,R11 | Measured cost per physical exposure/trial; full-run forecast and abort criteria. |
| R14 | P1 | Select main cohort and construct connected-component splits | R02,R03,R13 | No overlapping raw data, session, target, or near-duplicate leakage between partitions. |
| R15 | P1 | Run conventional detector comparison | R07,R10,R12,R14 | Local versus established pipeline results with separate score definitions and matched support. |
| R16 | P1 | Train/calibrate small feature ranker | R09,R14,R15 | Validation retention/burden curve; features exclude hidden truth. |
| R17 | P1 | Pilot physical realism and generator-shift checks | R10,R11,R15 | Independent synthesis check; simple versus integrated model recovery difference quantified. |
| R18 | P1 | Simulate statistical precision and freeze protocol | R13–R17 | Allocation/power memo; comparator, margins, weights and intervals frozen before test. |
| R19 | P1 | Render standardized candidate packets | R08,R09,R14 | Images preserve lines/units; no label-bearing filenames/difference images; input parity checked. |
| R20 | P1 | Screen text and multimodal LLM assistance | R16,R18,R19 | At most two initial variants, development-only outputs; evidence quality and total failure cost. |
| R21 | P1 | Decide AI branch continuation | R20 | Validation comparison; one selected arm, summary-only mode, or documented stop. |
| R22 | P1 | Freeze complete analysis/model/renderer/split versions | R18,R21 | Hashes, inaccessible-to-model truth, primary endpoint and test-access record. |
| R23 | P1 | Execute one locked technical comparison | R22 | Paired results, loss tables, uncertainty, all failures and truncations retained. |
| R24 | P1 | Recruit and pilot expert review protocol | R03,R18,R21 | Reviewer availability, common training, randomized assignments, time measurement definition. |
| R25 | P1 | Run human review experiment if feasible | R23,R24 | Case/reviewer-aware time and evidence-quality outcomes; limited injected-case precision stated. |
| R26 | P2 | Test external acquisition/receiver or unseen morphology | R23 | Separate transportability analysis and domain limits. |
| R27 | P1 | Independently reproduce representative locked results | R23 | Environment/source/data hashes, declared numeric tolerances, discrepancies resolved or reported. |
| R28 | P1 | Prepare reproducible benchmark/methods release | R01,R23,R27 | Data rights/citations, manifests, score definitions, figures, instructions, bounded claims. |
| R29 | P2 | Prepare AI-effectiveness manuscript if supported | R25,R26,R28 | Human/technical/cost evidence supports exact title and abstract; null results included. |

R13–R17 means all of those work packages, not a claim that they can be completed in an arbitrary order. The first implementation batch is R01–R13, stopping at each access/measurement gate if prerequisites fail.

## Scientific test plan

| Area | Test type | Required behavior/example | Gap in current fixture |
|---|---|---|---|
| Header/axis integrity | Unit and integration | Ascending/descending frequency, units, missing/truncated data, precise header reference | Only one validated shape/source currently accepted. |
| Injected signal physics | Analytic and convergence | Channel-integrated power, time smearing, fractional-channel phase, convergence as subsamples increase | Gaussian point samples only. |
| Cadence timing | Integration | Same physical chirp through ON/OFF gaps; no scan-time reset | No complete cadence. |
| Search coverage | Metamorphic/integration | Tile/whole equivalence, margins and masks in denominator; boundary crossing remains visible | Fixed common start band. |
| Catalogue integrity | Stress/integration | More than 50 real/synthetic maxima; no unreported clipping | Hard candidate cap. |
| Event grouping | Synthetic scenarios | One signal/secondary peaks; two nearby signals; crossing tracks | Starting-frequency suppression only. |
| Cleaning/calibration | Injection-recovery | Inject before processing; quantify each cleaning stage's losses | No full preprocessing chain. |
| Origin/reference labels | Annotation audit | Distinguish simulated positive, supported RFI, unresolved native case | No expert native-event set. |
| Split leakage | Data-integrity assertions | Shared raw/session/target components never span partitions | No scientific cohort split. |
| Model input parity | Contract/integration | Same features across arms, no truth-bearing metadata, fixed image scaling | No model input interface. |
| LLM factuality | Evidence audit | Recompute every quoted measurement; references resolve to actual supplied evidence | No LLM tested. |
| LLM technical failures | Failure injection | Invalid JSON, timeout, tool error, out-of-domain case retain/escalate and count toward burden | No failure policy implemented. |
| Statistical analysis | Reference calculations and simulations | Denominators reconstruct, paired grouping preserved, interval behavior at zero/rare failures | No population inference implemented. |
| Human study | Assignment/pilot checks | No reviewer sees duplicate case conditions; active timing and counterbalancing verified | No reviewer study. |
| Reproduction | End-to-end | Fresh environment, subset rerun, logged numerical tolerances and all manifests | Same-environment repeat only. |

All critical scientific behaviors must have explicit pass/fail or reported-uncertainty evidence. Line coverage alone is not an acceptance target. Do not add repetitive tests that merely assert implementation details without validating a scientific behavior.
