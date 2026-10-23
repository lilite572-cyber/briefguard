# Related work and contribution boundary

Checked against primary papers, author project pages, and official repositories on **2026-10-22**. This is a targeted review, not an exhaustive systematic review. Dates below are the first public preprint date unless stated otherwise. A paper's reported findings are not experiments executed by this project.

## What this project contributes

BriefGuard is an independently reproducible **CPU reference study** of frame selection for brief visual requirement violations. Its intended contribution is a transparent experimental pipeline: synthetic data with exact temporal labels, source-grouped splits, controlled sampling budgets, measured preprocessing overhead, separate evidence-capture and checker metrics, and inspectable failures.

Adaptive frame selection, relevance/coverage tradeoffs, transient-event benchmarks, video text evaluation, and selective prediction all have substantial prior work. This repository makes **no claim of a new sampling paradigm, state-of-the-art performance, or the first video brief checker**. A simple locally implemented heuristic is an experimental treatment, not a claim of algorithmic novelty. Generalization to naturally generated advertising videos requires separate data and human validation.

## Comparison of primary sources

The task, method, data and metrics columns summarize the cited sources. The final column is **our interpretation** of their relationship to this small study. It should not be read as an author-acknowledged limitation in every case.

| Source and publication date | Task | Method | Data | Metrics | Scope and relationship to BriefGuard |
| --- | --- | --- | --- | --- | --- |
| [InfoShot: Shot-Aware Frame Sampling for Video Understanding](https://arxiv.org/abs/2603.17374), 2026-03-18 | Retain brief critical evidence under a frame limit | Shot segmentation and complementary representative/unusual frames | SynFlash synthetic anomalies; real anomaly and general video datasets | Anomaly hit rate and downstream QA | Closest prior; already covers subsecond, localized and camouflaged events. BriefGuard is a narrower reference study, not the invention of transient-event evaluation. |
| [KFS-Bench](https://arxiv.org/abs/2512.14017), 2025-12-16; WACV 2026 | Directly evaluate keyframe sampling | Annotated relevant scenes; similarity/clustering sampling | LongVideoBench and Video-MME with relevant-scene annotations | Keyframe rate, scene hit rate, sampling balance, unified sampling score, QA accuracy | Motivates separating sampled evidence from answering performance. Its one-second annotation granularity differs from our exact synthetic frame intervals. |
| [VBench](https://arxiv.org/abs/2311.17982), 2023-11-29; CVPR 2024 | Evaluate video-generation quality | Dimension-specific evaluators and human preference alignment | Prompt suite, generated videos and human preferences | Sixteen dimensions including subject consistency, flicker and spatial relationships | Quality dimensions inform requirement design; aggregate generator quality is not a calibrated probability of missing a particular brief violation. |
| [VBench-2.0](https://arxiv.org/abs/2503.21755), 2025-03-27; revised 2025-08-20 | Evaluate intrinsic faithfulness | VLM/LLM generalists and specialist evaluators | Generated-video prompt suites and human annotations | Human fidelity, controllability, creativity, physics and commonsense dimensions | Broader semantic and physical evaluation than our narrow synthetic task. BriefGuard neither implements nor replaces this suite. |
| [VTR-Bench](https://arxiv.org/abs/2610.01499), 2026-10-01 | Evaluate text and scenario fidelity in generated videos | Carrier-specific transcription, requirement checklist, agentic generation refinement | Three hundred prompts across five scenarios, including advertisements | Bounded word error rate and checklist satisfaction | Direct application prior. Our question concerns loss of short-lived evidence during sampling, rather than introducing video text or advertising compliance evaluation. |
| [TemporalBench](https://arxiv.org/abs/2410.10818), 2024-10-14 | Evaluate fine-grained temporal understanding | Detailed temporal annotations; evaluation designed to reduce multiple-choice shortcuts | Approximately ten thousand QA pairs derived from approximately two thousand human annotations | QA measures including Multiple Binary Accuracy | Supports contrastive cases and shortcut checks. Capturing a changed frame is not equivalent to temporal reasoning. |
| [Adaptive Keyframe Sampling (AKS)](https://arxiv.org/abs/2502.21271), 2025-02-28; CVPR 2025 | Efficient long-video understanding | Training-free optimization of query relevance and temporal coverage | LongVideoBench and Video-MME | QA accuracy under fixed frame/token budgets | Relevance plus coverage is established. Our cheap visual heuristic is not an AKS reproduction and does not imply superiority over AKS. |
| [Q-Frame](https://arxiv.org/abs/2506.22139), 2025-06-27; ICCV 2025 | Adapt visual evidence to the query and compute budget | CLIP-like matching, Gumbel-Max selection and multi-resolution allocation | MLVU, LongVideoBench and Video-MME | QA accuracy and computational tradeoffs | Equal frame count does not guarantee equal visual-token cost. BriefGuard fixes selected-frame resolution and reports preprocessing separately. |
| [VideoTree](https://arxiv.org/abs/2405.19209), 2024-05-29; CVPR 2025 | Query-aware reasoning over long videos | Iterative selection and hierarchical coarse-to-fine representation | EgoSchema, NExT-QA and long Video-MME | QA accuracy and inference efficiency | Multistage adaptive allocation is prior art. Feature extraction, intermediate descriptions and extra calls must enter any cost comparison. |
| [SeViLA](https://arxiv.org/abs/2305.06988), 2023-05-11; NeurIPS 2023 | Localize evidence and answer video questions | BLIP-2 localizer/answerer; forward selection and reverse pseudo-label refinement | Video QA and event benchmarks, including NExT-QA, STAR, How2QA and VLEP | Task accuracy and keyframe ablations | Supports modular localization and answering. Its learned components and training costs are outside the lightweight CPU reference experiment. |
| [Selective Classification for Deep Neural Networks](https://arxiv.org/abs/1705.08500), 2017-05-23; NeurIPS 2017 | Abstain to trade coverage for prediction error | Confidence-based selective classification | CIFAR and ImageNet | Selective risk and coverage | Any human-review extension must report both remaining error and the fraction automated. Sending everything to a person is not useful automated performance. |
| [Conformal Risk Control](https://arxiv.org/abs/2208.02814), 2022-08-04; ICLR 2024; revised 2025-06-13 | Calibrate expected bounded monotone losses | Held-out calibration with finite-sample correction | Computer-vision and NLP examples | False-negative, graph-distance and F1-related risks | Formal claims require the stated assumptions and calibration procedure. A heuristic threshold or LLM self-confidence does not inherit these guarantees. |

## Closest prior and implementation availability

InfoShot is the strongest reason to narrow the claim. Its [paper and appendix](https://arxiv.org/html/2603.17374v1) describe the algorithm and SynFlash. However, the [official repository](https://github.com/mengyu02/InfoShot) exposed only a title-only `readme.md` when inspected; no runnable implementation or dataset was visible. Therefore any locally implemented shot-aware comparator is explicitly a **paper-inspired reference**, not the authors' implementation or a reproduction of their published scores. Differences in feature representation, segmentation, data and compute must be disclosed.

| Official resource | What was visible on the check date | What this review does not establish |
| --- | --- | --- |
| [VBench family](https://github.com/Vchitect/VBench) | Unified repository, including a `VBench-2.0` directory, evaluator code and prompt resources | That all components are installed, executable on an eight-GB laptop, or reproduced here |
| [VTR-Bench](https://github.com/hardenyu21/VTR-Bench) | Evaluation/generation code, prompt and checklist annotations; repository declares Apache-2.0 | That all externally hosted generated videos are downloadable or share the code's redistribution terms |
| [AKS](https://github.com/ncTimTang/AKS) | Feature extraction, frame selection and evaluation files | A successful local installation or our reproduction of published results |
| [Q-Frame](https://github.com/xiaomi-research/q-frame) | Authors' implementation repository | Performance on our synthetic data or feasibility of its full stack on the target laptop |
| [VideoTree](https://github.com/Ziyang412/VideoTree) | Official code and setup instructions | An independently verified API cost or locally reproduced result |
| [SeViLA](https://github.com/Yui010206/SeViLA) | Official localizer/answerer code and model instructions | That training or inference fits the local memory budget |
| [KFS-Bench](https://github.com/NEC-VID/KFS-Bench) | Repository linked by the primary paper | Permission to redistribute source videos from its underlying datasets |
| [Conformal Risk Control](https://github.com/aangelopoulos/conformal-risk) | Authors' reference repository | A guarantee for our checker without implementing and validating the required procedure |

Availability is a dated observation, not a promise. This project does not bundle third-party datasets or copy their code merely because a public repository exists.

## Yerzat Dulat's public repositories

[github.com/higgsfield](https://github.com/higgsfield) is the personal account labelled **Yerzat Dulat**. It is distinct from the `higgsfield-ai` organization. Pinned repositories include both his own educational implementations and organizational projects. Repository ownership or pinning is not evidence of authorship of the underlying research paper.

| Repository | Classification supported by its README | Relevant lesson for this project |
| --- | --- | --- |
| [RL-Adventure](https://github.com/higgsfield/RL-Adventure) | Step-by-step tutorial implementing published DQN-family methods with links to their papers | Use tractable experiments and explain components before increasing scale |
| [Imagination-Augmented-Agents](https://github.com/higgsfield/Imagination-Augmented-Agents) | Tutorial of imagination-based planning methods, explicitly referencing the original work | Separating a cheap planning signal from expensive verification is a useful analogy; it supplies no guarantee for frame sampling |
| [np-hard-deep-reinforcement-learning](https://github.com/higgsfield/np-hard-deep-reinforcement-learning) | IPython tutorials implementing neural combinatorial optimization and pointer networks | Its README explicitly acknowledges stronger classical TSP baselines; benchmark against simple methods and state negative results |
| [higgsfield-ai/higgsfield](https://github.com/higgsfield-ai/higgsfield) | Organizational GPU orchestration and model-training infrastructure pinned on the personal profile | Public infrastructure does not establish access to the commercial video-generation models' source |

The reviewed personal repositories support an implementation/tutorial classification. We do not infer that Dulat invented the algorithms they explain or that these repositories enumerate all his research. No reinforcement-learning component is added to BriefGuard solely to resemble his interests: it would add training cost and complicate attribution without answering the present experimental question.

## Consequences for interpretation

1. **Evidence capture and recognition are different measurements.** A sampler can miss the interval; a checker can also fail despite receiving it. Report both stages.
2. **Match downstream resources and expose upstream resources.** Equal selected frames, size and checker settings are useful controls, but a dense cheap prepass is still additional work.
3. **Synthetic intervals isolate a mechanism.** They do not measure the prevalence of natural generation failures, commercial review savings, or general visual-language competence.
4. **A negative result is informative.** If adaptive selection cannot beat change-based selection, or misses subtle changes, report that boundary without changing settings after observing the test split.
5. **Human review remains a separate empirical step.** Generated ground truth should be audited by a person before making claims about human agreement; automated visual inspection is not a human annotation.

Suggested description when presenting the repository:

> An independently reproducible CPU reference study of short synthetic visual violations under a limited downstream frame budget. It compares sampling strategies, measures preprocessing overhead, separates evidence capture from checker performance, and exposes failure cases. It does not establish state-of-the-art performance or generalization to natural video-generation failures.
