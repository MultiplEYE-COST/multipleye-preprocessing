"""Tests for EDF to ASC conversion (parallel, staging-dir based)."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from preprocessing.config import settings
from preprocessing.data_collection import MultipleyeDataCollection
from preprocessing.data_collection.session import Session


def _edf2asc_writes_produced(cmd, **kwargs):
    """Emulate `edf2asc -y -p <dir> <edf>` by writing into the -p directory."""
    staging_dir = Path(cmd[cmd.index("-p") + 1])
    edf = Path(cmd[-1])
    (staging_dir / f"{edf.stem}.asc").write_text("asc")
    return subprocess.CompletedProcess(cmd, 0)


def _edf2asc_does_nothing(cmd, **kwargs):
    return subprocess.CompletedProcess(cmd, 0)


@pytest.fixture
def mock_session(tmp_path):
    session = MagicMock(spec=Session)
    session.session_file_path = tmp_path / "data" / "S001" / "S001.edf"
    return session


@pytest.fixture
def data_collection(mock_session, tmp_path, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(settings, "ASC_FOLDER", Path("asc/"))
    monkeypatch.setattr(settings, "FORCE_RECONVERT_ASC", False)
    monkeypatch.setitem(settings.__dict__, "EDF2ASC_WORKERS", 2)

    with patch("preprocessing.data_collection.multipleye_data_collection.get_logger"):
        dc = MultipleyeDataCollection.__new__(MultipleyeDataCollection)
        dc.sessions = {"S001": mock_session}
        dc.skipped_sessions = {}
        dc.eye_tracker = "eyelink"
        dc.logger = MagicMock()
        return dc


@pytest.fixture(autouse=True)
def _quiet_tqdm(monkeypatch):
    monkeypatch.setattr(
        "preprocessing.data_collection.multipleye_data_collection.tqdm",
        lambda x, **kwargs: x,
    )


@pytest.mark.parametrize(
    "edf2asc_installed, expected_exception",
    [
        (True, None),
        (False, RuntimeError),
    ],
)
def test_convert_edf_to_asc_installation_check(
    data_collection, edf2asc_installed, expected_exception
):
    with patch(
        "shutil.which",
        return_value="/usr/local/bin/edf2asc" if edf2asc_installed else None,
    ):
        if expected_exception:
            with pytest.raises(expected_exception) as excinfo:
                data_collection.convert_edf_to_asc()
            assert "edf2asc" in str(excinfo.value)
        else:
            with patch(
                "preprocessing.data_collection.multipleye_data_collection.subprocess.run",
                side_effect=_edf2asc_writes_produced,
            ):
                data_collection.convert_edf_to_asc()


@pytest.mark.parametrize(
    "force_reconvert, asc_exists, expected_subprocess_call",
    [
        (False, False, True),  # ASC doesn't exist, should convert
        (False, True, False),  # ASC exists, no force, should skip
        (True, True, True),  # ASC exists, but force is True, should convert
    ],
)
def test_convert_edf_to_asc_conversion_logic(
    data_collection,
    mock_session,
    monkeypatch,
    force_reconvert,
    asc_exists,
    expected_subprocess_call,
):
    session_id = "S001"
    output_asc_path = (
        settings.OUTPUT_DIR / settings.ASC_FOLDER / session_id / f"{session_id}.asc"
    )
    monkeypatch.setattr(settings, "FORCE_RECONVERT_ASC", force_reconvert)
    if asc_exists:
        output_asc_path.parent.mkdir(parents=True, exist_ok=True)
        output_asc_path.write_text("existing")

    with (
        patch("shutil.which", return_value="/usr/bin/edf2asc"),
        patch(
            "preprocessing.data_collection.multipleye_data_collection.subprocess.run"
        ) as mock_run,
    ):
        mock_run.side_effect = _edf2asc_writes_produced
        data_collection.convert_edf_to_asc()

    if expected_subprocess_call:
        mock_run.assert_called()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "edf2asc"
        assert "-p" in cmd
    else:
        mock_run.assert_not_called()
        assert mock_session.asc_path == output_asc_path


def test_convert_edf_to_asc_conversion_failure(data_collection, mock_session):
    """Test error handling when no ASC file is produced."""
    output_asc_path = settings.OUTPUT_DIR / settings.ASC_FOLDER / "S001" / "S001.asc"

    with (
        patch("shutil.which", return_value="/usr/bin/edf2asc"),
        patch(
            "preprocessing.data_collection.multipleye_data_collection.subprocess.run",
            side_effect=_edf2asc_does_nothing,
        ),
    ):
        data_collection.convert_edf_to_asc()

    data_collection.logger.error.assert_called_once_with(
        "Failed to convert EDF to ASC for S001. Only processing comprehension answers."
    )
    assert not output_asc_path.exists()
    assert set(data_collection.skipped_sessions) == {"S001"}
    # No staging directories are left behind.
    assert list(settings.OUTPUT_DIR.glob("**/.edf2asc-*")) == []


def test_convert_edf_to_asc_postfix_identifier(tmp_path, monkeypatch):
    """Test session identifiers with postfixes are preserved in ASC folder paths."""
    postfix_session_id = "001_EN_UK_1_ET1_start_after_trial_4"
    monkeypatch.setitem(settings.__dict__, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(settings, "ASC_FOLDER", Path("asc/"))
    monkeypatch.setattr(settings, "FORCE_RECONVERT_ASC", False)
    monkeypatch.setitem(settings.__dict__, "EDF2ASC_WORKERS", 1)

    mock_ses = MagicMock(spec=Session)
    mock_ses.session_file_path = tmp_path / "data" / "001" / "001.edf"

    with patch("preprocessing.data_collection.multipleye_data_collection.get_logger"):
        dc = MultipleyeDataCollection.__new__(MultipleyeDataCollection)
        dc.sessions = {postfix_session_id: mock_ses}
        dc.skipped_sessions = {}
        dc.eye_tracker = "eyelink"
        dc.logger = MagicMock()

    expected_asc_path = (
        settings.OUTPUT_DIR
        / settings.ASC_FOLDER
        / postfix_session_id
        / f"{postfix_session_id}.asc"
    )

    with (
        patch("shutil.which", return_value="/usr/bin/edf2asc"),
        patch(
            "preprocessing.data_collection.multipleye_data_collection.subprocess.run",
            side_effect=_edf2asc_writes_produced,
        ),
    ):
        dc.convert_edf_to_asc()

    assert mock_ses.asc_path == expected_asc_path
    assert expected_asc_path.exists()
