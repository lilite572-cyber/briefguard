# Optional real-model pilot (not executed)

The published CPU experiment uses `pixel-template-v1`. `briefguard.vlm.ResponsesPilot` is a separately invoked OpenAI Responses API adapter; the experiment runner never calls it. All adapter tests use fake transport and fake credentials. They validate request construction and failure handling, not model accuracy or live compatibility.

## Authorization and cost

There is no default model or budget. Before running, the user must approve a request limit and estimated USD budget, review current model pricing, select a vision/Structured-Outputs-capable **dated snapshot**, and set `OPENAI_API_KEY` outside the repository. Never commit the key or pass it as a command-line argument.

`reservation_usd` is a **user-reviewed conservative estimate per attempt**, including image input tokens, other input and the configured maximum output. `max_spend_usd` limits the sum of these reservations; it is **not a guaranteed provider billing cap**. Tokenization, model pricing, failed requests, other applications and billing adjustments can invalidate an estimate. If a conservative reservation cannot be established, do not run. Confirm the amount with the user first. The adapter computes `estimated_api_cost_usd = (input_tokens × reviewed_input_rate + output_tokens × reviewed_output_rate) / 1,000,000` from returned usage, without cached-token discounts. Missing or invalid usage produces `null`, not a zero-cost claim. The reviewed rates are retained in the ledger; the adapter does not discover prices or authorize spending itself.

If any returned usage estimate exceeds its per-attempt reservation, the ledger permanently halts new requests for budget review, including after an incomplete or invalid model result. Already cached responses remain replayable without network calls. This detects an underestimated reservation after the request; it cannot undo the charge or guarantee the provider bill stayed within the approved amount. A successful result's `budget_halted` flag exposes that condition. Result cache files are written using a flushed temporary file and atomic replacement so interrupted writes cannot publish partial results.

Every attempt, including HTTP retries and unknown-outcome timeouts, consumes one request and a full reservation before transmission. The persistent ledger is locked on macOS/Linux and flushed to disk. Reuse the same directory and configuration when resuming. Do not delete the ledger, change directories or launch separate budgets to bypass the approved limit. Successful identical requests replay from the cache.

## Python usage

The following skeleton deliberately leaves prices, model and budget unspecified. Fill them only after approval; it is not an authorized runnable paid experiment.

```python
from PIL import Image
from briefguard.vlm import PilotConfig, ResponsesPilot

config = PilotConfig(
    model=reviewed_dated_snapshot,
    max_requests=approved_request_limit,
    max_spend_usd=approved_reservation_budget,
    reservation_usd=reviewed_conservative_per_attempt_estimate,
    input_usd_per_million=reviewed_input_rate,
    output_usd_per_million=reviewed_output_rate,
    authorized=True,
)
pilot = ResponsesPilot(config, "results/private-vlm-pilot")
result = pilot.verify(
    [Image.open("selected-frame.png")], [24],
    {"package_color": "The package must remain blue"},
    {"product": "Example product", "required_color": "blue"},
)
```

Pass the same selected resolution, brief, requirement IDs, model, output limit and image detail for all compared samplers. The adapter uses PNG data URIs and `detail=low`; small text may be unreadable, and this is a model/input limitation to measure. A pass refers only to supplied frames, never proves unseen parts comply. Model instructions treat image text and brief values as untrusted evidence, but prompt-injection resistance is not guaranteed.

## Outputs and failure semantics

Outputs have `status` (`pass`, `fail`, `indeterminate`) and `evidence` entries with `frame_index`, `requirement`, and `reason`. Cited indices must have been supplied and requirement IDs must exist. Failure needs evidence; pass cannot contain violation evidence. Invalid output, refusal, incomplete response, malformed JSON and HTTP errors raise `PilotError`; callers must record these as operational indeterminate outcomes rather than exclude them from evaluation or silently approve the clip.

The directory preserves the request without authentication headers, redacted raw response per attempt, returned model identifier, usage, response ID and result. It can contain sensitive images and briefs: inspect it before publishing. Exact API-key occurrences are redacted from raw responses. The URL is fixed to `https://api.openai.com/v1/responses`, redirects are refused, and environment proxy forwarding is disabled. The adapter uses no tools and requests `store=false`.

Only HTTP 429/5xx responses are candidates for bounded retries. Timeouts retain their reservation and are not automatically retried because the server outcome is unknown. `Retry-After` is honored when numeric and at most 30 seconds; longer/unsupported delays require manual action. At most two retries and a 60-second socket timeout can be configured. This timeout bounds individual socket operations, not total wall time for a malicious slow streaming peer.

## Pilot protocol before any expanded claim

Use a small development-only sample and a separately human-reviewed control subset. Preserve fixed settings before held-out evaluation. Reconcile every response's usage against the reviewed prices; include retries, prepasses, failures and abstentions. Report evidence-capture rate separately from end-to-end violation detection. Do not replace deterministic experiment results with projected VLM performance.

Official API documentation checked on 2026-10-22:

- [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Images and vision](https://developers.openai.com/api/docs/guides/images-vision)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Error codes](https://developers.openai.com/api/docs/guides/error-codes)

No live API request was made while implementing this adapter.
