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

## Historical checks not completed

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

## Continuation verification

The continuation started from published commit
`991edc8268bc8b57b7c33092af9f67ab3ece0b0b`. The original task was read in full.
Original protocol, freeze, analytical code, test artifacts and
`results/verification.json` are preserved. `test_results_seen: false` in the
freeze describes its creation time; the test has since been viewed.

New evidence is in [results/verification_followup](../results/verification_followup/).
The exact implementation commit and executed checks are in its status record.
This evidence does not replace the historical run.

| Acceptance item | Executed result or remaining dependency |
| --- | --- |
| Clean-source reproduction | A fresh archive of `991edc8` reproduced all 7,488 deterministic rows; canonical evidence digest and run metadata retained |
| Independent statistical recheck | A separate AI agent independently parsed rows and recomputed the paired bootstrap using stdlib/NumPy, without importing BriefGuard; counts and both intervals exactly matched |
| Frozen integrity | All six code/protocol hashes unchanged; pilot/dev/test source groups disjoint |
| Tests, CLI and malformed evidence | Follow-up suite covers incomplete/duplicated exports, identity drift and optimized-Python comparison; see recorded output |
| Replay artifacts | Six cases, 18 method-case mappings, 153 PNG assets and 576 exact sprite frames checked against the run; not browser visual QA |
| Fresh dependency download | Attempted and blocked by the agent's network environment; preinstalled pinned dependencies used for execution |
| Wheel smoke check | Local build/install without dependency resolution succeeded; CLI help works. Full study execution requires the source checkout and its data/configuration |
| Browser interaction/console | Local socket binding and `file://` browser access denied; checklist prepared, not marked passed |
| Docker | Client installed, daemon unavailable; starting Desktop encountered a denied service-log write. Build/run not claimed |
| Human labels and personal review | Blinded packet prepared; actual human decisions and Amir's code walkthrough remain pending |
| VLM/natural-video follow-up | Separate protocol, preparation and no-network tests; no live model result or natural-video accuracy claim |
| Publication | Agent GitHub write returned 403; terminal GitHub access failed at DNS. Local commits and an owner-run completion script prepared |

The fixed comparison uses explicit failure checks instead of Python assertions.
Before the fix, `python -O` could report equality for changed predictions. The
old reproduction was run without optimization and was independently rechecked
using a canonical digest, so this helper defect does not invalidate the saved
experiment. Completed-run reporting now validates the expected evidence matrix
before generating output. These changes do not alter the frozen samplers or checker.

Run `PYTHON_BIN=python3.12 bash scripts/acceptance.sh --docker` on a host with
working dependency downloads and Docker. It records a clean committed-source
installation, tests, full reproduction, comparison and static demo check. The
owner can instead run `bash scripts/finish_local.sh` to also publish the working
branch, update PR #1 and serve the replay. No paid inference is included.
Complete [browser checks](browser_checklist.md) and [human review](human_review.md)
separately; an automated run cannot attest to either.
