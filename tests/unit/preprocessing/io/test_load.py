import polars as pl
import pytest

from preprocessing.config import settings
from preprocessing.data_collection.stimulus import LabConfig
from preprocessing.io.load import load_gaze_data
from preprocessing.models.sid import Sid


@pytest.fixture
def synthetic_asc(tmp_path):
    path = tmp_path / "synthetic.asc"
    content = """** CONVERTED FROM synthetic.edf
MSG 1000 start_recording_trial_1_stimulus_Lit_MagicMountain_6_page_1
MSG 1500 start_recording_trial_1_stimulus_Lit_MagicMountain_6_question_6111
MSG 2000 trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_distractor_a_key
MSG 2500 trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_target_key
MSG 3000 trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_final_confirmation
MSG 3001 question_screen_image_offset
MSG 3001 trial_1_stimulus_Lit_MagicMountain_6_question_6111_final_answer_given_is_target_key
MSG 3001 trial_1_stimulus_Lit_MagicMountain_6_question_6111_answer_given_is_correct:True
MSG 3005 stop_recording_trial_1_stimulus_Lit_MagicMountain_6_question_6111
1000 500.0 500.0 100.0 .
1500 500.0 500.0 100.0 .
2000 500.0 500.0 100.0 .
3000 500.0 500.0 100.0 .
"""
    path.write_text(content)
    return path


@pytest.fixture
def lab_config():
    return LabConfig(
        screen_resolution=(1920, 1080),
        screen_size_cm=(50.0, 30.0),
        screen_distance_cm=60.0,
        image_resolution=(1920, 1080),
        image_size_cm=(50.0, 30.0),
        name_eye_tracker="EyeLink 1000 Plus",
        sampling_frequency_hz=1000.0,
    )


@pytest.mark.filterwarnings("ignore:No metadata found")
@pytest.mark.filterwarnings("ignore:No samples configuration found")
@pytest.mark.filterwarnings("ignore:No recording configuration found")
@pytest.mark.filterwarnings("ignore:No screen resolution found")
@pytest.mark.filterwarnings("ignore:No sampling rate found")
@pytest.mark.filterwarnings("ignore:No tracked eye information found")
@pytest.mark.filterwarnings("ignore:No mount configuration found")
@pytest.mark.filterwarnings("ignore:No eye tracker vendor found")
@pytest.mark.filterwarnings("ignore:No eye tracker model found")
@pytest.mark.filterwarnings("ignore:No eye tracker software version found")
def test_load_gaze_data_with_messages(synthetic_asc, lab_config):
    # Load with messages=True
    gaze = load_gaze_data(
        asc_file=synthetic_asc,
        lab_config=lab_config,
        sid=Sid("001_SV_CH_Zurich_S1_ET1"),
        messages=True,
    )

    # Assertions
    assert gaze.messages is not None
    assert isinstance(gaze.messages, pl.DataFrame)
    assert "time" in gaze.messages.columns
    assert "content" in gaze.messages.columns

    # Assert at least some answer-related messages are present
    answer_msgs = gaze.messages.filter(
        pl.col("content").str.contains(
            "question_.*_preliminary|question_.*_final|answer_given_is_correct"
        )
    )
    assert len(answer_msgs) > 0


@pytest.mark.filterwarnings("ignore:No metadata found")
@pytest.mark.filterwarnings("ignore:No samples configuration found")
@pytest.mark.filterwarnings("ignore:No recording configuration found")
@pytest.mark.filterwarnings("ignore:No screen resolution found")
@pytest.mark.filterwarnings("ignore:No sampling rate found")
@pytest.mark.filterwarnings("ignore:No tracked eye information found")
@pytest.mark.filterwarnings("ignore:No mount configuration found")
@pytest.mark.filterwarnings("ignore:No eye tracker vendor found")
@pytest.mark.filterwarnings("ignore:No eye tracker model found")
@pytest.mark.filterwarnings("ignore:No eye tracker software version found")
def test_load_gaze_data_without_messages(synthetic_asc, lab_config):
    # Load with messages=False (default)
    gaze = load_gaze_data(
        asc_file=synthetic_asc,
        lab_config=lab_config,
        sid=Sid("001_SV_CH_Zurich_S1_ET1"),
    )

    # Assertions
    assert gaze.messages is None


