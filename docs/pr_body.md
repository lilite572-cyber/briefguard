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
- Add an explicitly versioned NASA pilot v2 after the downloaded official GIF proved to contain 12 frames rather than v1's assumed minimum of 16. Pin its exact source hash, preserve all v1 files, and prepare six cases / eighteen checks before live inference.
- Record a $0.50 OpenAI pilot allocation within the user's combined $8 authorization for BriefGuard and Creative Experiments. Amir subsequently supplied six human labels and source confirmation; all 18 live requests completed. Usage-based cost estimate: $0.006478.

Supported workbench media: GIF, numeric NPZ and numbered PNG sequences. No MP4
support is claimed. The browser page prepares files/commands; decoding and model
execution run through the CLI. Imported JSON is operator-supplied and does not
prove provider origin. Paid execution is gated. The current pilot authorization is
OpenAI `gpt-4.1-mini-2025-04-14`, up to $0.50; it is not an additional allocation
for running the workbench in parallel. The executed six-case exploratory pilot is documented in `docs/live_pilot_results.md`; no additional workbench spending was performed.

## Verification

Final clean-source acceptance at `bcb67d3fb4283ea0884efb91a25c2a695e99accf`
downloaded the pinned dependencies into a new environment, passed `pip check`
and 102 tests, ran all 7,488 CPU units with zero cache reuse and matched every
deterministic evidence row. All 305 archived tracked blobs match that commit.
Static replay checks verified six cases, eighteen method/case mappings, 153
images and 576 sprite frames; workbench JavaScript/command checks passed.
Saved live-pilot outcomes and cost arithmetic were verified without new inference.
Evidence: `results/verification_final/status.json` and adjacent logs.

Owner-host acceptance for commit `26d2118` passed fresh installation, 73 tests,
all 7,488 deterministic reproduction rows, static demo checks, Docker build and
73 Docker tests. All 259 archived source blobs match that commit.

Current workbench test counts, exact file hashes and evidence are in
`results/verification_workflow/`. Static JavaScript/DOM-stub checks are separate
from real browser QA. The earlier Docker result does not automatically cover
later implementation changes. A new Docker attempt was denied access to the
daemon socket by the execution sandbox; no current build result is claimed.
See `docs/verification.md` for revision scopes.

The current pilot amendment passed all 95 local tests. All six CPU frozen hashes
and the v1 pilot runtime/config/protocol match their prior versions. Evidence:
`results/verification_vlm_preparation.json`. This does not repeat the historical
CPU reproduction or Docker run, or establish live-model quality.

The separate execution guard subsequently passed the complete 102-test local suite.
It checks real human inputs and halts subsequent HTTP attempts when earlier usage
or outcomes are unknown, without modifying the frozen v1/v2 runtime. The guarded
runner subsequently completed 18/18 live requests. Offline export verification
recomputes the status metrics and token costs and records two citations outside
human event intervals. Status agreement is not evidence-grounding accuracy.

## Remaining acceptance

Replay browser checks passed for all 18 case/method selections at 1280 px on
2026-10-23, with loaded evidence images and no console errors or overflow.
Workbench requirement entry, invalid-budget guard, command copying and JSON
download passed. See `results/verification_final/browser.json`. The 390 px layout,
missing-resource injection and workbench GIF preview remain unverified.
The separate 16-case CPU human audit and personal code walkthrough remain pending.
The six-case live VLM pilot now has actual owner labels and saved model responses;
one natural source and its artificial corruptions cannot validate advertising-video
compliance or establish sampler superiority. Frozen CPU results remain unchanged.

The formal security workflow remains incomplete; bounded source/regression review
must not be presented as a full audit. Implementation decisions and corrections
are recorded in `docs/development_notes.md`.

Keep the PR in draft until outstanding acceptance is actually recorded. No merge
or default-branch update is part of this work.

