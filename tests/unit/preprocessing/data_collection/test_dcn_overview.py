import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pymovements as pm
import pytest
import yaml

import preprocessing.data_collection.multipleye_data_collection as dcn_module
from preprocessing import settings as pipeline_settings
from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)
from preprocessing.data_collection.session import Session
from preprocessing.metadata.language_tree import LanguageTreeError


def _mock_lab_config():
    cfg = MagicMock()
    cfg.screen_resolution = (1920, 1080)
    cfg.screen_size_cm = (52.0, 32.0)
    cfg.screen_distance_cm = 60.0
    cfg.image_resolution = (1322, 980)
    cfg.image_size_cm = (38.0, 28.3)
    cfg.name_eye_tracker = "EyeLink 1000 Plus"
    cfg.sampling_frequency_hz = 1000.0
    cfg.psychometric_tests = ["TestA", "TestB"]
    return cfg


@pytest.fixture
def dummy_dcn_dir(request, tmp_path: Path) -> Path:
    """Create a dummy data collection folder structure with sessions."""
    collection_name = getattr(request, "param", "MultiplEYE_EN_UK_London_1_2025")
    data_dir = tmp_path / collection_name
    data_dir.mkdir()

    et_sessions_dir = data_dir / "eye-tracking-sessions"
    et_sessions_dir.mkdir()
    (data_dir / "psychometric-tests").mkdir()
    stimuli_dir = data_dir / f"stimuli_{collection_name}"
    stimuli_dir.mkdir()
    config_dir = stimuli_dir / "config"
    config_dir.mkdir()

    df = pd.DataFrame({"participant_id": [1, 2, 3], "version_number": [1, 1, 1]})
    df.to_csv(config_dir / "stimulus_order_versions_EN_UK_1.csv", index=False)

    for s_id in ["001_EN_UK_1_ET1", "002_EN_UK_1_ET1", "003_EN_UK_1_ET1"]:
        s_path = et_sessions_dir / s_id
        s_path.mkdir()
        (s_path / "data.edf").touch()

    return data_dir


@pytest.fixture
def mock_load_lab_config(monkeypatch):
    """Mock load_lab_config to return a mock config."""

    class MockLabConfig:
        def __init__(self):
            self.name_eye_tracker = "EyeLink 1000 Plus"
            self.psychometric_tests = ["TestA", "TestB"]
            self.screen_resolution = (1920, 1080)
            self.sampling_frequency_hz = 1000.0
            self.screen_size_cm = (52.0, 32.0)
            self.screen_distance_cm = 60.0
            self.image_resolution = (1322, 980)
            self.image_size_cm = (38.0, 28.3)

    monkeypatch.setattr(
        MultipleyeDataCollection,
        "load_lab_config",
        lambda *args, **kwargs: MockLabConfig(),
    )


@pytest.fixture
def mock_pipeline_version(monkeypatch):
    monkeypatch.setattr(
        MultipleyeDataCollection,
        "_get_pipeline_version",
        lambda self: "2026.08.11",
    )


@pytest.fixture
def mock_processing_environment(monkeypatch):
    """Mock the tool-version helpers used by the processing environment."""
    monkeypatch.setattr(
        dcn_module,
        "get_pipeline_info",
        lambda: (
            "2026.08.11",
            "v2026.08.11-2-gabc1234 (2026-08-11 10:00:00 +0200)",
        ),
    )
    monkeypatch.setattr(
        dcn_module,
        "get_edf2asc_version",
        lambda: "EDF2ASC version 4.2.1197.0 MacOS X standalone",
    )
    monkeypatch.setattr(pm, "__version__", "0.28.0")


def _create_dc(dummy_dcn_dir: Path, **kwargs) -> MultipleyeDataCollection:
    """Factory to create a MultipleyeDataCollection with dummy data."""
    return MultipleyeDataCollection.create_from_data_folder(dummy_dcn_dir, **kwargs)


def _write_metadata_form(dcn_dir: Path, filename: str, payload: dict) -> Path:
    """Write a metadata form into the data collection's documentation folder."""
    doc_dir = dcn_dir / "documentation"
    doc_dir.mkdir(parents=True, exist_ok=True)
    path = doc_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def _write_raw_metadata_form(dcn_dir: Path, filename: str, content: str) -> Path:
    """Write a metadata form verbatim (for non-strict JSON fixtures)."""
    doc_dir = dcn_dir / "documentation"
    doc_dir.mkdir(parents=True, exist_ok=True)
    path = doc_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def _write_answer_option_set(
    stimulus_dir: Path, set_name: str, versions: dict[int, object]
) -> None:
    """Write shuffled answer-option JSON files for a set."""
    set_dir = stimulus_dir / "config" / set_name
    set_dir.mkdir(parents=True, exist_ok=True)
    for version, payload in versions.items():
        path = (
            set_dir / f"shuffled_option_keys_en_question_images_version_{version}.json"
        )
        path.write_text(json.dumps(payload), encoding="utf-8")


