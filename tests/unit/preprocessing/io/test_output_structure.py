import pytest
import polars as pl
import pymovements as pm
from preprocessing.io.save import (
    save_raw_data,
    save_events_data,
    save_scanpaths,
    save_reading_measures,
    save_session_metadata,
)
from preprocessing.io.load import (
    load_trial_level_raw_data,
    load_trial_level_events_data,
    load_reading_measures,
)
from preprocessing.config import settings


@pytest.fixture
def dummy_gaze():
    df = pl.DataFrame(
        {
            "time": [0.0, 1.0, 2.0],
            "pixel_x": [100.0, 101.0, 102.0],
            "pixel_y": [200.0, 201.0, 202.0],
            "pupil": [10.0, 11.0, 12.0],
            "trial": ["trial_1", "trial_1", "trial_1"],
            "stimulus": ["Enc_WikiMoon_1", "Enc_WikiMoon_1", "Enc_WikiMoon_1"],
            "page": ["page_1", "page_1", "page_1"],
        }
    )
    gaze = pm.Gaze(
        df,
        trial_columns=["trial", "stimulus", "page"],
        pixel_columns=["pixel_x", "pixel_y"],
    )
    gaze.events = pm.Events(
        pl.DataFrame(
            {
                "name": ["fixation", "saccade"],
                "start": [0, 1],
                "end": [1, 2],
                "trial": ["trial_1", "trial_1"],
                "stimulus": ["Enc_WikiMoon_1", "Enc_WikiMoon_1"],
                "page": ["page_1", "page_1"],
                "char_idx": [1, 1],
                "char": ["a", "b"],
                "onset": [0, 1],
                "duration": [1, 1],
                "location_x": [100.0, 101.0],
                "location_y": [200.0, 201.0],
                "top_left_x": [0.0, 0.0],
                "top_left_y": [0.0, 0.0],
                "width": [10.0, 10.0],
                "height": [10.0, 10.0],
                "char_idx_in_line": [1, 1],
                "line_idx": [1, 1],
                "word_idx": [1, 1],
                "word_idx_in_line": [1, 1],
                "word": ["a", "b"],
            }
        )
    )
    gaze.validations = pl.DataFrame({"v": [1]})
    gaze.calibrations = pl.DataFrame({"c": [1]})
    gaze._metadata = {"datetime": "2023-01-01 12:00:00", "some": "metadata"}
    gaze.experiment = pm.Experiment(30, 40, 50, 60, 100, 100)
    return gaze


def test_save_load_raw_data_structure(tmp_path, dummy_gaze):
    session = "test_session"
    save_raw_data(tmp_path, session, dummy_gaze)
    expected_path = tmp_path / settings.RAW_DATA_FOLDER / session
    assert expected_path.exists()
    assert (expected_path / f"{session}_trial_1_Enc_WikiMoon_1_raw_data.csv").exists()

    loaded_gaze = load_trial_level_raw_data(
        tmp_path, session, trial_columns=["trial", "stimulus", "page"]
    )
    assert len(loaded_gaze.samples) == 3


def test_save_load_fixations_structure(tmp_path, dummy_gaze):
    session = "test_session"
    save_events_data(
        "fixation",
        tmp_path,
        session,
        "trial",
        ["stimulus"],
        ["name", "start", "end", "trial", "stimulus", "page"],
        dummy_gaze,
    )
    expected_path = tmp_path / settings.FIXATIONS_FOLDER / session
    assert expected_path.exists()
    assert (expected_path / f"{session}_Enc_WikiMoon_1_fixation.csv").exists()

    loaded_gaze = load_trial_level_events_data(
        dummy_gaze, tmp_path, session, "fixation"
    )
    assert len(loaded_gaze.events.frame.filter(pl.col("name") == "fixation")) >= 1


