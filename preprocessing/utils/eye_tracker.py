"""Canonical eye-tracker names and tolerant input normalization."""

from __future__ import annotations

import difflib
import re

__all__ = [
    "CANONICAL_EYE_TRACKERS",
    "EYE_TRACKER_BRANDS",
    "eye_tracker_brand",
    "normalize_eye_tracker_name",
    "suggest_eye_tracker_names",
]

CANONICAL_EYE_TRACKERS = (
    "EyeLink 1000",
    "EyeLink 1000 Plus",
    "EyeLink II",
    "EyeLink Portable Duo",
)

EYE_TRACKER_BRANDS = {
    "eyelink": CANONICAL_EYE_TRACKERS,
}

# Keys use the output of _normalize so aliases stay case-, punctuation- and
# whitespace-insensitive. Explicit aliases cover the spellings found in lab
# configurations and older metadata.
_ALIASES = {
    "eyelink 1000": "EyeLink 1000",
    "eyelink1000": "EyeLink 1000",
    "eyelink 1000 plus": "EyeLink 1000 Plus",
    "eyelink1000 plus": "EyeLink 1000 Plus",
    "eyelink ii": "EyeLink II",
    "eyelink 2": "EyeLink II",
    "eyelink portable duo": "EyeLink Portable Duo",
    "eyelink duo": "EyeLink Portable Duo",
    "eyelink portable duo 2000hz remote": "EyeLink Portable Duo",
    "eyelink portable duo 2000 hz remote": "EyeLink Portable Duo",
}

_PUNCTUATION = re.compile(r"[^a-z0-9]+")


def _normalize(value: object) -> str:
    """Return a lowercase, punctuation- and whitespace-insensitive string."""
    text = str(value).casefold().replace("+", " plus ")
    return _PUNCTUATION.sub(" ", text).strip()


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
    return _ALIASES.get(_normalize(value))


def eye_tracker_brand(name: str | None) -> str | None:
    """Return the brand key for a canonical eye-tracker model, or None."""
    if name is None:
        return None
    for brand, models in EYE_TRACKER_BRANDS.items():
        if name in models:
            return brand
    return None


def suggest_eye_tracker_names(value: object, max_suggestions: int = 3) -> list[str]:
    """Return close canonical eye-tracker names for an unsupported value."""
    if value is None or max_suggestions <= 0:
        return []
    close_aliases = difflib.get_close_matches(
        _normalize(value),
        list(_ALIASES),
        n=max_suggestions * 2,
        cutoff=0.5,
    )
    suggestions: list[str] = []
    for alias in close_aliases:
        canonical = _ALIASES[alias]
        if canonical not in suggestions:
            suggestions.append(canonical)
        if len(suggestions) == max_suggestions:
            break
    return suggestions
