"""Tests for the pinned Glottolog languoid table."""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest

from preprocessing.metadata.glottolog import (
    GlottologError,
    GlottologLanguoid,
    GlottologTable,
    default_cache_dir,
    load_glottolog_table,
)

_ROWS = [
    ("indo1319", "", "Indo-European", "family", ""),
    ("stan1295", "indo1319", "German", "language", "deu"),
    ("swis1247", "indo1319", "Central Alemannic", "language", "gsw"),
    ("zuri1239", "swis1247", "Zürich German", "dialect", ""),
]


def _write_zip(path: Path) -> None:
    header = "id,parent_id,name,level,iso639P3code,latitude,longitude\n"
    body = "".join(
        f"{gid},{parent},{name},{level},{iso},47.0,8.0\n"
        for gid, parent, name, level, iso in _ROWS
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("languoid.csv", header + body)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def glottolog_zip(tmp_path) -> Path:
    path = tmp_path / "glottolog_languoid.csv.zip"
    _write_zip(path)
    return path


def test_table_requires_language_or_dialect() -> None:
    table = GlottologTable(
        {
            "indo1319": GlottologLanguoid(
                "indo1319", "Indo-European", "family", None, None
            ),
            "zuri1239": GlottologLanguoid(
                "zuri1239", "Zürich German", "dialect", "swis1247", None
            ),
        }
    )

    assert table.require_assignable("zuri1239").name == "Zürich German"
    with pytest.raises(GlottologError, match="family"):
        table.require_assignable("indo1319")
    with pytest.raises(GlottologError, match="not a Glottolog"):
        table.require_assignable("xxxx1234")


def test_table_path() -> None:
    table = GlottologTable(
        {
            "indo1319": GlottologLanguoid(
                "indo1319", "Indo-European", "family", None, None
            ),
            "swis1247": GlottologLanguoid(
                "swis1247", "Central Alemannic", "language", "indo1319", "gsw"
            ),
            "zuri1239": GlottologLanguoid(
                "zuri1239", "Zürich German", "dialect", "swis1247", None
            ),
        }
    )

    assert table.path("zuri1239") == "Indo-European / Central Alemannic / Zürich German"


def test_load_explicit_zip_without_hash(glottolog_zip) -> None:
    table = load_glottolog_table(
        zip_path=glottolog_zip, expected_sha256=_sha256(glottolog_zip)
    )

    assert len(table) == 4
    assert table.require_assignable("stan1295").name == "German"


def test_missing_cache_without_download(tmp_path) -> None:
    with pytest.raises(GlottologError, match="not found"):
        load_glottolog_table(cache_dir=tmp_path, allow_download=False)


def test_download_from_file_url(tmp_path, glottolog_zip) -> None:
    cache_dir = tmp_path / "cache"
    url = glottolog_zip.as_uri()

    table = load_glottolog_table(
        cache_dir=cache_dir,
        url=url,
        expected_sha256=_sha256(glottolog_zip),
    )

    assert len(table) == 4
    assert (cache_dir / "glottolog_languoid.csv.zip").is_file()


def test_network_error_is_wrapped(monkeypatch, tmp_path) -> None:
    def _fail(*args, **kwargs):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(urllib.request, "urlopen", _fail)
    cache_dir = tmp_path / "cache"

    with pytest.raises(GlottologError) as excinfo:
        load_glottolog_table(cache_dir=cache_dir, allow_download=True)

    message = str(excinfo.value)
    assert not isinstance(excinfo.value, urllib.error.URLError)
    assert "network down" in message
    assert str(cache_dir / "glottolog_languoid.csv.zip") in message
    assert str(cache_dir) in message
    assert "language_tree.glottolog_check: false" in message
    assert not (cache_dir / "glottolog_languoid.csv.zip.part").exists()


def test_checksum_mismatch_removes_partial_download(tmp_path, glottolog_zip) -> None:
    cache_dir = tmp_path / "cache"

    with pytest.raises(GlottologError, match="checksum mismatch"):
        load_glottolog_table(
            cache_dir=cache_dir,
            url=glottolog_zip.as_uri(),
            expected_sha256="0" * 64,
        )

    assert not (cache_dir / "glottolog_languoid.csv.zip").exists()
    assert not (cache_dir / "glottolog_languoid.csv.zip.part").exists()


def test_cached_archive_is_reused(tmp_path, glottolog_zip) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    target = cache_dir / "glottolog_languoid.csv.zip"
    target.write_bytes(glottolog_zip.read_bytes())

    table = load_glottolog_table(
        cache_dir=cache_dir,
        allow_download=False,
        expected_sha256=_sha256(glottolog_zip),
    )

    assert table.require_assignable("swis1247").level == "language"


def test_default_cache_dir_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MULTIPLEYE_GLOTTOLOG_CACHE", str(tmp_path))

    assert default_cache_dir() == tmp_path


def test_default_cache_dir_is_repo_local(monkeypatch) -> None:
    monkeypatch.delenv("MULTIPLEYE_GLOTTOLOG_CACHE", raising=False)
    repo_root = Path(__file__).resolve().parents[4]

    assert default_cache_dir() == repo_root / ".cache" / "glottolog" / "5.3"


def test_official_glottolog_url_is_downloadable(tmp_path) -> None:
    cache_dir = tmp_path / "cache"

    table = load_glottolog_table(cache_dir=cache_dir)

    assert table.require_assignable("zuri1239").name == "Zürich German"
    assert (cache_dir / "glottolog_languoid.csv.zip").is_file()


# The real table is downloaded once and cached. A download failure is a test
# failure, so a broken official URL is caught immediately.
@pytest.fixture(scope="module")
def real_glottolog_table() -> GlottologTable:
    return load_glottolog_table()


def test_real_glottolog_contains_known_nodes(real_glottolog_table) -> None:
    assert real_glottolog_table.require_assignable("zuri1239").name == "Zürich German"
    assert real_glottolog_table.require_assignable("stan1295").name == "German"
    assert (
        real_glottolog_table.require_assignable("mand1415").name == "Mandarin Chinese"
    )
    assert real_glottolog_table.require_assignable("taib1240").name == "Taibei Mandarin"
    with pytest.raises(GlottologError, match="family"):
        real_glottolog_table.require_assignable("indo1319")