def _setup_session_with_data(
    session: Session,
    avg_calibration_error: float = 0.5,
    avg_validation_error: float = 0.3,
    total_data_loss: float = 0.02,
    blink_loss: float = 0.01,
    total_reading_time: float = 25000.0,
    total_session_duration: float = 1800.0,
    avg_comprehension: float = 0.8,
    avg_comprehension_local: float = 0.7,
    avg_comprehension_global: float = 0.9,
    avg_comprehension_bridging: float = 0.6,
    num_completed_trials: int = 10,
) -> None:
    session.avg_calibration_error = avg_calibration_error
    session.avg_validation_error = avg_validation_error
    session._measure_total_data_loss_ratio = total_data_loss
    session._measure_blink_loss_ratio = blink_loss
    session.total_reading_time = total_reading_time
    session.total_session_duration = total_session_duration
    session.avg_comprehension_score = avg_comprehension
    session.avg_comprehension_score_local = avg_comprehension_local
    session.avg_comprehension_score_global = avg_comprehension_global
    session.avg_comprehension_score_bridging = avg_comprehension_bridging
    session.num_completed_trials = num_completed_trials


def _admin(overview: dict) -> dict:
    return overview["administrative"]


def _lang(overview: dict) -> dict:
    return overview["language_details"]


def _avail(overview: dict) -> dict:
    return overview["data_availability"]


def _psych(overview: dict) -> dict:
    return overview["psychometric_tests"]


def _tech(overview: dict) -> dict:
    return overview["technical_setup"]


def _proc(overview: dict) -> dict:
    return overview["processing"]


def _env(overview: dict) -> dict:
    return overview["processing_environment"]


def _qual(overview: dict) -> dict:
    return overview["data_quality"]


