"""Tests for the AOI fix helpers (space remap and word-label repair)."""

import polars as pl
import pytest

from preprocessing.mapping.aoi import add_custom_uoa
from preprocessing.utils.fix_multipleye_aoi_files import (
    fix_aoi_file,
    remap_space_to_following_word,
    repair_word_labels,
)

PREFIX_COLUMNS = [
    "page",
    "line_idx",
    "word_idx",
    "word_idx_in_line",
    "char_idx_in_line",
    "char",
    "char_idx",
    "top_left_x",
    "top_left_y",
    "width",
    "height",
    "word",
]

PREFIX_SCHEMA = {
    "page": pl.String,
    "line_idx": pl.Int64,
    "word_idx": pl.Int64,
    "word_idx_in_line": pl.Int64,
    "char_idx_in_line": pl.Int64,
    "char": pl.String,
    "char_idx": pl.Int64,
    "top_left_x": pl.Int64,
    "top_left_y": pl.Int64,
    "width": pl.Int64,
    "height": pl.Int64,
    "word": pl.String,
}

POSTFIX_COLUMNS = [
    "page",
    "line_idx",
    "unit_of_analysis_idx",
    "unit_of_analysis_idx_in_line",
    "char_idx_in_line",
    "char",
    "char_idx",
    "top_left_x",
    "top_left_y",
    "width",
    "height",
    "unit_of_analysis",
]

POSTFIX_SCHEMA = {
    "page": pl.String,
    "line_idx": pl.Int64,
    "unit_of_analysis_idx": pl.Int64,
    "unit_of_analysis_idx_in_line": pl.Int64,
    "char_idx_in_line": pl.Int64,
    "char": pl.String,
    "char_idx": pl.Int64,
    "top_left_x": pl.Int64,
    "top_left_y": pl.Int64,
    "width": pl.Int64,
    "height": pl.Int64,
    "unit_of_analysis": pl.String,
}


def _write(path, rows, postfix=False):
    if postfix:
        pl.DataFrame(rows, schema=POSTFIX_SCHEMA).write_csv(path)
    else:
        pl.DataFrame(rows, schema=PREFIX_SCHEMA).write_csv(path)


def _space_and_words():
    return [
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 0,
            "char": "c",
            "char_idx": 0,
            "top_left_x": 0,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "word": "cat",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 1,
            "char": "a",
            "char_idx": 1,
            "top_left_x": 20,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "word": "cat",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 2,
            "char": "t",
            "char_idx": 2,
            "top_left_x": 40,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "word": "cat",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 3,
            "char": " ",
            "char_idx": 3,
            "top_left_x": 60,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "word": None,
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 4,
            "char": "d",
            "char_idx": 4,
            "top_left_x": 80,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "word": "dog",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 5,
            "char": "o",
            "char_idx": 5,
            "top_left_x": 100,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "word": "dog",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 6,
            "char": "g",
            "char_idx": 6,
            "top_left_x": 120,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "word": "dog",
        },
    ]


def _read(path):
    return pl.read_csv(path)


def test_fix_aoi_file_remaps_space_and_repairs_labels(tmp_path):
    path = tmp_path / "aoi.csv"
    _write(path, _space_and_words(), postfix=False)

    fix_aoi_file(path)

    df = _read(path)
    space = df.filter(pl.col("char") == " ")
    assert space["unit_of_analysis_idx"].to_list() == [1]
    assert space["unit_of_analysis_idx_in_line"].to_list() == [1]
    # the repaired label is propagated from the following word group
    assert space["unit_of_analysis"].to_list() == ["dog"]
    # rows and unit_of_analysis_idx for the real words are untouched
    assert df.height == 7
    assert df.filter(pl.col("char") == "c")["unit_of_analysis_idx"].to_list() == [0]


def test_fix_aoi_file_is_idempotent(tmp_path):
    path = tmp_path / "aoi.csv"
    _write(path, _space_and_words(), postfix=False)

    fix_aoi_file(path)
    first = _read(path)
    fix_aoi_file(path)
    second = _read(path)

    assert first.equals(second)


def test_fix_aoi_file_does_not_touch_last_row_space(tmp_path):
    rows = _space_and_words()
    # last row is a trailing space with no following row
    rows.append(
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 7,
            "char": " ",
            "char_idx": 7,
            "top_left_x": 0,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "word": None,
        }
    )
    path = tmp_path / "aoi.csv"
    _write(path, rows, postfix=False)

    fix_aoi_file(path)

    df = _read(path)
    last = df.filter(pl.col("char_idx_in_line") == 7)
    assert last["unit_of_analysis_idx"].to_list() == [1]  # unchanged, no next row


