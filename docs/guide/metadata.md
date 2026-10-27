(metadata_yaml)=

# Metadata YAML Files

The pipeline writes structured metadata alongside the preprocessed data. The metadata is split
into three levels:

| Level | File | Scope |
| --- | --- | --- |
| Dataset (DCN) | `preprocessed_data/<dcn>/<dcn>_overview.yaml` | One data collection: sessions, setup, processing settings and dataset-wide quality averages |
| Session | `preprocessed_data/<dcn>/metadata/<sid>/<sid>_overview.yaml` | One eye-tracking session: participant context, technical setup, calibration, procedure and quality |
| Trial | `trials` key inside the session overview | One entry per presented trial, including practice trials |

`<dcn>` is the data-collection name, for example `MultiplEYE_KL_DK_Copenhagen_1_2026`. `<sid>` is
the session identifier, for example `048_KL_DK_1_ET1`.

The trial level is a list inside the session file, not a separate YAML file. All files are
rewritten at the end of a preprocessing run, so they always describe the most recent run. For the
output layout, see {ref}`technical_architecture`. For where the files are written in the pipeline,
see {ref}`pipeline_stages`. Participant-level metadata is centralised in `participants.csv`, see
{ref}`participants_table`.

The schema is still being completed. Fields that are planned but not written yet are marked
**TODO** with the issue that tracks them.

## Conventions

- Section and field names are lowercase `snake_case`.
- Units are part of the field name when the value has a physical unit: `_ms` (milliseconds),
  `_s` (seconds), `_hz` (hertz), `_px` (pixels), `_cm` (centimetres) and `_dva` (degrees of visual
  angle). Counts and scores have no unit suffix.
- Ratios are fractions between 0 and 1, not percentages. This applies to data loss, blink loss
  and comprehension scores.
- Dates use `YYYY-MM-DD`. The month of data collection uses the abbreviation from the ASC header,
  for example `Feb`.
- A string `"unknown"` means that a session field could not be read from the available inputs.
  YAML `null` is used where an optional value is absent, for example a DCN average when no session
  contributed a numeric value. Neither value means zero; do not aggregate them as if they were
  measurements.
- Reading time appears in both seconds and milliseconds: `total_reading_time_s` is in seconds,
  while `mean_rt_per_stim_ms`, `sd_rt_per_stim_ms` and the per-trial reading time are in
  milliseconds. Check the suffix before using a value.

## Dataset (DCN) overview

`{dcn}_overview.yaml` summarises the whole data collection. A trimmed example:

```yaml
administrative:
  title: MultiplEYE_KL_DK_Copenhagen_1_2026
  dataset_type: MultiplEYE
  number_of_sessions: 1
  number_of_pilots: 0
  number_of_et_sessions_per_participant: 1
  session_completeness:
    expected_sessions_per_participant: 1
    total_participants: 1
    complete_participants: 1
  city: Copenhagen
  lab_number: 1
  country: DK
  tested_language: KL
processing:
  preprocessing_date: '2026-10-27'
  pipeline_version: 2026.10.13
data_quality:
  attrition_rate: 0.0
  mean_validation_error_dva: 0.3
  mean_comprehension_score: 0.4
# further sections: language_details, data_availability, psychometric_tests,
# technical_setup, processing_config, warnings
```

### Dataset `administrative`

| Field | Type | Description |
| --- | --- | --- |
| `title` | str | Data-collection name, identical to `<dcn>`. |
| `dataset_type` | str | Collection type, for example `MultiplEYE`. |
| `dataset_description` | str | Generated one-sentence description: country, city, lab number, tested language and collection dates. Dates read `unknown` when the metadata form is unavailable. |
| `number_of_sessions` | int | Number of non-pilot eye-tracking sessions. |
| `number_of_pilots` | int | Number of pilot sessions. |
| `number_of_et_sessions_per_participant` | int | Expected ET sessions per participant from the collection configuration, for example `1` for MultiplEYE. |
| `session_completeness` | dict | Completeness by participant base ID, non-pilot sessions only. See below. |
| `city` | str | Collection city. |
| `lab_number` | int | Lab number within the collection. |
| `country` | str | Country code. |
| `tested_language` | str | Tested-language code. |

