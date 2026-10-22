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

Supported workbench media: GIF, numeric NPZ and numbered PNG sequences. No MP4
support is claimed. The browser page prepares files/commands; decoding and model
execution run through the CLI. Imported JSON is operator-supplied and does not
prove provider origin. The guarded execution command requires separate model and
budget approval; no paid request was made during implementation.

## Verification

Owner-host acceptance for commit `26d2118` passed fresh installation, 73 tests,
all 7,488 deterministic reproduction rows, static demo checks, Docker build and
73 Docker tests. All 259 archived source blobs match that commit.

Current workbench test counts, exact file hashes and evidence are in
`results/verification_workflow/`. Static JavaScript/DOM-stub checks are separate
from real browser QA. The earlier Docker result does not automatically cover
later implementation changes. See `docs/verification.md` for revision scopes.

## Remaining acceptance

Browser interaction, real human labels and live VLM/natural-video accuracy remain
pending. The small NASA pilot is separately frozen; one source and its artificial
corruptions cannot validate advertising-video compliance. Neither that protocol
nor fake-transport tests count as an executed model evaluation.

The formal security workflow remains incomplete; bounded source/regression review
must not be presented as a full audit. Development history and contribution
records are centralized in `docs/development_notes.md`.

Keep the PR in draft until outstanding acceptance is actually recorded. No merge
or default-branch update is part of this work.
