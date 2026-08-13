import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
import yaml

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)
from preprocessing.data_collection.session import Session


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
def dummy_dcn_dir(tmp_path: Path) -> Path:
    """Create a dummy data collection folder structure with sessions."""
    collection_name = "MultiplEYE_EN_UK_London_1_2025"
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


def _create_dc(dummy_dcn_dir: Path, **kwargs) -> MultipleyeDataCollection:
    """Factory to create a MultipleyeDataCollection with dummy data."""
    return MultipleyeDataCollection.create_from_data_folder(dummy_dcn_dir, **kwargs)


def _setup_session_with_data(
    session: Session,
    avg_calibration_error: float = 0.5,
    avg_validation_error: float = 0.3,
    total_data_loss: float = 0.02,
    blink_loss: float = 0.01,
    total_reading_time: float = 25000.0,
    total_session_duration: float = 1800.0,
    avg_comprehension: float = 0.8,
    num_completed_trials: int = 10,
) -> None:
    session.avg_calibration_error = avg_calibration_error
    session.avg_validation_error = avg_validation_error
    session._measure_total_data_loss_ratio = total_data_loss
    session._measure_blink_loss_ratio = blink_loss
    session.total_reading_time = total_reading_time
    session.total_session_duration = total_session_duration
    session.avg_comprehension_score = avg_comprehension
    session.num_completed_trials = num_completed_trials


def _admin(overview: dict) -> dict:
    return overview["Administrative"]


def _lang(overview: dict) -> dict:
    return overview["Language_details"]


def _avail(overview: dict) -> dict:
    return overview["Data_availability"]


def _psych(overview: dict) -> dict:
    return overview["Psychometric_tests"]


def _tech(overview: dict) -> dict:
    return overview["Technical_setup"]


def _proc(overview: dict) -> dict:
    return overview["Processing"]


def _qual(overview: dict) -> dict:
    return overview["Data_quality"]


