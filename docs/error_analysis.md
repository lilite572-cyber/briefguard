# Error analysis

Derived from held-out run `72b02803d9e0b835` at K=8. All slices below were prespecified, are descriptive, and were not used to tune the algorithm.

## Separate sampling misses from checker misses

| Method | All false approvals | Event absent from selection | Event captured but checker missed |
|---|---:|---:|---:|
| uniform | 500 | 339 | 161 |
| change | 433 | 273 | 160 |
| adaptive | 449 | 300 | 149 |

## Descriptive slice: duration_frames

| Slice | Uniform recall | Change recall | Adaptive recall | Uniform coverage | Change coverage | Adaptive coverage |
|---|---:|---:|---:|---:|---:|---:|
| 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| 12 | 64.06% | 61.33% | 59.38% | 100.00% | 92.97% | 90.23% |
| 2 | 11.72% | 24.22% | 23.83% | 20.31% | 34.77% | 30.47% |
| 6 | 28.91% | 45.31% | 41.41% | 47.27% | 65.62% | 62.11% |

## Descriptive slice: violation_type

| Slice | Uniform recall | Change recall | Adaptive recall | Uniform coverage | Change coverage | Adaptive coverage |
|---|---:|---:|---:|---:|---:|---:|
| None | n/a | n/a | n/a | n/a | n/a | n/a |
| forbidden_patch | 28.65% | 30.21% | 31.25% | 55.73% | 56.25% | 55.21% |
| label_corruption | 26.56% | 24.48% | 24.48% | 51.56% | 52.08% | 52.60% |
| missing_product | 56.77% | 87.50% | 84.90% | 56.77% | 87.50% | 84.90% |
| wrong_color | 27.60% | 32.29% | 25.52% | 59.38% | 61.98% | 51.04% |

## Descriptive slice: motion

| Slice | Uniform recall | Change recall | Adaptive recall | Uniform coverage | Change coverage | Adaptive coverage |
|---|---:|---:|---:|---:|---:|---:|
| distractor | 31.77% | 39.58% | 37.76% | 54.43% | 61.20% | 60.68% |
| quiet | 38.02% | 47.66% | 45.31% | 57.29% | 67.71% | 61.20% |

## Descriptive slice: severity

| Slice | Uniform recall | Change recall | Adaptive recall | Uniform coverage | Change coverage | Adaptive coverage |
|---|---:|---:|---:|---:|---:|---:|
| clear | 57.51% | 71.89% | 68.45% | 57.51% | 71.89% | 68.45% |
| none | n/a | n/a | n/a | n/a | n/a | n/a |
| subtle | 0.00% | 0.00% | 0.00% | 53.31% | 52.98% | 49.34% |

## Concrete examples

The temporal interval is half-open; a selected exit frame is already compliant. These examples are deterministic first matches in the saved rows, not a random audit sample.

- `uniform`, `s010000-distractor-forbidden_patch-6`: clear forbidden_patch, event [8,14), selected [6, 18, 30, 42, 54, 66, 78, 90]; not captured.
- `uniform`, `s010000-distractor-forbidden_patch-12`: subtle forbidden_patch, event [10,22), selected [6, 18, 30, 42, 54, 66, 78, 90]; captured but missed by checker.
- `change`, `s010000-distractor-forbidden_patch-2`: subtle forbidden_patch, event [66,68), selected [16, 22, 32, 43, 54, 64, 80, 86]; not captured.
- `change`, `s010000-distractor-forbidden_patch-12`: subtle forbidden_patch, event [10,22), selected [16, 22, 32, 43, 54, 64, 80, 86]; captured but missed by checker.
- `adaptive`, `s010000-distractor-forbidden_patch-2`: subtle forbidden_patch, event [66,68), selected [1, 12, 24, 36, 49, 60, 72, 84]; not captured.
- `adaptive`, `s010000-distractor-forbidden_patch-12`: subtle forbidden_patch, event [10,22), selected [1, 12, 24, 36, 49, 60, 72, 84]; captured but missed by checker.

## Interpretation and limits

The checker's tolerance thresholds deliberately miss all subtle fixture variants. This ceiling is an engineered diagnostic, not evidence that a VLM would miss them. The adaptive method also loses event coverage on some longer, color-change and subtle slices: local novelty plus coverage anchors is not uniformly protective. Distractor sensitivity and downsampling may explain failures, but this run contains no causal ablation proving which component is responsible.

Zero observed false alarms on the small, easy clean control set must not be read as zero population risk; the bootstrap interval can degenerate at zero when no events occur. Natural errors, camera motion, occlusions, typography/OCR and human perceptual validity remain unevaluated. An actionable next study should freeze new source groups, add human temporal labels, and compare a common VLM checker with audited total costs. Do not reuse these held-out seeds as an untouched test after further tuning.
