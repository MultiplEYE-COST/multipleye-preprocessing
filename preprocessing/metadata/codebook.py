"""Write the codebook package and generated EyeStore bundle."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import shutil
import zipfile
from pathlib import Path
from typing import Any

from preprocessing.metadata.schema import validate_codebook_package

__all__ = [
    "CODEBOOK_DIR",
    "codebook_hash",
    "load_codebook_identity",
    "load_codebook_info",
    "write_codebook_outputs",
]

logger = logging.getLogger(__name__)

CODEBOOK_DIR = Path(__file__).resolve().parents[2] / "codebook"

_CODEBOOK_FILES = (
    "fields.csv",
    "views.csv",
    "relations.csv",
    "display_groups.csv",
    "display_group_members.csv",
    "semantic_categories.csv",
    "codebook_info.csv",
    "README.md",
)

_HASH_FILES = tuple(name for name in _CODEBOOK_FILES if name.endswith(".csv"))

_ENVIRONMENT_COLUMNS = (
    "codebook_version",
    "credit",
    "pipeline_version",
    "pipeline_git",
    "pymovements_version",
    "edf2asc_version",
    "python_version",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of dictionaries."""
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_codebook_info(codebook_dir: Path | None = None) -> dict[str, str]:
    """Return the version and credit row from ``codebook_info.csv``."""
    path = Path(codebook_dir or CODEBOOK_DIR) / "codebook_info.csv"
    if not path.exists():
        return {}
    rows = _read_csv(path)
    return dict(rows[0]) if rows else {}


def codebook_hash(codebook_dir: Path | None = None) -> str:
    """Return a deterministic SHA256 hash of the canonical CSV package."""
    source = Path(codebook_dir or CODEBOOK_DIR)
    digest = hashlib.sha256()
    for name in _HASH_FILES:
        path = source / name
        if not path.exists():
            raise FileNotFoundError(f"Codebook file not found: {path}")
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def load_codebook_identity(codebook_dir: Path | None = None) -> dict[str, str]:
    """Return the codebook version, credit and package hash."""
    source = Path(codebook_dir or CODEBOOK_DIR)
    info = load_codebook_info(source)
    if not info:
        return {}
    return {**info, "hash": codebook_hash(source)}


def _environment_rows(
    codebook_info: dict[str, str], environment: dict[str, Any]
) -> list[dict[str, str]]:
    """Combine codebook and processing environment values into one CSV row."""
    values = {
        "codebook_version": codebook_info.get("codebook_version", ""),
        "credit": codebook_info.get("credit", ""),
        "pipeline_version": environment.get("pipeline_version", ""),
        "pipeline_git": environment.get("pipeline_git", ""),
        "pymovements_version": environment.get("pymovements_version", ""),
        "edf2asc_version": environment.get("edf2asc_version", ""),
        "python_version": environment.get("python_version", ""),
    }
    return [{key: "" if value is None else str(value) for key, value in values.items()}]


def write_codebook_outputs(
    output_dir: Path | str,
    environment: dict[str, Any],
    codebook_dir: Path | str | None = None,
) -> Path | None:
    """Copy the codebook package and write the generated bundle.

    Existing codebook outputs in ``output_dir`` are overwritten.

    Parameters
    ----------
    output_dir : Path or str
        Processed data collection directory.
    environment : dict
        Pipeline, edf2asc, Python and pymovements versions.
    codebook_dir : Path or str, optional
        Source codebook package. Defaults to the repository ``codebook/`` folder.

    Returns
    -------
    Path or None
        Destination codebook directory, or None when the source package is absent.
    """
    source = Path(codebook_dir or CODEBOOK_DIR)
    if not source.is_dir():
        logger.warning("Codebook source package not found at %s", source)
        return None
    validate_codebook_package(source)

    output = Path(output_dir)
    destination = output / "codebook"
    destination.mkdir(parents=True, exist_ok=True)
    generated = destination / "generated"
    generated.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for name in _CODEBOOK_FILES:
        source_path = source / name
        if not source_path.exists():
            continue
        target = destination / name
        shutil.copy2(source_path, target)
        copied.append(target)

    root_codebook = output / "codebook.csv"
    shutil.copy2(source / "fields.csv", root_codebook)

    codebook_info = load_codebook_identity(source)
    environment_path = destination / "environment.csv"
    with environment_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_ENVIRONMENT_COLUMNS))
        writer.writeheader()
        writer.writerows(_environment_rows(codebook_info, environment))

    bundle = {
        "codebook": codebook_info,
        "environment": environment,
        "fields": _read_csv(source / "fields.csv"),
        "views": _read_csv(source / "views.csv"),
        "relations": _read_csv(source / "relations.csv"),
        "display_groups": _read_csv(source / "display_groups.csv"),
        "display_group_members": _read_csv(source / "display_group_members.csv"),
        "semantic_categories": _read_csv(source / "semantic_categories.csv"),
    }
    bundle_path = generated / "codebook_bundle.json"
    bundle_path.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    archive_path = generated / "codebook_bundle.zip"
    archive_files = [*copied, root_codebook, environment_path, bundle_path]
    availability = destination / "availability.csv"
    if availability.exists():
        archive_files.append(availability)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in archive_files:
            archive.write(path, path.relative_to(output))

    return destination
