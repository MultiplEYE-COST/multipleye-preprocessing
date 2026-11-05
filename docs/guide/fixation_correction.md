(fixation_correction)=

# Fixation Correction

The pEYEpline corrects vertical drift in fixation locations before scanpaths and reading measures
are calculated. Drift correction moves each fixation toward the text line it was read from. It is
useful when the recorded gaze drifts away from the line during a trial.

The correction is **on by default** (`RUN_FIXATION_CORRECTION: true`). Set it to `false` to
disable it.

## Where it runs

Correction runs after fixation detection and before scanpaths, reading measures and sanity plots.
The raw detected fixations are saved first. The corrected fixations are then used by all later
stages for that session.

## When correction is on

This is the default:

- `fixations/` contains the corrected fixations.
- `fixations_uncorrected/` contains the raw detected fixations.
- `scanpaths/`, `reading_measures/` and sanity plots use the corrected fixations.
- `processing_config.aoi_enlargement` is `none`.
- Corrected fixation files keep the original coordinates in `location_x_original` and
  `location_y_original`.
- The applied algorithm is stored in `correction_algorithm`.

## When correction is off

Set `RUN_FIXATION_CORRECTION: false` to disable correction:

- `fixations/` contains the detected, uncorrected fixations.
- `scanpaths/`, `reading_measures/` and sanity plots use those uncorrected fixations.
- `fixations_uncorrected/` is not written.
- `processing_config.aoi_enlargement` is `half_line_spacing`, which extends each AOI to the space
  between lines.

```{figure} ../_static/fixation_correction_before_after.png
---
name: fixation-correction-before-after
alt: Fixation positions on a stimulus page before and after drift correction
width: 100%
---
Fixation positions on one stimulus page. Red points are before correction. Blue points are after
correction. Grey lines connect the original and corrected positions. Fixations on the final dot
overlap before and after correction and stay at the dot.
```

All output folders are subfolders of the processed data collection folder:

```text
preprocessed_data/<dcn>/
├── fixations/
│   └── <session>_<trial>_<stimulus>_fixation.csv
├── fixations_uncorrected/
│   └── <session>_<trial>_<stimulus>_fixation.csv
├── scanpaths/
├── reading_measures/
└── sanity_checks/
```

`fixations_uncorrected` is therefore part of the processed data collection, not a top-level
project folder and not a folder inside `internal/`.

## Settings

```yaml
RUN_FIXATION_CORRECTION: true
fixation_correction_algorithm: "wisdom_of_the_crowd"
fixation_correction_kwargs: {}
fixations_uncorrected_folder: "fixations_uncorrected/"
```

- `RUN_FIXATION_CORRECTION` enables or disables the step.
- `fixation_correction_algorithm` accepts a single algorithm or `wisdom_of_the_crowd`.
  Supported single algorithms are `attach`, `chain`, `cluster`, `compare`, `merge`, `regress`,
  `segment`, `slice`, `split`, `stretch` and `warp`.
- `wisdom_of_the_crowd` runs all algorithms and combines their line assignments by majority vote.
  No kwargs are required; each algorithm uses its own defaults.
- `fixation_correction_kwargs` passes extra tuning parameters to the algorithms.
- `fixations_uncorrected_folder` is the subfolder name inside the processed data collection.

## Final fixation dot

Each stimulus page ends with a fixation dot. Dot positions can differ by language and collection, so
the pipeline reads the geometry from the stimulus config and does not hardcode a position.

Newer stimulus configs write the final-dot geometry directly:

```python
POS_BOTTOM_DOT_X_PX = 1236
POS_BOTTOM_DOT_Y_PX = 920
FIX_DOT_RADIUS = 8
```

When those keys are absent, `LabConfig` derives the same values from the existing config with the
image generator geometry:

```python
is_ltr = FIX_DOT_X < IMAGE_WIDTH_PX / 2

POS_BOTTOM_DOT_X_PX = (
    IMAGE_WIDTH_PX - MIN_MARGIN_RIGHT_PX
    if is_ltr
    else MIN_MARGIN_LEFT_PX
)

POS_BOTTOM_DOT_Y_PX = int(
    IMAGE_HEIGHT_PX - 2 * RESOLUTION[1] / SCREEN_SIZE_CM[1]
)

FIX_DOT_RADIUS = max(int(0.1 * MIN_MARGIN_LEFT_PX), 7)
```

The radius therefore depends on the horizontal screen DPI. It ranges from 7 to 9 pixels in the
current collections. It is not a fixed constant.

`LabConfig` stores the result in `final_fix_dot_x`, `final_fix_dot_y` and
`final_fix_dot_radius`. If correction is active and the geometry cannot be derived, the run stops
with an error. There is no AOI fallback for the final dot.

A fixation counts as a dot fixation only when it is outside the text AOI bounds, with one line
height of tolerance, and within a tolerance around the dot centre. The tolerance is the larger of
four dot radii and the distance from the dot to the last text line, because gaze positions on the
dot can be several dot radii away from its centre. Dot fixations are removed from the correction
input before pymovements runs. Correction therefore uses only the real text lines. The dot fixations
are reinserted unchanged afterwards. This avoids a fake dot line and prevents text fixations near
the bottom of the page from snapping to the dot.

## Dataset overview and codebook

The dataset overview records the resolved settings in `processing_config`:

```yaml
processing_config:
  fixation_correction: true
  fixation_correction_algorithm: wisdom_of_the_crowd
  fixation_correction_kwargs: {}
  aoi_enlargement: none
```

The codebook has matching fields:

- `dataset.processing_config.fixation_correction`
- `dataset.processing_config.fixation_correction_algorithm`
- `dataset.processing_config.fixation_correction_kwargs`

When `fixation_correction` is `true`, the corrected fixations feed scanpaths and reading measures
and `aoi_enlargement` is `none`. When it is `false`, the algorithm and kwargs are recorded for
reproducibility but were not applied, and the fixation, scanpath and reading-measure outputs are
uncorrected.

## Recalculation

Cached fixation files are reused only when they match the current correction setting and algorithm.
Changing `RUN_FIXATION_CORRECTION` or `fixation_correction_algorithm` invalidates cached fixations.
The next run detects fixations again, applies or skips correction, and rewrites the affected
downstream outputs.

## Current limitations

- Top-to-bottom (TTB) scripts are not supported yet. Correction currently fixes the vertical
  coordinate, which suits left-to-right and right-to-left text. For TTB scripts the AOIs must be
  enlarged along the horizontal axis and correction must fix the horizontal coordinate instead.
  This applies to the `ttb` value of `dataset.administrative.script_direction`. Until it is
  implemented, keep `RUN_FIXATION_CORRECTION: false` for TTB collections.
- The pipeline temporarily pins pymovements to the commit that contains the correction API. The pin
  is removed when a pymovements release includes it.
