"""Checks that the codebook documentation matches the package."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from preprocessing.metadata.codebook import CODEBOOK_DIR
from preprocessing.metadata.schema import VIEW_LEVELS, read_fields
from preprocessing.metadata.vocabulary import BOOLEAN_ALLOWED_VALUES, unit_for_name

REPO_ROOT = Path(__file__).resolve().parents[4]
_GUIDE_DOCS = (
    "metadata.md",
    "participant_questionnaire.md",
    "participants.md",
    "pipeline_stages.md",
    "technical_architecture.md",
    "configuration.md",
)
DOC_PATHS = (
    CODEBOOK_DIR / "README.md",
    *(REPO_ROOT / "docs" / "guide" / name for name in _GUIDE_DOCS),
)

_VARIABLE_ID = re.compile(r"`([a-z_]+\.[A-Za-z0-9_.\[\]]+)`")
_UNIT_SUFFIX = re.compile(r"`_(ms|sec|s|hz|px|cm|dva|wpm|year|days)`")
_REPO_PATH = re.compile(r"`((?:preprocessing|codebook|docs)/[A-Za-z0-9_./-]+)`")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _table_rows(text: str, header: str) -> list[list[str]]:
    """Return the rows of the Markdown table that starts with ``header``."""
    lines = text.splitlines()
    if header not in lines:
        raise AssertionError(f"Markdown table not found: {header}")
    rows: list[list[str]] = []
    for line in lines[lines.index(header) + 1 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and set(cells[0]) <= {"-", ":", " "}:
            continue
        rows.append(cells)
    return rows


def _field_views() -> dict[str, str]:
    return {
        field.variable_id: field.view_level
        for field in read_fields(CODEBOOK_DIR / "fields.csv")
    }


def _group_coverage() -> dict[str, set[str]]:
    field_views = _field_views()
    coverage: dict[str, set[str]] = {}
    for member in _read_csv(CODEBOOK_DIR / "display_group_members.csv"):
        coverage.setdefault(member["group_id"], set()).add(
            field_views[member["variable_id"]]
        )
    return coverage


def test_readme_view_table_matches_views_csv() -> None:
    text = (CODEBOOK_DIR / "README.md").read_text(encoding="utf-8")
    rows = _table_rows(text, "| View | Key field |")
    documented = {row[0].strip("`"): row[1].strip("`") for row in rows}
    actual = {
        row["view_id"]: row["key"] for row in _read_csv(CODEBOOK_DIR / "views.csv")
    }

    assert documented == actual


def test_readme_display_group_table_matches_members() -> None:
    text = (CODEBOOK_DIR / "README.md").read_text(encoding="utf-8")
    rows = _table_rows(text, "| Group | Views | Purpose |")
    documented: dict[str, set[str]] = {}
    for row in rows:
        group_id = row[0].strip("`")
        views_text = row[1]
        if views_text == "all":
            views = set(VIEW_LEVELS)
        else:
            views = {
                view.strip()
                for view in views_text.replace(" and ", ", ").split(",")
                if view.strip()
            }
        documented[group_id] = views

    groups = {row["group_id"] for row in _read_csv(CODEBOOK_DIR / "display_groups.csv")}
    coverage = _group_coverage()

    assert set(documented) == groups
    assert documented == {
        group_id: coverage.get(group_id, set()) for group_id in groups
    }


def test_default_group_covers_all_views() -> None:
    assert _group_coverage()["default"] == set(VIEW_LEVELS)


def test_documented_variable_ids_exist() -> None:
    known = set(_field_views())
    for path in DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        for match in _VARIABLE_ID.finditer(text):
            variable_id = match.group(1)
            if variable_id.split(".", 1)[0] in VIEW_LEVELS:
                assert variable_id in known, f"{path.name}: unknown {variable_id}"


def test_documented_repository_paths_exist() -> None:
    for path in DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        for token in _REPO_PATH.findall(text):
            if token.endswith("/"):
                assert (REPO_ROOT / token).is_dir(), f"{path.name}: missing {token}"
            else:
                assert (REPO_ROOT / token).exists(), f"{path.name}: missing {token}"


def test_documented_unit_suffixes_are_known() -> None:
    text = (REPO_ROOT / "docs" / "guide" / "metadata.md").read_text(encoding="utf-8")
    suffixes = set(_UNIT_SUFFIX.findall(text))

    assert "ms" in suffixes
    assert "dva" in suffixes
    for suffix in suffixes:
        assert unit_for_name(f"example_{suffix}"), f"unknown unit suffix _{suffix}"


def test_documented_boolean_values_match_the_vocabulary() -> None:
    readme = (CODEBOOK_DIR / "README.md").read_text(encoding="utf-8")
    guide = (REPO_ROOT / "docs" / "guide" / "metadata.md").read_text(encoding="utf-8")

    assert BOOLEAN_ALLOWED_VALUES == "true,false"
    assert "true,false" in readme
    assert "true,false" in guide


def test_guides_state_canonical_language_codes() -> None:
    guide = (REPO_ROOT / "docs" / "guide" / "participants.md").read_text(
        encoding="utf-8"
    )
    stages = (REPO_ROOT / "docs" / "guide" / "pipeline_stages.md").read_text(
        encoding="utf-8"
    )

    assert "ISO 639-1 codes" in guide
    assert "kept **raw**" not in guide
    assert "keeps the language fields raw" not in stages


def test_technical_architecture_lists_the_codebook_outputs() -> None:
    text = (REPO_ROOT / "docs" / "guide" / "technical_architecture.md").read_text(
        encoding="utf-8"
    )

    assert "codebook/" in text
    assert "codebook.csv" in text
    assert "display groups" in text
