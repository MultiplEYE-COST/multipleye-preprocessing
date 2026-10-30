"""Registry coverage for the delivered dataset and session overview paths."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from preprocessing.metadata.registry import iter_registry_fields


def _paths(section: str, names: Iterable[str]) -> set[str]:
    return {f"{section}.{name}" for name in names}


DATASET_PATHS = {
    *_paths(
        "administrative",
        (
            "title",
            "dataset_type",
            "dataset_description",
            "number_of_sessions",
            "number_of_pilots",
            "number_of_et_sessions_per_participant",
            "city",
            "lab_number",
            "country",
            "tested_language",
        ),
    ),
    *_paths(
        "administrative.session_completeness",
        (
            "expected_sessions_per_participant",
            "total_participants",
            "complete_participants",
            "incomplete_participants",
            "extra_sessions_participants",
        ),
    ),
    *_paths(
        "language_details",
        (
            "metadata_form_exists",
            "language_script",
            "language_family",
            "start_date_of_data_collection",
            "end_date_of_data_collection",
        ),
    ),
    *_paths(
        "data_availability",
        (
            "raw_data_available",
            "fixations_available",
            "saccades_available",
            "reading_measures_available",
        ),
    ),
    *_paths("psychometric_tests", ("tests_available",)),
    *_paths(
        "technical_setup",
        (
            "eye_tracker_name_raw",
            "eye_tracker_name",
            "sampling_frequency_hz",
            "monitor_name",
            "screen_resolution_width_px",
            "screen_resolution_height_px",
            "screen_size_width_cm",
            "screen_size_height_cm",
            "screen_distance_cm",
            "image_resolution_width_px",
            "image_resolution_height_px",
            "image_size_width_cm",
            "image_size_height_cm",
        ),
    ),
    *_paths(
        "processing",
        (
            "preprocessing_date",
            "pipeline_version",
            "number_of_stimulus_versions",
            "required_pq_fixing",
            "psychotests_restructuring",
            "custom_units_of_analysis",
        ),
    ),
    *_paths(
        "processing.answer_option_shuffling",
        ("flagged", "num_sets", "num_sessions", "num_flagged_sets"),
    ),
    *_paths(
        "processing.answer_option_shuffling.sets[]",
        (
            "flagged",
            "num_sessions",
            "num_versions",
            "num_unique",
            "max_identical_sessions",
            "max_identical_share",
            "all_files_identical",
        ),
    ),
    *_paths(
        "processing_environment",
        (
            "pipeline_git",
            "pymovements_version",
            "edf2asc_version",
            "python_version",
        ),
    ),
    *_paths(
        "processing_config",
        (
            "fixation_method",
            "fixation_minimum_duration_ms",
            "fixation_velocity_threshold",
            "saccade_method",
            "saccade_minimum_duration",
            "saccade_threshold_factor",
            "velocity_estimation_method",
            "velocity_smoothing_window_ms",
            "velocity_polynomial_degree",
            "psym_wikivocab_min_rt",
            "psym_wikivocab_max_rt",
            "psym_stroop_min_rt",
            "psym_stroop_max_rt",
            "psym_flanker_min_rt",
            "psym_flanker_max_rt",
            "tracked_eye",
            "trial_cols",
            "trial_col",
            "page_col",
            "stimulus_col",
            "word_idx_col",
            "char_idx_col",
            "aoi_enlargement",
            "reading_measures_null_fill",
            "scanpath_drop_unmapped",
            "data_loss_missingness_column",
            "per_trial_loss_weighting",
        ),
    ),
    *_paths(
        "data_quality",
        (
            "attrition_rate",
            "mean_calibration_error_dva",
            "mean_validation_error_dva",
            "mean_rt_per_stim_ms",
            "mean_total_question_time_ms",
            "mean_total_rating_time_ms",
            "mean_data_loss_ratio",
            "mean_blink_ratio",
            "mean_total_reading_time_s",
            "mean_total_session_duration_s",
            "mean_wpm",
            "mean_comprehension_score",
            "mean_comprehension_score_local",
            "mean_comprehension_score_global",
            "mean_comprehension_score_bridging",
        ),
    ),
    *_paths("codebook", ("version", "credit", "hash")),
    "warnings",
}

SESSION_PATHS = {
    *_paths(
        "administrative",
        (
            "participant_id",
            "session_identifier",
            "is_pilot",
            "year_of_data_collection",
            "month_of_data_collection",
        ),
    ),
    *_paths(
        "participant",
        (
            "gender",
            "bi_monolingualism",
            "psychometric_tests",
            "tests_conducted_this_session",
            "tests_conducted_separate_session",
            "has_pt_data_same_day_as_session",
            "gap_to_previous_session_days",
            "gap_to_next_session_days",
            "gap_to_psychometric_tests_days",
            "psychometric_test_scores",
        ),
    ),
    *_paths(
        "technical_setup",
        (
            "eye_tracker_name",
            "sampling_frequency_hz",
            "mount_type",
            "mount_short_name",
            "head_stabilization",
            "eyes_recorded",
            "pupil_data_type",
            "dominant_eye",
            "dominant_eye_test",
            "screen_resolution_width_px",
            "screen_resolution_height_px",
            "screen_size_width_cm",
            "screen_size_height_cm",
            "screen_distance_cm",
            "image_resolution_width_px",
            "image_resolution_height_px",
            "image_size_width_cm",
            "image_size_height_cm",
        ),
    ),
    *_paths(
        "technical_setup.eyelink_filters",
        ("events", "samples"),
    ),
    *_paths("tracking", ("tracked_eye", "tracked_eye_consistent")),
    *_paths(
        "calibration_validation",
        (
            "num_calibrations",
            "num_validations",
            "avg_calibration_error_dva",
            "avg_validation_error_dva",
            "final_validation_score_dva",
            "calibration_quality",
            "validation_quality",
            "num_aborted_validations",
            "num_good_validations",
            "num_moderate_validations",
            "num_bad_validations",
        ),
    ),
    *_paths(
        "data_quality",
        ("session_total_data_loss_ratio", "session_blink_loss_ratio"),
    ),
    *_paths(
        "experiment_procedure",
        (
            "stimulus_content_version",
            "stimulus_order_ids",
            "stimulus_order_ids_with_names",
            "num_completed_trials",
            "was_session_interrupted",
            "restarted_session_name",
            "obligatory_break_made",
            "num_optional_breaks_made",
            "total_break_time_s",
            "total_reading_time_s",
            "total_session_duration_s",
            "mean_rt_per_stim_ms",
            "sd_rt_per_stim_ms",
            "total_question_time_ms",
            "total_rating_time_ms",
            "familiarity_1",
            "familiarity_2",
            "subjective_difficulty",
        ),
    ),
    *_paths(
        "comprehension",
        (
            "avg_comprehension_score",
            "avg_comprehension_score_local",
            "avg_comprehension_score_global",
            "avg_comprehension_score_bridging",
        ),
    ),
    *_paths(
        "data_formats",
        ("raw_data", "fixations", "saccades", "reading_measures", "answers"),
    ),
}


@pytest.fixture(scope="module")
def registry_paths() -> dict[str, set[str]]:
    """Return the registered YAML paths grouped by view."""
    paths: dict[str, set[str]] = {}
    for field in iter_registry_fields():
        paths.setdefault(field.view_level, set()).add(field.yaml_path)
    return paths


@pytest.mark.parametrize(
    ("view_level", "expected"),
    [("dataset", DATASET_PATHS), ("session", SESSION_PATHS)],
)
def test_registry_covers_delivered_view_paths(
    registry_paths: dict[str, set[str]],
    view_level: str,
    expected: set[str],
) -> None:
    missing = expected - registry_paths[view_level]

    assert not missing, f"Missing {view_level} registry paths: {sorted(missing)}"


@pytest.mark.parametrize(
    ("view_level", "expected"),
    [("dataset", DATASET_PATHS), ("session", SESSION_PATHS)],
)
def test_registry_paths_have_unique_field_ids(
    view_level: str, expected: set[str]
) -> None:
    fields = [
        field for field in iter_registry_fields() if field.view_level == view_level
    ]
    paths = [field.yaml_path for field in fields if field.yaml_path in expected]
    ids = [field.variable_id for field in fields if field.yaml_path in expected]

    assert len(paths) == len(set(paths))
    assert len(ids) == len(set(ids))
