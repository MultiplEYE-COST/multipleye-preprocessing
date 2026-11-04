(fixation_correction)=

# Fixation Correction

The pEYEpline can optionally correct vertical drift in fixation locations before scanpaths and
reading measures are calculated. Drift correction moves each fixation toward the text line it was
read from. It is useful when the recorded gaze drifts away from the line during a trial.

The correction is **off by default**. Existing outputs stay unchanged unless
`RUN_FIXATION_CORRECTION` is enabled.

## Where it runs

When enabled, correction runs after fixation detection and before scanpaths, reading measures and
sanity plots. The raw detected fixations are saved first. The corrected fixations are then used by
all later stages for that session.

## When correction is off

This is the default and matches the previous pipeline behaviour:

- `fixations/` contains the detected, uncorrected fixations.
- `scanpaths/`, `reading_measures/` and sanity plots use those uncorrected fixations.
- `fixations_uncorrected/` is not written.
- `processing_config.aoi_enlargement` is `half_line_spacing`.

## When correction is on

- `fixations/` contains the corrected fixations.
- `fixations_uncorrected/` contains the raw detected fixations.
- `scanpaths/`, `reading_measures/` and sanity plots use the corrected fixations.
- `processing_config.aoi_enlargement` is `none`.
- Corrected fixation files keep the original coordinates in `location_x_original` and
  `location_y_original`.
- The applied algorithm is stored in `correction_algorithm`.

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
RUN_FIXATION_CORRECTION: false
fixation_correction_algorithm: "wisdom_of_the_crowd"
fixation_correction_kwargs: {}
fixations_uncorrected_folder: "fixations_uncorrected/"
```

- `RUN_FIXATION_CORRECTION` enables or disables the step.
- `fixation_correction_algorithm` accepts a single algorithm or `wisdom_of_the_crowd`.
  Supported single algorithms are `attach`, `chain`, `cluster`, `compare`, `merge`, `regress`,
  `segment`, `slice`, `split`, `stretch` and `warp`.
- `fixation_correction_kwargs` passes extra tuning parameters to the algorithms.
- `fixations_uncorrected_folder` is the subfolder name inside the processed data collection.

## Final fixation dot

Each stimulus page ends with a fixation dot. Dot positions can differ by language and collection, so
the pipeline reads them from the stimulus config and does not hardcode a position.

The stimulus config must define:

```python
FINAL_FIX_DOT_X = 1214.0
FINAL_FIX_DOT_Y = 1028.0
FINAL_FIX_DOT_RADIUS = 7.0
```

`LabConfig` loads these values into `final_fix_dot_x`, `final_fix_dot_y` and
`final_fix_dot_radius`. When correction is active, all three keys are required. Missing or invalid
dot metadata raises an error before correction starts. There is no AOI fallback for the final dot.

Dot fixations are removed from the correction input before pymovements runs. Correction therefore
uses only the real text lines. Dot fixations are reinserted unchanged afterwards. This avoids a fake
dot line and prevents text fixations near the bottom of the page from snapping to the dot.

## Dataset overview and codebook

The dataset overview records the resolved settings in `processing_config`:

```yaml
processing_config:
  fixation_correction: false
  fixation_correction_algorithm: wisdom_of_the_crowd
  fixation_correction_kwargs: {}
  aoi_enlargement: half_line_spacing
```

The codebook has matching fields:

- `dataset.processing_config.fixation_correction`
- `dataset.processing_config.fixation_correction_algorithm`
- `dataset.processing_config.fixation_correction_kwargs`

When `fixation_correction` is `false`, the algorithm and kwargs are recorded for reproducibility
but were not applied. The fixation, scanpath and reading-measure outputs are uncorrected.

## Recalculation

Cached fixation files are reused only when they match the current correction setting and algorithm.
Changing `RUN_FIXATION_CORRECTION` or `fixation_correction_algorithm` invalidates cached fixations.
The next run detects fixations again, applies or skips correction, and rewrites the affected
downstream outputs.

## Current limitations

- Horizontal correction for vertical writing systems is not implemented yet.
- The pipeline temporarily pins pymovements to the commit that contains the correction API. The pin
  is removed when a pymovements release includes it.
