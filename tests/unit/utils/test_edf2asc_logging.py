from unittest.mock import MagicMock, patch

from preprocessing.utils.logging import get_edf2asc_version


def test_get_edf2asc_version_success():
    """Test get_edf2asc_version when edf2asc is available and returns version info."""
    mock_output = "EDF2ASC version 4.2.1197.0 MacOS X standalone Sep 27 2024\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
        version = get_edf2asc_version()
        assert version == "EDF2ASC version 4.2.1197.0 MacOS X standalone Sep 27 2024"
        mock_run.assert_called_once_with(
            ["edf2asc", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )


def test_get_edf2asc_version_not_found():
    """Test get_edf2asc_version when edf2asc is not found (CI scenario)."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError
        version = get_edf2asc_version()
        assert version == "unknown"


def test_get_edf2asc_version_error_exit_code():
    """Test get_edf2asc_version when edf2asc returns a non-zero exit code (like on MacOS)."""
    # The current implementation uses subprocess.run(..., check=False).stdout
    # So it doesn't care about the exit code if stdout is captured.
    mock_output = "EDF2ASC version 4.2.1197.0 MacOS X standalone Sep 27 2024\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=255)
        version = get_edf2asc_version()
        assert version == "EDF2ASC version 4.2.1197.0 MacOS X standalone Sep 27 2024"


def test_get_edf2asc_version_unexpected_output():
    """Test get_edf2asc_version when the output doesn't contain 'EDF2ASC version'."""
    mock_output = "Some other tool v1.0\nLine 2: data\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
        version = get_edf2asc_version()
        # Fallback logic: return output.splitlines()[1].strip() if len > 1
        assert version == "Line 2: data"


def test_get_edf2asc_version_empty_output():
    """Test get_edf2asc_version when the output is empty."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        version = get_edf2asc_version()
        assert version == "unknown"
