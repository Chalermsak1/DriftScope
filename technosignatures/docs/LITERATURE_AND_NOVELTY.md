# Literature and novelty register

Reviewed for planning on 19 November 2026. This is a focused starting review, not a systematic or exhaustive literature survey. “Verified” below means the indicated primary abstract/page or cited passages were inspected; it does not mean independent reproduction of the paper. Proposed research choices remain our hypotheses.

## Primary evidence and implications

| ID | Primary source and access status | Relevant established work | Implication for this project |
|---|---|---|---|
| S01 | [Wright, Strategies and Advice for the Search for Extraterrestrial Intelligence](https://arxiv.org/abs/2107.07283), 2021; abstract inspected | Discusses search philosophies, upper limits, and research practice. | Define the searched signal domain and claims before building an assistant. |
| S02 | [Brzycki et al., Setigen: Simulating Radio Technosignatures for SETI](https://arxiv.org/abs/2203.09668), 2022; abstract inspected | Provides spectrogram/voltage signal synthesis and injection tools. | Injection by itself is established methodology; test its suitability and limitations here. |
| S03 | [Ma et al., A deep-learning search for technosignatures from 820 nearby stars](https://www.nature.com/articles/s41550-022-01872-z), 2023; primary abstract inspected | Demonstrates a deep-learning radio search with candidate reduction; follow-up did not re-detect the reported signals. | Compare with serious non-LLM methods; anomaly ranking is not confirmation. |
| S04 | [Choza et al., Technosignature Search of 97 Nearby Galaxies](https://arxiv.org/abs/2312.03943), AJ 2024; abstract and [author-hosted draft, sections 3.1.2–3.1.4](https://seti.berkeley.edu/galaxies/choza.pdf) inspected | Investigates injection recovery, normalization/bandpass effects, spectral response, and drift smearing. | A sensitivity audit must measure injection/score conventions and integration effects. We cannot claim those general issues as new discoveries. |
| S05 | [Breakthrough Listen 1327-star analysis and data release](https://seti.berkeley.edu/listen2019/overview.html); project page inspected | Supplies public-data context and links to the analysis, archive-format paper, and tools. | Archive data are potential inputs, but this project's exact usable cohort still requires an access audit. |
| S06 | [BLC1 verification flowchart](https://seti.berkeley.edu/blc1/flowchart.html); primary guidance inspected | Covers instrumental checks, pointing response, and distinguishing interference; explains possible source leakage into OFF pointings. | Cadence behavior is evidence requiring physical interpretation; rigid absence-in-OFF rules need testing. |
| S07 | [Hyperseti hit-search documentation](https://hyperseti.readthedocs.io/en/latest/pipeline/hitsearch.html); indexed official excerpts available, direct fetch unsuccessful | Discusses drift smearing and the footprint of a narrowband hit in search space. | Consider optimized comparison and event grouping, but validate exact software/version behavior locally before relying on it. |
| S08 | [AstroAlertBench](https://arxiv.org/abs/2605.05573), May 2026 preprint; primary abstract inspected | Evaluates multimodal LLMs on optical astronomical alert review, including the relationship between accuracy and self-evaluation. | Motivates separate evidence/factuality evaluation; optical-alert results do not establish radio SETI performance. |
| S09 | [Margot et al., A Search for Technosignatures Around 31 Sun-like Stars](https://arxiv.org/abs/2011.05265), 2021; primary abstract available in search | Includes preliminary pipeline injection-recovery testing. | Extend the baseline comparison/related-work review; do not describe injection recovery as a new field. |

The source summaries intentionally stay narrow. The complete methodological recommendations in the plan are proposed study design, not claims that these papers endorse our exact thresholds, sample sizes, or LLM architecture.

## Recent overlap requiring further verification

A search surfaced an October 2026 preprint titled [Missed Detections and False Alarms in a CNN Technosignature Detector on Breakthrough Listen Data](https://arxiv.org/abs/2610.22050). The primary full record/text could not be retrieved during this review. Treat it as an **unverified related-work lead**, not a numerical evidence source. Its apparent overlap makes retrieval and comparison an explicit first-stage task. No performance figures from third-party descriptions are adopted here.

Similarly, new detector/normalization work and survey releases should be checked through primary papers and code before the novelty statement is frozen. A web query returning few explicit LLM-radio papers does not establish that nobody is working on the topic.

## Contribution matrix to complete before publication

For every closest comparator, record: observation cohort; receiver; signal generator; integration/channel response; injected family/amplitude support; preprocessing stage of injection; split/group design; event definition; coverage and truncation policy; uncertainty method; native workload; expert review; cost; released code/data; and exact claim.

Proposed differentiators to verify:

1. A single stage-loss ledger spanning coverage, candidate generation, event grouping, cadence processing, and AI triage.
2. Matched comparisons against a strong feature/cadence model and an established detector, rather than a weak baseline alone.
3. Session/target-held-out evaluation plus deliberately unseen signal morphologies and independent simulator checks.
4. Evidence-linked LLM reports with measured factual error, abstention, and failure cost.
5. A controlled expert review-time experiment with explicit sensitivity constraints.

If these are already combined in prior work, select a narrower reproducible extension such as a new receiver/domain, independently validated physical effects, or a controlled negative result. An LLM wrapper around an existing plot is not automatically a scientific contribution.

## Search and update procedure

Before freezing the research claim, search primary astronomy literature and code for radio SETI injection recovery, completeness/selection functions, dedoppler losses, ON/OFF candidate ranking, event grouping, interference learning, multimodal review, and language-model assistance. Follow references and citing papers from S02–S04 and the recent lead. Record query, date, inclusion reason, version, and access limits.

Before the locked evaluation and again before manuscript submission, perform a bounded update of this review. Record any new overlaps and revise the title/claim where necessary. Do not delay a well-defined methods experiment indefinitely for an impossible proof that no similar work exists.