class TestAdministrative:
    def test_legacy_fields_preserved(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        a = _admin(overview)

        assert a["title"] == "MultiplEYE_EN_UK_London_1_2025"
        assert a["dataset_type"] == "MultiplEYE"
        assert a["tested_language"] == "EN"
        assert a["country"] == "UK"
        assert a["city"] == "London"
        assert a["lab_number"] == 1

    def test_dataset_description(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        a = _admin(overview)

        assert "London" in a["dataset_description"]
        assert "EN" in a["dataset_description"]

    def test_session_counts(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        a = _admin(overview)

        assert a["number_of_sessions"] == 3
        assert a["number_of_pilots"] == 0
        assert "number_of_et_sessions_per_participant" in a

    def test_session_completeness(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        sc = _admin(overview)["session_completeness"]

        assert sc["expected_sessions_per_participant"] == 1
        assert sc["total_participants"] == 3
        assert sc["complete_participants"] == 3
        assert "incomplete_participants" not in sc
        assert "extra_sessions_participants" not in sc


class TestProcessing:
    def test_processing_metadata(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        p = _proc(overview)

        assert p["pipeline_version"] == "2026.08.11"
        assert p["preprocessing_date"] == datetime.now(tz=UTC).strftime("%Y-%m-%d")

    def test_pipeline_version_not_duplicated_in_environment(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        assert "pipeline_version" not in _env(overview)


class TestProcessingEnvironment:
    def test_processing_environment_values(
        self,
        dummy_dcn_dir,
        mock_load_lab_config,
        mock_pipeline_version,
        mock_processing_environment,
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        env = _env(overview)

        assert env["pipeline_git"] == (
            "v2026.08.11-2-gabc1234 (2026-08-11 10:00:00 +0200)"
        )
        assert env["pymovements_version"] == "0.28.0"
        assert env["edf2asc_version"] == (
            "EDF2ASC version 4.2.1197.0 MacOS X standalone"
        )
        assert env["python_version"] == (
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )

    def test_unavailable_values_are_none(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            dcn_module, "get_pipeline_info", lambda: ("unknown", "unknown")
        )
        monkeypatch.setattr(dcn_module, "get_edf2asc_version", lambda: "unknown")
        monkeypatch.setattr(pm, "__version__", "unknown")

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        env = _env(overview)

        assert env["pipeline_git"] is None
        assert env["pymovements_version"] is None
        assert env["edf2asc_version"] is None
        assert env["python_version"] is not None

    def test_processing_environment_round_trips_through_yaml(
        self,
        dummy_dcn_dir,
        mock_load_lab_config,
        mock_pipeline_version,
        mock_processing_environment,
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        dc.create_dataset_overview(path=dummy_dcn_dir)
        yaml_path = dummy_dcn_dir / "MultiplEYE_EN_UK_London_1_2025_overview.yaml"

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        env = data["processing_environment"]
        assert env["pipeline_git"] == (
            "v2026.08.11-2-gabc1234 (2026-08-11 10:00:00 +0200)"
        )
        assert env["pymovements_version"] == "0.28.0"
        assert env["edf2asc_version"] == (
            "EDF2ASC version 4.2.1197.0 MacOS X standalone"
        )


class TestAnswerOptionShuffling:
    set_name = "question_answer_option_shuffling_en_uk_1"

    @staticmethod
    def _set_versions(dc: MultipleyeDataCollection, versions: dict[str, int]) -> None:
        for session_id, version in versions.items():
            dc.sessions[session_id].randomization_version = version

    def test_flags_majority_content(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        self._set_versions(
            dc,
            {
                "001_EN_UK_1_ET1": 1,
                "002_EN_UK_1_ET1": 2,
                "003_EN_UK_1_ET1": 3,
            },
        )
        _write_answer_option_set(
            dc.stimulus_dir,
            self.set_name,
            {
                1: {"q1": ["a", "b"]},
                2: {"q1": ["a", "b"]},
                3: {"q1": ["b", "a"]},
            },
        )

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        check = _proc(overview)["answer_option_shuffling"]

        assert check["flagged"] is True
        assert check["num_sets"] == 1
        assert check["num_sessions"] == 3
        assert check["num_flagged_sets"] == 1
        stats = check["sets"][self.set_name]
        assert stats["num_sessions"] == 3
        assert stats["num_versions"] == 3
        assert stats["num_unique"] == 2
        assert stats["max_identical_sessions"] == 2
        assert stats["max_identical_share"] == 0.667
        assert stats["all_files_identical"] is False
        assert any(
            "Answer-option shuffling check" in warning
            for warning in overview["warnings"]
        )

    def test_one_of_two_split_is_not_flagged(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        dc.sessions.pop("003_EN_UK_1_ET1")
        self._set_versions(
            dc,
            {
                "001_EN_UK_1_ET1": 1,
                "002_EN_UK_1_ET1": 2,
            },
        )
        _write_answer_option_set(
            dc.stimulus_dir,
            self.set_name,
            {
                1: {"q1": ["a", "b"]},
                2: {"q1": ["b", "a"]},
            },
        )

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        stats = _proc(overview)["answer_option_shuffling"]["sets"][self.set_name]

        assert stats["max_identical_sessions"] == 1
        assert stats["max_identical_share"] == 0.5
        assert stats["flagged"] is False

    def test_all_files_identical_is_flagged(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        self._set_versions(
            dc,
            {
                "001_EN_UK_1_ET1": 1,
                "002_EN_UK_1_ET1": 2,
                "003_EN_UK_1_ET1": 3,
            },
        )
        payload = {"q1": ["a", "b"]}
        _write_answer_option_set(
            dc.stimulus_dir,
            self.set_name,
            {1: payload, 2: payload, 3: payload},
        )

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        stats = _proc(overview)["answer_option_shuffling"]["sets"][self.set_name]

        assert stats["all_files_identical"] is True
        assert stats["max_identical_sessions"] == 3
        assert stats["flagged"] is True

    def test_all_files_differ_but_used_files_are_identical(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        dc.sessions.pop("003_EN_UK_1_ET1")
        self._set_versions(
            dc,
            {
                "001_EN_UK_1_ET1": 1,
                "002_EN_UK_1_ET1": 2,
            },
        )
        shared = {"q1": ["a", "b"]}
        _write_answer_option_set(
            dc.stimulus_dir,
            self.set_name,
            {1: shared, 2: shared, 3: {"q1": ["b", "a"]}},
        )

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        stats = _proc(overview)["answer_option_shuffling"]["sets"][self.set_name]

        assert stats["all_files_identical"] is False
        assert stats["max_identical_sessions"] == 2
        assert stats["max_identical_share"] == 1.0
        assert stats["flagged"] is True

    def test_unreadable_files_leave_all_files_identical_unknown(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        set_dir = dc.stimulus_dir / "config" / self.set_name
        set_dir.mkdir(parents=True)
        (set_dir / "shuffled_option_keys_en_question_images_version_1.json").write_text(
            "{not json", encoding="utf-8"
        )

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        stats = _proc(overview)["answer_option_shuffling"]["sets"][self.set_name]

        assert stats["num_sessions"] == 0
        assert stats["num_versions"] == 0
        assert stats["all_files_identical"] is None
        assert stats["flagged"] is False


class TestEyeTrackerMapping:
    @staticmethod
    def _lab_config(name: str) -> object:
        class LabConfigStub:
            psychometric_tests: list[str] = []

        LabConfigStub.name_eye_tracker = name
        return LabConfigStub()

    def test_alias_is_canonicalized_and_raw_name_is_kept(
        self, dummy_dcn_dir, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            MultipleyeDataCollection,
            "load_lab_config",
            lambda *args, **kwargs: self._lab_config("Eyelink Duo"),
        )

        dc = _create_dc(dummy_dcn_dir)

        assert dc.eye_tracker_name_raw == "Eyelink Duo"
        assert dc.eye_tracker_name == "EyeLink Portable Duo"
        assert dc.eye_tracker == "eyelink"

    def test_unsupported_name_raises_with_suggestion(
        self, dummy_dcn_dir, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            MultipleyeDataCollection,
            "load_lab_config",
            lambda *args, **kwargs: self._lab_config("EyeLink 1000 Pluss"),
        )

        with pytest.raises(ValueError, match="Did you mean: EyeLink 1000 Plus"):
            _create_dc(dummy_dcn_dir)


class TestTechnicalSetup:
    def test_technical_setup(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        t = _tech(overview)

        assert t["eye_tracker_name_raw"] == "EyeLink 1000 Plus"
        assert t["eye_tracker_name"] == "EyeLink 1000 Plus"
        assert t["sampling_frequency_hz"] == 1000.0
        assert t["screen_resolution_width_px"] == 1920
        assert t["screen_resolution_height_px"] == 1080

    def test_lab_level_screen_and_image_dimensions(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        t = _tech(overview)

        assert t["screen_size_width_cm"] == 52.0
        assert t["screen_size_height_cm"] == 32.0
        assert t["screen_distance_cm"] == 60.0
        assert t["image_resolution_width_px"] == 1322
        assert t["image_resolution_height_px"] == 980
        assert t["image_size_width_cm"] == 38.0
        assert t["image_size_height_cm"] == 28.3

    def test_psychometric_tests(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        p = _psych(overview)

        assert p["tests_available"] == ["TestA", "TestB"]


class TestCodebookMetadata:
    def test_codebook_version_and_credit(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        codebook = overview["codebook"]

        assert codebook["version"] == "2.0-dev0"
        assert "Marie-Luise Müller" in codebook["credit"]
        assert "Carlson Moses Büth" in codebook["credit"]
        assert codebook["hash"].startswith("sha256:")


class TestCodebookOutputs:
    def test_dcn_writes_codebook_outputs(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version, tmp_path
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)

        destination = dc.write_codebook_outputs(tmp_path)

        assert destination == tmp_path / "codebook"
        assert (tmp_path / "codebook.csv").exists()
        assert (tmp_path / "codebook" / "codebook_info.csv").exists()
        assert (tmp_path / "codebook" / "environment.csv").exists()
        assert (tmp_path / "codebook" / "generated" / "codebook_bundle.json").exists()
        assert (tmp_path / "codebook" / "generated" / "codebook_bundle.zip").exists()


class TestYAMLOutput:
    def test_yaml_output_is_valid(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        dc.create_dataset_overview(path=dummy_dcn_dir)
        yaml_path = dummy_dcn_dir / "MultiplEYE_EN_UK_London_1_2025_overview.yaml"
        assert yaml_path.exists()

        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        assert data["administrative"]["title"] == "MultiplEYE_EN_UK_London_1_2025"

    def test_sections_ordered(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        keys = list(overview.keys())
        assert keys[0] == "administrative"
        assert keys[1] == "language_details"
        assert keys[2] == "data_availability"
        assert keys[3] == "psychometric_tests"
        assert keys[4] == "technical_setup"
        assert keys[5] == "processing"
        assert keys[6] == "processing_environment"
        assert keys[7] == "processing_config"
        assert keys[8] == "data_quality"


class TestProcessingConfig:
    def test_processing_config_reflects_settings(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        pc = overview["processing_config"]

        assert pc["fixation_method"] == "ivt"
        assert pc["fixation_minimum_duration_ms"] == 100
        assert pc["fixation_velocity_threshold"] == 20.0
        assert pc["saccade_method"] == "microsaccades"
        assert pc["saccade_minimum_duration"] == 6
        assert pc["saccade_threshold_factor"] == 6.0
        assert pc["velocity_estimation_method"] == "savitzky_golay"
        assert pc["velocity_smoothing_window_ms"] == 50
        assert pc["velocity_polynomial_degree"] == 2

    def test_processing_config_records_fixed_design_decisions(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        pc = overview["processing_config"]

        assert pc["aoi_enlargement"] == "half_line_spacing"
        assert pc["reading_measures_null_fill"] == 0
        assert pc["scanpath_drop_unmapped"] is True
        assert pc["data_loss_missingness_column"] == "pixel"
        assert pc["per_trial_loss_weighting"] == "equal"

    def test_processing_config_records_psychometric_thresholds(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        from preprocessing import settings

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        pc = overview["processing_config"]

        assert pc["psym_wikivocab_min_rt"] == settings.PSYM_WIKIVOCAB_MIN_RT
        assert pc["psym_wikivocab_max_rt"] == settings.PSYM_WIKIVOCAB_MAX_RT
        assert pc["psym_stroop_min_rt"] == settings.PSYM_STROOP_MIN_RT
        assert pc["psym_stroop_max_rt"] == settings.PSYM_STROOP_MAX_RT
        assert pc["psym_flanker_min_rt"] == settings.PSYM_FLANKER_MIN_RT
        assert pc["psym_flanker_max_rt"] == settings.PSYM_FLANKER_MAX_RT

    def test_processing_config_records_eye_and_column_mappings(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        from preprocessing import settings

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        pc = overview["processing_config"]

        assert pc["tracked_eye"] == settings.TRACKED_EYE
        assert pc["trial_cols"] == settings.TRIAL_COLS
        assert pc["trial_col"] == settings.TRIAL_COL
        assert pc["page_col"] == settings.PAGE_COL
        assert pc["stimulus_col"] == settings.STIMULUS_COL
        assert pc["word_idx_col"] == settings.WORD_IDX_COL
        assert pc["char_idx_col"] == settings.CHAR_IDX_COL

    def test_processing_config_inf_round_trips_through_yaml(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        dc.create_dataset_overview(path=dummy_dcn_dir)
        yaml_path = dummy_dcn_dir / "MultiplEYE_EN_UK_London_1_2025_overview.yaml"

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        pc = data["processing_config"]
        assert pc["psym_wikivocab_max_rt"] == float("inf")
        assert pc["psym_stroop_max_rt"] == float("inf")
        assert pc["psym_flanker_max_rt"] == float("inf")
        assert pc["tracked_eye"] == ["L", "R", "RIGHT", "LEFT"]


class TestDataAvailability:
    def test_all_formats_hardcoded_true(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        a = _avail(overview)

        assert a["raw_data_available"] is True
        assert a["fixations_available"] is True
        assert a["saccades_available"] is True
        assert a["reading_measures_available"] is True


class TestComputedAverages:
    def test_none_with_unprocessed_sessions(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_calibration_error_dva"] is None
        assert q["mean_validation_error_dva"] is None
        assert q["mean_data_loss_ratio"] is None
        assert q["mean_blink_ratio"] is None
        assert q["mean_total_reading_time_s"] is None
        assert q["mean_rt_per_stim_ms"] is None
        assert q["mean_total_question_time_ms"] is None
        assert q["mean_total_rating_time_ms"] is None
        assert q["mean_comprehension_score"] is None
        assert q["mean_comprehension_score_local"] is None
        assert q["mean_comprehension_score_global"] is None
        assert q["mean_comprehension_score_bridging"] is None

    def test_time_rating_averages(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        for session, question_ms, rating_ms in [
            ("001_EN_UK_1_ET1", 1000.0, 3000.0),
            ("002_EN_UK_1_ET1", 2000.0, 4000.0),
            ("003_EN_UK_1_ET1", 3000.0, 5000.0),
        ]:
            s = dc.sessions[session]
            _setup_session_with_data(s)
            s.total_question_time_ms = question_ms
            s.total_rating_time_ms = rating_ms

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_total_question_time_ms"] == 2000.0
        assert q["mean_total_rating_time_ms"] == 4000.0

    def test_comprehension_by_type_averages(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        _setup_session_with_data(
            dc.sessions["001_EN_UK_1_ET1"],
            avg_comprehension=0.8,
            avg_comprehension_local=0.7,
            avg_comprehension_global=0.9,
            avg_comprehension_bridging=0.6,
        )
        _setup_session_with_data(
            dc.sessions["002_EN_UK_1_ET1"],
            avg_comprehension=0.6,
            avg_comprehension_local=0.5,
            avg_comprehension_global=0.7,
            avg_comprehension_bridging=0.4,
        )

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_comprehension_score"] == 0.7
        assert q["mean_comprehension_score_local"] == 0.6
        assert q["mean_comprehension_score_global"] == 0.8
        assert q["mean_comprehension_score_bridging"] == 0.5

    def test_averages_with_multiple_sessions(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        _setup_session_with_data(
            dc.sessions["001_EN_UK_1_ET1"],
            avg_calibration_error=0.5,
            avg_validation_error=0.3,
            total_data_loss=0.02,
            blink_loss=0.01,
        )
        _setup_session_with_data(
            dc.sessions["002_EN_UK_1_ET1"],
            avg_calibration_error=0.7,
            avg_validation_error=0.4,
            total_data_loss=0.03,
            blink_loss=0.02,
        )
        _setup_session_with_data(
            dc.sessions["003_EN_UK_1_ET1"],
            avg_calibration_error=0.6,
            avg_validation_error=0.5,
            total_data_loss=0.01,
            blink_loss=0.03,
        )

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_calibration_error_dva"] == 0.6
        assert q["mean_validation_error_dva"] == 0.4
        assert q["mean_data_loss_ratio"] == 0.02
        assert q["mean_blink_ratio"] == 0.02

    def test_mean_rt_per_stim_averages(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        for s in dc.sessions.values():
            _setup_session_with_data(s)
            s.mean_rt_per_stim_ms = 3000.0
        dc.sessions["003_EN_UK_1_ET1"].mean_rt_per_stim_ms = 5000.0

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_rt_per_stim_ms"] == 3666.67


class TestAttritionRate:
    def test_attrition_rate(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        for s in dc.sessions.values():
            _setup_session_with_data(s)
        dc.crashed_session_ids = ["1"]

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        assert _qual(overview)["attrition_rate"] == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_attrition_rate_zero_with_no_crashes(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        for s in dc.sessions.values():
            _setup_session_with_data(s)

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        assert _qual(overview)["attrition_rate"] == 0.0


class TestMetadataForm:
    def test_missing_metadata_form(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        ld = _lang(overview)

        assert ld["metadata_form_exists"] is False
        assert ld["language_script"] is None
        assert ld["language_family"] is None
        assert ld["start_date_of_data_collection"] is None
        assert ld["end_date_of_data_collection"] is None

    def test_metadata_form_fields_loaded(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        _write_metadata_form(
            dummy_dcn_dir,
            "MultiplEYE_en_uk_London_1_2025_metadata_form.json",
            {
                "Script": "Latin",
                "Language_family": "Indo-European",
                "Start_date_of_data_collection": "2025-01-15",
                "End_date_of_data_collection": "2025-03-20",
                "Required_pq_fixing": "yes",
                "Monitor_name": "Dell U2412M",
                "Custom_units_of_analysis": False,
            },
        )

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        ld = _lang(overview)
        t = _tech(overview)
        p = _proc(overview)

        assert ld["metadata_form_exists"] is True
        assert ld["language_script"] == "Latin"
        assert ld["language_family"] == "Indo-European"
        assert ld["start_date_of_data_collection"] == "2025-01-15"
        assert ld["end_date_of_data_collection"] == "2025-03-20"
        assert t["monitor_name"] == "Dell U2412M"
        assert p["required_pq_fixing"] == "yes"
        assert "2025-01-15" in _admin(overview)["dataset_description"]

    @pytest.mark.parametrize(
        "dummy_dcn_dir",
        ["MultiplEYE_EN_UK_Copenhagen_1_2025"],
        indirect=True,
    )
    def test_copenhagen_metadata_form_with_trailing_space(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        _write_metadata_form(
            dummy_dcn_dir,
            "metadataForm_MultiplEYE_EN_UK_Copenhagen_1_2025 .json",
            {
                "Tested_language": {
                    "Language_script": ["Latin"],
                    "Language_family": ["Indo-European"],
                },
                "Time_frame": {
                    "Start_date": "2025-01-15",
                    "End_date": "2025-03-20",
                },
            },
        )

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        ld = _lang(overview)
        description = _admin(overview)["dataset_description"]

        assert ld["metadata_form_exists"] is True
        assert ld["language_script"] == ["Latin"]
        assert ld["language_family"] == ["Indo-European"]
        assert ld["start_date_of_data_collection"] == "2025-01-15"
        assert ld["end_date_of_data_collection"] == "2025-03-20"
        assert "2025-01-15" in description
        assert "2025-03-20" in description

    def test_turin_style_metadata_form(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        _write_metadata_form(
            dummy_dcn_dir,
            "metadataform_MultiplEYE_EN_UK_London_1_2025.json",
            {
                "Tested_language": {
                    "Language_script": ["Latin", "Cyrillic"],
                    "Language_family": ["Indo-European", "Turkic"],
                },
                "Time_frame": {
                    "Start_date": "2025-02-01",
                    "End_date": "2025-04-30",
                },
            },
        )

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        ld = _lang(overview)

        assert ld["metadata_form_exists"] is True
        assert ld["language_script"] == ["Latin", "Cyrillic"]
        assert ld["language_family"] == ["Indo-European", "Turkic"]
        assert ld["start_date_of_data_collection"] == "2025-02-01"
        assert ld["end_date_of_data_collection"] == "2025-04-30"

    @pytest.mark.parametrize(
        "dummy_dcn_dir, filename",
        [
            (
                "MultiplEYE_EN_UK_Copenhagen_1_2025",
                "metadataForm_MultiplEYE_EN_UK_Copenhagen_1_2025 .json",
            ),
            (
                "MultiplEYE_EN_UK_London_1_2025",
                "metadataform_MultiplEYE_EN_UK_London_1_2025.json",
            ),
        ],
        indirect=["dummy_dcn_dir"],
    )
    def test_real_filename_with_non_strict_json(
        self, dummy_dcn_dir, filename, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        """Real uploads may contain raw newlines and trailing commas."""
        _write_raw_metadata_form(
            dummy_dcn_dir,
            filename,
            """{
  "Tested_language": {
    "Language_script": ["Latin"],
    "Language_family": ["Indo-
European"]
  },
  "Time_frame": {
    "Start_date": "2025-01-15",
    "End_date": "2025-03-20",
  },
}
""",
        )

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        ld = _lang(overview)

        assert ld["metadata_form_exists"] is True
        assert ld["language_script"] == ["Latin"]
        assert ld["language_family"] == ["Indo-\nEuropean"]
        assert ld["start_date_of_data_collection"] == "2025-01-15"
        assert ld["end_date_of_data_collection"] == "2025-03-20"

    def test_non_strict_json_preserves_comma_brace_in_string(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        """The trailing-comma sanitizer must not touch string contents."""
        _write_raw_metadata_form(
            dummy_dcn_dir,
            "metadataform_MultiplEYE_EN_UK_London_1_2025.json",
            """{
  "Monitor_name": "Dell U2412M,} odd",
  "Required_pq_fixing": "yes",
}
""",
        )

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        assert _tech(overview)["monitor_name"] == "Dell U2412M,} odd"
        assert _proc(overview)["required_pq_fixing"] == "yes"

    def test_prefers_form_matching_dcn(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        _write_metadata_form(
            dummy_dcn_dir,
            "metadataform_MultiplEYE_DE_DE_Berlin_1_2025.json",
            {
                "Tested_language": {
                    "Language_script": ["Latin"],
                    "Language_family": ["Indo-European"],
                },
                "Time_frame": {"Start_date": "2024-01-01", "End_date": "2024-02-01"},
            },
        )
        _write_metadata_form(
            dummy_dcn_dir,
            "metadataform_MultiplEYE_EN_UK_London_1_2025.json",
            {
                "Tested_language": {
                    "Language_script": ["Latin", "Cyrillic"],
                    "Language_family": ["Indo-European", "Turkic"],
                },
                "Time_frame": {"Start_date": "2025-01-15", "End_date": "2025-03-20"},
            },
        )

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        ld = _lang(overview)

        assert ld["language_script"] == ["Latin", "Cyrillic"]
        assert ld["language_family"] == ["Indo-European", "Turkic"]
        assert ld["start_date_of_data_collection"] == "2025-01-15"
        assert ld["end_date_of_data_collection"] == "2025-03-20"


class TestWPM:
    def test_wpm_none_when_no_stimuli(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        s1 = dc.sessions["001_EN_UK_1_ET1"]
        _setup_session_with_data(s1, total_reading_time=30.0)
        s1.stimuli = "unknown"

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_total_reading_time_s"] == 30.0
        assert q["mean_wpm"] is None

    def test_wpm_computed_from_page_texts(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        page = MagicMock()
        page.text = "This is a test sentence with eight words here."
        stim = MagicMock()
        stim.pages = [page, page]

        dc = _create_dc(dummy_dcn_dir)
        s1 = dc.sessions["001_EN_UK_1_ET1"]
        _setup_session_with_data(s1, total_reading_time=60.0)
        s1.stimuli = [stim]

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_total_reading_time_s"] == 60.0
        assert q["mean_wpm"] == pytest.approx(18.0, abs=0.5)


class TestLanguageNode:
    @pytest.fixture
    def language_snapshot(self, tmp_path):
        path = tmp_path / "language_tree.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "version": "2026.10",
                    "nodes": [
                        {"id": "root", "label": "Root"},
                        {"id": "branch", "label": "Branch", "parent": "root"},
                        {"id": "leaf", "label": "Leaf", "parent": "branch"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    @pytest.fixture
    def configured_language_node(self, monkeypatch, language_snapshot):
        monkeypatch.setattr(pipeline_settings, "LANGUAGE_NODE_ID", "leaf")
        monkeypatch.setattr(pipeline_settings, "LANGUAGE_TREE_PATH", "root/branch/leaf")
        monkeypatch.setattr(pipeline_settings, "LANGUAGE_TREE_VERSION", "2026.10")
        monkeypatch.setattr(
            pipeline_settings, "LANGUAGE_TREE_SNAPSHOT", language_snapshot
        )
        return language_snapshot

    def test_no_language_node_configured(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        assert "language_node" not in overview

    def test_language_node_written_to_dcn_yaml(
        self,
        dummy_dcn_dir,
        mock_load_lab_config,
        mock_pipeline_version,
        configured_language_node,
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        node = overview["language_node"]

        assert node["language_node_id"] == "leaf"
        assert node["language_node_path"] == "root/branch/leaf"
        assert node["language_node_label"] == "Leaf"
        assert node["language_tree_version"] == "2026.10"
        assert node["language_tree_hash"].startswith("sha256:")

        yaml_path = dummy_dcn_dir / "MultiplEYE_EN_UK_London_1_2025_overview.yaml"
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["language_node"] == node
        assert data["administrative"]["tested_language"] == "EN"
        assert data["administrative"]["country"] == "UK"

    def test_invalid_language_node_raises(
        self,
        dummy_dcn_dir,
        mock_load_lab_config,
        mock_pipeline_version,
        monkeypatch,
        language_snapshot,
    ) -> None:
        monkeypatch.setattr(pipeline_settings, "LANGUAGE_NODE_ID", "unknown")
        monkeypatch.setattr(
            pipeline_settings, "LANGUAGE_TREE_SNAPSHOT", language_snapshot
        )

        with pytest.raises(LanguageTreeError, match="not in the pinned"):
            _create_dc(dummy_dcn_dir)

    def test_missing_language_snapshot_raises(
        self,
        dummy_dcn_dir,
        mock_load_lab_config,
        mock_pipeline_version,
        monkeypatch,
        tmp_path,
    ) -> None:
        monkeypatch.setattr(pipeline_settings, "LANGUAGE_NODE_ID", "leaf")
        monkeypatch.setattr(
            pipeline_settings,
            "LANGUAGE_TREE_SNAPSHOT",
            tmp_path / "missing.yaml",
        )

        with pytest.raises(LanguageTreeError, match="snapshot not found"):
            _create_dc(dummy_dcn_dir)


class TestLabConfigAttributeSafety:
    def test_missing_lab_config_attrs_handled(
        self, dummy_dcn_dir, mock_pipeline_version, monkeypatch
    ) -> None:
        class SparseLabConfig:
            def __init__(self):
                self.name_eye_tracker = "EyeLink 1000 Plus"
                self.psychometric_tests = None

        monkeypatch.setattr(
            MultipleyeDataCollection,
            "load_lab_config",
            lambda *args, **kwargs: SparseLabConfig(),
        )
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        t = _tech(overview)
        p = _psych(overview)

        assert t["eye_tracker_name"] is not None
        assert t["sampling_frequency_hz"] is None
        assert t["screen_resolution_width_px"] is None
        assert t["screen_resolution_height_px"] is None
        assert t["screen_size_width_cm"] is None
        assert t["screen_size_height_cm"] is None
        assert t["screen_distance_cm"] is None
        assert t["image_resolution_width_px"] is None
        assert t["image_resolution_height_px"] is None
        assert t["image_size_width_cm"] is None
        assert t["image_size_height_cm"] is None
        assert p["tests_available"] is None
