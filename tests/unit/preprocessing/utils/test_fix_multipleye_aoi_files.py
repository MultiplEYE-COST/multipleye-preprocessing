"""Tests for the AOI fix helpers (space remap and word-label repair)."""

import polars as pl
import pytest

from preprocessing.utils.fix_multipleye_aoi_files import (
    fix_aoi_file,
    remap_space_to_following_word,
    repair_word_labels,
)

COLUMNS = [
    "page",
    "line_idx",
    "word_idx",
    "word_idx_in_line",
    "char_idx_in_line",
    "char",
    "word",
]

SCHEMA = {
    "page": pl.String,
    "line_idx": pl.Int64,
    "word_idx": pl.Int64,
    "word_idx_in_line": pl.Int64,
    "char_idx_in_line": pl.Int64,
    "char": pl.String,
    "word": pl.String,
}


def _write(path, rows):
    pl.DataFrame(rows, schema=SCHEMA).write_csv(path)


def _space_and_words():
    return [
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 0,
            "char": "c",
            "word": "cat",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 1,
            "char": "a",
            "word": "cat",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 2,
            "char": "t",
            "word": "cat",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 3,
            "char": " ",
            "word": None,
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 4,
            "char": "d",
            "word": "dog",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 5,
            "char": "o",
            "word": "dog",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 6,
            "char": "g",
            "word": "dog",
        },
    ]


def _read(path):
    return pl.read_csv(path)


def test_fix_aoi_file_remaps_space_and_repairs_labels(tmp_path):
    path = tmp_path / "aoi.csv"
    _write(path, _space_and_words())

    fix_aoi_file(path)

    df = _read(path)
    space = df.filter(pl.col("char") == " ")
    assert space["word_idx"].to_list() == [1]
    assert space["word_idx_in_line"].to_list() == [1]
    # the repaired label is propagated from the following word group
    assert space["word"].to_list() == ["dog"]
    # rows and word_idx for the real words are untouched
    assert df.height == 7
    assert df.filter(pl.col("char") == "c")["word_idx"].to_list() == [0]


def test_fix_aoi_file_is_idempotent(tmp_path):
    path = tmp_path / "aoi.csv"
    _write(path, _space_and_words())

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
            "word": None,
        }
    )
    path = tmp_path / "aoi.csv"
    _write(path, rows)

    fix_aoi_file(path)

    df = _read(path)
    last = df.filter(pl.col("char_idx_in_line") == 7)
    assert last["word_idx"].to_list() == [1]  # unchanged, no next row


def test_repair_word_labels_fills_within_group_not_across(tmp_path):
    rows = [
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 0,
            "char": "a",
            "word": "alpha",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 1,
            "char": " ",
            "word": None,
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 2,
            "char": "b",
            "word": "beta",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 1,
            "word_idx_in_line": 1,
            "char_idx_in_line": 3,
            "char": " ",
            "word": None,
        },
    ]
    path = tmp_path / "aoi.csv"
    _write(path, rows)

    repair_word_labels(path)

    df = _read(path)
    labels = {
        row["word_idx"]: row["word"]
        for row in df.filter(pl.col("char") == " ").to_dicts()
    }
    assert labels == {0: "alpha", 1: "beta"}


def test_repair_word_labels_treats_whitespace_only_as_missing(tmp_path):
    rows = [
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 0,
            "char": "x",
            "word": "gamma",
        },
        {
            "page": "page_1",
            "line_idx": 0,
            "word_idx": 0,
            "word_idx_in_line": 0,
            "char_idx_in_line": 1,
            "char": " ",
            "word": "   ",
        },
    ]
    path = tmp_path / "aoi.csv"
    _write(path, rows)

    repair_word_labels(path)

    df = _read(path)
    assert df.filter(pl.col("char") == " ")["word"].to_list() == ["gamma"]


def test_remap_space_standalone(tmp_path):
    path = tmp_path / "aoi.csv"
    _write(path, _space_and_words())

    remap_space_to_following_word(path)

    df = _read(path)
    space = df.filter(pl.col("char") == " ")
    assert space["word_idx"].to_list() == [1]
    # remap alone does not fill the word label
    assert space["word"].to_list() == [None]


def test_remap_preserves_row_order_and_columns(tmp_path):
    path = tmp_path / "aoi.csv"
    _write(path, _space_and_words())
    before = _read(path)

    fix_aoi_file(path)

    after = _read(path)
    assert after.columns == before.columns
    assert after.height == before.height
    assert after["char_idx_in_line"].to_list() == before["char_idx_in_line"].to_list()


def test_fix_aoi_file_missing_columns_raises(tmp_path):
    path = tmp_path / "aoi.csv"
    pl.DataFrame({"foo": [1]}).write_csv(path)
    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        fix_aoi_file(path)
