# Exploratory VLM pilot v1 — separate from the frozen CPU study

Protocol specified on 2026-10-22 before any pilot model response. This is a small
integration and failure-analysis pilot, not a confirmatory test or a claim of
adaptive superiority. It does not modify the v1 generator, samplers, checker,
protocol, freeze, test sources or saved held-out evidence.

## Data, rights and independence

Use exactly the three development clips listed in `configs/vlm_pilot_v1.json`
(seeds 2000, 2001, 2002; one clean and two violating clips), plus three siblings
from **one** natural-source image sequence: NOAA/NASA EPIC Team, *As the World
Turns*, Earth on 2019-04-17. Download its Animation GIF from the
[original NASA page](https://science.nasa.gov/resource/as-the-world-turns/).
The [NASA media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
permit educational/informational use of NASA media, generally not copyrighted
in the US. Credit the NOAA/NASA EPIC Team; do not imply NASA endorsement. This
source has no identified third-party credit on its page. Raw media are kept local;
any later redistribution must retain the credit, source link and modification note.

This is a time-lapse of real spacecraft images, **not ordinary advertising
footage and not a naturally occurring generative-model error**. The added failures
are artificial: a blackout and a magenta overlay. They probe whether an image VLM
can recognize selected evidence beyond template drawings. Even perfect results
would not validate advertising-video compliance or natural generation errors.

The independent source unit is the original recording, not its frames, crops,
corruption variants, methods or repeated API calls. Effective design: three
synthetic source groups and one natural recording; report the strata separately.
All six clips belong to exploratory development. There is no new held-out set,
no significance claim and no useful population confidence interval at this size.
A future confirmatory study requires new independent sources and a separate freeze.

## Fixed transformation and requirements

Load the complete GIF using the bounded local loader, preserve all source-frame
indices and GIF display durations, resize to 128×128 with BOX, and require at least
16 frames. The human must first confirm this is the specified NASA animation.
Do not replace it with a visually similar source under the same protocol.
Record the original file SHA-256 before sampling and preserve it with the plan.

Make three siblings: unmodified, full-frame black pixels over
`[N//3, N//3+2)`, and opaque RGB `(255,0,255)` in the top-right quarter (pixel box x=[64,128), y=[0,64)) over
`[N//2, N//2+6)`. These are half-open **display-frame** intervals, not physical
Earth-observation time. Frame durations determine displayed event seconds.
Use the same two requirements for every natural sibling: Earth remains visible;
no opaque magenta rectangle overlays the scene. Synthetic clips keep the shared
original template brief. Human review can mark a case indeterminate, or disagree
with the injected annotation; the primary pilot report uses the human labels and
retains generator annotations separately for disagreement inspection.

## Methods, measurements and limitations

Use unchanged uniform, change and adaptive, exactly eight unique frames each,
original sampling configuration, common model snapshot, prompt, low image detail,
output cap and native prepared resolution within each stratum. Count each
method's entire preprocessing time and pixels; decoding is recorded separately.
One model observation per distinct request, with at most one HTTP retry on
429/5xx. Identical requests share the adapter cache; they are not independent
model replicates. Never treat retries as additional samples.

Metrics by stratum/method: violation recall, false approval among violating
clips, false alarm among clean clips, abstention/operational-error count, known
label denominators, and event capture versus recognition among captured events.
Unknown labels are excluded from binary denominators and counted. API failures
are operational indeterminate predictions, not passes or silently removed rows.
Report raw counts, exact selected frames, usage, billed-token cost estimates,
reservations and latency. With one or two positives per stratum, percentages are
illustrative only. No causal explanation or superiority claim follows.

## Freeze and execution

`python -m briefguard.pilot prepare --out results/private-vlm-pilot` prepares the
three synthetic clips and records that NASA data are absent. Add the downloaded
GIF only when available:

```bash
python -m briefguard.pilot prepare --natural-input /absolute/path/to/nasa-epic.gif --out results/private-vlm-pilot
```

A partial directory cannot be silently expanded: move it aside as a dry-run
artifact and prepare a new directory **before any paid request**. Preparation
writes `input_freeze.json` (protocol/config/source-code and pixel hashes) before
frame selections, then `plan.json`, media and blank `human_review.csv`. It refuses
an existing plan. Open `review/index.html`; the review page and CSV omit method
answers and injected intervals. The local plan remains accessible to the owner,
so this is practical blinding, not a secure independent-review arrangement.

The human confirms the downloaded animation against the NASA page in
`source_confirmation.json` (reviewer and `confirmed_exact_nasa_source: true`).
This is an explicit provenance check, not something the loader can establish.

The human fills every case's `label` (`pass`, `fail`, `indeterminate`), reviewer
name/alias and, for a fail, integer `start_frame,end_frame`. End is excluded.
Review full clips and individual PNG frames; GIF is a preview with centisecond
rounding, while the original timeline in `plan.json` is authoritative. A fail
means at least one requirement is visibly violated. Use indeterminate when the
small imagery cannot be judged. Do not copy machine labels into the human CSV.

After separate authorization of provider, snapshot and total cap, set the API key
privately in the process environment. Do not put it in chat, scripts or Git:

```bash
python -m briefguard.pilot run --directory results/private-vlm-pilot --approve-openai-gpt41mini-usd050
```

Without that flag the command refuses to instantiate the paid adapter. It also
refuses incomplete data, changed protocol/code/pixels and unfinished human labels.
The flag records operator acknowledgement; it does not itself grant permission.
Use the SAME directory to resume. Each completed logical outcome is saved;
operational errors remain visible and are not automatically resubmitted across
invocations. The adapter accounts for its bounded HTTP retry. A new recovery
attempt requires review and must stay within the same ledger; never reset budgets.

## Cost and current status

18 logical checks × at most two HTTP attempts = **36 attempts**. No additional
stochastic repetitions are planned. At $0.40/M input and $1.60/M output, a loose
10,000-input +800-output allowance gives $0.00528 per attempt or **$0.19008**.
Reserve $0.01 per attempt, at most **$0.36**, inside the requested **$0.50 cap**.
This is an estimate and local reservation limit, not a provider billing guarantee.
Reconcile actual usage including failed attempts. Stop if a reservation is exceeded.

Official [model prices/snapshot](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
and [deprecations](https://developers.openai.com/api/docs/deprecations) were checked
on 2026-10-22. This snapshot is deprecated with shutdown scheduled 2027-01-14;
a later run must recheck availability and use a new explicitly approved protocol
if the snapshot changes. No live compatibility or model-access claim is made.

**Executed:** synthetic-only preparation and fake-transport tests. **Not executed:**
NASA download (shell DNS unavailable), natural sampling, human annotation or live
VLM inference. This protocol supplies no new VLM accuracy result.
