"""Tests for review YAML read/write service."""

from pathlib import Path

from review_app.services.review import save_review, load_review, REVIEW_STATUSES


def test_load_review_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "review_app.config.PREPROCESSED_DATA_DIR", Path("/tmp/nonexistent")
    )
    annotation = load_review("test_dcn", "test_sid")
    assert annotation.status == "unreviewed"
    assert annotation.reviewer == ""
    assert annotation.comment == ""


def test_save_and_load_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("review_app.config.PREPROCESSED_DATA_DIR", tmp_path)

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
    monkeypatch.setattr("review_app.config.PREPROCESSED_DATA_DIR", tmp_path)
    import pytest

    with pytest.raises(ValueError, match="Invalid review status"):
        save_review(
            "MultiplEYE_DA_DK_Aalborg_1_2026", "001_DA_DK_1_ET1", status="bogus"
        )


def test_save_overwrites_previous(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("review_app.config.PREPROCESSED_DATA_DIR", tmp_path)

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
    monkeypatch.setattr("review_app.config.PREPROCESSED_DATA_DIR", tmp_path)

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
