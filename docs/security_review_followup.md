# Scoped static review of the completion changes

This is an AI-assisted source and regression review, not a completed Codex
Security scan, dependency audit, penetration test, or human security sign-off.
The earlier formal scan remains incomplete as recorded in
[security_review.md](security_review.md). It was not restarted or sealed here.

## Revision and scope

The starting immutable revision was
`991edc8268bc8b57b7c33092af9f67ab3ece0b0b`. The integrated reviewed implementation
is commit **`a28a651e801c1fc0f6bbeef0c0ee9cc8a0441c53`**. The follow-up examined
the local single-user loader, VLM adapter and pilot workflow, CLI, replay
exporter/viewer, comparison script, packaging, and new evidence-validation
changes. This exact commit anchors the bounded static review, not a formal scan.
A subsequent evidence/documentation-only commit does not change that reviewed
implementation; later executable changes are not automatically covered.

The assigned reviewer also implemented the evidence-validation fixes below.
Those changes therefore have AI regression verification, not an independent
second review by their own author. The coordinating agent performs integration
checks separately. The separate pilot received the additional bounded review
described below before the final code revision was recorded.

## Findings and corrections

Two research-integrity defects were confirmed. Neither is described as remote
code execution or a privilege escalation in this local research workflow.

1. `scripts/compare_runs.py` used Python `assert` for equality. With `python -O`,
   mismatched prediction evidence could be reported as an exact match. Explicit
   exceptions now enforce comparison in both normal and optimized Python.
2. The report command trusted a completed flag without validating the exported
   row inventory. A truncated export could produce apparently finished metrics.
   The new non-frozen `briefguard/evidence.py` checks run identity, manifest
   coverage of every source/variant, the complete method/budget matrix, unique
   units, brief/pixel/annotation consistency, exact frame budgets and event
   coverage before reporting. `briefguard check` exposes this validation.

The CLI demo path now uses the same inventory validation and recomputes the
summary from the saved rows to reject stale aggregates before creating output.
It never silently replaces a mismatched saved summary. Direct calls to the
low-level `export_demo` helper retain its narrower metadata/count/reconstruction
checks; use the CLI for validated research replay exports.

These changes affect evidence consumption and reporting. The frozen generator,
samplers, verifier, runner, metrics, protocol, lock and original held-out results
are unchanged. They do not establish a new sampling result or turn the inspected
test sources into unseen data.

## Inspected boundaries

| Boundary | Observation |
|---|---|
| Local NPZ/GIF/PNG media | Numeric NPZ headers and expanded sizes are checked before loading; object arrays are forbidden and pickle loading is disabled. Frame/output bounds reject oversized inputs. Native decoder isolation and fuzzing were not performed. |
| VLM credentials and destination | The optional adapter uses a fixed HTTPS endpoint, disables redirects/environment proxies and reads the key from the environment. It retains spending reservations before attempts and after uncertain outcomes. No live call, TLS test, provider billing test or model evaluation was performed. |
| VLM saved responses | Exact-byte key redaction remains a limited precaution, not a guarantee against all transformed or escaped secret representations. Responses and ledgers are local operator-owned evidence. Review them before publication. |
| Replay DOM and assets | Inspected text is assigned with `textContent`; replay asset paths use the local basename allowlist. Executable `data.js` is a repository-generated trusted artifact, not an untrusted upload format. |
| Human review interface | The reviewed package builder omits method predictions and generator labels from the reviewer payload. The scorer requires human self-attestation; this does not authenticate an independent expert. Full blinding is impossible when the reviewer also has the evaluator key/repository. |
| Packaging | Docker context excludes environment files, private keys, local environments and private/pilot/review outputs. Docker execution and fresh network installation are recorded separately and must not be inferred from this review. |
| Local paths and serving | Operator-selected paths remain intentional local authority. Static serving binds loopback and has no upload endpoint. No multi-tenant web-service security claim is made. |

No confirmed exploitable vulnerability was established in these inspected local
boundaries. This limited result does not certify the repository or its
dependencies as vulnerability-free.

## Executed evidence

The reviewer ran the full available suite after the fixes: **66 tests passed**
at that intermediate working snapshot, including seven new regression tests.
The optimized-Python regression compares two otherwise valid runs with a changed
prediction and requires a nonzero exit. Other tests reject truncation even when
the row-count field is adjusted, duplicated units, manifest/brief/pixel/label
drift, and a stale summary without writing replay output.

`python -m briefguard check --run results/test` validated all **7,488** rows.
Recomputing the saved held-out summary from those validated rows matched exactly.
These are source/artifact checks; browser visual QA, human labels and paid model
inference are separate evidence categories. The final integrated test count and
exact revision belong to the current verification record.

After integration, the coordinating agent reported **73 passing tests** at
`a28a651e801c1fc0f6bbeef0c0ee9cc8a0441c53` and unchanged frozen analytical
paths. This integration result is separate from the reviewer's intermediate
66-test run above and does not mark the formal security workflow complete.

## Separate pilot review addendum

The reviewer subsequently inspected `briefguard/pilot.py`, its config/protocol,
and six workflow tests. The pilot prepares local media without downloading or
calling a model. Live execution requires explicit approval, complete prepared
data, filled human labels and human confirmation of the specific NASA source.
The named approval flag is tied to literal provider, dated model, pricing,
request, output and spending settings; an edited plan cannot expand that
contract. Code/config/input hashes, plan hash, and a label/source-review-bound
run identity reject ordinary drift and incompatible resume. Saved logical
outcomes must match that run identity and job selection.

The review found and prompted corrections to the documented-versus-implemented
overlay size, nonstring reviewer acceptance, contradictory pass/unknown event
intervals, and missing returned-model verification. A response from an unexpected
model is now retained but counted as an operational indeterminate result. The
coordinator separately identified plan/budget and resume-identity gaps, which
were corrected before any paid execution. These are local integrity/authorization
guards, not cryptographic authentication against a user rewriting every file.

All **six pilot workflow tests passed** when rerun by this reviewer, using only
fake transport and temporary synthetic test footage. No real NASA footage was
downloaded or evaluated, no real human labels were supplied, and no paid API
request was sent. The reservation mechanism is a conservative local allowance,
not a guarantee about a provider invoice. The model endpoint, native GIF decoder,
source provenance and billing were not independently exercised live.
