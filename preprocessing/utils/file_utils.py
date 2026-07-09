"""File system utility functions for cross-platform path handling."""

import os
import shutil
from pathlib import Path


def _to_win_long_path(p: Path) -> str:
    abs_path = str(os.path.abspath(p))
    if os.name != "nt":
        return abs_path
    if not abs_path.startswith("\\\\?\\"):
        return "\\\\?\\" + abs_path
    return abs_path


def _copytree(src: Path, dst: Path, **kwargs) -> None:
    shutil.copytree(
        src if os.name != "nt" else _to_win_long_path(src),
        dst if os.name != "nt" else _to_win_long_path(dst),
        ignore=shutil.ignore_patterns(".*", "._*"),
        **kwargs,
    )


__all__ = [
    "_to_win_long_path",
    "_copytree",
]
