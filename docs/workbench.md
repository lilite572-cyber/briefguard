# Local workbench

This workflow prepares a new clip for visual review. It is separate from the
frozen synthetic experiment and the six-clip VLM pilot. Preparation and response import are offline and spend no API credits. The separate
`execute` command sends a paid request only after explicit approval. A prepared
request is not a model result.

## Browser entry

Open `web/workbench.html` locally. The interface lets you write requirements,
download `requirements.json`, choose a sampler and frame budget, and copy the
corresponding commands. It can preview a local GIF; that preview does not run the
checker. Files remain on the device. No API-key field or upload server is present.

A browser cannot reveal the full local path of a selected file. Enter the correct
input path yourself and save the downloaded JSON at the path shown in the command.
Run commands from the repository root with the installed Python environment.

Supported inputs are animated GIF, numeric NPZ (`frames` and `fps`), and a numbered
PNG directory with explicit constant frame rate. MP4/MOV are not decoded here;
do not select that format or silently discard variable-rate timing during an
external conversion. Inputs exceeding loader bounds are rejected, not truncated.

## Prepare without inference

Example `requirements.json`:

```json
{
  "product_visible": "The product must remain visible in every supplied frame.",
  "no_overlay": "No opaque bright magenta rectangle may cover the product."
}
```

These example requirements are useful only if they describe your actual clip.
Replace them rather than accepting unrelated defaults. A requirement must be
visually testable in the supplied frames. Use a new output directory for each
preparation; existing preparations cannot be overwritten.

```bash
python -m briefguard.workflow prepare \
  --input /absolute/path/to/clip.gif \
  --requirements requirements.json \
  --out results/private-workbench-01 \
  --method uniform --budget 8
```

For PNG input, use the directory path and add `--fps 24` only if 24 is its actual
constant source frame rate. Available methods are `uniform`, `change`, and
`adaptive`; frame budgets are 1–32, limited by the number of available frames.

Open `results/private-workbench-01/report.html`. It displays the selected frames,
their indices and timestamps, and the requirements. The folder also contains:

- `manifest.json`: source/preparation identity and selected-frame metadata;
- `request.json`: an **unsent** Responses API request;
- selected PNG files: exact normalized model inputs;
- `report.html`: a local report, initially marked prepared with no inference.

The model snapshot in the request is a proposal. Offline preparation does not
verify provider availability or authorize spending. Review the frames, privacy,
model and total budget before using any separate execution tool. Do not publish
private footage, request payloads or raw responses without review. The default
`results/private*` location is ignored by Git.

## Execute only after approval

The optional live path uses OpenAI `gpt-4.1-mini-2025-04-14`. Obtain explicit
approval of that provider/model and a USD 0.50 total limit, at most 36 attempts
including retries, before running. The command flag records acknowledgement;
it is not permission by itself. Model availability must be checked before use.
Set `OPENAI_API_KEY` privately in the process environment; never put it in chat,
a command-line argument, project file or browser field.

```bash
python -m briefguard.workflow execute \
  --directory results/private-workbench-01 \
  --approve-openai-gpt41mini-usd050
```

All prepared bundles in this repository share `results/private-workbench-api`.
Do not delete that ledger or move to a new repository copy to reset the budget.
The local allowance reserves USD 0.01 per attempt; it does not guarantee provider
billing. Inspect retained usage and errors. Reopen `report.html` afterward; no
human label or dataset accuracy result is inferred from one model judgment.
This workbench ledger is separate from the older six-clip research pilot. An
approval of USD 0.50 is not permission to spend USD 0.50 in each workflow; choose
the approved workflow and review any prior spending before starting another.

## Import a response you actually obtained

After a separately authorized real request, retain the provider's raw JSON and
import it against the same preparation:

```bash
python -m briefguard.workflow import-response \
  --directory results/private-workbench-01 \
  --response /absolute/path/to/response.json
```

Reopen the report to inspect the judgment and cited evidence. The importer checks
format, model identity and evidence references. An imported file is nevertheless
operator-supplied: its provider origin and association with this request are not
authenticated. Do not use fabricated provider-shaped test fixtures as measured
model results. Automated fixture tests are not accuracy experiments.

A model pass applies only to the selected frames. It cannot establish that the
whole clip complies. Check cited evidence against the images, record disagreements,
and keep human decisions separate from model judgments. A single imported result
is not an evaluation dataset or a claim about production accuracy.

## Acceptance boundary

Run `node scripts/check_workbench.cjs` for dependency-free syntax and command-
generation checks against the actual inline JavaScript. The checker uses a small
DOM stub and exercises requirements, budget/FPS boundaries and shell quoting.
An evidence record can be written with `--out PATH`. Real browser acceptance must separately check requirements download,
local GIF preview, input errors, clipboard fallback, and opening the generated
report. Do not infer that those interactions passed from static validation alone.
