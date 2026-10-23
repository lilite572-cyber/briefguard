# Development notes

These notes record implementation decisions, corrections and verification on
2026-10-22 and 2026-10-23.

## Completed live follow-up

On 23 October, Amir's six-case observations and source confirmation were frozen
before the owner executed 18 real OpenAI checks. One uncertain label remains
indeterminate. The saved responses demonstrate both misses despite selected event
frames and evidence citations outside human event intervals. See the
[live report](live_pilot_results.md). This owner review does not complete the
separate 16-case CPU audit or the personal code walkthrough below. No new paid
inference is required to reproduce the published calculations.

## Continuation from the published branch

The continuation started from the clean published head
`991edc8268bc8b57b7c33092af9f67ab3ece0b0b`. GitHub PR #1 was checked and had the
same head. The original `Pasted text(1).txt` task was read in full. Work continued
in an isolated local clone on `research/briefguard`; the earlier checkout was
left unchanged. The original protocol, freeze, analytical sources and held-out
artifacts remain the historical experiment, not a development set for tuning.

The follow-up added methodology and input/output checks, a VLM-pilot workflow
and a blinded human-review package. Human labels, paid-API approval and a record
of personal code review were pending at that stage. The live pilot later received
actual authorization and owner labels; the other personal checks remain open.

Fresh-source reproduction again matched all 7,488 deterministic rows. The
comparison script's use of Python `assert` was identified as a verification
defect: optimized Python can omit assertions. Follow-up changes make comparison
fail explicitly and validate completed evidence before reporting it. This fixes
verification and presentation; it does not amend or rerun a corrected sampling
algorithm. See [verification](verification.md) for the final executed scope and
remaining environment restrictions.

## Starting point

Amir wanted a research project about short advertising-video brief violations,
with reproducible experiments and a demo he could explain in an AI Engineer
interview. His hardware constraint was a MacBook Air M2 with 8 GB RAM. No paid
API budget was authorized. Those requirements came from the project brief.

## Choices made during implementation

| Choice | Reason in this experiment | Cost or limitation |
|---|---|---|
| Start with generated clips and a pixel checker | Run locally and know the exact event interval | No evidence yet about natural videos or VLM accuracy |
| Include a change sampler alongside uniform | Check whether adaptive complexity earns its cost | Beating uniform alone cannot establish the main hypothesis |
| Give the selectors pixels, without the brief or region coordinates | Avoid a privileged localization shortcut | The heuristic cannot prioritize a region because the brief calls it important |
| Split by source seed | Keep related variants together | The effective sample is source groups, not thousands of independent clips |
| Count the complete preprocessing pass | Expose work done before the selected frames reach the checker | Equal checker budgets still have different CPU costs |
| Keep subtle corruptions below the checker tolerances | Exercise the distinction between capture and recognition | Their zero recall is expected by construction |

## What the first result says

The saved test run is `72b02803d9e0b835`. At eight frames, adaptive improves on
uniform but does not demonstrate an advantage over change. There was no
post-test adjustment to turn this into a positive result.

Two examples are worth following in the code:

- In `s010000-distractor-forbidden_patch-6`, uniform selects frames 6 and 18
  around an event occupying [8,14). It never supplies the violation to the checker.
- In `s010000-distractor-forbidden_patch-12`, adaptive selects frame 12 inside
  [10,22), but the checker still returns pass. The corruption is subtle and
  deliberately below that checker's tolerance.

The saved [error analysis](error_analysis.md) contains the full selected indices
and counts. These are illustrative examples chosen after the run.

## Mistakes found and corrected

The initial demo exporter looked for `frames_sha256`, while runner predictions
used `pixels_sha256`. That meant its intended reconstruction check was skipped.
Commit `5561328` corrected the lookup and included a mismatch rejection test.

The exporter also accepted rows without checking that the run had finished.
Commit `67f2359` added completion metadata and row-count checks. The actual test
replay was exported again after this fix. Both fixes concern presentation of
saved results; the frozen analytical code and experiment remain unchanged.

The formal security workflow encountered a tool error reading a valid committed
file. It remains incomplete. The separate static source review is not a
completed formal security scan or an independent human audit.

## Personal review before presenting

Complete these checks and add your actual observations. Leave items open until
you have done them; automated execution does not complete a personal review.

- [ ] Follow one clip from generation through selection, checking and scoring.
- [ ] Explain how the adaptive score and temporal diversity term choose frames.
- [ ] Recompute one reported metric from saved prediction rows.
- [ ] Explain why source clusters, rather than clips, are bootstrapped.
- [ ] Inspect the two failure examples above and record what you see.
- [ ] Run the documented reproduction commands yourself and record the outcome.
- [x] Review the six separate VLM pilot cases before model outputs (saved owner labels).
- [ ] Complete the separate 16-case CPU human-review CSV, or retain its pending status.

Record completed personal checks with the command, result and your observations.
