# Verification record

Checked on 2026-10-22. This record distinguishes automated source/artifact review
from human annotation validation, which remains **pending**.

## Second AI review of source and saved results

A separately tasked AI agent inspected `data.py`, `sampling.py`, `verifier.py`,
`runner.py`, `metrics.py`, and the experiment protocol. Selectors receive pixels
only; the verifier receives selected pixels and the public template. Ground-truth
intervals enter scoring, not selection or verification. The paired bootstrap
resamples source clusters and preserves sibling variants and method pairings.
The runner checks frozen source/configuration identity and cached run/unit identity.

The reviewer separately parsed the saved test predictions, without rerunning or
tuning the experiment. At the primary budget, all observations contained exactly
eight unique selected frames, and recorded event coverage agreed with the
annotated integer half-open intervals. Counts reproduced from the saved rows were:

| Method | Detected / violating clips | False alarms / clean clips |
|---|---:|---:|
| Uniform | 268 / 768 | 0 / 64 |
| Change | 335 / 768 | 0 / 64 |
| Adaptive | 319 / 768 | 0 / 64 |

No blocker was identified for the stated controlled synthetic experiment. This is
not a certification of generic video compliance, security, or production readiness.

## Reproduction evidence

The coordinating implementation agent reproduced the experiment from a clean
`git archive` of commit `975a23a`, using Python 3.12.14, NumPy 2.3.5 and Pillow
12.3.0. `scripts/compare_runs.py` found all **7,488** deterministic prediction rows
equal: pixel hashes, labels, briefs, selected indices, predictions and resource
counts. Timing values were intentionally excluded from equality checks.

See [machine-readable verification](../results/verification.json) and the
[test metadata](../results/test/metadata.json). The original main test recorded
approximately 41.16 seconds of invocation wall time and zero external API calls
or API spend. These are observations on that execution host, not performance
guarantees for another machine.

## Timing interpretation

Each method is charged its own full preprocessing cost. Feature extraction is
reused across budgets, and the measured preprocessing duration is attributed to
each corresponding budget. Reported latency therefore combines measured
components; it is not a collection of independent cold end-to-end executions for
every budget. Generation is recorded separately, and codec decoding is outside
this raw-frame study. Cached replay preserves original component observations
and does not constitute a new latency measurement.

## Checks not completed

- Human review of generated ground truth and representative errors remains pending.
- Real generated-video and VLM evaluations have not been executed.
- A fresh network dependency installation and Docker build were not run because
  package-download network access was restricted. The clean-source replay used
  preinstalled pinned dependencies.
- Browser visual QA was not completed because local binding and file-URL access
  were restricted in the execution environment.

The verifier's documented blindness to the constructed subtle variants and the
absence of human-reviewed natural errors limit the conclusions. The primary
hypothesis remains unsupported: adaptive sampling did not demonstrate an
improvement over both prespecified baselines.
