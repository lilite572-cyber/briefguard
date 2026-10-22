# BriefGuard: reproducible temporal sampling study and validation follow-up

## Why

A sparse video checker can approve a clip because it missed a short violation,
or because it failed to recognize evidence that it sampled. BriefGuard measures
these failure modes separately, including the cost of content-aware preprocessing.
This is a controlled CPU reference study, not a new model or a SOTA claim.

## Preserved study and result

The original protocol, six frozen source/protocol hashes, splits and raw held-out
results are unchanged. The study contains 832 clips from 32 source groups and
7,488 checks. At eight frames, recall is 34.90% for uniform, 43.62% for change,
and 41.54% for adaptive. Adaptive minus change is -2.08 percentage points
(95% interval -4.95 to +0.65). The prespecified hypothesis is not supported.
These results use synthetic pixels and a deterministic checker, not a VLM.

## Completion changes

- Validate complete run inventories, unique paired units, identity and annotations
  before reporting or exporting a replay; reject stale saved summaries.
- Replace comparison assertions with explicit checks that also work under `python -O`.
- Add a static replay checker and a clean committed-source acceptance script.
- Prepare a blinded human-review packet: 16 clips from distinct development
  sources, unknown answers, draft/resume support, and a strict label scorer.
- Add a separately frozen exploratory VLM preparation/execution workflow with
  explicit human/source gates, fixed approval limits, bounded retries, recorded
  outcomes and identity-bound resume. No paid inference was run.
- Document actual acceptance gaps, bounded static review, AI contributions and
  Russian interview preparation.

## Executed verification

- All 73 tests passed on the integrated implementation.
- A clean archive of the published baseline reproduced all 7,488 deterministic
  rows using preinstalled pinned dependencies. An independent AI recheck,
  without importing BriefGuard, reproduced counts and paired bootstrap intervals.
- The strict inventory validator accepted 832 clips / 32 groups / 7,488 rows.
- Static replay checks verified six cases, 18 method-case mappings, 153 PNGs and
  576 exact sprite frames. This is not browser interaction or console testing.
- Partial pilot preparation produced three synthetic clips and nine selections.
  Live API calls, human labels and natural-video evaluations: zero.

See `results/verification_followup/` and `docs/verification.md` for evidence,
revision scope and environment limits. The historical verification is preserved.

## Pending acceptance and empirical work

Fresh dependency downloads, Docker execution and browser visual QA were blocked
in the agent environment. `scripts/acceptance.sh`, `scripts/finish_local.sh` and
`docs/browser_checklist.md` make the remaining owner-run steps concrete.
Human annotation and Amir's personal code walkthrough remain pending.

The proposed natural-media pilot uses one credited NOAA/NASA EPIC timelapse
source, with separately documented provenance and human source confirmation.
The source has not been downloaded here. Artificial corruptions of one source
cannot establish accuracy on natural generated ads. The separate six-clip pilot
requires approval for OpenAI `gpt-4.1-mini-2025-04-14`, a USD 0.50 total limit,
and at most 36 attempts including retries, plus completed preparation and labels.
It is exploratory and will not change the original hypothesis or held-out result.

The earlier formal Codex Security scan remains incomplete. The follow-up is a
bounded AI static/regression review with an exact code revision, not a full audit.

## Contribution

Amir Asan supplied the project brief, use case and constraints. Codex and delegated
agents implemented the study and follow-up, executed automated experiments and
checks, and drafted the analysis and documentation. Human annotations and Amir's
own code review are not attributed to agents or marked complete. Keep this PR a
draft until the remaining acceptance decisions are actually completed.
