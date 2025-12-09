from __future__ import annotations

from pathlib import Path

import polars as pl


def write_answers(df: pl.DataFrame, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_csv(out_path)
    return out_path


def load_answers(path: Path) -> pl.DataFrame:
    return pl.read_csv(path)
