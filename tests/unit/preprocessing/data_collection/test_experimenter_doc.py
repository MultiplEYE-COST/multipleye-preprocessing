"""Tests for parsing the experimenter session documentation workbook."""

from pathlib import Path

import polars as pl
import pytest
from openpyxl import Workbook

from preprocessing.data_collection.experimenter_doc import ExperimenterDoc
from preprocessing.data_collection.multipleye_data_collection import (
    _find_experimenter_doc,
)

ET_HEADERS = list(ExperimenterDoc.et_header_prefixes.values())
PT_HEADERS = list(ExperimenterDoc.pt_header_prefixes.values())
PT_ROW = ["2025-01-01", "001_EN_UK_1_PT1", "001", "10:00", "LWMC", "ok", "10:30"]


def _et_row(headers: list[str], participant_id: str = "001") -> list[str]:
    values = list(headers)
    values[headers.index("participant id")] = participant_id
    return values


@pytest.fixture
def write_doc(tmp_path: Path):
    """Return a factory that writes a documentation workbook to ``tmp_path``."""

    def _write(
        et_rows: list[list[object]],
        pt_rows: list[list[object]] | None = None,
        *,
        include_et: bool = True,
        include_pt: bool = True,
    ) -> Path:
        wb = Workbook()
        wb.remove(wb.active)
        sheets = (
            (include_et, ExperimenterDoc.et_sheet_name, et_rows),
            (
                include_pt,
                ExperimenterDoc.pt_sheet_name,
                pt_rows if pt_rows is not None else [PT_HEADERS, PT_ROW],
            ),
        )
        for include, name, rows in sheets:
            if include:
                sheet = wb.create_sheet(name)
                for row in rows:
                    sheet.append(row)
        path = tmp_path / "doc.xlsx"
        wb.save(path)
        return path

    return _write


@pytest.fixture
def parse_doc(write_doc):
    def _parse(
        et_rows: list[list[object]],
        pt_rows: list[list[object]] | None = None,
        **kwargs,
    ) -> ExperimenterDoc:
        return ExperimenterDoc.create_from_excel(write_doc(et_rows, pt_rows, **kwargs))

    return _parse


@pytest.mark.parametrize(
    "layout",
    ["canonical", "reordered", "extra_middle", "extra_end"],
)
def test_matches_columns_by_header(parse_doc, layout):
    headers = list(ET_HEADERS)
    values = _et_row(headers)

    if layout == "reordered":
        pairs = list(zip(headers, values))
        pairs = pairs[10:] + pairs[:10]
        headers = [header for header, _ in pairs]
        values = [value for _, value in pairs]
    elif layout == "extra_middle":
        headers.insert(5, "lab notes")
        values.insert(5, "note")
    elif layout == "extra_end":
        headers.append("lab notes")
        values.append("note")

    doc = parse_doc([["title"], headers, values])

    assert list(doc.et_frame.columns[: len(ExperimenterDoc.et_columns)]) == (
        ExperimenterDoc.et_columns
    )
    assert doc.et_frame["participant_id"].to_list() == ["001"]
    assert doc.et_frame["session_id"].to_list() == ["session id"]
    assert doc.et_frame["comments"].to_list() == ["additional comments"]
    assert doc.get_pids("et") == ([1], [])
    assert doc.get_pids("pt") == ([1], [])


def test_falls_back_to_expected_order_when_headers_change(parse_doc):
    unknown = len(ExperimenterDoc.et_columns) - 3
    headers = ["Date (dd-mm-yyyy)", "Session ID", "Participant ID"] + [
        f"Unknown {i}" for i in range(unknown)
    ]
    values = ["2025-01-01", "001_EN_UK_1_ET1", "001"] + [
        f"x{i}" for i in range(unknown)
    ]

    doc = parse_doc([["title"], headers, values])

    assert list(doc.et_frame.columns) == ExperimenterDoc.et_columns
    assert doc.et_frame["participant_id"].to_list() == ["001"]
    assert doc.get_pids("et") == ([1], [])


def test_pt_session_end_is_optional(parse_doc):
    doc = parse_doc(
        [["title"], ET_HEADERS, _et_row(ET_HEADERS)],
        [PT_HEADERS[:6], PT_ROW[:6]],
    )

    assert "session_end" not in doc.pt_frame.columns
    assert doc.get_pids("pt") == ([1], [])


def test_missing_header_row_raises(parse_doc):
    with pytest.raises(ValueError, match="Could not locate the header row"):
        parse_doc([["title"], ["a", "b", "c"]])


def test_unknown_layout_with_unmatched_headers_raises(parse_doc):
    unknown = len(ExperimenterDoc.et_columns)
    headers = ["Date (dd-mm-yyyy)", "Session ID", "Participant ID"] + [
        f"Unknown {i}" for i in range(unknown)
    ]
    values = ["2025-01-01", "001_EN_UK_1_ET1", "001"] + [
        f"x{i}" for i in range(unknown)
    ]

    with pytest.raises(ValueError, match="Could not map all required columns"):
        parse_doc([["title"], headers, values])


def test_missing_sheet_raises(parse_doc):
    with pytest.raises(ValueError, match="no sheet named"):
        parse_doc([], include_et=False)


@pytest.mark.parametrize(
    ("participant_ids", "expected"),
    [
        (["001", "002"], ([1, 2], [])),
        (["001", "2", "abc", None, ""], ([1, 2], ["abc"])),
        (["3.0", "1.5"], ([3], ["1.5"])),
        ([], ([], [])),
    ],
)
def test_get_pids_from_et(participant_ids, expected):
    doc = ExperimenterDoc(
        pl.DataFrame({"participant_id": participant_ids}), None, None, None
    )

    assert doc.get_pids("et") == expected


def test_get_pids_rejects_unknown_sheet():
    doc = ExperimenterDoc(None, None, None, None)

    with pytest.raises(ValueError, match="sheet must be 'et' or 'pt'"):
        doc.get_pids("nope")


def test_find_experimenter_doc_accepts_name_without_lab(tmp_path: Path) -> None:
    documentation = tmp_path / "documentation"
    documentation.mkdir()
    expected = (
        documentation
        / "MultiplEYE_Experimenter_Session_Documentation_IT_IT_TORINO.xlsx"
    )
    expected.write_text("x", encoding="utf-8")

    found = _find_experimenter_doc(tmp_path, "IT_IT_Torino_1", "IT", "IT", "Torino")

    assert found == expected


def test_find_experimenter_doc_accepts_name_with_lab(tmp_path: Path) -> None:
    documentation = tmp_path / "documentation"
    documentation.mkdir()
    expected = (
        documentation
        / "MultiplEYE_Experimenter_Session_Documentation_KL_DK_Nuuk_1.xlsx"
    )
    expected.write_text("x", encoding="utf-8")

    found = _find_experimenter_doc(tmp_path, "KL_DK_Nuuk_1", "KL", "DK", "Nuuk")

    assert found == expected


def test_find_experimenter_doc_returns_none(tmp_path: Path) -> None:
    assert _find_experimenter_doc(tmp_path, "X_Y_Z_1", "X", "Y", "Z") is None
