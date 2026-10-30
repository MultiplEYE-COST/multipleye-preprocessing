import csv
import json
import zipfile
from pathlib import Path

import pytest

from preprocessing.metadata.codebook import (
    CODEBOOK_DIR,
    load_codebook_info,
    write_codebook_outputs,
)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("pipeline_version", "2026.10.29"),
        ("pipeline_git", "v2026.10.29-1-gabc123"),
        ("pymovements_version", "0.28.0"),
        ("edf2asc_version", "EDF2ASC version 4.2"),
        ("python_version", "3.13.2"),
    ],
)
def test_environment_versions_are_written(tmp_path: Path, key: str, value: str) -> None:
    write_codebook_outputs(tmp_path, {key: value}, codebook_dir=CODEBOOK_DIR)

    with (tmp_path / "codebook" / "environment.csv").open(newline="") as handle:
        row = next(csv.DictReader(handle))

    assert row[key] == value
    assert row["codebook_version"] == "2.0-dev0"
    assert "Marie-Luise Müller" in row["credit"]


def test_write_codebook_outputs(tmp_path: Path) -> None:
    environment = {
        "pipeline_version": "2026.10.29",
        "pipeline_git": "v2026.10.29-1-gabc123",
        "pymovements_version": "0.28.0",
        "edf2asc_version": "EDF2ASC version 4.2",
        "python_version": "3.13.2",
    }

    destination = write_codebook_outputs(
        tmp_path, environment, codebook_dir=CODEBOOK_DIR
    )

    assert destination == tmp_path / "codebook"
    assert (tmp_path / "codebook.csv").exists()
    assert (tmp_path / "codebook" / "fields.csv").exists()
    assert (tmp_path / "codebook" / "codebook_info.csv").exists()
    assert (tmp_path / "codebook" / "environment.csv").exists()
    assert (tmp_path / "codebook" / "generated" / "codebook_bundle.json").exists()
    assert (tmp_path / "codebook" / "generated" / "codebook_bundle.zip").exists()

    info = load_codebook_info(CODEBOOK_DIR)
    assert info["codebook_version"] == "2.0-dev0"
    assert "Marie-Luise Müller" in info["credit"]

    environment_text = (tmp_path / "codebook" / "environment.csv").read_text()
    assert "2.0-dev0" in environment_text
    assert "2026.10.29" in environment_text
    assert "0.28.0" in environment_text

    bundle = json.loads(
        (tmp_path / "codebook" / "generated" / "codebook_bundle.json").read_text()
    )
    assert bundle["codebook"]["codebook_version"] == "2.0-dev0"
    assert bundle["codebook"]["hash"].startswith("sha256:")
    assert bundle["environment"]["pymovements_version"] == "0.28.0"
    assert bundle["views"]
    assert bundle["display_groups"]

    with zipfile.ZipFile(
        tmp_path / "codebook" / "generated" / "codebook_bundle.zip"
    ) as archive:
        names = set(archive.namelist())

    assert "codebook.csv" in names
    assert "codebook/environment.csv" in names
    assert "codebook/codebook_info.csv" in names
    assert "codebook/README.md" in names
    assert "codebook/generated/codebook_bundle.json" in names


def test_bundle_matches_csv_package(tmp_path: Path) -> None:
    write_codebook_outputs(tmp_path, {}, codebook_dir=CODEBOOK_DIR)

    bundle = json.loads(
        (tmp_path / "codebook" / "generated" / "codebook_bundle.json").read_text()
    )

    for key, name in (
        ("fields", "fields.csv"),
        ("views", "views.csv"),
        ("relations", "relations.csv"),
        ("display_groups", "display_groups.csv"),
        ("display_group_members", "display_group_members.csv"),
        ("semantic_categories", "semantic_categories.csv"),
    ):
        with (CODEBOOK_DIR / name).open(newline="") as handle:
            assert bundle[key] == list(csv.DictReader(handle))


def test_write_codebook_outputs_overwrites_previous_run(tmp_path: Path) -> None:
    write_codebook_outputs(
        tmp_path,
        {"pipeline_version": "first", "pipeline_git": "old"},
        codebook_dir=CODEBOOK_DIR,
    )

    (tmp_path / "codebook.csv").write_text("stale root")
    (tmp_path / "codebook" / "fields.csv").write_text("stale fields")
    (tmp_path / "codebook" / "codebook_info.csv").write_text("stale info")

    write_codebook_outputs(
        tmp_path,
        {"pipeline_version": "second", "pipeline_git": "new"},
        codebook_dir=CODEBOOK_DIR,
    )

    with (tmp_path / "codebook" / "environment.csv").open(newline="") as handle:
        row = next(csv.DictReader(handle))

    assert row["pipeline_version"] == "second"
    assert row["pipeline_git"] == "new"
    assert "first" not in (tmp_path / "codebook" / "environment.csv").read_text()
    assert (tmp_path / "codebook.csv").read_text() == (
        CODEBOOK_DIR / "fields.csv"
    ).read_text()
    assert (tmp_path / "codebook" / "fields.csv").read_text() == (
        CODEBOOK_DIR / "fields.csv"
    ).read_text()
    assert (tmp_path / "codebook" / "codebook_info.csv").read_text() == (
        CODEBOOK_DIR / "codebook_info.csv"
    ).read_text()

    bundle = json.loads(
        (tmp_path / "codebook" / "generated" / "codebook_bundle.json").read_text()
    )
    assert bundle["environment"]["pipeline_version"] == "second"
    assert bundle["codebook"]["codebook_version"] == "2.0-dev0"

    with zipfile.ZipFile(
        tmp_path / "codebook" / "generated" / "codebook_bundle.zip"
    ) as archive:
        names = archive.namelist()

    assert len(names) == len(set(names))


def test_root_codebook_matches_field_table(tmp_path: Path) -> None:
    write_codebook_outputs(tmp_path, {}, codebook_dir=CODEBOOK_DIR)

    assert (tmp_path / "codebook.csv").read_text() == (
        CODEBOOK_DIR / "fields.csv"
    ).read_text()


def test_load_codebook_info_missing(tmp_path: Path) -> None:
    assert load_codebook_info(tmp_path / "missing") == {}


def test_write_codebook_outputs_missing_source(tmp_path: Path) -> None:
    assert (
        write_codebook_outputs(tmp_path, {}, codebook_dir=tmp_path / "missing") is None
    )
