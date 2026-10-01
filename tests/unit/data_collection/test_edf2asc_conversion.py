from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from preprocessing.data_collection import MultipleyeDataCollection
from preprocessing.data_collection.session import Session


@pytest.fixture
def mock_session():
    session = MagicMock(spec=Session)
    session.session_file_path = Path("/fake/data/S001/S001.edf")
    return session


@pytest.fixture
def data_collection(mock_session):
    with patch("preprocessing.data_collection.multipleye_data_collection.get_logger"):
        dc = MultipleyeDataCollection.__new__(MultipleyeDataCollection)
        dc.sessions = {"S001": mock_session}
        dc.eye_tracker = "eyelink"
        dc.logger = MagicMock()
        return dc


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
            # If installed, it should proceed to conversion (which we'll mock)
            with patch(
                "preprocessing.data_collection.multipleye_data_collection.tqdm",
                return_value=[],
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
    data_collection, mock_session, force_reconvert, asc_exists, expected_subprocess_call
):
    session_id = "S001"
    output_dir = Path("/fake/output")
    asc_folder = Path("asc")

    expected_asc_path = output_dir / asc_folder / session_id / f"{session_id}.asc"

    def exists_side_effect(self_path):
        path_str = str(self_path)
        if path_str == str(expected_asc_path):
            return asc_exists
        return path_str.endswith(".asc") and not path_str.startswith("/fake/output")

    with patch(
        "preprocessing.data_collection.multipleye_data_collection.settings"
    ) as mock_settings:
        mock_settings.OUTPUT_DIR = output_dir
        mock_settings.ASC_FOLDER = asc_folder
        mock_settings.FORCE_RECONVERT_ASC = force_reconvert

        with (
            patch("shutil.which", return_value="/usr/bin/edf2asc"),
            patch.object(Path, "exists", autospec=True) as mock_exists,
            patch("subprocess.run") as mock_run,
            patch("shutil.copy2"),
            patch.object(Path, "mkdir"),
            patch(
                "preprocessing.data_collection.multipleye_data_collection.tqdm",
                side_effect=lambda x, **kwargs: x,
            ),
        ):
            mock_exists.side_effect = exists_side_effect

            data_collection.convert_edf_to_asc()

            if expected_subprocess_call:
                mock_run.assert_called()
                assert mock_run.call_args[0][0][0] == "edf2asc"
            else:
                mock_run.assert_not_called()


def test_convert_edf_to_asc_conversion_failure(data_collection, mock_session):
    """Test error handling when ASC file is not created after conversion."""
    output_dir = Path("/fake/output")
    asc_folder = Path("asc")

    with patch(
        "preprocessing.data_collection.multipleye_data_collection.settings"
    ) as mock_settings:
        mock_settings.OUTPUT_DIR = output_dir
        mock_settings.ASC_FOLDER = asc_folder
        mock_settings.FORCE_RECONVERT_ASC = False

        with (
            patch("shutil.which", return_value="/usr/bin/edf2asc"),
            patch.object(Path, "exists", return_value=False),
            patch("subprocess.run"),
            patch("shutil.copy2") as mock_copy,
            patch.object(Path, "mkdir"),
            patch(
                "preprocessing.data_collection.multipleye_data_collection.tqdm",
                side_effect=lambda x, **kwargs: x,
            ),
        ):
            data_collection.convert_edf_to_asc()

            data_collection.logger.error.assert_called_once_with(
                "Failed to convert EDF to ASC for S001"
            )
            mock_copy.assert_not_called()


def test_convert_edf_to_asc_postfix_identifier():
    """Test session identifiers with postfixes are preserved in ASC folder paths."""
    postfix_session_id = "001_EN_UK_1_ET1_start_after_trial_4"
    output_dir = Path("/fake/output")
    asc_folder = Path("asc")
    expected_asc_path = (
        output_dir / asc_folder / postfix_session_id / f"{postfix_session_id}.asc"
    )

    mock_ses = MagicMock(spec=Session)
    mock_ses.session_file_path = Path("/fake/data/001/001.edf")

    with patch("preprocessing.data_collection.multipleye_data_collection.get_logger"):
        dc = MultipleyeDataCollection.__new__(MultipleyeDataCollection)
        dc.sessions = {postfix_session_id: mock_ses}
        dc.eye_tracker = "eyelink"
        dc.logger = MagicMock()

    def exists_side_effect(self_path):
        path_str = str(self_path)
        if path_str == str(expected_asc_path):
            return False  # output asc missing, trigger conversion
        return path_str.endswith(".asc")

    with patch(
        "preprocessing.data_collection.multipleye_data_collection.settings"
    ) as mock_settings:
        mock_settings.OUTPUT_DIR = output_dir
        mock_settings.ASC_FOLDER = asc_folder
        mock_settings.FORCE_RECONVERT_ASC = False

        with (
            patch("shutil.which", return_value="/usr/bin/edf2asc"),
            patch.object(Path, "exists", autospec=True) as mock_exists,
            patch("subprocess.run"),
            patch("shutil.copy2"),
            patch.object(Path, "mkdir"),
            patch(
                "preprocessing.data_collection.multipleye_data_collection.tqdm",
                side_effect=lambda x, **kwargs: x,
            ),
        ):
            mock_exists.side_effect = exists_side_effect

            dc.convert_edf_to_asc()

            assert mock_ses.asc_path == expected_asc_path
