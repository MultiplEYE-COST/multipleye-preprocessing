from pathlib import Path

import polars as pl

from ..utils.logging import get_logger

logger = get_logger()


def _remap_space(df: pl.DataFrame) -> pl.DataFrame:
    """Remap inter-word spaces to the following word.

    By default, white space is mapped to the previous word. This is bad practice
    as the space is typically read as part of the next word in reading direction.
    Rows whose ``word`` is null and whose ``char`` is a space take the
    ``unit_of_analysis_idx`` and ``_idx_in_line`` of the following row.

    The operation is idempotent and vectorised (a shift of the two index
    columns), so it can be applied without a per-row loop.
    """
    is_space = pl.col("unit_of_analysis").is_null() & (pl.col("char") == " ")
    next_word_idx = pl.col("unit_of_analysis_idx").shift(-1)
    next_word_idx_in_line = pl.col("unit_of_analysis_idx_in_line").shift(-1)
    has_next = next_word_idx.is_not_null()
    return df.with_columns(
        pl.when(is_space & has_next)
        .then(next_word_idx)
        .otherwise(pl.col("unit_of_analysis_idx"))
        .alias("unit_of_analysis_idx"),
        pl.when(is_space & has_next)
        .then(next_word_idx_in_line)
        .otherwise(pl.col("unit_of_analysis_idx_in_line"))
        .alias("unit_of_analysis_idx_in_line"),
    )


def _repair_word_labels(df: pl.DataFrame) -> pl.DataFrame:
    """Ensure consistent word string labels within each word index group.

    Normalizes the ``word`` column so that all characters belonging to the same
    (``page``, ``line_idx``, ``unit_of_analysis_idx``) group share an identical word label.
    Whitespace-only or empty ``word`` entries are treated as missing and are
    forward- and backward-filled within each group. The ``unit_of_analysis_idx`` column is
    not modified and no rows are added or removed.
    """
    group_cols = ["page", "line_idx", "unit_of_analysis_idx"]
    return (
        df.sort(group_cols + ["char_idx_in_line"])
        .with_columns(
            pl.when(pl.col("unit_of_analysis").is_null() | (pl.col("unit_of_analysis").str.strip_chars() == ""))
            .then(None)
            .otherwise(pl.col("unit_of_analysis"))
            .alias("_unit_of_analysis_tmp")
        )
        .with_columns(
            pl.col("_unit_of_analysis_tmp")
            .forward_fill()
            .backward_fill()
            .over(
                group_cols
            )  # ensures that the label is only propagated within the same word group
            .alias("unit_of_analysis")
        )
        .drop("_unit_of_analysis_tmp")
    )


def fix_aoi_file(aoi_file_path: str | Path) -> None:
    """Apply all AOI fixes in a single read and write pass.

    Remaps inter-word spaces to the following word and repairs the word labels.
    Renames all word columns to unit of analysis for consistent naming conventions.
    The file is changed and then rewritten to the same path.

    Parameters
    ----------
    aoi_file_path : Path | str
        Character-level AOI table.
    """
    df = pl.read_csv(aoi_file_path)
    df = df.rename(
            {
                "word_idx": "unit_of_analysis_idx",
                "word": "unit_of_analysis",
                "word_idx_in_line": "unit_of_analysis_idx_in_line",
            },
            strict=False
        )
    df = df.with_columns([
        pl.lit(None).alias("secondary_unit_of_analysis"),
        pl.lit(None).alias("secondary_unit_of_analysis_idx"),
        pl.lit(None).alias("secondary_unit_of_analysis_idx_in_line"),
        ])
    
    df = _repair_word_labels(_remap_space(df))

    #Ensure consistent column order to enable stacking
    col_order = [
        "char_idx",
        "char",
        "top_left_x",
        "top_left_y",
        "width",
        "height",
        "char_idx_in_line",
        "line_idx",
        "page",
        "unit_of_analysis_idx",
        "unit_of_analysis_idx_in_line",
        "unit_of_analysis",
        "secondary_unit_of_analysis_idx",
        "secondary_unit_of_analysis_idx_in_line",
        "secondary_unit_of_analysis",
    ]

    if "questions" in aoi_file_path.name:
        col_order.append("question_image_version")

    df = df[col_order]

    df.write_csv(aoi_file_path)
    logger.debug(f"Applied AOI fixes to: {aoi_file_path}")


def remap_space_to_following_word(aoi_file_path: str | Path) -> None:
    """Remap inter-word spaces to the following word.

    The file is changed and then rewritten to the same path.

    Parameters
    ----------
    aoi_file_path : Path | str
        Character-level AOI table.
    """
    df = pl.read_csv(aoi_file_path)
    df = _remap_space(df)
    df.write_csv(aoi_file_path)
    logger.debug(f"Remapped space to following word for AOI file: {aoi_file_path}")


def repair_word_labels(aoi_file_path: str | Path) -> None:
    """Ensure consistent word string labels within each word index group.

    The file is changed and then rewritten to the same path.

    Parameters
    ----------
    aoi_file_path : Path | str
        Character-level AOI table containing at least ``unit_of_analysis_idx``, ``unit_of_analysis``,
        ``char_idx_in_line``, and ``page``, ``line_idx``.
    """
    df = pl.read_csv(aoi_file_path)
    df = _repair_word_labels(df)
    df.write_csv(aoi_file_path)
    logger.debug(f"Filled missing word labels in AOI file: {aoi_file_path}")
