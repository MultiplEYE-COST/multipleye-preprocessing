"""Tests for review YAML read/write service."""

from pathlib import Path

import yaml

from review_app.services.review import (
    save_review,
    load_review,
    REVIEW_STATUSES,
    ISSUE_TYPES,
)


def test_load_review_missing(monkeypatch) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", Path("/tmp/nonexistent"))
    annotation = load_review("test_dcn", "test_sid")
    assert annotation.status == "unreviewed"
    assert annotation.reviewer == ""
    assert annotation.comment == ""


def test_save_and_load_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    saved = save_review(
        dcn_name="MultiplEYE_DA_DK_Aalborg_1_2026",
        sid="001_DA_DK_1_ET1",
        status="accepted",
        reviewer="Jane Doe",
        comment="Looks good.",
    )

    assert saved.status == "accepted"
    assert saved.reviewer == "Jane Doe"
    assert saved.comment == "Looks good."
    assert saved.reviewed_at is not None

    loaded = load_review("MultiplEYE_DA_DK_Aalborg_1_2026", "001_DA_DK_1_ET1")
    assert loaded.status == "accepted"
    assert loaded.reviewer == "Jane Doe"
    assert loaded.comment == "Looks good."
    assert loaded.reviewed_at == saved.reviewed_at


def test_save_invalid_status(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)
    import pytest

    with pytest.raises(ValueError, match="Invalid review status"):
        save_review(
            "MultiplEYE_DA_DK_Aalborg_1_2026", "001_DA_DK_1_ET1", status="bogus"
        )


def test_save_overwrites_previous(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    save_review(
        "MultiplEYE_DA_DK_Aalborg_1_2026",
        "001_DA_DK_1_ET1",
        status="flagged",
        reviewer="Alice",
        comment="Issue here.",
    )

    save_review(
        "MultiplEYE_DA_DK_Aalborg_1_2026",
        "001_DA_DK_1_ET1",
        status="accepted",
        reviewer="Alice",
        comment="Actually fine.",
    )

    loaded = load_review("MultiplEYE_DA_DK_Aalborg_1_2026", "001_DA_DK_1_ET1")
    assert loaded.status == "accepted"
    assert loaded.comment == "Actually fine."


def test_reviewed_at_auto_set(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)

    saved = save_review(
        "MultiplEYE_DA_DK_Aalborg_1_2026",
        "001_DA_DK_1_ET1",
        status="accepted",
        reviewer="Bob",
    )

    assert saved.reviewed_at is not None
    assert "T" in saved.reviewed_at


def test_review_statuses_match_plan() -> None:
    assert REVIEW_STATUSES == {"unreviewed", "accepted", "flagged", "excluded"}


def test_save_with_type_of_issue(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)
    saved = save_review(
        "MultiplEYE_DA_DK_Aalborg_1_2026",
        "001_DA_DK_1_ET1",
        status="flagged",
        reviewer="Test",
        type_of_issue="data_loss",
    )
    assert saved.type_of_issue == "data_loss"

    loaded = load_review("MultiplEYE_DA_DK_Aalborg_1_2026", "001_DA_DK_1_ET1")
    assert loaded.type_of_issue == "data_loss"


def test_save_with_needs_reprocessing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)
    saved = save_review(
        "MultiplEYE_DA_DK_Aalborg_1_2026",
        "001_DA_DK_1_ET1",
        status="flagged",
        reviewer="Test",
        needs_reprocessing=True,
    )
    assert saved.needs_reprocessing is True

    loaded = load_review("MultiplEYE_DA_DK_Aalborg_1_2026", "001_DA_DK_1_ET1")
    assert loaded.needs_reprocessing is True


def test_save_with_all_new_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)
    saved = save_review(
        "MultiplEYE_DA_DK_Aalborg_1_2026",
        "001_DA_DK_1_ET1",
        status="flagged",
        reviewer="Test",
        comment="Bad calibration.",
        type_of_issue="calibration_validation",
        needs_reprocessing=True,
    )
    assert saved.type_of_issue == "calibration_validation"
    assert saved.needs_reprocessing is True
    assert saved.status == "flagged"
    assert saved.comment == "Bad calibration."

    loaded = load_review("MultiplEYE_DA_DK_Aalborg_1_2026", "001_DA_DK_1_ET1")
    assert loaded.type_of_issue == "calibration_validation"
    assert loaded.needs_reprocessing is True
    assert loaded.status == "flagged"
    assert loaded.comment == "Bad calibration."


def test_save_invalid_type_of_issue_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)
    import pytest

    with pytest.raises(ValueError, match="Invalid issue type"):
        save_review(
            "MultiplEYE_DA_DK_Aalborg_1_2026",
            "001_DA_DK_1_ET1",
            status="flagged",
            reviewer="Test",
            type_of_issue="bogus_type",
        )


def test_load_old_review_without_new_fields(monkeypatch, tmp_path: Path) -> None:
    """Loading a review YAML without type_of_issue/needs_reprocessing
    should return defaults (empty string / False)."""
    monkeypatch.setattr("review_app.config.REVIEW_DATA_DIR", tmp_path)
    dcn_dir = tmp_path / "MultiplEYE_DA_DK_Aalborg_1_2026"
    dcn_dir.mkdir(parents=True)
    reviews_path = dcn_dir / "reviews.yaml"
    reviews_path.write_text(
        yaml.dump(
            {
                "001_DA_DK_1_ET1": {
                    "status": "flagged",
                    "reviewer": "Old",
                    "comment": "No issue field",
                }
            }
        )
    )

    loaded = load_review("MultiplEYE_DA_DK_Aalborg_1_2026", "001_DA_DK_1_ET1")
    assert loaded.type_of_issue == ""
    assert loaded.needs_reprocessing is False
    assert loaded.status == "flagged"
    assert loaded.reviewer == "Old"


def test_issue_types_defined() -> None:
    assert "calibration_validation" in ISSUE_TYPES
    assert "data_loss" in ISSUE_TYPES
    assert "incomplete" in ISSUE_TYPES
    assert "see_comment" in ISSUE_TYPES
    assert len(ISSUE_TYPES) == 4
