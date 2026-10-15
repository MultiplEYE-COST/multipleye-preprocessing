"""Tests for copying the used question-image version folders to the output."""

from pathlib import Path

from preprocessing.config import settings
from preprocessing.models.dcn import Dcn
from preprocessing.scripts import prepare_language_folder as plf


def _make_version_folder(base: Path, version: int, content: str = "img") -> Path:
    folder = base / f"question_images_version_{version}"
    folder.mkdir(parents=True)
    (folder / "image.png").write_text(content)
    return folder


def test_copies_only_used_versions(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    _make_version_folder(source, 5)
    _make_version_folder(source, 9)

    plf._copy_used_version_folders(source, dest, {5})

    assert (dest / "question_images_version_5" / "image.png").exists()
    assert not (dest / "question_images_version_9").exists()


def test_missing_source_base_is_noop(tmp_path):
    dest = tmp_path / "dest"
    plf._copy_used_version_folders(tmp_path / "does_not_exist", dest, {5})
    assert not dest.exists()


def test_existing_destination_version_is_kept(tmp_path):
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    _make_version_folder(source, 5, content="new")
    dest_version = _make_version_folder(dest, 5, content="existing")

    plf._copy_used_version_folders(source, dest, {5})

    assert (dest_version / "image.png").read_text() == "existing"


def test_aoi_question_images_copied_when_enabled(tmp_path, monkeypatch):
    source = tmp_path / "stimuli"
    dest = tmp_path / "preprocessed"
    _make_version_folder(source / "aoi_question_images_en_uk_1", 7)

    monkeypatch.setattr(plf, "_get_used_stimulus_versions", lambda _: {7})
    monkeypatch.setattr(settings, "_loaded", True)
    monkeypatch.setitem(settings.__dict__, "COPY_AOI_IMAGES_OVERLAY", True)

    plf._copy_stimulus_assets(
        source, dest, tmp_path / "sessions", Dcn("MultiplEYE_EN_UK_London_1_2025")
    )

    assert (
        dest / "aoi_question_images_en_uk_1" / "question_images_version_7" / "image.png"
    ).exists()


def test_aoi_question_images_not_copied_when_disabled(tmp_path, monkeypatch):
    source = tmp_path / "stimuli"
    dest = tmp_path / "preprocessed"
    _make_version_folder(source / "aoi_question_images_en_uk_1", 7)

    monkeypatch.setattr(plf, "_get_used_stimulus_versions", lambda _: {7})
    monkeypatch.setattr(settings, "_loaded", True)
    monkeypatch.setitem(settings.__dict__, "COPY_AOI_IMAGES_OVERLAY", False)

    plf._copy_stimulus_assets(
        source, dest, tmp_path / "sessions", Dcn("MultiplEYE_EN_UK_London_1_2025")
    )

    assert not (dest / "aoi_question_images_en_uk_1").exists()
