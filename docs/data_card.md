# Dataset card: Template Ad Stress Test v1

## Provenance and intended use

All clips are generated locally by `briefguard/data.py` from original geometric
drawings and an original small NOVA bitmap. NOVA is a fictional package label;
there is no third-party footage, human likeness, external font, or scraped data.
The generated dataset is distributed under the repository's license. The
generator version is `template-ad-v1`. Generation uses NumPy PCG64 streams
derived from the source integer and fixed salt `20261022`.

This is a **fixed-template, fixed-camera synthetic workload**, not a collection
of real advertisements or natural video-model failures. It supports controlled
testing of temporal selection and a deliberately simple visual verifier. It
does not establish real-world ad-compliance accuracy, OCR ability, VLM quality,
or superiority to published sampling systems.

## Source groups and variants

One source determines a package layout, colors and scene. Every source produces
two motion regimes: quiet background motion and distracting background motion.
Each regime has one clean control and one example for every combination of four
violation types and three default durations. Thus each source has 26 clips:
2 clean and 24 violating siblings. Splits must assign entire sources, including
both motion regimes and all modifications, to a single split. They must not
treat sibling clips as independent observations in uncertainty estimates.

Default frames have shape `96 × 72 × 128 × 3`, RGB uint8, at 24 fps. Violations
last 2, 6 or 12 frames. Onset is randomly drawn separately for each variant and
is not aligned to uniform sampling. The annotation's integer half-open interval
`[start_frame, end_frame)` is authoritative. Seconds are display values only.
GIF previews round frame durations to centiseconds and must not be decoded as
the experimental timebase.

| Type | Artificial modification | Subtle variant |
|---|---|---|
| `missing_product` | Remove product and cap, restore background | None |
| `wrong_color` | Increase red channel of package body | +12 instead of +65 |
| `label_corruption` | Remove a column of bitmap strokes | Remove one lit bitmap cell |
| `forbidden_patch` | Add forbidden red rectangle in an inspection region | 2 × 2 pixels instead of 12 × 8 |

Benign lighting varies by at most three levels per RGB channel. A changing
non-required background block and, in the distractor regime, a flashing border
introduce salient motion. They never constitute a labeled violation. The event
is a step insertion, not a natural generative failure. Smooth fades, camera
motion, moving products, real typography, compression, audio and arbitrary
semantic briefs remain outside this version.

## Public brief versus hidden annotation

The brief supplies normalized half-open product/color/label/forbidden ROIs,
expected RGB colors, the expected bitmap, the frame dimensions and requirements.
These are privileged template inputs, supplied identically to all methods.
Do not generalize results to unlocalized natural-language briefs. The selector
and verifier must receive only pixels and this brief. Source ID, category,
severity, event onset/end and clean counterpart are annotation-side fields and
must never enter model or selector inputs.

Annotations include `violated`, `violation_type`, `start_frame`, `end_frame`,
`duration_frames`, `duration_seconds`, `motion`, `severity`, provenance,
generator version and `human_audit: pending`. All current generator ground truth
is known by construction. The evaluation schema can represent unknown truth;
unknown labels must not be silently counted as negatives.

## Verifier limitations

`pixel-template-v1` checks all four requirements on every selected frame using
fixed engineering tolerances: product-color presence fraction below 0.35,
package median max-channel error above 20, label bitmap mismatch fraction above
0.035, or forbidden-color fraction above 0.08. These thresholds are not calibrated
probabilities. The tolerant checker deliberately can miss small, genuinely
inserted defects even when the selected frame contains them. Report sampling
coverage separately from observed detection recall. Changing a checker threshold
after seeing test results invalidates the frozen test comparison.

## Human audit status

**Pending. No human labels or human validation are claimed.** Programmatic
intervals are independently checked in unit tests by comparing modified pixels
with the clean sibling. That verifies rendering mechanics, not perceptual or
semantic validity. Before using this dataset for external claims, a human should
review a stratified subset spanning type, duration, motion and subtlety, record
`confirmed`, `ambiguous` or `incorrect`, and annotate any corrected intervals.
Automated inspection is not a substitute for that human audit.

## Reproducibility and resources

Clips are yielded one at a time rather than retained as a dataset in RAM.
There is a 128 MiB raw-pixel per-clip guard. Baseline-sized clips occupy about
2.53 MiB each before temporary generation buffers. Raw `.npz` files contain
only frames and fps; public briefs and annotations belong in separate JSON.
Exact pixel reproducibility requires the recorded NumPy and generator version;
Pillow is used only to export previews, not to produce experimental pixels.
