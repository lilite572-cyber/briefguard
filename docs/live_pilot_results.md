# Live VLM pilot: observed results

Recorded 23 October 2026. Execution code commit:
`1ba4029ae16b34a0a5cb23d4e4fe15aadbde4bd5`.
This report follows the unchanged [v2 protocol](natural_video_pilot_v2.md).
The user launched the guarded runner from their Terminal; the agent verified
the saved artifacts without repeating inference.

## Execution and human reference

OpenAI Responses API, `gpt-4.1-mini-2025-04-14`, eight frames per check.
Six cases × three methods produced 18 completed requests, no retries and no
operational errors. All 18 outputs include the pinned model and token usage.
Returned usage totals 13,719 input and 619 output tokens. At the protocol's fixed
rates the cost estimate is **$0.006478**. The ledger reserved $0.18 against its
$0.50 allocation; reservations are not charges. This estimate is not an invoice
or verification of unrelated account spending.

Amir reviewed full sequences and specified event intervals before model outputs
were available. His chat observations were transcribed into the CSV; uncertainty
was retained. He recognized the original NASA sequence on its official source page.
This is an owner review with hidden method outputs, not an independent expert
study. It does not certify his personal code walkthrough or the separate 16-case
CPU audit. The original labels and run identity are frozen in the saved run.

| Case | Human observation | Uniform | Change | Adaptive |
| --- | --- | --- | --- | --- |
| 01, synthetic | Red element, [32,38) | pass | fail | fail, cites frame 60 outside event |
| 02, synthetic | Product absent, [33,39) | pass | indeterminate | pass |
| 03, NASA clean | pass | pass | pass | pass |
| 04, synthetic | indeterminate: uncertain color match | pass | pass | pass |
| 05, NASA overlay | Magenta rectangle, [6,12) | fail | fail | fail |
| 06, NASA blackout | Earth absent, [4,6) | fail | pass | fail, also cites frame 6 outside event |

Case 04 is excluded from human-agreement denominators, not converted to a clean
negative. The original status-based metrics are reproduced unchanged below.
`fail` is the model's classification, not a guarantee of a correct explanation.

| Stratum | Method | Positive cases classified fail | False approvals | Model indeterminate |
| --- | --- | --- | --- | --- |
| Synthetic | uniform | 0/2 | 2/2 | 0 |
| Synthetic | change | 1/2 | 0/2 | 1 |
| Synthetic | adaptive | 1/2 | 1/2 | 0 |
| NASA-derived | uniform | 2/2 | 0/2 | 0 |
| NASA-derived | change | 1/2 | 1/2 | 0 |
| NASA-derived | adaptive | 2/2 | 0/2 | 0 |

All methods passed the one human-negative NASA case. There is no human-negative
synthetic case after excluding the uncertain label, so synthetic false-alarm rate
is undefined. Counts are descriptive; do not rank methods from this sample.

## Evidence consistency, examined after the run

All 14 cited frame indices belong to the corresponding supplied selections.
Twelve lie inside the human event interval and two lie outside. This temporal
consistency check does not establish that every in-interval explanation is true.
It is an additional post-hoc diagnostic, not a newly prespecified endpoint.

- Case 01/adaptive rejects the clip but locates the red element at frame 60;
  Amir's event interval is [32,38). The status-only recall counts this as detected,
  while its cited location does not match the reviewed event.
- Case 06/adaptive cites blackout at frames 4, 5 and 6. The reviewed blackout ends
  before frame 6, where Amir reported Earth visible again.
- Case 02/change and adaptive receive event frames yet do not return `fail`.
  Case 06/change also receives a blackout frame yet returns `pass`.

This supports separating selection coverage, final classification and evidence
grounding in the engineering design. It does not show improved model quality.

## Limits and reproducibility

There are three synthetic source groups and **one natural source** (NOAA/NASA EPIC,
*As the World Turns*, 17 April 2019). Its clean, blackout and overlay variants are
dependent observations. The original GIF is normalized; errors are artificially
inserted, not naturally occurring failures of video generation. Eight of twelve
frames are selected and the overlay spans half the sequence. These are easy,
bounded integration cases, not a representative advertising benchmark. No
confidence interval, causal effect, calibrated confidence, engagement gain or
adaptive superiority is established. The original negative CPU result stands.

The public [evidence folder](../results/vlm_pilot_v2_live/) contains model statuses,
evidence text, selections, returned usage, original human CSV, frozen hashes and
summary. It omits credentials, images and provider-specific response IDs. Raw
requests/responses remain in the private packet. File hashes and local saved API
records are reproducibility evidence, not independent provider attestation.

Recompute the report without a key or network:

```bash
python scripts/report_live_pilot.py --verify results/vlm_pilot_v2_live
```

The verifier checks all 18 case/method combinations, human-label hash, supplied
frame citations, summary counts and exact token-cost arithmetic. Export from a
completed private packet is also supported with `--source PACKET --out NEW_DIR`;
existing exports are refused. Frozen protocols/runtime and original outputs were
not edited. Fresh API calls are stochastic and are not required to replay these
saved calculations.
