import polars as pl
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)
from preprocessing.data_collection.stimulus import Stimulus, StimulusPage


def _mock_page(number: int) -> Mock:
    page = Mock(spec=StimulusPage)
    page.number = number
    return page


def _mock_stimulus(
    name: str, num_pages: int, stimulus_type: str = "experiment"
) -> Mock:
    stim = Mock(spec=Stimulus)
    stim.name = name
    stim.type = stimulus_type
    stim.pages = [_mock_page(i) for i in range(1, num_pages + 1)]
    return stim


def _mock_dc(
    output_dir: Path | None = None,
    stimuli: list[Mock] | None = None,
    stimuli_trial_mapping: dict[str, str] | None = None,
    messages: list[dict[str, str]] | None = None,
) -> MultipleyeDataCollection:
    dc = Mock(spec=MultipleyeDataCollection)
    dc.output_dir = output_dir or Path(tempfile.mkdtemp())
    dc.reports_folder = "reports"

    session = Mock()
    session.stimuli = stimuli or []
    session.stimuli_trial_mapping = stimuli_trial_mapping or {}
    session.messages = messages or []

    dc.sessions = {"test_session": session}
    dc.logger = Mock()

    dc._create_empty_rt_frame = lambda sid: (
        MultipleyeDataCollection._create_empty_rt_frame(dc, sid)
    )
    return dc


class TestCreateEmptyRtFrame:
    def test_creates_dataframe_with_correct_schema(self) -> None:
        stim = _mock_stimulus("Stim_A_1", num_pages=3)
        dc = _mock_dc(
            stimuli=[stim],
            stimuli_trial_mapping={"trial_1": "Stim_A_1"},
        )

        df = MultipleyeDataCollection._create_empty_rt_frame(dc, "test_session")

        assert isinstance(df, pl.DataFrame)
        expected_cols = {
            "stimulus_name",
            "start_ts",
            "stop_ts",
            "start_msg",
            "stop_msg",
            "duration_ms",
            "duration_str",
            "trial",
            "page",
            "status",
        }
        assert set(df.columns) == expected_cols

    def test_row_count_matches_total_pages(self) -> None:
        stim_a = _mock_stimulus("Stim_A_1", num_pages=2)
        stim_b = _mock_stimulus("Stim_B_2", num_pages=4)
        dc = _mock_dc(
            stimuli=[stim_a, stim_b],
            stimuli_trial_mapping={
                "trial_1": "Stim_A_1",
                "trial_2": "Stim_B_2",
            },
        )

        df = MultipleyeDataCollection._create_empty_rt_frame(dc, "test_session")

        assert len(df) == 6  # 2 + 4 pages

    def test_page_values_are_correct(self) -> None:
        stim = _mock_stimulus("Stim_X_1", num_pages=3)
        dc = _mock_dc(
            stimuli=[stim],
            stimuli_trial_mapping={"trial_1": "Stim_X_1"},
        )

        df = MultipleyeDataCollection._create_empty_rt_frame(dc, "test_session")

        pages = df["page"].to_list()
        assert pages == ["page_1", "page_2", "page_3"]

    def test_stimulus_name_filled_from_mapping(self) -> None:
        stim = _mock_stimulus("Stim_Q_5", num_pages=1)
        dc = _mock_dc(
            stimuli=[stim],
            stimuli_trial_mapping={"trial_3": "Stim_Q_5"},
        )

        df = MultipleyeDataCollection._create_empty_rt_frame(dc, "test_session")

        assert df["stimulus_name"].to_list() == ["Stim_Q_5"]

    def test_start_ts_stop_ts_are_null_initially(self) -> None:
        stim = _mock_stimulus("Stim_A_1", num_pages=2)
        dc = _mock_dc(
            stimuli=[stim],
            stimuli_trial_mapping={"trial_1": "Stim_A_1"},
        )

        df = MultipleyeDataCollection._create_empty_rt_frame(dc, "test_session")

        assert df["start_ts"].null_count() == 2
        assert df["stop_ts"].null_count() == 2

    def test_skips_stimuli_not_in_mapping(self) -> None:
        stim_a = _mock_stimulus("Stim_A_1", num_pages=2)
        stim_b = _mock_stimulus("Stim_B_2", num_pages=2)
        dc = _mock_dc(
            stimuli=[stim_a, stim_b],
            stimuli_trial_mapping={"trial_1": "Stim_A_1"},  # B not in mapping
        )

        df = MultipleyeDataCollection._create_empty_rt_frame(dc, "test_session")

        assert len(df) == 2  # only A's pages