class TestAdministrative:
    def test_legacy_fields_preserved(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        a = _admin(overview)

        assert a["Title"] == "MultiplEYE_EN_UK_London_1_2025"
        assert a["Dataset_type"] == "MultiplEYE"
        assert a["Tested_language"] == "EN"
        assert a["Country"] == "UK"
        assert a["Year"] == 2025
        assert a["City"] == "London"
        assert a["Lab_number"] == 1

    def test_dataset_description(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        a = _admin(overview)

        assert "London" in a["Dataset_description"]
        assert "EN" in a["Dataset_description"]

    def test_session_counts(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        a = _admin(overview)

        assert a["Number_of_sessions"] == 3
        assert a["Number_of_pilots"] == 0
        assert "Number of eye-tracking (ET) sessions per participant" in a


class TestProcessing:
    def test_processing_metadata(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        p = _proc(overview)

        assert p["Pipeline_version"] == "2026.08.11"
        assert p["Preprocessing_date"] == datetime.now(tz=UTC).strftime("%Y-%m-%d")


class TestTechnicalSetup:
    def test_technical_setup(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        t = _tech(overview)

        assert t["Eye_tracker_name"] == "EyeLink 1000 Plus"
        assert t["Sampling_frequency_hz"] == 1000.0
        assert t["Screen_resolution_width_px"] == 1920
        assert t["Screen_resolution_height_px"] == 1080

    def test_psychometric_tests(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        p = _psych(overview)

        assert p["Tests_available"] == ["TestA", "TestB"]


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
        assert data["Administrative"]["Title"] == "MultiplEYE_EN_UK_London_1_2025"

    def test_sections_ordered(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        keys = list(overview.keys())
        assert keys[0] == "Administrative"
        assert keys[1] == "Language_details"
        assert keys[2] == "Data_availability"
        assert keys[3] == "Psychometric_tests"
        assert keys[4] == "Technical_setup"
        assert keys[5] == "Processing"
        assert keys[6] == "Data_quality"


class TestDataAvailability:
    def test_all_formats_hardcoded_true(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        a = _avail(overview)

        assert a["Raw_data_available"] is True
        assert a["Fixations_available"] is True
        assert a["Saccades_available"] is True
        assert a["Reading_measures_available"] is True


class TestComputedAverages:
    def test_none_with_unprocessed_sessions(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_calibration_error"] is None
        assert q["mean_validation_error"] is None
        assert q["mean_data_loss_ratio"] is None
        assert q["mean_blink_ratio"] is None
        assert q["mean_total_reading_time_ms"] is None
        assert q["mean_comprehension_score"] is None

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

        assert q["mean_calibration_error"] == 0.6
        assert q["mean_validation_error"] == 0.4
        assert q["mean_data_loss_ratio"] == 0.02
        assert q["mean_blink_ratio"] == 0.02


class TestAttritionRate:
    def test_attrition_rate(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        for s in dc.sessions.values():
            _setup_session_with_data(s)
        dc.crashed_session_ids = ["1"]

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        assert _qual(overview)["Attrition_rate"] == pytest.approx(1.0 / 3.0, abs=0.01)

    def test_attrition_rate_zero_with_no_crashes(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        for s in dc.sessions.values():
            _setup_session_with_data(s)

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        assert _qual(overview)["Attrition_rate"] == 0.0


class TestMetadataForm:
    def test_missing_metadata_form(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        ld = _lang(overview)

        assert ld["Metadata_form_exists"] is False
        assert ld["Language_script"] is None
        assert ld["Language_family"] is None

    def test_metadata_form_fields_loaded(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        collection_name = "MultiplEYE_EN_UK_London_1_2025"
        stimuli_dir = dummy_dcn_dir / f"stimuli_{collection_name}"
        doc_dir = stimuli_dir.parent / "documentation"
        doc_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = doc_dir / "MultiplEYE_en_uk_London_1_2025_metadata_form.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "Script": "Latin",
                    "Language_family": "Indo-European",
                    "Start_date_of_data_collection": "2025-01-15",
                    "End_date_of_data_collection": "2025-03-20",
                    "Required_pq_fixing": "yes",
                    "Monitor_name": "Dell U2412M",
                    "Custom_units_of_analysis": False,
                },
                f,
            )

        dc = _create_dc(dummy_dcn_dir)
        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        ld = _lang(overview)
        t = _tech(overview)
        p = _proc(overview)

        assert ld["Metadata_form_exists"] is True
        assert ld["Language_script"] == "Latin"
        assert ld["Language_family"] == "Indo-European"
        assert ld["Start_date_of_data_collection"] == "2025-01-15"
        assert ld["End_date_of_data_collection"] == "2025-03-20"
        assert t["Monitor_name"] == "Dell U2412M"
        assert p["Required_pq_fixing"] == "yes"
        assert "2025-01-15" in _admin(overview)["Dataset_description"]


class TestWPM:
    def test_wpm_none_when_no_stimuli(
        self, dummy_dcn_dir, mock_load_lab_config, mock_pipeline_version
    ) -> None:
        dc = _create_dc(dummy_dcn_dir)
        s1 = dc.sessions["001_EN_UK_1_ET1"]
        _setup_session_with_data(s1, total_reading_time=30000.0)
        s1.stimuli = "unknown"

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)
        q = _qual(overview)

        assert q["mean_total_reading_time_ms"] == 30000.0
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
        _setup_session_with_data(s1, total_reading_time=60000.0)
        s1.stimuli = [stim]

        overview = dc.create_dataset_overview(path=dummy_dcn_dir)

        assert _qual(overview)["mean_wpm"] == pytest.approx(18.0, abs=0.5)


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

        assert t["Eye_tracker_name"] is not None
        assert t["Sampling_frequency_hz"] is None
        assert t["Screen_resolution_width_px"] is None
        assert t["Screen_resolution_height_px"] is None
        assert p["Tests_available"] is None
