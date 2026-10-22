# Protocol v1 — fixed before the held-out run

This is an independently implemented **controlled synthetic reference study**, not a new
sampling paradigm, official reproduction, production ad checker, or model-training result.
The closest work is InfoShot/SynFlash; see [related work](related_work.md).

## Question and decision rule

At a fixed budget of **8 checked frames**, does pixel-only adaptive sampling improve
clip-level violation recall over **both** midpoint-uniform and a global-change heuristic?
Primary endpoint: TP/(TP+FN), based on the actual pixel verifier. Positive support requires
both paired source-cluster-bootstrap 95% intervals for recall differences to have lower
bounds above zero. Otherwise the hypothesis is not supported by this experiment. These are
pointwise exploratory intervals, not a multiplicity-corrected confirmatory clinical test.
The decision is an intersection criterion; no independent 'win' is claimed by choosing
only the favorable baseline. No minimum practically meaningful gain is asserted.

## Units and data

Source seed is the independent sampling/uncertainty unit. Every source produces clean and
modified sibling clips in quiet and distracting-motion conditions. All siblings stay in
one split. Ground truth comes from the generator's integer half-open [start_frame,end_frame)
interval, independently of verifier predictions. Required properties are product presence,
package color, bitmap-label integrity, and absence of a forbidden patch. Fixed-template
requirements provide the same explicit regions and expected appearances to every verifier.
Selectors receive pixels only. This privileged template setting does **not** establish
generic language-based video understanding. Human audit remains pending until a human
actually records their decisions. Do not substitute model output for human annotations.

Frames are 128×72 RGB, 96 frames at 24 fps. Durations are 2, 6, 12 frames with seeded event
phase. Four violation types × three durations + one clean variant, for each of two motion
regimes, gives 26 siblings per source. See the data card for generation details and limits.
This workload samples controlled injected violations; natural generation errors are absent.

## Comparators and resources

Uniform uses segment midpoints. Change ranks adjacent global frame differences with temporal
spacing. Adaptive reserves half the frame slots for coverage and allocates the remainder by
local robust novelty/change and temporal diversity. It adapts to pixels, not checker feedback.
All use the same verifier, brief, full-resolution frames and exact K unique checked frames.
No learned model, paid call or GPU is used. No claim of outperforming AKS, InfoShot or VBench.

Change/adaptive inspect **all frames** at 32×18 for preprocessing. Charge each method its
own complete preprocessing cost even when features are reused across budgets. Uniform has
no preprocessing pass. Equal checker budgets do not mean equal total computation. Record
generation, preprocessing, selection and checking times separately; local CPU cost is not
monetized. Inputs are uncompressed generated arrays; codec decoding latency is not measured.
Secondary budgets 4 and 16 and all type/duration/motion slices are descriptive. Do not tune
on them after test evaluation.

## Split, pilot, freeze and uncertainty

Pilot IDs 1000–1011; development IDs 2000–2015; test IDs begin at 10000. The source ranges
must be disjoint. Pilot verifies the measurement path, runtime and variability. Estimate
per-source paired recall-difference SD against each baseline at K=8. Choose test N as the
larger ceil((1.96×SD/0.06)^2), clipped to [32,96]. This is approximate precision planning,
not a power guarantee, and excludes population shift. The minimum cluster count is a
practical uncertainty floor, the maximum a laptop runtime cap. Record actual selection.

Before test, `freeze` writes protocol/config/core-source SHA-256 and source IDs to
`configs/frozen.json`, together with pilot digest and planning inputs. Test refuses drift.
Commit the freeze before running test. If a bug invalidates the experiment, document an
amendment and rerun; do not silently call the same data unseen. Only root performs test.
Code documentation/demo changes are permitted afterward if analytical source is unchanged.

Use 2000 paired bootstrap resamples of source IDs with replacement (seed 572). Carry all
sibling variants and compare methods on identical resamples. Report percentile intervals,
sample counts, and descriptive slices. No assertions about real deployment prevalence.

## Endpoints and exclusions

- Recall: TP / (TP+FN); an indeterminate result is not a detected violation.
- Missed violations: FN / (TP+FN); differs from actual automatic approval rate when abstaining.
- False approval among violating clips: count(predicted pass AND violated) / all violating clips.
- False alarms: FP / (FP+TN), where abstained clean clips do not count as FP.
- Contamination among approvals: false passes / all predicted passes, prevalence dependent.
- Oracle event coverage: any selected index in annotated interval, **diagnostic only**.
- Abstention fraction and unknown-ground-truth count are reported separately.
- Cold per-clip component timings, selected/preprocessed pixels and API spend.

Unknown GT cases are excluded from binary accuracy denominators and counted separately.
Failed executions are logged; a run with any unresolved failure is incomplete, not silently
scored as a pass. Resume must preserve immutable run identity and skip successful cached
units only. All model responses/predictions remain inspectable. A cached replay is not a
new latency observation. Sample source-level errors and publish representative misses even
when the aggregate comparison looks favorable.

## Cost and next validation

This run has a zero external-API spending limit. Human labeling, real generated videos and
VLM-based judgment are unexecuted follow-up work. Before such a pilot, choose an accessible
pinned model, inspect actual input/output billing and receive a monetary limit. No paid
pilot is implied by this protocol. Heavy evaluation can run the same commands on a separate
CPU/GPU host; freeze, source groups and model identity must remain explicit.