def test_repair_word_labels_fills_within_group_not_across(tmp_path):
    rows = [
        {
            "page": "page_1",
            "line_idx": 0,
            "unit_of_analysis_idx": 0,
            "unit_of_analysis_idx_in_line": 0,
            "char_idx_in_line": 0,
            "char": "a",
            "char_idx": 0,
            "top_left_x": 0,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "unit_of_analysis": "alpha",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "unit_of_analysis_idx": 0,
            "unit_of_analysis_idx_in_line": 0,
            "char_idx_in_line": 1,
            "char": " ",
            "char_idx": 1,
            "top_left_x": 20,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "unit_of_analysis": None,
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "unit_of_analysis_idx": 1,
            "unit_of_analysis_idx_in_line": 1,
            "char_idx_in_line": 2,
            "char": "b",
            "char_idx": 2,
            "top_left_x": 40,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "unit_of_analysis": "beta",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "unit_of_analysis_idx": 1,
            "unit_of_analysis_idx_in_line": 1,
            "char_idx_in_line": 3,
            "char": " ",
            "char_idx": 3,
            "top_left_x": 60,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "unit_of_analysis": None,
        },
    ]
    path = tmp_path / "aoi.csv"
    _write(path, rows, postfix=True)

    repair_word_labels(path)

    df = _read(path)
    labels = {
        row["unit_of_analysis_idx"]: row["unit_of_analysis"]
        for row in df.filter(pl.col("char") == " ").to_dicts()
    }
    assert labels == {0: "alpha", 1: "beta"}


def test_repair_word_labels_treats_whitespace_only_as_missing(tmp_path):
    rows = [
        {
            "page": "page_1",
            "line_idx": 0,
            "unit_of_analysis_idx": 0,
            "unit_of_analysis_idx_in_line": 0,
            "char_idx_in_line": 0,
            "char": "x",
            "char_idx": 0,
            "top_left_x": 0,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "unit_of_analysis": "gamma",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "unit_of_analysis_idx": 0,
            "unit_of_analysis_idx_in_line": 0,
            "char_idx_in_line": 1,
            "char": " ",
            "char_idx": 1,
            "top_left_x": 20,
            "top_left_y": 0,
            "width": 20,
            "height": 20,
            "unit_of_analysis": "   ",
        },
    ]
    path = tmp_path / "aoi.csv"
    _write(path, rows, postfix=True)

    repair_word_labels(path)

    df = _read(path)
    assert df.filter(pl.col("char") == " ")["unit_of_analysis"].to_list() == ["gamma"]


def test_remap_space_standalone(tmp_path):
    path = tmp_path / "aoi.csv"
    aoi_df = pl.DataFrame(_space_and_words()).rename(
        {
            "word": "unit_of_analysis",
            "word_idx": "unit_of_analysis_idx",
            "word_idx_in_line": "unit_of_analysis_idx_in_line",
        }
    )
    _write(path, aoi_df, postfix=True)

    remap_space_to_following_word(path)

    df = _read(path)
    space = df.filter(pl.col("char") == " ")
    assert space["unit_of_analysis_idx"].to_list() == [1]
    # remap alone does not fill the word label
    assert space["unit_of_analysis"].to_list() == [None]


def test_remap_preserves_row_order_and_corrects_column_order(tmp_path):
    path = tmp_path / "aoi.csv"
    _write(path, _space_and_words(), postfix=False)
    before = _read(path)

    fix_aoi_file(path)

    after = _read(path)
    correct_order = [
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

    assert after.columns == correct_order
    assert after.height == before.height
    assert after["char_idx_in_line"].to_list() == before["char_idx_in_line"].to_list()


def test_fix_aoi_file_missing_columns_raises(tmp_path):
    path = tmp_path / "aoi.csv"
    pl.DataFrame({"foo": [1]}).write_csv(path)
    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        fix_aoi_file(path)


def test_add_custom_uoa(tmp_path):
    uoa_path = tmp_path / "custom_units_of_analysis" / "test_aoi.csv"
    uoa_path.parent.mkdir()
    aoi_rows = _space_and_words()
    aoi_df = pl.DataFrame(aoi_rows)
    uoa_df = aoi_df.drop(
        [
            "word",
            "word_idx_in_line",
            "word_idx",
            "top_left_x",
            "top_left_y",
            "width",
            "height",
        ]
    )
    uoa_column = pl.Series(
        "unit_of_analysis", ["c", "at ", "at ", "at ", "d", "og", "og"]
    )
    uoa_idx_column = pl.Series("unit_of_analysis_idx", range(7))
    uoa_df = uoa_df.with_columns([uoa_column, uoa_idx_column])
    uoa_df.write_csv(uoa_path)

    aoi_path = tmp_path / "test_aoi.csv"
    aoi_df = aoi_df.with_columns(
        pl.lit(None).alias("secondary_unit_of_analysis"),
        pl.lit(None).alias("secondary_unit_of_analysis_idx"),
        pl.lit(None).alias("secondary_unit_of_analysis_idx_in_line"),
    )
    aoi_df = aoi_df.rename(
        {
            "word": "unit_of_analysis",
            "word_idx": "unit_of_analysis_idx",
            "word_idx_in_line": "unit_of_analysis_idx_in_line",
        }
    )
    aoi_df.write_csv(aoi_path)
    add_custom_uoa(
        tmp_path,
        aoi_path,
        uoa_column_name="unit_of_analysis",
        uoa_idx_colum_name="unit_of_analysis_idx",
    )

    new_aoi_df = pl.read_csv(aoi_path)

    assert list(new_aoi_df["char"]) == list(aoi_df["char"])
    assert list(new_aoi_df["secondary_unit_of_analysis"]) == list(
        aoi_df["unit_of_analysis"]
    )
    assert list(new_aoi_df["unit_of_analysis"]) == list(uoa_df["unit_of_analysis"])