`session_completeness` contains:

- `expected_sessions_per_participant`: expected session count.
- `total_participants`: distinct participant base IDs with at least one non-pilot session.
- `complete_participants`: participants with exactly the expected number of sessions.
- `incomplete_participants`: only present when some participants have fewer sessions.
- `extra_sessions_participants`: only present when some participants have more sessions.

### `language_details`

| Field | Type | Description |
| --- | --- | --- |
| `metadata_form_exists` | bool | Whether the data-collection metadata form was found and loaded. |
| `language_script` | list, null | Script or scripts of the tested language from the metadata form. |
| `language_family` | list, null | Language family or families from the metadata form. |
| `start_date_of_data_collection` | str, null | Start date as recorded in the metadata form, normally `YYYY-MM-DD`. |
| `end_date_of_data_collection` | str, null | End date as recorded in the metadata form, normally `YYYY-MM-DD`. |

The content fields are `null` when the metadata form is missing or does not contain the value.

### `data_availability`

| Field | Type | Description |
| --- | --- | --- |
| `raw_data_available` | bool | Raw gaze samples are part of the output. |
| `fixations_available` | bool | Fixation tables are part of the output. |
| `saccades_available` | bool | Saccade tables are part of the output. |
| `reading_measures_available` | bool | Word-level reading measures are part of the output. |

The MultiplEYE pipeline sets all four flags to `true`.

### `psychometric_tests`

| Field | Type | Description |
| --- | --- | --- |
| `tests_available` | list, null | Psychometric tests configured for the lab, for example `LWMC`, `PLAB`, `Stroop`, `RAN`. `null` when the lab configuration lists none. |

### Dataset `technical_setup`

| Field | Type | Description |
| --- | --- | --- |
| `eye_tracker_name` | str | Eye-tracker model from the lab configuration. |
| `sampling_frequency_hz` | float | Nominal sampling frequency in hertz. |
| `monitor_name` | str, null | Monitor name from the metadata form. |
| `screen_resolution_width_px` | int | Screen width in pixels. |
| `screen_resolution_height_px` | int | Screen height in pixels. |

The dataset level keeps only the core setup. The session level adds mount, pupil and physical
screen details.

### `processing`

