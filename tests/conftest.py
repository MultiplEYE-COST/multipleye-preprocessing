from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(name="make_text_file", scope="function")
def fixture_make_text_file(tmp_path: Path):
    """Create a text file in a temporary directory.

    Returns a factory that writes ``header + body`` to the given filename and returns the Path.
    """

    def _make_text_file(
        filename: str | Path,
        header: str = "",
        body: str = "\n",
        encoding: str = "utf-8",
    ) -> Path:
        filepath = tmp_path / Path(filename)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(header + body, encoding=encoding)
        return filepath

    return _make_text_file
