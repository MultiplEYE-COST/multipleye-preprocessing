"""Pinned Glottolog languoid table for language node validation.

The pipeline stores one Glottocode per data collection. Glottolog is the
authority for that identifier, so the language node is validated against the
pinned Glottolog release when the settings are loaded. The table is downloaded
once and cached locally. The pipeline does not ship the table and does not use
it for coordinates, tree paths or display labels.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "GLOTTOLOG_DOI",
    "GLOTTOLOG_SHA256",
    "GLOTTOLOG_URL",
    "GLOTTOLOG_VERSION",
    "GlottologError",
    "GlottologLanguoid",
    "GlottologTable",
    "default_cache_dir",
    "load_glottolog_table",
    "resolve_glottolog_node",
]

logger = logging.getLogger(__name__)

GLOTTOLOG_VERSION = "5.3"
GLOTTOLOG_DOI = "10.5281/zenodo.18840935"
GLOTTOLOG_URL = (
    "https://cdstar.eva.mpg.de//bitstreams/EAEA0-608B-9919-A962-0/"
    "glottolog_languoid.csv.zip"
)
GLOTTOLOG_SHA256 = "47fcc04c18f3f6bff43198b5be14f1f6954600c90573373df9ecf6fc12622bfb"
_ARCHIVE_NAME = "glottolog_languoid.csv.zip"
_TABLE_NAME = "languoid.csv"
_ASSIGNABLE_LEVELS = frozenset({"language", "dialect"})


class GlottologError(ValueError):
    """Raised when the Glottolog table or a selected node is invalid."""


@dataclass(frozen=True, slots=True)
class GlottologLanguoid:
    """One row from the Glottolog languoid table."""

    id: str
    name: str
    level: str
    parent_id: str | None
    iso639_3: str | None


class GlottologTable:
    """Lookup table for Glottolog languoids."""

    def __init__(
        self,
        rows: dict[str, GlottologLanguoid],
        version: str = GLOTTOLOG_VERSION,
    ) -> None:
        self._rows = rows
        self.version = version

    def __len__(self) -> int:
        """Return the number of languoids in the table."""
        return len(self._rows)

    def get(self, glottocode: str) -> GlottologLanguoid | None:
        """Return one languoid or ``None`` when the code is unknown."""
        return self._rows.get(glottocode)

    def require_assignable(self, glottocode: str) -> GlottologLanguoid:
        """Return a language or dialect row and reject families and unknown codes.

        Parameters
        ----------
        glottocode : str
            Glottocode configured for the data collection.

        Returns
        -------
        GlottologLanguoid
            The matching Glottolog row.

        Raises
        ------
        GlottologError
            If the code is unknown or does not point at a language or dialect.
        """
        row = self._rows.get(glottocode)
        if row is None:
            raise GlottologError(
                f"Language node {glottocode!r} is not a Glottolog "
                f"{self.version} Glottocode. Configure a valid Glottocode or set "
                "language_tree.glottolog_check: false."
            )
        if row.level not in _ASSIGNABLE_LEVELS:
            raise GlottologError(
                f"Language node {glottocode!r} is a Glottolog {row.level!r} row. "
                "Only language and dialect rows can be assigned to a data collection."
            )
        return row

    def path(self, glottocode: str) -> str:
        """Return the Glottolog name path from the root to the node.

        Parameters
        ----------
        glottocode : str
            Glottocode to resolve.

        Returns
        -------
        str
            Slash separated Glottolog names.

        Raises
        ------
        GlottologError
            If a parent is missing or the parent chain contains a cycle.
        """
        names: list[str] = []
        seen: set[str] = set()
        current: str | None = glottocode
        while current is not None:
            if current in seen:
                raise GlottologError(
                    f"Glottolog parent cycle at language node {current!r}."
                )
            seen.add(current)
            row = self._rows.get(current)
            if row is None:
                raise GlottologError(
                    f"Glottolog parent {current!r} is missing from the table."
                )
            names.append(row.name)
            current = row.parent_id
        return " / ".join(reversed(names))


def default_cache_dir() -> Path:
    """Return the default Glottolog cache directory.

    The ``MULTIPLEYE_GLOTTOLOG_CACHE`` environment variable overrides the
    location. Otherwise the XDG cache directory, or ``~/.cache``, is used.
    """
    override = os.environ.get("MULTIPLEYE_GLOTTOLOG_CACHE")
    if override:
        return Path(override).expanduser()
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache).expanduser() if xdg_cache else Path.home() / ".cache"
    return base / "multipleye" / "glottolog" / GLOTTOLOG_VERSION


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, target: Path, expected_sha256: str, timeout: float) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    logger.info("Downloading Glottolog languoid table from %s", url)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "MultiplEYE-preprocessing"},
    )
    try:
        with (
            urllib.request.urlopen(request, timeout=timeout) as response,
            temporary.open("wb") as handle,
        ):
            shutil.copyfileobj(response, handle)
        actual = _sha256(temporary)
        if actual != expected_sha256:
            raise GlottologError(
                "Downloaded Glottolog table checksum mismatch: "
                f"expected {expected_sha256}, got {actual}."
            )
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _read_table(path: Path) -> dict[str, GlottologLanguoid]:
    try:
        with zipfile.ZipFile(path) as archive, archive.open(_TABLE_NAME) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            reader = csv.DictReader(text)
            rows: dict[str, GlottologLanguoid] = {}
            for record in reader:
                glottocode = (record.get("id") or "").strip()
                if not glottocode:
                    continue
                rows[glottocode] = GlottologLanguoid(
                    id=glottocode,
                    name=(record.get("name") or "").strip(),
                    level=(record.get("level") or "").strip(),
                    parent_id=(record.get("parent_id") or "").strip() or None,
                    iso639_3=(record.get("iso639P3code") or "").strip() or None,
                )
    except (OSError, KeyError, zipfile.BadZipFile, csv.Error) as exc:
        raise GlottologError(
            f"Could not read Glottolog languoid table {path}: {exc}"
        ) from exc
    if not rows:
        raise GlottologError(f"Glottolog languoid table {path} has no rows.")
    return rows


def load_glottolog_table(
    cache_dir: Path | str | None = None,
    zip_path: Path | str | None = None,
    *,
    allow_download: bool = True,
    url: str = GLOTTOLOG_URL,
    expected_sha256: str = GLOTTOLOG_SHA256,
    version: str = GLOTTOLOG_VERSION,
    timeout: float = 60.0,
) -> GlottologTable:
    """Load the pinned Glottolog languoid table.

    Parameters
    ----------
    cache_dir : Path or str, optional
        Directory holding ``glottolog_languoid.csv.zip``. Defaults to
        :func:`default_cache_dir`.
    zip_path : Path or str, optional
        Explicit archive path. Overrides ``cache_dir``.
    allow_download : bool, optional
        Download the pinned archive when it is missing. Defaults to ``True``.
    url : str, optional
        Download URL for the pinned archive.
    expected_sha256 : str, optional
        Expected checksum of the archive.
    version : str, optional
        Glottolog version stored on the table.
    timeout : float, optional
        Download timeout in seconds.

    Returns
    -------
    GlottologTable
        Parsed languoid table.

    Raises
    ------
    GlottologError
        If the archive is missing, cannot be downloaded, has a wrong checksum
        or cannot be parsed.
    """
    archive = Path(zip_path) if zip_path is not None else None
    if archive is None:
        directory = Path(cache_dir) if cache_dir is not None else default_cache_dir()
        archive = directory / _ARCHIVE_NAME

    if not archive.is_file():
        if not allow_download:
            raise GlottologError(
                f"Glottolog languoid table not found at {archive}. Download it "
                "once or set language_tree.glottolog_cache to an existing cache."
            )
        _download(url, archive, expected_sha256, timeout)

    actual = _sha256(archive)
    if actual != expected_sha256:
        raise GlottologError(
            f"Glottolog table {archive} has checksum {actual}, expected "
            f"{expected_sha256}. Delete the file and run again."
        )

    return GlottologTable(_read_table(archive), version=version)


def resolve_glottolog_node(
    glottocode: str,
    cache_dir: Path | str | None = None,
    *,
    allow_download: bool = True,
) -> GlottologLanguoid:
    """Validate one Glottocode against the pinned Glottolog table.

    Parameters
    ----------
    glottocode : str
        Glottocode configured for the data collection.
    cache_dir : Path or str, optional
        Glottolog cache directory.
    allow_download : bool, optional
        Download the table when the cache is empty.

    Returns
    -------
    GlottologLanguoid
        The matching language or dialect row.

    Raises
    ------
    GlottologError
        If the table is unavailable or the node is unknown or not assignable.
    """
    table = load_glottolog_table(cache_dir, allow_download=allow_download)
    return table.require_assignable(glottocode)
