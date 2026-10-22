(participants_table)=

# Participant Overview

`participants.csv` contains one row per participant. It is the unified view of eye-tracking
sessions, psychometric tests and the participant questionnaire, and is intended for publishing,
processing and lab feedback.

The file is written to `preprocessed_data/<data_collection_id>/participants.csv`.

## Participant set

Participants are the union of:

- processed eye-tracking (ET) sessions,
- psychometric-test (PT) sessions or the PT results table,
- questionnaire files in `participant_questionnaire_*` or `documentation/`.

A participant with only questionnaire or psychometric data still gets a row; the ET columns stay
empty. Excluded sessions never appear.

## Grouping

By default the participant ID is the 3-digit PID. Use `participant_groups` when one participant
used more than one PID, or when a PID must be split across sessions:

```yaml
participant_groups:
  # One participant used two PIDs: all sessions of both become one row.
  - label: "006"
    pids: ["006", "007"]

  # Only the listed session belongs to this group. Other sessions of PID 010
  # are not included.
  - label: "010"
    pids: ["010"]
    sessions: ["010_EN_UK_1_ET1"]
```

A group includes exactly what it lists: `pids` only means all sessions of those PIDs; `pids` and
`sessions` means only the listed session IDs. Labels must be unique 3-digit IDs, and a PID may
appear in only one group. If a PID is split and the remaining sessions would collide with the
group label, the pipeline raises an error asking for an explicit group with a unique label.

## Identity columns

- `participant_id`: row label (3-digit PID or explicit group label).
- `pids`: all PIDs in the row, separated by `; `.
- `et_session_ids`, `pt_session_ids`: attributed session IDs, separated by `; `.

## Questionnaire columns

The questionnaire is normalised with the data collection's questionnaire workbook (see
{ref}`participant_questionnaire`). Base fields use the canonical codes:

- `pq_gender`, `pq_age`, `pq_years_education`, `pq_years_education_open_ended`,
  `pq_level_education`, `pq_socio_economic_status`, `pq_childhood_languages`, `pq_tiredness`,
  `pq_eyewear`, `pq_alcohol_yesterday`, `pq_alcohol_today`.
- `pq_bi_monolingualism`: derived from the distinct native languages.

Language names are kept **raw** in one column per slot:

- `pq_native_language_1`, `pq_native_language_2`, `pq_native_language_3`
- `pq_use_language`, `pq_dominant_language`
- `pq_additional_read_language_1` to `pq_additional_read_language_4`

The per-language reading-time answers are stored in `pq_language_reading_times` as a JSON object
keyed by language slot and question (for example `{"native_language_1": {"academic":
"1_to_3_hours"}}`).

## Eye-tracking columns

- `et_session_status`, `et_session_ids`
- `et_trials_completed`, `et_trials_total`, `et_trials_practice`, `et_stimuli_presented`
- `et_total_reading_time_s`, `et_total_session_duration_s`
- `et_total_question_time_ms`, `et_total_rating_time_ms`, `et_total_break_time_s`
- `et_blink_loss_ratio`, `et_data_loss_ratio`
- `et_avg_validation_error_dva`, `et_num_calibrations`, `et_num_validations`
- `et_was_interrupted`, `et_restarted_session_names`
- `et_session_stats`: JSON list with the per-session values.

Aggregation across multiple ET sessions:

- Additive values are summed: reading time, session duration, question/rating/break time, trials,
  calibrations and validations.
- Blink-loss and data-loss ratios are weighted by `total_session_duration_s`:
  `sum(ratio * duration) / sum(duration)`.
- Validation error is a simple mean across sessions.

## Psychometric-test columns

- `pt_session_ids`: attributed PT session IDs.
- `pt_tests_status`: test status, for example `RAN:done; LWMC:partial(MU,OS)`.
  `LWMC` is partial when only some subtasks have data.

The test results themselves stay in `psychometric_results_<dcn>.csv` and
`psychometric_results_<dcn>_merged.csv`. Join them on `participant_id` and `session_id`.

## Experimenter-sheet columns

- `doc_setup_deviation`, `doc_technical_issues`, `doc_interruptions`, `doc_irritations`,
  `doc_abortion`, `doc_file_issues`, `doc_comments`
- `doc_extras`: JSON with lab-specific columns such as `Stimulus Version` or `Room used`.

Only rows that can be matched to a participant are used. Rows with a non-numeric PID (for
example `6->7`) or a PID that does not occur in the data are appended as separate rows with the
reason in `manual_comments`.

## Completeness and source-of-truth columns

- `expected_session_ids`: ET/PT session IDs from the experimenter sheet, or `ET` / `PT` when the
  sheet has no session ID.
- `missing_session_ids`: expected sessions with no matching data.
- `missing_sources`: `ET`, `PT` or `PQ` when an expected source has no data.
- `missing_sheet`: source types with data but no matching experimenter-sheet row.
- `pt_tests_expected`: expected tests from the participant configs and the sheet test list.
- `pt_tests_missing`: expected tests not found across the participant's PT sessions.

The checks run in both directions: sheet rows without data are reported in
`missing_session_ids` and `missing_sources`, and data without a sheet row is reported in
`missing_sheet`. Rows marked as aborted/cancelled in the sheet are excluded from the missing-data
checks, but any data that exists is still processed. `num_sessions` is used as a secondary check
when the sheet has no ET row.

## Preflight and comments

- `preflight_status`: `ok`, `warnings`, `errors` or `unknown`.
- `preflight_failed`: failed check names, separated by `; `. The `Cross-source completeness`
  group reports the missing sources, sessions and tests described above.
- `manual_comments`: free-text column for labs. For unassigned experimenter-sheet rows it contains
  the reason.
