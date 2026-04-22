import logging
import pytest
import yaml
from preprocessing.utils.data_path_utils import validate_psychometric_data


@pytest.fixture
def psycho_structure(tmp_path):
    """Creates a temporary structure for psychometric tests."""
    config_folder = tmp_path / "configs"
    data_folder = tmp_path / "data"

    config_folder.mkdir()
    data_folder.mkdir()

    return config_folder, data_folder


def test_validate_raw_success(psycho_structure, caplog):
    config_folder, data_folder = psycho_structure
    sid = "001_ZH_CH_1_PT1"

    # Enable PLAB
    config_data = {"plab": True, "ran": False}
    with open(config_folder / f"{sid}.yaml", "w") as f:
        yaml.dump(config_data, f)

    # Create PLAB data in raw layout: data/PLAB/sid
    (data_folder / "PLAB" / sid).mkdir(parents=True)

    with caplog.at_level(logging.WARNING):
        issues = validate_psychometric_data(
            config_folder, data_folder, is_restructured=False
        )

    assert not issues
    assert caplog.text == ""


def test_validate_restructured_success(psycho_structure, caplog):
    config_folder, data_folder = psycho_structure
    sid = "001_ZH_CH_1_PT1"

    # Enable PLAB
    config_data = {"plab": True}
    with open(config_folder / f"{sid}.yaml", "w") as f:
        yaml.dump(config_data, f)

    # Create PLAB data in restructured layout: data/sid/PLAB
    (data_folder / sid / "PLAB").mkdir(parents=True)

    with caplog.at_level(logging.WARNING):
        issues = validate_psychometric_data(
            config_folder, data_folder, is_restructured=True
        )

    assert not issues
    assert caplog.text == ""


def test_validate_missing_data_warning(psycho_structure, caplog):
    config_folder, data_folder = psycho_structure
    sid = "002_ZH_CH_1_PT1"

    config_data = {"plab": True}
    with open(config_folder / f"{sid}.yaml", "w") as f:
        yaml.dump(config_data, f)

    # Data is missing
    with caplog.at_level(logging.WARNING):
        issues = validate_psychometric_data(
            config_folder, data_folder, is_restructured=False
        )

    assert sid in issues
    assert "!!! MISSING DATA !!!" in caplog.text
    assert "experimenter session documentation" in caplog.text
    assert "restarted" in caplog.text


def test_validate_unexpected_data_raw(psycho_structure, caplog):
    config_folder, data_folder = psycho_structure
    sid = "003_ZH_CH_1_PT1"

    config_data = {"plab": False}
    with open(config_folder / f"{sid}.yaml", "w") as f:
        yaml.dump(config_data, f)

    # Data exists but marked False
    (data_folder / "PLAB" / sid).mkdir(parents=True)

    with caplog.at_level(logging.WARNING):
        issues = validate_psychometric_data(
            config_folder, data_folder, is_restructured=False
        )

    assert sid in issues
    assert "marked as False" in caplog.text
    assert "Copying anyway." in caplog.text


def test_validate_unexpected_data_restructured(psycho_structure, caplog):
    config_folder, data_folder = psycho_structure
    sid = "004_ZH_CH_1_PT1"

    config_data = {"plab": False}
    with open(config_folder / f"{sid}.yaml", "w") as f:
        yaml.dump(config_data, f)

    # Data exists but marked False
    (data_folder / sid / "PLAB").mkdir(parents=True)

    with caplog.at_level(logging.WARNING):
        issues = validate_psychometric_data(
            config_folder, data_folder, is_restructured=True
        )

    assert sid in issues
    assert "marked as False" in caplog.text
    assert "Copying anyway." not in caplog.text


def test_validate_session_normalization(psycho_structure, caplog):
    config_folder, data_folder = psycho_structure
    sid_s1 = "005_ZH_CH_1_S1"
    sid_pt1 = "005_ZH_CH_1_PT1"

    config_data = {"plab": True}
    with open(config_folder / f"{sid_s1}.yaml", "w") as f:
        yaml.dump(config_data, f)

    # In restructured layout, we expect normalization
    (data_folder / sid_pt1 / "PLAB").mkdir(parents=True)

    issues = validate_psychometric_data(
        config_folder, data_folder, is_restructured=True
    )
    assert not issues


def test_validate_non_sid_compliant(psycho_structure, caplog):
    config_folder, data_folder = psycho_structure
    invalid_sid = "invalid"

    config_data = {"plab": True}
    with open(config_folder / f"{invalid_sid}.yaml", "w") as f:
        yaml.dump(config_data, f)

    (data_folder / "PLAB" / invalid_sid).mkdir(parents=True)

    with caplog.at_level(logging.WARNING):
        issues = validate_psychometric_data(
            config_folder, data_folder, is_restructured=False
        )

    assert invalid_sid in issues
    assert "not SID-compliant" in caplog.text


def test_validate_no_configs(tmp_path, caplog):
    config_folder = tmp_path / "empty"
    config_folder.mkdir()

    with caplog.at_level(logging.WARNING):
        issues = validate_psychometric_data(config_folder, tmp_path)

    assert not issues
    assert "No configuration files" in caplog.text
