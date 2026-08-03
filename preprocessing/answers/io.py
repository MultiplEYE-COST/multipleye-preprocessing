from __future__ import annotations

from pathlib import Path

import polars as pl


def write_answers(df: pl.DataFrame, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    list_cols = [c for c in df.columns if isinstance(df.schema[c], pl.List)]
    if list_cols:
        df = df.with_columns(
            pl.col(c).list.eval(pl.element().cast(pl.Utf8)).list.join(";").alias(c)
            for c in list_cols
        )

    df.write_csv(out_path)
    return out_path


def load_answers(path: Path) -> pl.DataFrame:
    return pl.read_csv(path)
