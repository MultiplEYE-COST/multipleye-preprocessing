import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from preprocessing.plotting.plot import plot_gaze
from preprocessing.data_collection.stimulus import (
    Stimulus,
)
from preprocessing.config import settings


@pytest.fixture
def mock_stimulus():
    page = MagicMock()
    page.number = 1
    page.image_path = Path("stimulus.png")
    page.aoi_image_path = MagicMock(spec=Path)

    question = MagicMock()
    question.id = 1
    question.image_path = Path("question.png")
    question.aoi_image_path = MagicMock(spec=Path)

    stimulus = MagicMock(spec=Stimulus)
    stimulus.name = "test_stim"
    stimulus.id = 1
    stimulus.pages = [page]
    stimulus.questions = [question]
    stimulus.ratings = []
    return stimulus


@pytest.fixture
def mock_gaze():
    gaze = MagicMock()
    gaze.clone.return_value = gaze
    gaze.experiment.screen.width_px = 1920
    gaze.experiment.screen.width_cm = 50
    gaze.experiment.screen.height_px = 1080

    # Mock polars dataframes
    import polars as pl

    gaze.frame = pl.DataFrame(
        {
            "stimulus": ["test_stim_1"],
            "page": ["page_1"],
            "pixel_x": [100],
            "pixel_y": [100],
        }
    )
    gaze.events.frame = pl.DataFrame(
        {
            "stimulus": ["test_stim_1"],
            "page": ["page_1"],
            "name": ["fixation"],
            "duration": [100],
            "location_x": [100],
            "location_y": [100],
        }
    )
    return gaze


@patch("PIL.Image.open")
@patch("matplotlib.pyplot.subplots")
def test_plot_gaze_aoi_fallback(
    mock_subplots, mock_image_open, mock_gaze, mock_stimulus, tmp_path
):
    mock_ax = MagicMock()
    mock_fig = MagicMock()
    mock_subplots.return_value = (mock_fig, mock_ax)

    # Setup: AOI images do NOT exist
    # Use real Paths that are relative to settings.OUTPUT_DIR to avoid ValueError
    page_aoi_path = settings.OUTPUT_DIR / "stimuli/aoi_images/page1_aoi.png"
    question_aoi_path = settings.OUTPUT_DIR / "stimuli/aoi_images/question1_aoi.png"

    # Ensure they don't exist on disk (mocking exists for Path)
    with patch.object(Path, "exists", return_value=False):
        mock_stimulus.pages[0].aoi_image_path = page_aoi_path
        mock_stimulus.questions[0].aoi_image_path = question_aoi_path

        plot_gaze(mock_gaze, mock_stimulus, tmp_path, aoi_image=True)

    # Verify that PIL.Image.open was called with image_path, not aoi_image_path
    calls = [call[0][0] for call in mock_image_open.call_args_list]
    assert mock_stimulus.pages[0].image_path in calls
    assert mock_stimulus.pages[0].aoi_image_path not in calls
    assert mock_stimulus.questions[0].image_path in calls
    assert mock_stimulus.questions[0].aoi_image_path not in calls


@patch("PIL.Image.open")
@patch("matplotlib.pyplot.subplots")
def test_plot_gaze_aoi_no_fallback(
    mock_subplots, mock_image_open, mock_gaze, mock_stimulus, tmp_path
):
    mock_ax = MagicMock()
    mock_fig = MagicMock()
    mock_subplots.return_value = (mock_fig, mock_ax)

    # Setup: AOI images DO exist
    # Use real Paths that are relative to settings.OUTPUT_DIR to avoid ValueError
    page_aoi_path = settings.OUTPUT_DIR / "stimuli/aoi_images/page1_aoi.png"
    question_aoi_path = settings.OUTPUT_DIR / "stimuli/aoi_images/question1_aoi.png"

    # We must mock .exists() on these paths since they won't exist on disk
    with patch.object(Path, "exists", return_value=True):
        mock_stimulus.pages[0].aoi_image_path = page_aoi_path
        mock_stimulus.questions[0].aoi_image_path = question_aoi_path

        plot_gaze(mock_gaze, mock_stimulus, tmp_path, aoi_image=True)

    # Verify that PIL.Image.open was called with aoi_image_path
    calls = [call[0][0] for call in mock_image_open.call_args_list]
    assert mock_stimulus.pages[0].aoi_image_path in calls
    assert mock_stimulus.questions[0].aoi_image_path in calls
