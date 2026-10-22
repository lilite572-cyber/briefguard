# BriefGuard: reproducible sampling study and local video-review workbench

## Problem and preserved result

Sparse video review can miss a brief violation because the event was not selected,
or because the checker failed to recognize the selected evidence. BriefGuard
measures those causes separately and includes preprocessing cost.

The frozen CPU study remains unchanged: 832 clips / 32 source groups / 7,488 checks.
At eight frames, recall is 34.90% uniform, 43.62% change and 41.54% adaptive.
Adaptive minus change is -2.08 percentage points (95% interval -4.95 to +0.65).
The prespecified hypothesis is not supported. These are synthetic pixel-checker
results, not natural-video or VLM accuracy measurements.

## What changed

- Restyle replay using Tabler as a visual reference, with self-contained CSS.
- Explain sampling misses versus checker misses directly in the comparison.
- Verify all 18 case/method selections in a real browser; record viewport limits.
- Remove repetitive authorship narration from UI and routine documentation.

- Validate complete evidence inventories and reject stale summaries; comparison
  remains effective under optimized Python.
- Provide a blinded 16-clip development review packet and strict label scorer.
- Add a separate local workbench: requirements editor, selected frames with source
  timestamps, exact request export, guarded API execution and response inspection.
- Preserve request/response identity and use one persistent workbench spending
  ledger across bundles. Preparation and import make no network requests.
- Test malformed evidence, response references, interrupted imports, input limits
  and command generation. Reports limit judgments to selected frames.
- Preserve actual owner-host installation, reproduction and Docker evidence.
- Add an explicitly versioned NASA pilot v2 after the downloaded official GIF proved to contain 12 frames rather than v1's assumed minimum of 16. Pin its exact source hash, preserve all v1 files, and prepare six cases / eighteen checks without live inference.
- Record a $0.50 OpenAI pilot allocation within the user's combined $8 authorization for BriefGuard and Creative Experiments. Human labels and private key setup remain pending.

Supported workbench media: GIF, numeric NPZ and numbered PNG sequences. No MP4
support is claimed. The browser page prepares files/commands; decoding and model
execution run through the CLI. Imported JSON is operator-supplied and does not
prove provider origin. Paid execution is gated. The current pilot authorization is
OpenAI `gpt-4.1-mini-2025-04-14`, up to $0.50; it is not an additional allocation
for running the workbench in parallel. No paid request was made during implementation.

## Verification

Owner-host acceptance for commit `26d2118` passed fresh installation, 73 tests,
all 7,488 deterministic reproduction rows, static demo checks, Docker build and
73 Docker tests. All 259 archived source blobs match that commit.

Current workbench test counts, exact file hashes and evidence are in
`results/verification_workflow/`. Static JavaScript/DOM-stub checks are separate
from real browser QA. The earlier Docker result does not automatically cover
later implementation changes. See `docs/verification.md` for revision scopes.

The current pilot amendment passed all 95 local tests. All six CPU frozen hashes
and the v1 pilot runtime/config/protocol match their prior versions. Evidence:
`results/verification_vlm_preparation.json`. This does not repeat the historical
CPU reproduction or Docker run, or establish live-model quality.

The separate execution guard subsequently passed the complete 102-test local suite.
It checks real human inputs and halts subsequent HTTP attempts when earlier usage
or outcomes are unknown, without modifying the frozen v1/v2 runtime. The guarded
runner has not executed live inference; human annotations remain pending.

## Remaining acceptance

Replay browser checks passed for 18 case/method selections at 639 px;
390/1280 px, missing-resource injection and workbench browser QA remain pending.
Real human labels and live VLM/natural-video accuracy also remain pending. The small NASA pilot is separately frozen; one source and its artificial
corruptions cannot validate advertising-video compliance. Neither that protocol
nor fake-transport tests count as an executed model evaluation.

The formal security workflow remains incomplete; bounded source/regression review
must not be presented as a full audit. Implementation decisions and corrections
are recorded in `docs/development_notes.md`.

Keep the PR in draft until outstanding acceptance is actually recorded. No merge
or default-branch update is part of this work.

