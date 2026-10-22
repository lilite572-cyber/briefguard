# BriefGuard

**When a video checker sees only a few frames, what does it miss?**

A reproducible CPU reference study of transient visual brief violations. It compares
uniform, global-change and adaptive local-novelty sampling, separating **evidence capture**
from **checker accuracy**, and charges the complete preprocessing cost.

![Concept cover](demo/concept-cover.png)

*AI-generated concept illustration; not a dataset frame or experimental result.*

The contribution is an auditable evaluation harness and a controlled negative result,
not a new sampling paradigm or a production advertising-compliance system. The closest
prior, [InfoShot/SynFlash](https://arxiv.org/abs/2603.17374), already studies short synthetic
anomalies. The [related-work table](docs/related_work.md) compares twelve primary sources,
including VBench, VBench-2.0 and VTR-Bench, checked on 2026-10-22.

## Results

<!-- BEGIN GENERATED RESULTS -->
Held-out run `72b02803d9e0b835`: **32 source groups**, **832 clips** (768 violating, 64 clean), **7,488 recorded checks** across the prespecified budgets. Primary budget: **8 frames per clip**.

| Method | Violation recall | Event coverage (diagnostic) | Median CPU check time, including prepass |
|---|---:|---:|---:|
| uniform | 34.90% | 55.86% | 0.62 ms |
| change | 43.62% | 64.45% | 13.33 ms |
| adaptive | 41.54% | 60.94% | 19.27 ms |

Paired source-cluster bootstrap recall differences (percentage points, 95% intervals):

- `adaptive_minus_uniform`: **+6.64** [+2.99, +10.16].
- `adaptive_minus_change`: **-2.08** [-4.95, +0.65].

The prespecified hypothesis is **not supported**: an advantage over uniform selection alone is insufficient; it must also beat the simple change baseline.

Measured test execution: 41.16 s, peak process RSS 227.1 MiB, external API spend $0.00. These are recorded host observations, not cross-machine performance guarantees. Resource figures exclude environment installation and image illustration generation.

Every value above derives from `results/test/summary.json`, `metadata.json`, and the compressed predictions; regenerate this block with `python scripts/update_readme.py`.
<!-- END GENERATED RESULTS -->

Interpretation: the adaptive heuristic is a plausible implementation choice, but this
experiment does not justify its extra complexity over the simple change baseline.
Small fixed-template requirements are much narrower than semantic brief understanding.
Subtle violations deliberately fall below the pixel checker's engineering tolerances;
their failure is a **known diagnostic limitation by construction**, not an unexpected
discovery about a learned model. No thresholds were tuned on the held-out results.

## Replay in seconds

Open `demo/index.html` in a browser after downloading the repository. It loads the bundled
`data.js` and local media without inference or an API key. Alternatively:

```bash
python3 -m http.server --bind 127.0.0.1 8765 --directory demo
# Open http://127.0.0.1:8765
```

The replay labels synthetic inputs, exact selected frame indices, per-method findings,
ground-truth intervals and actual misses. GIF playback rounds timestamps; the integer
frame timeline and lossless PNG frames are authoritative. `demo/human_review.csv` leaves
reviewer decisions blank. Human validation is **pending**.

## Reproduce

Python **3.11+**; the recorded host used Python 3.12.14 on macOS/arm64. No GPU or paid service
is required. NumPy and Pillow are the only runtime dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m briefguard run --split test --out results/reproduce
python scripts/compare_runs.py results/test results/reproduce
```

The last command compares pixels, briefs, selections, predictions, labels and resources
exactly. Latency is machine dependent and is intentionally excluded from equality.
Run the same command again to resume: successful units are loaded from the atomic cache
or exported compressed evidence. Cached observations retain their original component timings.

To rebuild tables and the replay from recorded evidence:

```bash
python -m briefguard report --run results/test
python scripts/update_readme.py
python -m briefguard demo --run results/test --out demo
```

Study history: pilot → development inspection → config/code freeze commit → held-out test.
`configs/frozen.json` fixes the exact source IDs and hashes the analytical code and
protocol. A changed core source or configuration is rejected for the test run. To conduct
a different study, use an explicitly new protocol, split and freeze; do not overwrite this
study's lock. `make pilot`, `make dev`, `make freeze`, and `make experiment` expose the
original steps; `make freeze` intentionally refuses to overwrite the included freeze.

## Architecture

```mermaid
flowchart TD
  A[Seeded source clips] --> B[Pixel-only selection]
  A --> C[Generator annotations]
  B --> D[Selected-frame verifier]
  D --> E[Predictions and resource log]
  C --> F[Paired source evaluation]
  E --> F
  F --> G[Tables and replay]
```

- `data.py`: original synthetic generator, public template briefs and separate annotations.
- `sampling.py`: three interchangeable strategies; all nonuniform preprocessing is accounted for.
- `verifier.py`: deterministic selected-pixel checker. It cannot receive a clip or its annotations.
- `video.py`: bounded NPZ, GIF and PNG-sequence normalization preserving source timing; no MP4 decoder is claimed.
- `runner.py` / `metrics.py`: immutable run identity, atomic cache/resume, raw responses,
  explicit denominators and paired source-cluster bootstrap intervals.
- `demo_export.py`: regenerates exact example clips and checks their pixel hashes.
- `vlm.py`: optional, separately gated Responses API adapter; **not used in reported results**.

## Evidence and limitations

| Artifact | Purpose |
|---|---|
| [Protocol](docs/protocol.md) | Primary hypothesis, decision rule, resource accounting, precision planning |
| [Frozen inputs](configs/frozen.json) | Pre-test code/config hashes and test sources |
| [Data card](docs/data_card.md) | Original generation process, privileges, intervals, provenance |
| [Results](results/test/tables.md) | All prespecified frame budgets and paired differences |
| [Predictions](results/test/predictions.jsonl.gz) | Every actual selected frame, response, label, pixel hash and timing |
| [Manifest](results/test/manifest.jsonl.gz) | Source grouping and per-clip identities |
| [Error analysis](docs/error_analysis.md) | Concrete misses and duration/type/severity slices |
| [Interview guide, Russian](docs/interview_ru.md) | Explain and defend the work without overstating it |
| [VLM follow-up](docs/vlm_pilot.md) | Explicit budget/model requirements for future real inference |

The clean controls are easy and few; an observed zero false-alarm count is not a population
guarantee. Source siblings are dependent and are resampled together. This dataset's high
violation prevalence is artificial: approval contamination does not estimate deployment
risk. The static camera, known template regions, simple shapes and synthetic corruptions
limit generalization. There are no natural generated-video failures, independent human
labels, VLM experiments, confidence calibration or selective-risk guarantees in this run.
Real ad compliance remains unvalidated.

## Separate host

For a CPU server, run the same commands with the same pinned dependencies and freeze.
The included Dockerfile is an optional packaging recipe; its build was not executed in
the restricted authoring environment. A heavier VLM study needs a separately reviewed
model/budget and human-labeled data. Do not silently mix its results into this CPU study.

## License and attribution

MIT for the code and original procedural fixtures. The concept cover was generated with
ImageGen and is not used as research evidence. Cited papers and external datasets retain
their own terms; none of their videos or model weights are redistributed. This project is
independent and is not affiliated with Higgsfield or the cited authors.