def test_save_load_saccades_structure(tmp_path, dummy_gaze):
    session = "test_session"
    save_events_data(
        "saccade",
        tmp_path,
        session,
        "trial",
        ["stimulus"],
        ["name", "start", "end", "trial", "stimulus", "page"],
        dummy_gaze,
    )
    expected_path = tmp_path / settings.SACCADES_FOLDER / session
    assert expected_path.exists()
    assert (expected_path / f"{session}_Enc_WikiMoon_1_saccade.csv").exists()

    loaded_gaze = load_trial_level_events_data(dummy_gaze, tmp_path, session, "saccade")
    assert len(loaded_gaze.events.frame.filter(pl.col("name") == "saccade")) >= 1


def test_save_scanpaths_structure(tmp_path, dummy_gaze):
    session = "test_session"
    save_scanpaths(tmp_path, session, dummy_gaze)
    expected_path = tmp_path / settings.SCANPATHS_FOLDER / session
    assert expected_path.exists()
    assert (expected_path / f"{session}_trial_1_Enc_WikiMoon_1_scanpath.csv").exists()


def test_save_load_reading_measures_structure(tmp_path):
    session = "test_session"
    df_rm = pl.DataFrame(
        {"trial": ["trial_1"], "stimulus": ["Enc_WikiMoon_1"], "val": [1.0]}
    )
    save_reading_measures(tmp_path, session, df_rm)
    expected_path = tmp_path / settings.READING_MEASURES_FOLDER / session
    assert expected_path.exists()
    assert (
        expected_path / f"{session}_trial_1_Enc_WikiMoon_1_reading_measures.csv"
    ).exists()

    loaded_rm = load_reading_measures(tmp_path, session)
    assert len(loaded_rm) == 1


def test_save_load_metadata_structure(tmp_path, dummy_gaze):
    session = "test_session"
    # First save raw data because load_trial_level_raw_data expects it
    save_raw_data(tmp_path, session, dummy_gaze)
    save_session_metadata(tmp_path, session, dummy_gaze)
    expected_path = tmp_path / settings.METADATA_FOLDER / session
    assert expected_path.exists()
    assert (expected_path / "gaze_metadata.json").exists()
    assert (expected_path / "calibrations.feather").exists()
    assert (expected_path / "validations.feather").exists()
    assert (expected_path / "calibrations.tsv").exists()
    assert (expected_path / "validations.tsv").exists()

    # Ensure experiment.yaml exists (usually saved by gaze.save)
    if not (expected_path / "experiment.yaml").exists():
        with open(expected_path / "experiment.yaml", "w") as f:
            f.write("sampling_rate: 100")

    loaded_gaze = load_trial_level_raw_data(
        tmp_path,
        session,
        trial_columns=["trial", "stimulus", "page"],
        load_metadata=True,
    )
    assert loaded_gaze._metadata["some"] == "metadata"
    assert len(loaded_gaze.calibrations) > 0
    assert len(loaded_gaze.validations) > 0


def test_load_reading_measures_with_actual_filenames(tmp_path):
    # Setup: Create dummy reading measures files with the reported naming convention
    session = "017_DA_DK_1_ET1"
    reading_measures_dir = tmp_path / settings.READING_MEASURES_FOLDER / session
    reading_measures_dir.mkdir(parents=True)

    # Files as reported in the issue
    filenames = [
        f"{session}_PRACTICE_trial_1_Enc_WikiMoon_reading_measures.csv",
        f"{session}_trial_1_Lit_MagicMountain_reading_measures.csv",
        f"{session}_trial_5_PopSci_MultiplEYE_reading_measures.csv",
    ]

    for filename in filenames:
        df = pl.DataFrame({"measure": [1.0], "trial": ["dummy"], "stimulus": ["dummy"]})
        df.write_csv(reading_measures_dir / filename)

    # Test loading
    df_loaded = load_reading_measures(tmp_path, session)

    assert len(df_loaded) == 3
    assert set(df_loaded["trial"].unique()) == {
        "PRACTICE_trial_1",
        "trial_1",
        "trial_5",
    }
    assert set(df_loaded["stimulus"].unique()) == {
        "Enc_WikiMoon",
        "Lit_MagicMountain",
        "PopSci_MultiplEYE",
    }
