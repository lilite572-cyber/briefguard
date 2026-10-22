# Add BriefGuard: reproducible temporal sampling study

## Why

A sparse video checker can approve a clip because it missed a short violation, or because it failed to recognize evidence that it did sample. These failure modes require separate measurement, and content-aware preprocessing must be included in the cost comparison.

## Changes

- Add original synthetic source-grouped clips, three samplers, a deterministic selected-frame checker, and bounded video normalization.
- Freeze the hypothesis, splits and analytical code before held-out evaluation; preserve raw predictions, resources and paired source-cluster bootstrap intervals.
- Add an offline replay, transparent error analysis, related-work comparison and Russian interview guide.
- Include a separately gated VLM pilot adapter with fake-transport tests; no live VLM evaluation is claimed.

## Results

At eight frames, recall is 34.90% for uniform, 43.62% for change, and 41.54% for adaptive. The adaptive-minus-change difference is -2.08 percentage points (95% interval -4.95 to +0.65). The prespecified hypothesis is not supported.

## Verification

The held-out run covers 832 clips from 32 source groups, with 7,488 checks across all budgets. A clean source checkout reproduces every deterministic row. Automated tests and static demo checks pass; see `results/verification.json` and `docs/verification.md` for the executed checks and environment limits.

## Scope

This is a controlled CPU reference study, not evidence of production accuracy on natural generated video. Human annotation review, live VLM evaluation, Docker build and browser visual QA remain pending. The formal security workflow status is documented separately.
