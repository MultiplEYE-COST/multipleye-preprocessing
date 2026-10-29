"""Canonical eye-tracker names and tolerant input normalization."""

from __future__ import annotations

import difflib
import re
from typing import TypedDict

__all__ = [
    "CANONICAL_EYE_TRACKERS",
    "EYE_TRACKER_MODELS",
    "eye_tracker_brand",
    "normalize_eye_tracker_name",
    "suggest_eye_tracker_names",
]


class EyeTrackerSpec(TypedDict):
    """Maintenance metadata for one canonical eye-tracker model."""

    brand: str
    aliases: tuple[str, ...]


EYE_TRACKER_MODELS: dict[str, EyeTrackerSpec] = {
    "EyeLink 1000": {
        "brand": "eyelink",
        "aliases": ("Eyelink 1000", "EyeLink1000"),
    },
    "EyeLink 1000 Plus": {
        "brand": "eyelink",
        "aliases": (
            "Eyelink 1000 Plus",
            "EyeLink 1000+",
            "EyeLink 1000-Plus",
            "EyeLink1000 Plus",
        ),
    },
    "EyeLink II": {
        "brand": "eyelink",
        "aliases": ("Eyelink II", "EyeLink 2"),
    },
    "EyeLink Portable Duo": {
        "brand": "eyelink",
        "aliases": (
            "Eyelink Portable Duo",
            "EyeLink Duo",
            "Eyelink Duo",
            "EyeLink Portable Duo 2000Hz Remote",
            "EyeLink Portable Duo 2000 Hz Remote",
        ),
    },
}

CANONICAL_EYE_TRACKERS = tuple(EYE_TRACKER_MODELS)

_PUNCTUATION = re.compile(r"[^a-z0-9]+")


def _normalize(value: object) -> str:
    """Return a lowercase, punctuation- and whitespace-insensitive string."""
    text = str(value).casefold().replace("+", " plus ")
    return _PUNCTUATION.sub(" ", text).strip()


def _build_alias_lookup() -> dict[str, str]:
    """Build the flat lookup and reject aliases claimed by two models."""
    lookup: dict[str, str] = {}
    for canonical, spec in EYE_TRACKER_MODELS.items():
        for alias in (canonical, *spec["aliases"]):
            normalized = _normalize(alias)
            if not normalized:
                raise ValueError(f"Empty eye-tracker alias for {canonical!r}.")
            existing = lookup.get(normalized)
            if existing is not None and existing != canonical:
                raise ValueError(
                    f"Eye-tracker alias {alias!r} maps to both "
                    f"{existing!r} and {canonical!r}."
                )
            lookup[normalized] = canonical
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def normalize_eye_tracker_name(value: object) -> str | None:
    """Return the canonical model for an eye-tracker name, or None.

    Parameters
    ----------
    value : object
        Raw eye-tracker name from a lab configuration or metadata source.

    Returns
    -------
    str or None
        One of ``CANONICAL_EYE_TRACKERS``, or None when the value is empty or
        cannot be mapped.
    """
    if value is None:
        return None
    return _ALIAS_LOOKUP.get(_normalize(value))


def eye_tracker_brand(name: str | None) -> str | None:
    """Return the brand key for a canonical eye-tracker model, or None."""
    if name is None:
        return None
    spec = EYE_TRACKER_MODELS.get(name)
    return spec["brand"] if spec is not None else None


def suggest_eye_tracker_names(value: object, max_suggestions: int = 3) -> list[str]:
    """Return close canonical eye-tracker names for an unsupported value."""
    if value is None or max_suggestions <= 0:
        return []
    close_aliases = difflib.get_close_matches(
        _normalize(value),
        list(_ALIAS_LOOKUP),
        n=max_suggestions * 2,
        cutoff=0.5,
    )
    suggestions: list[str] = []
    for alias in close_aliases:
        canonical = _ALIAS_LOOKUP[alias]
        if canonical not in suggestions:
            suggestions.append(canonical)
        if len(suggestions) == max_suggestions:
            break
    return suggestions