class TestCategorizeAscMessages:
    def test_categorizes_start_recording_messages(self) -> None:
        stim = _mock_stimulus("PopSci_MultiplEYE_1", num_pages=2)
        dc = _mock_dc(
            stimuli=[stim],
            stimuli_trial_mapping={"trial_1": "PopSci_MultiplEYE_1"},
            messages=[
                {
                    "message": "start_recording_trial_1_stimulus__1_page_1",
                    "timestamp": "1000",
                },
                {
                    "message": "stop_recording_trial_1_stimulus_PopSci_MultiplEYE_1_1_page_1",
                    "timestamp": "5000",
                },
                {
                    "message": "start_recording_trial_1_stimulus__1_page_2",
                    "timestamp": "5200",
                },
                {
                    "message": "stop_recording_trial_1_stimulus_PopSci_MultiplEYE_1_1_page_2",
                    "timestamp": "9000",
                },
            ],
        )

        rt_df, breaks, screens, uncat, initial_ts = (
            MultipleyeDataCollection._categorize_asc_messages(dc, "test_session")
        )

        assert isinstance(rt_df, pl.DataFrame)
        assert initial_ts == "1000"

        row1 = rt_df.filter(pl.col("page") == "page_1")
        assert row1["start_ts"][0] == "1000"
        assert row1["stop_ts"][0] == "5000"

        row2 = rt_df.filter(pl.col("page") == "page_2")
        assert row2["start_ts"][0] == "5200"
        assert row2["stop_ts"][0] == "9000"

    def test_categorizes_break_messages(self) -> None:
        dc = _mock_dc(
            messages=[
                {"message": "optional_break", "timestamp": "2000"},
                {"message": "optional_break_end", "timestamp": "6000"},
                {"message": "obligatory_break", "timestamp": "8000"},
                {"message": "obligatory_break_end", "timestamp": "10000"},
            ],
        )

        _, breaks, _, _, _ = MultipleyeDataCollection._categorize_asc_messages(
            dc, "test_session"
        )

        assert len(breaks) == 4
        assert breaks[0]["message"] == "optional_break"

    def test_categorizes_other_screen_messages(self) -> None:
        dc = _mock_dc(
            messages=[
                {"message": "welcome_screen", "timestamp": "100"},
                {"message": "start_experiment", "timestamp": "200"},
            ],
        )

        _, _, screens, _, _ = MultipleyeDataCollection._categorize_asc_messages(
            dc, "test_session"
        )

        assert len(screens) == 2
        assert screens[0]["message"] == "welcome_screen"

    def test_uncategorized_messages_are_returned(self) -> None:
        dc = _mock_dc(
            messages=[
                {"message": "unknown_msg_format", "timestamp": "100"},
            ],
        )

        _, _, _, uncat, _ = MultipleyeDataCollection._categorize_asc_messages(
            dc, "test_session"
        )

        assert len(uncat) == 1
        assert uncat[0]["message"] == "unknown_msg_format"

    def test_handles_empty_messages(self) -> None:
        dc = _mock_dc(messages=[])

        rt_df, breaks, screens, uncat, initial_ts = (
            MultipleyeDataCollection._categorize_asc_messages(dc, "test_session")
        )

        assert len(rt_df) == 0  # no stimuli in mapping
        assert len(breaks) == 0
        assert len(screens) == 0
        assert len(uncat) == 0
        assert initial_ts == 0


class TestDocumentBreaks:
    def test_writes_break_tsv(self) -> None:
        breaks = [
            {"message": "optional_break", "timestamp": "1000"},
            {"message": "optional_break_end", "timestamp": "5000"},
        ]
        dc = _mock_dc()
        output_dir = dc.output_dir / "test_session" / dc.reports_folder
        os.makedirs(output_dir, exist_ok=True)

        MultipleyeDataCollection._document_breaks(dc, "test_session", breaks)

        csv_path = output_dir / "breaks_test_session.tsv"
        assert csv_path.exists()

        df = pl.read_csv(csv_path, separator="\t")
        assert str(df["start_ts"][0]) == "1000"
        assert str(df["stop_ts"][0]) == "5000"
        assert df["type"][0] == "optional"

    def test_handles_unclosed_break(self) -> None:
        breaks = [
            {"message": "obligatory_break", "timestamp": "1000"},
        ]
        dc = _mock_dc()
        output_dir = dc.output_dir / "test_session" / dc.reports_folder
        os.makedirs(output_dir, exist_ok=True)

        MultipleyeDataCollection._document_breaks(dc, "test_session", breaks)

        csv_path = output_dir / "breaks_test_session.tsv"
        df = pl.read_csv(csv_path, separator="\t")
        assert str(df["start_ts"][0]) == "1000"
        assert df["stop_ts"][0] is None
        dc.logger.warning.assert_called_once()

    def test_handles_empty_breaks(self) -> None:
        dc = _mock_dc()
        output_dir = dc.output_dir / "test_session" / dc.reports_folder
        os.makedirs(output_dir, exist_ok=True)

        MultipleyeDataCollection._document_breaks(dc, "test_session", [])

        csv_path = output_dir / "breaks_test_session.tsv"
        assert csv_path.exists()
        df = pl.read_csv(csv_path, separator="\t")
        assert len(df) == 0
