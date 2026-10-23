# Exploratory VLM pilot v2: verified 12-frame NASA source

Amendment recorded on 2026-10-23, before any model inference. This supersedes
only the source-length assumption for a **new** pilot preparation. Version one's
configuration, protocol, executable module and existing packets remain unchanged.
The CPU study's frozen files, source splits and original results are unaffected.

## Why version two exists

The actual Animation GIF downloaded from the official [NASA source page](https://science.nasa.gov/resource/as-the-world-turns/)
contains **12 display frames**, each 600×600 pixels with a 500 ms display duration
(6 seconds per displayed loop). Version one assumed a minimum of 16 frames and
correctly refused this file. That assumption was made before acquisition; it was
not a property of the source. No model output or comparative result was used to
choose this amendment.

Pinned original-file SHA-256:

`4858503ffe82d78e5a95a13771f31b598c2ebdaebeea353a3d41f14b8b74d229`

Version two requires these exact bytes and exactly 12 frames. It does **not**
duplicate frames, interpolate observations, repeat the loop to enlarge the
sample or substitute a visually similar animation. Source pixels are normalized
to 128×128 using the existing bounded loader; all original frame timings remain.

## Preserved design and explicit limitations

All other choices remain those of [version one](natural_video_pilot.md):
three fixed development clips and three variants of the single NOAA/NASA EPIC
sequence, uniform/change/adaptive at eight frames, one model observation per
request, the same prompt, snapshot, source-group interpretation, human review,
metrics and budget. The three natural variants are:

- Clean: unchanged normalized sequence.
- Blackout: original display frames `[4,6)`, two frames / one displayed second.
- Magenta overlay: top-right quarter over `[6,12)`, six frames / three seconds.

The intervals follow the original formulas evaluated at `N=12`; no interval was
retuned to favor a sampler. Eight selected frames now cover two-thirds of this
short sequence. This is a permissive integration check and may make differences
between samplers uninformative. A six-frame overlay occupies half the sequence.
Do not present these cases as difficult short-event detection or as evidence of
accuracy on advertising/video-generation errors.

There is **one independent natural source**, not three and not twelve. Together
with the three synthetic source groups, this remains a six-clip exploratory
pilot, reported by stratum with raw counts, failures and indeterminate outcomes.
There is no new held-out test, superiority claim or population confidence interval.

## Provenance and rights

Source: NOAA/NASA EPIC Team, *As the World Turns*, Earth on 2019-04-17.
The original page and [NASA media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/)
are retained in the version-two config. Keep the source credit and modification
note; do not imply endorsement. Raw footage remains in ignored local storage.
The hash identifies downloaded bytes, not independent human provenance validation.
A person must confirm the actual source and complete the blind annotations.

## Commands and compatibility

The version-aware CLI is a non-frozen dispatcher. Its default remains `v1`;
the historical `python -m briefguard.pilot ...` commands still run unchanged v1.
Version two is explicit:

```bash
python -m briefguard pilot prepare --protocol v2 \
  --natural-input results/private-source-assets/nasa-epic.gif \
  --out results/private-vlm-pilot-v2
python -m briefguard pilot check --protocol v2 \
  --directory results/private-vlm-pilot-v2
```

Open `results/private-vlm-pilot-v2/review/index.html`, fill the blank human CSV,
and confirm the source in `source_confirmation.json`. Do not copy injected
annotations or method outputs into human labels. The packet freezes the v2
config/protocol/module and all runtime dependencies, including the unchanged v1
helpers, before sampling. V1 and v2 packets are not interchangeable; checking or
running with the wrong protocol fails.

After the required human work, private API-key setup and applicable spending
approval, the explicit execution command is:

```bash
python -m briefguard pilot run --protocol v2 \
  --directory results/private-vlm-pilot-v2 \
  --approve-openai-gpt41mini-usd050
```

This is a command template, not evidence of execution. The model remains
OpenAI `gpt-4.1-mini-2025-04-14`; 18 logical checks, at most 36 attempts including
one retry, $0.01 reservation per attempt, $0.50 allocation. The earlier cost
projection remains $0.19008, not measured charges. The packet's persistent ledger
must be reused. Do not also spend the same allocation through another workbench
or pilot directory. Human labels/source confirmation and the API key are still
required; preparation itself never calls a model.

No live model result, human annotation or new accuracy conclusion is supplied by
this amendment. The downloaded source resolves acquisition and offline preparation,
not the remaining human and inference acceptance requirements.
