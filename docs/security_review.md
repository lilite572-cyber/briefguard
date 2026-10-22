# Security review status

Checked on 2026-10-22. **The formal Codex Security workflow is incomplete.**
The separate bounded static review described below found no confirmed exploitable
security vulnerability in the inspected local, single-user research workflow.
This is not a security certification or a completed formal clean scan.

## Exact scope

The formal scan and core source review target the immutable range:

- Base: `eaa69f14edf1db998d08764d5257d76cbc59efed`
- Head: `60add9a5c291d7fdaecd72088c4c173ea7db17c4`
- Scan ID: `74477850-2353-4eee-860f-b0a655e98777`

All nine Python package files, the comparison script, all five test modules,
the static HTML/JavaScript viewer, Dockerfile, Makefile, dependency/packaging
configuration and study configuration were inspected at that head. The import
initializer was read directly. The protocol was reviewed for runtime/workflow
assumptions. Documentation, license, ignore rules and the concept image were
accounted for as non-executable material; no vulnerability claim relies on
fetching literature links or executing image content. No `SECURITY.md` or
`AGENTS.md` exists in this immutable tree.

The optional VLM adapter and later demo changes are **outside this immutable
scan**. See the separately attributed addendum below.

## Formal workflow state and blocker

The scan was created successfully. Its capability preflight returned `ready`;
missing goal tools were a nonblocking suggestion. Progress advanced to
`threat_model`. A generated Markdown threat model and a partial semantic
checkpoint were saved successfully after independent architecture review.

Transport interruptions initially prevented reads. After recovery, the formal
inventory tool returned:

```text
review_items: the scan inventory helper failed: generate_in_scope_files:
could not read committed diff blob:
60add9a5c291d7fdaecd72088c4c173ea7db17c4:briefguard/__init__.py
```

The list tool then reported that its inventory artifact was unavailable.
Direct `git show` succeeds and `git ls-tree --long` reports a 96-byte file;
the helper failure's cause is not established. The immutable target was not
modified to bypass the error. The existing scan remains running and unsealed
for later recovery. Formal discovery, validation, attack-path processing and
completion were not performed. No formal SARIF or sealed report is claimed.

## Static review evidence

| Boundary | Inspected control and result |
|---|---|
| NPZ media to NumPy | `video.py:67–115` checks members, headers, dtype, shape and expanded sizes before loading. Object arrays are rejected; `np.load(..., allow_pickle=False)` remains explicit. No archive extraction occurs. |
| PNG/GIF decoding | `video.py:122–185` checks source format, dimensions, frame count and output budgets. Unsupported MP4 conversion is not executed as a subprocess. Native decoder overhead is explicitly outside a hard OS memory guarantee. |
| Saved labels to browser DOM | `demo/index.html:42–44,63,102` uses `textContent` and a relative `assets/` basename allowlist. Inspected paths do not turn labels into HTML or arbitrary remote image URLs. |
| Clip identifiers to output filenames | `demo_export.py:157–177` uses SHA-256-derived names and bounded frame indices. The existing test includes a traversal-like identifier. |
| Run/cache files | `runner.py:38–45,114–145,177–187` uses source/config identity checks, digest cache names and atomic replacement. These are consistency measures, not authentication against an actor who can already modify local artifacts. |
| Local serving | `Makefile:19` binds the static demo to `127.0.0.1` and serves only the selected demo directory. No upload or mutating HTTP endpoint is implemented. |
| Spending and decisions | `runner.py:53–54,191–222` enforces zero external API spend for this study, calls the local checker, and records checker errors as failed units. Ground truth is used after selection/checking. |

No reachable command-execution, unsafe pickle-deserialization, archive-extraction,
DOM-script-injection or remote credential-exfiltration path was established in
this inspected core. No security-specific exploit execution or native decoder
fuzzing was performed. Existing unit-test sources were inspected; the broader
test execution is reported separately by the project validation workflow.

## Limits and non-security discrepancies

The normal deployment is an operator-controlled offline CLI, not a hosted
multi-tenant service. Operator-selected output paths are intentional local
authority. Result JSON/gzip is read whole (`runner.py:70–75`); it is not a bounded
hostile-artifact import format. Media decoder isolation remains a caller
responsibility. No dependency-vulnerability database or container-image audit
was performed.

The immutable exporter has two research-integrity discrepancies: it checks
`frames_sha256`, whereas runner rows contain `pixels_sha256`, and it reads
prediction rows without validating run metadata completeness. These were
retained as correctness observations, not promoted to security vulnerabilities
without a concrete authority gain. Later fixes are outside this old commit's
formal scope and should be assessed at their own revision.

The implementation coordinator subsequently corrected both current-demo issues:
the exporter now consumes `pixels_sha256` and requires completed metadata plus
an exact prediction-row count before export. The coordinator reported 50 passing
unit tests and successful re-export of the actual test run after that amendment.
This later validation does not retroactively change the immutable scan target.

## Separate optional VLM addendum

A separate methodology/source reviewer examined the optional adapter at commit
`5561328` under operator-owned configuration, output-directory and transport
assumptions. That reviewer reported no blocking security or cost-control bug:
fixed HTTPS destination, disabled redirects/proxies, durable reservation before
each attempt, ledger locking, configuration consistency and malformed-response
rejection were inspected. No live model request, TLS validation or external
exfiltration test was executed.

That review identified limitations, not demonstrated exfiltration: exact-byte
API-key redaction may not recognize an escaped representation, and syntactically
valid empty evidence explanations do not establish semantic correctness.
Fake-transport unit tests do not establish production-model accuracy. This
addendum is explicitly **not** part of the incomplete formal immutable scan.