@pytest.mark.filterwarnings("ignore:No metadata found")
@pytest.mark.filterwarnings("ignore:No samples configuration found")
@pytest.mark.filterwarnings("ignore:No recording configuration found")
@pytest.mark.filterwarnings("ignore:No screen resolution found")
@pytest.mark.filterwarnings("ignore:No sampling rate found")
@pytest.mark.filterwarnings("ignore:No tracked eye information found")
@pytest.mark.filterwarnings("ignore:No mount configuration found")
@pytest.mark.filterwarnings("ignore:No eye tracker vendor found")
@pytest.mark.filterwarnings("ignore:No eye tracker model found")
@pytest.mark.filterwarnings("ignore:No eye tracker software version found")
def test_load_gaze_data_messages_none(synthetic_asc, lab_config):
    # Load with messages=None
    gaze = load_gaze_data(
        asc_file=synthetic_asc,
        lab_config=lab_config,
        sid=Sid("001_SV_CH_Zurich_S1_ET1"),
        messages=None,
    )

    # Assertions
    assert gaze.messages is None


@pytest.mark.filterwarnings("ignore:No metadata found")
@pytest.mark.filterwarnings("ignore:No samples configuration found")
@pytest.mark.filterwarnings("ignore:No recording configuration found")
@pytest.mark.filterwarnings("ignore:No screen resolution found")
@pytest.mark.filterwarnings("ignore:No sampling rate found")
@pytest.mark.filterwarnings("ignore:No tracked eye information found")
@pytest.mark.filterwarnings("ignore:No mount configuration found")
@pytest.mark.filterwarnings("ignore:No eye tracker vendor found")
@pytest.mark.filterwarnings("ignore:No eye tracker model found")
@pytest.mark.filterwarnings("ignore:No eye tracker software version found")
def test_load_gaze_data_with_patterns(synthetic_asc, lab_config):
    # Load with specific patterns
    gaze = load_gaze_data(
        asc_file=synthetic_asc,
        lab_config=lab_config,
        sid=Sid("001_SV_CH_Zurich_S1_ET1"),
        messages=settings.EXPERIMENT_MSG_PATTERNS,
    )

    # Assertions
    assert gaze.messages is not None
    # EXPERIMENT_MSG_PATTERNS now includes start_recording_.* so page_1 messages
    # are expected along with question messages
    assert gaze.messages["content"].str.contains("page_1").any()
    # Question start should be here
    assert gaze.messages["content"].str.contains("question_6111").any()


def test_blink_loss_ratio_is_scalar_with_trial_columns():
    import pymovements as pm
    from pymovements import transforms

    samples = pl.DataFrame(
        {
            "time": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            "x": [0.0] * 6,
            "y": [0.0] * 6,
            "trial": ["trial_1"] * 6,
            "stimulus": ["stim"] * 6,
            "page": ["page_1"] * 6,
        }
    )
    events = pm.Events(
        pl.DataFrame(
            {
                "name": ["blink_eyelink", "blink_eyelink"],
                "onset": [1.0, 4.0],
                "offset": [2.0, 5.0],
                "trial": ["trial_1", "trial_1"],
                "stimulus": ["stim", "stim"],
                "page": ["page_1", "page_1"],
            }
        ),
        trial_columns=["trial", "stimulus", "page"],
    )
    gaze = pm.Gaze(
        samples,
        trial_columns=["trial", "stimulus", "page"],
        pixel_columns=["x", "y"],
    )
    gaze.events = events

    sr = 1000.0
    expr = transforms.events2timeratio(
        events=gaze.events.frame,
        samples=gaze.samples,
        name="blink_eyelink",
        trial_columns=None,
        sampling_rate=sr,
    )
    result = gaze.samples.select(expr)

    assert result.height == 1
