import pytest

from preprocessing.utils.eye_tracker import (
    CANONICAL_EYE_TRACKERS,
    EYE_TRACKER_BRANDS,
    eye_tracker_brand,
    normalize_eye_tracker_name,
    suggest_eye_tracker_names,
)


@pytest.mark.parametrize("name", CANONICAL_EYE_TRACKERS)
def test_canonical_names_round_trip(name: str) -> None:
    assert normalize_eye_tracker_name(name) == name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Eyelink 1000 Plus", "EyeLink 1000 Plus"),
        ("EyeLink 1000+", "EyeLink 1000 Plus"),
        ("EyeLink 1000-Plus", "EyeLink 1000 Plus"),
        ("  eyelink   1000 plus  ", "EyeLink 1000 Plus"),
        ("EyeLink 1000", "EyeLink 1000"),
        ("Eyelink II", "EyeLink II"),
        ("EyeLink 2", "EyeLink II"),
        ("Eyelink Duo", "EyeLink Portable Duo"),
        ("EyeLink Duo", "EyeLink Portable Duo"),
        ("Eyelink Portable Duo", "EyeLink Portable Duo"),
        ("EyeLink Portable Duo 2000Hz Remote", "EyeLink Portable Duo"),
    ],
)
def test_aliases_are_normalized(raw: str, expected: str) -> None:
    assert normalize_eye_tracker_name(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "Tobii Pro Spectrum", "unknown"])
def test_unsupported_names_return_none(raw: object) -> None:
    assert normalize_eye_tracker_name(raw) is None


@pytest.mark.parametrize("name", CANONICAL_EYE_TRACKERS)
def test_all_models_keep_the_eyelink_brand(name: str) -> None:
    assert eye_tracker_brand(name) == "eyelink"
    assert name in EYE_TRACKER_BRANDS["eyelink"]


def test_unknown_brand_is_none() -> None:
    assert eye_tracker_brand("Tobii Pro Spectrum") is None
    assert eye_tracker_brand(None) is None


def test_close_match_returns_canonical_suggestion() -> None:
    assert "EyeLink 1000 Plus" in suggest_eye_tracker_names("EyeLink 1000 Pluss")
    assert "EyeLink Portable Duo" in suggest_eye_tracker_names("EyeLink Portable Du")


def test_no_close_match_returns_empty_list() -> None:
    assert suggest_eye_tracker_names("Tobii Pro Spectrum") == []
    assert suggest_eye_tracker_names(None) == []