| Field | Type | Description |
| --- | --- | --- |
| `preprocessing_date` | str | Date of the run, `YYYY-MM-DD`. |
| `pipeline_version` | str, null | Installed pEYEpline version, or `null` when it cannot be determined. |
| `number_of_stimulus_versions` | int | Number of distinct stimulus-order versions used by the processed sessions, `0` when unknown. |
| `required_pq_fixing` | bool, null | Data-collection flag from the metadata form. |
| `psychotests_restructuring` | bool, null | Data-collection flag from the metadata form. |
| `custom_units_of_analysis` | bool, null | Data-collection flag from the metadata form. |
| `answer_option_shuffling_bug` | bool, null | **TODO (#291).** The flag is read from the metadata form, but the form has no such key and no detection rule is implemented. Currently always `null`. |

### `processing_config`

This section records the resolved settings used for the run. It covers:

- event detection: `fixation_method`, `fixation_minimum_duration_ms`,
  `fixation_velocity_threshold`, `saccade_method`, `saccade_minimum_duration`,
  `saccade_threshold_factor`;
- velocity estimation: `velocity_estimation_method`, `velocity_smoothing_window_ms`,
  `velocity_polynomial_degree`;
- psychometric scoring windows: `psym_wikivocab_min_rt`, `psym_wikivocab_max_rt`,
  `psym_stroop_min_rt`, `psym_stroop_max_rt`, `psym_flanker_min_rt`, `psym_flanker_max_rt`;
- column mappings: `trial_cols`, `trial_col`, `page_col`, `stimulus_col`, `word_idx_col`,
  `char_idx_col`;
- fixed design decisions: `aoi_enlargement`, `reading_measures_null_fill`,
  `scanpath_drop_unmapped`, `data_loss_missingness_column`, `per_trial_loss_weighting`.

`tracked_eye` in this section is the list of accepted eye labels from the configuration, not the
eye tracked in a particular session. The session-level `tracking.tracked_eye` holds the actual
value. {ref}`technical_architecture` describes the meaning of the individual settings.

### Dataset `data_quality`

Except for `attrition_rate`, all values are averages across non-pilot sessions. The averages are
unweighted across sessions: every session contributes one value, regardless of its duration. A
field is `null` when no session has a numeric value for it.

| Field | Type | Description |
| --- | --- | --- |
| `attrition_rate` | float, null | Share of non-pilot sessions that crashed, rounded to two decimals. |
| `mean_calibration_error_dva` | float, null | Mean session-level calibration error in degrees of visual angle. Usually `null` because EyeLink calibration rows do not report `accuracy_avg`. |
| `mean_validation_error_dva` | float, null | Mean session-level validation error in degrees of visual angle. |
| `mean_rt_per_stim_ms` | float, null | Mean of the session `mean_rt_per_stim_ms` values, in milliseconds. |
| `mean_total_question_time_ms` | float, null | Mean comprehension-question time per session, in milliseconds. |
| `mean_total_rating_time_ms` | float, null | Mean rating-screen time per session, in milliseconds. |
| `mean_data_loss_ratio` | float, null | Mean of the session data-loss ratios, `0` to `1`. Each session ratio is duration-weighted within the session before averaging. |
| `mean_blink_ratio` | float, null | Mean of the session blink-loss ratios, `0` to `1`. |
| `mean_total_reading_time_s` | float, null | Mean total reading time per session, in seconds. |
| `mean_total_session_duration_s` | float, null | Mean session duration, in seconds. |
| `mean_wpm` | float, null | Reading speed: total words across sessions divided by total reading minutes. Rounded to one decimal. |
| `mean_comprehension_score` | float, null | Mean proportion of correct comprehension answers per session, `0` to `1`. |
| `mean_comprehension_score_local` | float, null | Same, restricted to local questions. |
| `mean_comprehension_score_global` | float, null | Same, restricted to global questions. |
| `mean_comprehension_score_bridging` | float, null | Same, restricted to bridging questions. |

### `warnings`

An optional list of warnings captured during the run. The key is absent when no warnings were
recorded.

## Session overview

`{sid}_overview.yaml` describes one eye-tracking session. It is grouped into the sections below.
A trimmed example:

```yaml
administrative:
  participant_id: 48
  session_identifier: 048_KL_DK_1_ET1
  is_pilot: false
  year_of_data_collection: 2026
  month_of_data_collection: Feb
tracking:
  tracked_eye: R
  tracked_eye_consistent: true
experiment_procedure:
  num_completed_trials: 12
  total_reading_time_s: 3776.272
  total_session_duration_s: 9521.715
  mean_rt_per_stim_ms: 270366.5
# further sections: participant, technical_setup, calibration_validation,
# data_quality, comprehension, data_formats, trials
```

### Session `administrative`

| Field | Type | Description |
| --- | --- | --- |
| `participant_id` | int | Participant ID, normally the 3-digit PID. |
| `session_identifier` | str | Full session ID. |
| `is_pilot` | bool | Whether this is a pilot session. |
| `year_of_data_collection` | int, str | Collection year from the ASC metadata. |
| `month_of_data_collection` | str | Collection month abbreviation from the ASC metadata. |

### `participant`

This is a convenience subset for quick inspection. The complete participant view is
`participants.csv`, see {ref}`participants_table`.

| Field | Type | Description |
| --- | --- | --- |
| `gender` | str | Gender answer from the participant questionnaire. |
| `bi_monolingualism` | str | `monolingual`, `bilingual` or `multilingual`, derived from the distinct native languages. `unknown` when no native language is recorded. |
| `psychometric_tests` | list | All psychometric tests with data for this participant. |
| `tests_conducted_this_session` | list | Tests conducted together with this ET session. |
| `tests_conducted_separate_session` | list | Tests available for the participant from another session. |
| `has_pt_data_same_day_as_session` | bool, null | Whether psychometric data exists for the same date. `null` when the session date is unknown. |
| `gap_to_previous_session_days` | int, str | Days to the participant's previous ET session, `unknown` for the first session or when a date is missing. |
| `gap_to_next_session_days` | int, str | Days to the participant's next ET session. |
| `gap_to_psychometric_tests_days` | int, str | Smallest absolute gap in days to any psychometric-test date for the participant. |
| `psychometric_test_scores` | dict, str | Curated psychometric scores for the participant, `unknown` when no results are available. |

### Session `technical_setup`

| Field | Type | Description |
| --- | --- | --- |
| `eye_tracker_name` | str, null | Eye-tracker model. |
| `sampling_frequency_hz` | float, null | Sampling frequency in hertz. |
| `mount_type` | str, null | Mount type from the gaze mount configuration, for example `Desktop`. |
| `head_stabilization` | str, null | Head-stabilisation setting, for example `stabilized`. |
| `eyes_recorded` | str, null | Recorded eyes, for example `binocular / monocular`. |
| `pupil_data_type` | str, null | Pupil measure reported by the tracker, for example `AREA`. |
| `screen_resolution_width_px` | int, null | Screen width in pixels. |
| `screen_resolution_height_px` | int, null | Screen height in pixels. |
| `screen_size_width_cm` | float, null | Physical screen width in centimetres. |
| `screen_size_height_cm` | float, null | Physical screen height in centimetres. |
| `screen_distance_cm` | float, null | Eye-to-screen distance in centimetres. |
| `image_resolution_width_px` | int, null | Width of the stimulus image area used for gaze mapping, in pixels. |
| `image_resolution_height_px` | int, null | Height of the stimulus image area used for gaze mapping, in pixels. |
| `image_size_width_cm` | float, null | Physical width of the stimulus image area in centimetres. |
| `image_size_height_cm` | float, null | Physical height of the stimulus image area in centimetres. |
| `dominant_eye` | str | **TODO (#170).** Planned: dominant eye from the experimenter sheet. Must not be inferred from `tracked_eye`. |
| `dominant_eye_test` | bool, str | **TODO (#170).** Planned: whether an eye-dominance test was performed. |
| `mount_short_name` | str, null | Explicit short mount code from the mount configuration, for example `BTABLER`. `null` when the mount configuration does not provide one. |
| `eyelink_filters` | dict | **TODO (#188).** Planned: EyeLink filter settings parsed from the ASC file. |

### `tracking`

| Field | Type | Description |
| --- | --- | --- |
| `tracked_eye` | str | Eye used for analysis, `L` or `R`. |
| `tracked_eye_consistent` | bool | `false` when a validation was recorded for a different eye than `tracked_eye`. |

The eye-dominance fields are planned in `technical_setup`, not here. `tracked_eye` describes the
eye tracker setup; it is not a dominance measure.

### `calibration_validation`

| Field | Type | Description |
| --- | --- | --- |
| `num_calibrations` | int | Number of calibration events. |
| `num_validations` | int | Number of validation events. |
| `avg_calibration_error_dva` | float, str | Mean calibration accuracy in degrees of visual angle, `unknown` when the calibrations table has no `accuracy_avg` column. This is common for EyeLink calibrations. |
| `avg_validation_error_dva` | float, str | Mean validation accuracy in degrees of visual angle, `unknown` when no validation score is available. |
| `calibration_quality` | str | Aggregate EyeLink calibration grade: `GOOD` when all calibration lines report `GOOD`, `FAILED` when all report `FAILED`, `MIXED` when they differ, `unknown` when no calibration line is available. |
| `validation_quality` | str | Worst scored EyeLink validation grade: `GOOD`, `FAIR` or `POOR`. `ABORTED` when only aborted validations exist, `unknown` when no validation line is available. |
| `num_aborted_validations` | int | Number of aborted validation lines. |
| `num_good_validations` | int | Validations with `accuracy_avg` below `0.305` degrees. |
| `num_moderate_validations` | int | Validations with `accuracy_avg` from `0.305` up to but excluding `0.45` degrees. |
| `num_bad_validations` | int | Validations with `accuracy_avg` of `0.45` degrees or more. |
| `final_validation_score_dva` | float, str | `accuracy_avg` of the last validation after the final experimental trial, in degrees of visual angle, provided no calibration happened between that trial and the validation. `unknown` when the condition cannot be established from the available data. |

The quality labels come from the EyeLink `!CAL` lines. The `num_good_validations`,
`num_moderate_validations` and `num_bad_validations` counts use the pipeline thresholds
`SINGLE_VALIDATION_GOOD_MAX` and `SINGLE_VALIDATION_MODERATE_MAX`; they are independent of the
EyeLink grade, so a validation can be EyeLink `GOOD` and still count as moderate here.

### Session `data_quality`

| Field | Type | Description |
| --- | --- | --- |
| `session_total_data_loss_ratio` | float, null | Missing or invalid samples divided by expected samples over the session, `0` to `1`. Duration-weighted across the session. |
| `session_blink_loss_ratio` | float, null | Time spent in blink events divided by total recording time, `0` to `1`. |

`null` means the measure was not available for this session. It is not a zero-loss result.

### `experiment_procedure`

| Field | Type | Description |
| --- | --- | --- |
| `question_order` | dict, str | **TODO (#170).** Intended to map conditions to question order. Not populated yet, currently `unknown`. |
| `stimulus_content_version` | str, null | Stimulus content version suffix when the collection configures one. `null` or `unknown` otherwise. |
| `stimulus_order_ids` | list, str | Numeric stimulus IDs in presentation order, including practice trials. `unknown` when no order is available. |
| `stimulus_order_ids_with_names` | list, str | One entry per presented stimulus, usually with `stimulus_id`, `stimulus_name` and `trial`, for example `trial: PRACTICE_trial_1` or `trial: trial_1`. |
| `num_completed_trials` | int, null | Number of entries in `stimulus_order_ids`, including practice trials. |
| `was_session_interrupted` | bool, str | Whether the session was restarted, derived from the session-ID postfix. |
| `restarted_session_name` | str | Canonical session ID without the restart postfix, `unknown` when the session is not a restart. |
| `obligatory_break_made` | bool, str | **TODO (#170).** Field exists but is not populated yet; currently `unknown`. |
| `num_optional_breaks_made` | int, str | **TODO (#170).** Field exists but is not populated yet; currently `unknown`. |
| `total_break_time_s` | float, str | **TODO (#170).** Field exists but is not populated yet; currently `unknown`. |
| `total_reading_time_s` | float | Sum of non-negative reading spans over all stimuli, in seconds. |
| `total_session_duration_s` | float | Last minus first ASC message timestamp, in seconds. |
| `mean_rt_per_stim_ms` | float | Mean summed reading time per stimulus, in milliseconds. |
| `sd_rt_per_stim_ms` | float | Sample standard deviation of the per-stimulus reading times, in milliseconds. `0.0` when only one stimulus is available. |
| `total_question_time_ms` | float | Summed comprehension-question time over experiment trials, in milliseconds. Practice trials are excluded. |
| `total_rating_time_ms` | float | Summed duration of the familiarity and difficulty rating screens, in milliseconds. |
| `familiarity_1` | float, str | Mean selected option number on the first familiarity rating screen, `unknown` when the screen was not logged. |
| `familiarity_2` | float, str | Mean selected option number on the second familiarity rating screen. |
| `subjective_difficulty` | float, str | Mean selected option number on the subjective-difficulty screen. |

### `comprehension`

| Field | Type | Description |
| --- | --- | --- |
| `avg_comprehension_score` | float, str | Proportion of correct comprehension answers, `0` to `1`, over experiment trials. Practice trials are excluded. |
| `avg_comprehension_score_local` | float, str | Same, for local questions (`condition_number` 1). |
| `avg_comprehension_score_bridging` | float, str | Same, for bridging questions (`condition_number` 2). |
| `avg_comprehension_score_global` | float, str | Same, for global questions (`condition_number` 3). |

### `data_formats`

| Field | Type | Description |
| --- | --- | --- |
| `raw_data` | bool | Raw gaze data was produced for this session. |
| `fixations` | bool | Fixation data was produced for this session. |
| `saccades` | bool | Saccade data was produced for this session. |
| `reading_measures` | bool | Reading measures were produced for this session. |
| `answers` | bool | Comprehension answers were produced for this session. |

The pipeline sets all five to `true`. Other pipelines that write the same schema can set a flag
to `false` when they do not generate a format.

### `trials`

A list of per-trial entries. The value is the string `"unknown"` when the session answers CSV is
missing or lacks the required columns. Practice trials are listed after the experiment trials and
are marked with `is_practice: true`.

## Trial list

Each entry in `trials` has the following fields:

| Field | Type | Description |
| --- | --- | --- |
| `trial_number` | int | Trial number, 1-based. Numbering restarts for practice trials, so pair it with `is_practice`. |
| `stimulus_id` | int | Numeric stimulus ID. |
| `stimulus_name` | str | Stimulus name, for example `Lit_MagicMountain`. |
| `is_practice` | bool | `true` for practice trials. |
| `num_questions` | int | Number of comprehension questions answered for the trial. |
| `comprehension_score` | float | Proportion of correct answers for the trial, `0` to `1`. |
| `comprehension_question_time_ms` | float | Total comprehension-question time for the trial, in milliseconds. |
| `reading_time_ms` | float | Total reading time for the trial's pages, in milliseconds. |
| `trial_duration_ms` | float | **TODO (#171).** Planned: total trial recording duration in milliseconds. |
| `data_loss_ratio` | float | **TODO (#171).** Planned: fraction of missing samples in the trial, `0` to `1`. Per-trial data loss is currently written to the sanity-check file `per_trial_data_loss_<sid>.tsv`. |
| `blink_ratio` | float | **TODO (#171).** Planned: fraction of trial time spent in blinks, `0` to `1`. |
| `validation_before_start_dva` | float | **TODO (#171).** Planned: validation accuracy before the trial starts, in degrees of visual angle. |

A real entry looks like this:

```yaml
- trial_number: 5
  stimulus_id: 6
  stimulus_name: Lit_MagicMountain
  is_practice: false
  num_questions: 6
  comprehension_score: 0.5
  comprehension_question_time_ms: 146035.0
  reading_time_ms: 204963.0
```

## Still open

The metadata schema is being completed in several issues:

- [#168](https://github.com/MultiplEYE-COST/multipleye-preprocessing/issues/168) tracks the
  metadata YAML work as a whole.
- [#170](https://github.com/MultiplEYE-COST/multipleye-preprocessing/issues/170) covers the
  remaining session fields: `dominant_eye`, `dominant_eye_test`, `question_order` and the
  break fields.
- [#171](https://github.com/MultiplEYE-COST/multipleye-preprocessing/issues/171) covers the
  remaining per-trial fields: `trial_duration_ms`, `data_loss_ratio`, `blink_ratio` and
  `validation_before_start_dva`.
- [#188](https://github.com/MultiplEYE-COST/multipleye-preprocessing/issues/188) covers
  `eyelink_filters`.
- [#291](https://github.com/MultiplEYE-COST/multipleye-preprocessing/issues/291) covers the
  `answer_option_shuffling_bug` flag and its detection rule.
- DCN data-quality metrics such as `mean_pupil_loss_ratio` and
  `mean_missing_values_ratio` remain blocked on definitions and a data source; see #169
  and #168. Linguistic and UZH features are likewise not part of the current schema.

## See also

- {ref}`technical_architecture`: output layout and processing-config settings.
- {ref}`pipeline_stages`: when the overview files are written.
- {ref}`participants_table`: the participant-level table derived from the session metadata.
- {ref}`sanity_check_report`: per-session quality report, including per-trial data loss tables.
