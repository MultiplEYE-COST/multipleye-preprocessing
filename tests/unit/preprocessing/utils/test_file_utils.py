"""Tests for the file_utils submodule."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from preprocessing.utils.file_utils import _copytree, _to_win_long_path


@pytest.fixture
def source_dir(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    (src / "file.txt").write_text("imasourcedirfile")
    return src


@pytest.fixture
def source_dest(source_dir, tmp_path):
    return source_dir, tmp_path / "dest"


class TestToWinLongPath:
    @pytest.mark.parametrize(
        "path_str",
        [
            "/home/user/file.txt",
            "/",
            "/home/user/my documents/file.txt",
        ],
    )
    @patch("os.name", "posix")
    def test_unix_returns_absolute_path_without_prefix(self, path_str):
        result = _to_win_long_path(Path(path_str))
        assert result == os.path.abspath(path_str)
        assert not result.startswith("\\\\?\\")

    @pytest.mark.parametrize(
        "path_str",
        [
            "relative/path",
            "another/./docs/../file.txt",
        ],
    )
    @patch("os.name", "posix")
    def test_unix_resolves_relative_to_absolute(self, path_str):
        result = _to_win_long_path(Path(path_str))
        assert result == os.path.abspath(path_str)
        assert os.path.isabs(result)

    @pytest.mark.parametrize(
        "path_str, expected_suffix",
        [
            ("C:\\Users\\test\\file.txt", "C:\\Users\\test\\file.txt"),
            ("C:\\Program Files\\app\\file.txt", "Program Files"),
        ],
    )
    @patch("os.name", "nt")
    def test_windows_prefixes_absolute_path(self, path_str, expected_suffix):
        result = _to_win_long_path(Path(path_str))
        assert result.startswith("\\\\?\\")
        assert expected_suffix in result

    @patch("os.name", "nt")
    def test_windows_does_not_double_prefix(self):
        with patch("os.path.abspath", return_value="\\\\?\\C:\\Users\\test\\file.txt"):
            result = _to_win_long_path(Path("C:\\Users\\test\\file.txt"))
            assert result == "\\\\?\\C:\\Users\\test\\file.txt"

    @patch("os.name", "nt")
    def test_windows_resolves_relative_to_absolute_then_prefixes(self):
        result = _to_win_long_path(Path("relative\\path"))
        assert result.startswith("\\\\?\\")
        assert os.path.isabs(result[4:])


class TestCopytree:
    def test_copies_directory_tree(self, source_dest):
        src, dst = source_dest
        _copytree(src, dst)
        assert dst.exists()
        assert (dst / "file.txt").read_text() == "imasourcedirfile"

    @pytest.mark.parametrize("hidden_name", [".hidden", "._apple_double"])
    def test_skips_hidden_files(self, source_dir, tmp_path, hidden_name):
        src = source_dir
        dst = tmp_path / "dest"
        (src / hidden_name).write_text("hidden")

        _copytree(src, dst)

        assert (dst / "file.txt").exists()
        assert not (dst / hidden_name).exists()

    def test_skips_hidden_directories(self, source_dir, tmp_path):
        src = source_dir
        dst = tmp_path / "dest"
        (src / ".git").mkdir()
        (src / ".git" / "config").write_text("config")

        _copytree(src, dst)

        assert (dst / "file.txt").exists()
        assert not (dst / ".git").exists()

    def test_passes_dirs_exist_ok(self, source_dest):
        src, dst = source_dest
        dst.mkdir()

        _copytree(src, dst, dirs_exist_ok=True)

        assert (dst / "file.txt").exists()

    def test_raises_on_existing_dest_without_dirs_exist_ok(self, source_dest):
        src, dst = source_dest
        dst.mkdir()

        with pytest.raises(FileExistsError):
            _copytree(src, dst)

    @pytest.mark.parametrize(
        "is_windows, expect_wrapped",
        [
            (False, False),
            (True, True),
        ],
    )
    def test_path_wrapping(self, source_dir, tmp_path, is_windows, expect_wrapped):
        src = source_dir
        dst = tmp_path / "dest"

        with (
            patch("os.name", "nt" if is_windows else "posix"),
            patch("preprocessing.utils.file_utils.shutil.copytree") as mock_copytree,
        ):
            _copytree(src, dst, dirs_exist_ok=True)

        call_args, call_kwargs = mock_copytree.call_args
        src_arg, dst_arg = call_args[0], call_args[1]
        assert call_kwargs["dirs_exist_ok"] is True

        if expect_wrapped:
            assert isinstance(src_arg, str)
            assert isinstance(dst_arg, str)
            assert src_arg.startswith("\\\\?\\")
            assert dst_arg.startswith("\\\\?\\")
        else:
            assert isinstance(src_arg, Path)
            assert isinstance(dst_arg, Path)
