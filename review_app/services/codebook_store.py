"""Application-level codebook store for the review app."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ..config import PREPROCESSED_DATA_DIR
from .codebook import (
    REPO_CODEBOOK_DIR,
    Availability,
    Codebook,
    availability_for,
    codebook_hash,
    load_dcn_codebook,
    load_union_codebook,
    overlay_codebook,
)


def dcn_path(dcn_name: str) -> Path:
    return PREPROCESSED_DATA_DIR / dcn_name


def _fingerprint() -> tuple[tuple[str, int, int], ...]:
    entries: list[tuple[str, int, int]] = []
    for path in sorted(REPO_CODEBOOK_DIR.glob("*")):
        if path.is_file():
            stat = path.stat()
            entries.append((str(path), stat.st_mtime_ns, stat.st_size))
    if PREPROCESSED_DATA_DIR.exists():
        for candidate in sorted(PREPROCESSED_DATA_DIR.iterdir()):
            if not candidate.is_dir():
                continue
            bundle = candidate / "codebook" / "generated" / "codebook_bundle.json"
            if bundle.exists():
                stat = bundle.stat()
                entries.append((str(bundle), stat.st_mtime_ns, stat.st_size))
    return tuple(entries)


@lru_cache(maxsize=8)
def _cached_union(
    preprocessed_dir: str,
    repo_dir: str,
    fingerprint: tuple[tuple[str, int, int], ...],
) -> Codebook:
    del fingerprint
    return load_union_codebook(Path(preprocessed_dir), Path(repo_dir))


def union_codebook() -> Codebook:
    return _cached_union(
        str(PREPROCESSED_DATA_DIR),
        str(REPO_CODEBOOK_DIR),
        _fingerprint(),
    )


_DCN_CACHE: dict[tuple[str, str], tuple[tuple, Codebook]] = {}


def dcn_codebook(dcn_name: str) -> Codebook:
    fingerprint = _fingerprint()
    base = union_codebook()
    cache_key = (dcn_name, base.hash)
    cached = _DCN_CACHE.get(cache_key)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]
    own = load_dcn_codebook(dcn_path(dcn_name))
    codebook = overlay_codebook(base, own) if own is not None else base
    _DCN_CACHE[cache_key] = (fingerprint, codebook)
    return codebook


def availability(
    dcn_name: str,
    codebook: Codebook | None = None,
) -> dict[str, Availability]:
    return availability_for(dcn_path(dcn_name), codebook or dcn_codebook(dcn_name))


def codebook_status(dcn_name: str) -> dict[str, str]:
    own = load_dcn_codebook(dcn_path(dcn_name))
    if own is None:
        codebook = union_codebook()
        return {
            "source": "repo",
            "version": codebook.version,
            "hash": codebook.hash,
        }
    return {"source": "collection", "version": own.version, "hash": own.hash}


def repo_hash() -> str:
    return codebook_hash(REPO_CODEBOOK_DIR)
