# Human review package — pending until a person submits labels

The package is at `human_review/reviewer/index.html`. It has 16 development clips,
exact lossless RGB frames, the common public requirements and an empty annotation
form. No model selections, predictions, generator answers, event intervals or
source names are shipped in the reviewer payload. The evaluator mapping is kept
outside that directory in `human_review/evaluator_key.json`.

**No human labels have been supplied.** Source inspection, asset tests and automated
parser fixtures do not complete human review. Browser interaction QA for this new
form is also pending because the current environment cannot open the local page.

## Reviewer instructions

1. Open only `human_review/reviewer/index.html` in your browser, or serve the
   reviewer folder locally with the command below. Do not open the evaluator key,
   saved benchmark answers or the ordinary demo until you export your labels.
2. Enter a reviewer alias, not personal contact details. Read the four requirements
   and target references. The bitmap and ROIs are public task inputs, not answers.
3. Play each clip, then use the slider and ±1-frame buttons. All 96 frames are
   available; no sampler restricts what you see. Playback is approximate. For
   timing use integer frame indices, not perceived playback duration.
4. Record `Violation`, `Compliant` or `Impossible to determine`. For a violation,
   select its type and mark `[start,end)`: start is the first violating frame,
   end is the first frame after the event. End may be 96. A one-frame event at
   frame 10 is `[10,11)`. For compliant/unknown leave type and interval blank.
5. Use unknown if color, label or event timing cannot be judged confidently. Give
   a short reason. Do not guess the generator answer. The pixel inspector may
   help with small changes; when a file URL blocks canvas readback, serve locally.
6. Check the human-review attestation only after personally inspecting every clip.
   Use **Save draft JSON** before taking a break, and **Resume draft** to import it later. A draft does not certify human completion. Export the completed JSON when finished. No labels are auto-saved or sent online.

```bash
python3 -m http.server --bind 127.0.0.1 8766 --directory human_review/reviewer
# Open http://127.0.0.1:8766
```

A typical review is a small manual task, not a blind expert certification. The
repository is public, so anyone can inspect its evaluator key. Operational
blinding requires sharing **only the reviewer directory** and withholding model
answers until label export. Amir can perform this audit, but must not call himself
an independent expert who was uninvolved in the project.

## Evaluate a completed submission

Keep the original downloaded `human_labels.json` unchanged. The following command
rejects a blank or incomplete submission, duplicate/extra IDs, a different dataset,
missing human attestation, invalid types and impossible intervals. Unknown cases
require an explanation and are excluded from agreement denominators.

```bash
python scripts/score_human_review.py \
  --key human_review/evaluator_key.json \
  --labels /path/to/human_labels.json \
  --out results/human-review/summary.json
```

The summary records the input-file hash, reviewer alias, unknown count, agreement
counts, individual discrepancies and source-group counts. Attestation is
self-reported, not identity authentication. Preserve the actual submission with
the report; do not replace it with the bundled blank template. Do not commit
personal details inadvertently included in free-text notes.

Human observations can disagree with generator truth. Record and investigate that
disagreement; do not silently rewrite the original frozen labels or benchmark
scores. A corrected study would need a separate amendment and separate results.
Do not rank sampling methods using this audit: it assesses data validity and
perception with all frames available, not sparse-frame algorithm performance.

## Sampling and provenance (evaluator)

The selection rule is fixed in `scripts/prepare_human_review.py`: one case in each
available violation-type × severity × motion stratum, including clean controls.
It prefers unused source IDs, then underrepresented durations, with SHA-256 ties.
Selection uses the development manifest, never method predictions or performance.
Presentation order and case IDs use separate deterministic hashes. This is a
purposefully stratified audit, not a probability sample of real advertising.

The committed package contains 16 clips from 16 distinct development source groups:
2 clean controls and 14 violations, covering both motion conditions, clear/subtle
variants and durations of 2, 6 and 12 frames. No test source is used. All footage
comes from the project's original MIT-licensed procedural generator. Reconstruction
checks exact pixels, annotations and public-brief hashes against the saved manifest.
The evaluator key records the run, manifest hash and public package identity.

The package is reproducible without overwriting an active annotation task:

```bash
python scripts/prepare_human_review.py --out /tmp/briefguard-human-review-new
python -m unittest discover -s tests -p 'test_human_review.py' -v
```

Use a new empty output directory. The preparer refuses existing content and
non-development runs. Every annotation field in the delivered template remains
blank. Automated tests use explicitly named `UNIT_TEST_NOT_A_HUMAN` fixtures in a
temporary directory; these are parser tests, not submitted annotations.

Only descriptive counts should be reported from this small stratified review.
Although this export uses one clip per source, future enlarged exports must keep
sibling dependencies explicit. Unknown labels are not clean negatives. No natural
video validation, population accuracy estimate, confidence interval, independent
expert agreement or formal completion of Amir's code review follows from this pack.
