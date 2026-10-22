# Development notes

These notes describe the recorded work session on 2026-10-22. They are not a
retrospective personal diary. The implementation and initial analysis were done
by Codex and delegated AI agents in response to Amir Asan's project brief.

## Continuation from the published branch

The continuation started from the clean published head
`991edc8268bc8b57b7c33092af9f67ab3ece0b0b`. GitHub PR #1 was checked and had the
same head. The original `Pasted text(1).txt` task was read in full. Work continued
in an isolated local clone on `research/briefguard`; the earlier checkout was
left unchanged. The original protocol, freeze, analytical sources and held-out
artifacts remain the historical experiment, not a development set for tuning.

Codex performed the follow-up implementation and execution. Separately tasked
AI agents reviewed methodology and input/output boundaries and prepared the
VLM-pilot and blinded human-review workflows. These are additional AI reviews,
not independent human experts. Amir requested the continuation and its acceptance
criteria; he has not yet supplied human labels, a paid-API approval or a record
of personal code review.

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

These choices were implemented by the agents. The record does not establish
that Amir personally selected or validated each one.

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
file. It remains incomplete. The separate static code review is an AI review,
not a completed formal security scan or an independent human audit.

## Division of work

| Work | Recorded contributor and status |
|---|---|
| Research question, intended audience and hardware constraints | Amir's supplied brief |
| Literature search, protocol, code, tests, execution and initial interpretation | Codex and delegated AI agents |
| Second methodology and source reviews | Separately tasked AI agents |
| Request to review the project's presentation and AI attribution | Amir |
| Personal code review and independent result verification | No completed record yet |
| Human checks of video labels | Pending |

## Personal review before presenting

Complete these checks and add your actual observations. Leave items open until
you have done them; an agent run does not complete a personal review.

- [ ] Follow one clip from generation through selection, checking and scoring.
- [ ] Explain how the adaptive score and temporal diversity term choose frames.
- [ ] Recompute one reported metric from saved prediction rows.
- [ ] Explain why source clusters, rather than clips, are bootstrapped.
- [ ] Inspect the two failure examples above and record what you see.
- [ ] Run the documented reproduction commands yourself and record the outcome.
- [ ] Complete the human-review CSV, or keep human validation marked pending.

For an interview, describe the contribution you can actually demonstrate. The
current record supports “I set the question and constraints and used Codex agents
to build and run the first version. I am reviewing the implementation.” Claims
about personal implementation or verification need the corresponding completed work.
