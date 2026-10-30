import csv
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from preprocessing.metadata.codebook import (
    CODEBOOK_DIR,
    codebook_hash,
    load_codebook_identity,
    write_codebook_outputs,
)
from preprocessing.metadata.registry import iter_registry_fields
from preprocessing.metadata.schema import (
    VIEW_LEVELS,
    CodebookField,
    CodebookValidationError,
    read_fields,
    validate_codebook_package,
    write_fields,
)
from preprocessing.scripts.build_codebook import build_fields, main


def _copy_package(tmp_path: Path) -> Path:
    target = tmp_path / "codebook"
    shutil.copytree(CODEBOOK_DIR, target)
    return target


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _set_field(target: Path, index: int, **changes: str) -> None:
    fields = read_fields(target / "fields.csv")
    fields[index] = replace(fields[index], **changes)
    write_fields(target / "fields.csv", fields)


def test_current_package_is_valid() -> None:
    validate_codebook_package(CODEBOOK_DIR)


def test_registry_covers_all_views() -> None:
    fields = list(iter_registry_fields())

    assert {field.view_level for field in fields} == set(VIEW_LEVELS)
    assert len({field.variable_id for field in fields}) == len(fields)


def test_committed_fields_match_registry() -> None:
    actual = read_fields(CODEBOOK_DIR / "fields.csv")
    expected = build_fields(CODEBOOK_DIR)

    assert [field.to_row() for field in actual] == [
        field.to_row() for field in expected
    ]


def test_build_fields_keeps_curated_rows(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    curated = CodebookField(
        variable_id="participant.curated_example",
        view_level="participant",
        variable_name="curated_example",
        feature_label="Curated example",
        description="A source row that is not registered in code",
        data_type="string",
        semantic_category="participant",
    )
    fields = read_fields(target / "fields.csv")
    write_fields(target / "fields.csv", [*fields, curated])

    built = build_fields(target)

    assert curated in built


def test_build_check_passes() -> None:
    assert main(["--codebook-dir", str(CODEBOOK_DIR), "--check"]) == 0


def test_build_check_detects_outdated_fields(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    _set_field(target, 0, description="Changed outside the registry")

    assert main(["--codebook-dir", str(target)]) == 1


def test_build_write_updates_fields(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    _set_field(target, 0, description="Changed outside the registry")

    assert main(["--codebook-dir", str(target), "--write"]) == 0
    actual = read_fields(target / "fields.csv")
    assert actual[0].description == "Name of the data collection"


def test_validate_rejects_duplicate_field_id(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    fields = read_fields(target / "fields.csv")
    write_fields(target / "fields.csv", [*fields, fields[0]])

    with pytest.raises(CodebookValidationError, match="Duplicate variable_id"):
        validate_codebook_package(target)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"view_level": "unknown"}, "unknown view_level"),
        ({"yaml_path": ".bad.path"}, "yaml_path"),
        ({"semantic_category": "unknown"}, "unknown semantic_category"),
        ({"aggregation_method": "median"}, "unknown aggregation_method"),
        ({"aggregation_input": "trial.missing"}, "references unknown field"),
        ({"dynamic_equivalent": "trial.missing"}, "dynamic_equivalent"),
    ],
)
def test_validate_rejects_invalid_field_values(
    tmp_path: Path, changes: dict[str, str], message: str
) -> None:
    target = _copy_package(tmp_path)
    _set_field(target, 0, **changes)

    with pytest.raises(CodebookValidationError, match=message):
        validate_codebook_package(target)


def test_validate_rejects_unknown_view_key(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    views = _read_csv(target / "views.csv")
    views[0]["key"] = "missing_key"
    _write_csv(target / "views.csv", views)

    with pytest.raises(CodebookValidationError, match="has no field"):
        validate_codebook_package(target)


def test_validate_rejects_missing_view(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    views = [
        view for view in _read_csv(target / "views.csv") if view["view_id"] != "session"
    ]
    _write_csv(target / "views.csv", views)

    with pytest.raises(CodebookValidationError, match="Missing view: session"):
        validate_codebook_package(target)


def test_validate_rejects_unknown_relation_view(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    relations = _read_csv(target / "relations.csv")
    relations[0]["to_view"] = "missing_view"
    _write_csv(target / "relations.csv", relations)

    with pytest.raises(CodebookValidationError, match="unknown to_view"):
        validate_codebook_package(target)


def test_validate_rejects_unknown_relation_key(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    relations = _read_csv(target / "relations.csv")
    relations[0]["to_key"] = "missing_key"
    _write_csv(target / "relations.csv", relations)

    with pytest.raises(CodebookValidationError, match="is not a known key"):
        validate_codebook_package(target)


def test_validate_rejects_unknown_group_member(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    members = _read_csv(target / "display_group_members.csv")
    members.append({"group_id": "default", "variable_id": "trial.missing"})
    _write_csv(target / "display_group_members.csv", members)

    with pytest.raises(CodebookValidationError, match="unknown field"):
        validate_codebook_package(target)


def test_codebook_hash_is_stable() -> None:
    first = codebook_hash(CODEBOOK_DIR)
    second = codebook_hash(CODEBOOK_DIR)

    assert first == second
    assert first.startswith("sha256:")


def test_codebook_hash_changes_with_package_content(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    before = codebook_hash(target)

    with (target / "fields.csv").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    assert codebook_hash(target) != before


def test_load_codebook_identity() -> None:
    identity = load_codebook_identity(CODEBOOK_DIR)

    assert identity["codebook_version"] == "2.0-dev0"
    assert "Marie-Luise Müller" in identity["credit"]
    assert identity["hash"].startswith("sha256:")


def test_write_codebook_outputs_rejects_invalid_package(tmp_path: Path) -> None:
    target = _copy_package(tmp_path)
    _set_field(target, 0, description="")

    with pytest.raises(CodebookValidationError, match="description is required"):
        write_codebook_outputs(tmp_path / "output", {}, codebook_dir=target)
