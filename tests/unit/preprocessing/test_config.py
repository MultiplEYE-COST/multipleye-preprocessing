import logging
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def settings_obj():
    from preprocessing.config import Settings

    return Settings()


@pytest.mark.parametrize(
    "attr, expected",
    [
        ("INCLUDE_PILOTS", False),
        ("DEVELOPMENT", False),
        ("EXPECTED_SAMPLING_RATE_HZ", 1000),
        ("FIXATION", "fixation"),
        ("SACCADE", "saccade"),
        ("ASC_FOLDER", Path("asc/")),
        ("FORCE_RECONVERT_ASC", False),
        ("SANITY_CHECKS_FOLDER", Path("sanity_checks/")),
        ("METADATA_FOLDER", Path("metadata/")),
    ],
)
def test_settings_default_values(settings_obj, attr, expected):
    """Test that settings have expected default values."""
    assert getattr(settings_obj, attr) == expected


@pytest.mark.parametrize(
    "attr, value, expected_log",
    [
        (
            "DATA_COLLECTION_NAME",
            "NEW_VAL",
            "Changing setting DATA_COLLECTION_NAME: None -> NEW_VAL",
        ),
        ("INCLUDE_PILOTS", True, "Changing setting INCLUDE_PILOTS: False -> True"),
        ("NEW_ATTR", 42, "Setting new attribute NEW_ATTR: 42"),
    ],
)
def test_settings_direct_set_logging(settings_obj, caplog, attr, value, expected_log):
    """Test that setting attributes directly logs the changes."""
    settings_obj._loaded = True  # Avoid auto-loading
    with caplog.at_level(logging.DEBUG):
        setattr(settings_obj, attr, value)

    assert expected_log in caplog.text


def test_settings_setup_logging(settings_obj, tmp_path):
    """Test that setup_logging configures handlers correctly."""
    log_file = tmp_path / "test.log"
    settings_obj.CONSOLE_LOG_LEVEL = "ERROR"
    settings_obj.FILE_LOG_LEVEL = "DEBUG"
    settings_obj.setup_logging(log_file=log_file)

    logger = logging.getLogger("preprocessing")
    handlers = logger.handlers
    assert len(handlers) == 2

    stream_handler = next(h for h in handlers if isinstance(h, logging.StreamHandler))
    file_handler = next(h for h in handlers if isinstance(h, logging.FileHandler))

    assert stream_handler.level == logging.ERROR
    assert file_handler.level == logging.DEBUG
    assert str(file_handler.baseFilename) == str(log_file.resolve())


@pytest.mark.parametrize(
    "update_dict, expected_logs",
    [
        (
            {"data_collection_name": "ME_TEST"},
            ["Changing setting DATA_COLLECTION_NAME: None -> ME_TEST"],
        ),
        ({"include_pilots": True}, ["Changing setting INCLUDE_PILOTS: False -> True"]),
        ({"NEW_SETTING": 123}, ["Setting new attribute NEW_SETTING: 123"]),
    ],
)
def test_settings_update_logging(settings_obj, caplog, update_dict, expected_logs):
    """Test that updating settings logs the changes correctly."""
    settings_obj._loaded = True  # Avoid auto-loading
    with caplog.at_level(logging.DEBUG):
        settings_obj.update(update_dict)

    for log_msg in expected_logs:
        assert log_msg in caplog.text


@pytest.mark.parametrize(
    "config_data",
    [
        {
            "data_collection_name": "ME_EN_UK_LON_LAB1_2025",
            "expected_sampling_rate_hz": 500,
        },
    ],
)
def test_settings_load_from_yaml_logging(settings_obj, caplog, tmp_path, config_data):
    """Test that loading from YAML logs the path and changes."""
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    with caplog.at_level(logging.DEBUG):
        settings_obj.load(path=config_file)

    assert f"Loading config from: {config_file.resolve()}" in caplog.text
    assert (
        "Changing setting DATA_COLLECTION_NAME: None -> ME_EN_UK_LON_LAB1_2025"
        in caplog.text
    )
    assert "Changing setting EXPECTED_SAMPLING_RATE_HZ: 1000 -> 500" in caplog.text


@pytest.mark.parametrize(
    "update_dict, attr, expected",
    [
        ({"data_collection_name": "ME_TEST"}, "DATA_COLLECTION_NAME", "ME_TEST"),
        ({"include_pilots": True}, "INCLUDE_PILOTS", True),
        ({"EXPECTED_SAMPLING_RATE_HZ": 500}, "EXPECTED_SAMPLING_RATE_HZ", 500),
    ],
)
def test_settings_update(settings_obj, update_dict, attr, expected):
    """Test updating settings from a dictionary."""
    settings_obj.update(update_dict)
    assert getattr(settings_obj, attr) == expected


def test_settings_load_from_yaml(settings_obj, tmp_path):
    """Test loading settings from a YAML file."""
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "data_collection_name": "ME_EN_UK_LON_LAB1_2025",
        "expected_sampling_rate_hz": 500,
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    settings_obj.load(path=config_file)
    assert settings_obj.DATA_COLLECTION_NAME == "ME_EN_UK_LON_LAB1_2025"
    assert settings_obj.EXPECTED_SAMPLING_RATE_HZ == 500


def test_settings_validation_cases(settings_obj):
    """Test that missing required fields or placeholders do not raise errors during initial load."""
    settings_obj._validate()  # Should not raise initially
    settings_obj.DATA_COLLECTION_NAME = "REPLACE_WITH_YOUR_COLLECTION_NAME"
    settings_obj._validate()  # Should also not raise initially


def test_prepare_language_folder_none_error():
    """Test that prepare_language_folder raises a ValueError when name is None and no config."""
    import preprocessing
    from preprocessing.config import Settings
    from preprocessing.scripts.prepare_language_folder import prepare_language_folder

    # Use a fresh settings object without a config file
    s = Settings()
    s._loaded = True  # mock as loaded with no config found

    # Temporarily monkeypatch the global settings
    original_settings = preprocessing.settings
    preprocessing.settings = s
    try:
        with pytest.raises(ValueError, match="data_collection_name is None"):
            prepare_language_folder(None)
    finally:
        preprocessing.settings = original_settings


@pytest.mark.parametrize(
    "name, expected",
    [
        ("LANGUAGE", "EN"),
        ("COUNTRY", "UK"),
        ("CITY", "London"),
        ("LAB", "1"),
        ("YEAR", "2026"),
    ],
)
def test_settings_dynamic_properties(settings_obj, name, expected):
    """Test that dynamic properties are correctly computed."""
    settings_obj.DATA_COLLECTION_NAME = "MultiplEYE_EN_UK_London_1_2026"
    settings_obj._loaded = True  # Prevent auto-loading legacy config

    assert getattr(settings_obj, name) == expected
    assert "MultiplEYE_EN_UK_London_1_2026" in str(settings_obj.DATASET_DIR)


def test_settings_precedence_env_var(tmp_path, monkeypatch):
    """Test that environment variable has precedence over CWD default."""
    from preprocessing.config import Settings

    env_config = tmp_path / "env_config.yaml"
    with open(env_config, "w") as f:
        yaml.dump({"data_collection_name": "ENV_COLLECTION"}, f)

    monkeypatch.setenv("MULTIPLEYE_CONFIG", str(env_config))

    s = Settings()
    s.load()
    assert s.DATA_COLLECTION_NAME == "ENV_COLLECTION"


def test_settings_copies_template_silently(tmp_path, monkeypatch, caplog):
    """Test that missing config copies template silently during load."""
    from preprocessing.config import TEMPLATE_RELATIVE_PATH, Settings

    template_path = Settings()._repo_root / TEMPLATE_RELATIVE_PATH
    template_contents = template_path.read_text(encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MULTIPLEYE_CONFIG", raising=False)

    s = Settings()
    with caplog.at_level(logging.ERROR):
        s.load()

    # load() should now be silent
    assert "CONFIGURATION REQUIRED" not in caplog.text
    assert s._is_template_loaded

    copied_path = tmp_path / "multipleye_settings_preprocessing.yaml"
    assert copied_path.exists()
    assert copied_path.read_text(encoding="utf-8") == template_contents

    # Now verify get_config_status_message returns the error
    msg = s.get_config_status_message()
    assert "CONFIGURATION REQUIRED" in msg
    assert str(copied_path) in msg


@pytest.mark.parametrize(
    "folder_name, expected_auto_filled, expected_msg_part",
    [
        (
            "MultiplEYE_DA_DK_Aalborg_1_2026",
            True,
            "The data collection name has been detected as 'MultiplEYE_DA_DK_Aalborg_1_2026'",
        ),
        (
            "Invalid_Folder_Name",
            False,
            "A template has been created for you at:",
        ),
    ],
)
def test_settings_template_auto_fill_behavior(
    tmp_path, monkeypatch, folder_name, expected_auto_filled, expected_msg_part
):
    """Test template generation behavior based on folder name compliance."""
    from preprocessing.config import Settings

    case_dir = tmp_path / folder_name
    case_dir.mkdir()

    monkeypatch.chdir(case_dir)
    monkeypatch.delenv("MULTIPLEYE_CONFIG", raising=False)

    s = Settings()
    s.load()

    assert s._is_template_loaded
    assert s._is_auto_filled == expected_auto_filled

    copied_path = case_dir / "multipleye_settings_preprocessing.yaml"
    assert copied_path.exists()
    content = copied_path.read_text(encoding="utf-8")

    if expected_auto_filled:
        assert f'data_collection_name: "{folder_name}"' in content
    else:
        assert 'data_collection_name: "REPLACE_WITH_YOUR_COLLECTION_NAME"' in content

    msg = s.get_config_status_message()
    assert "CONFIGURATION REQUIRED" in msg
    assert expected_msg_part in msg


def test_settings_placeholder_status_message(settings_obj):
    """Test that placeholder DATA_COLLECTION_NAME is reported in status message."""
    settings_obj.DATA_COLLECTION_NAME = "REPLACE_WITH_YOUR_COLLECTION_NAME"
    msg = settings_obj.get_config_status_message()
    assert "INVALID CONFIGURATION" in msg
    assert "Invalid DATA_COLLECTION_NAME" in msg
    assert "REPLACE_WITH_YOUR_COLLECTION_NAME" in msg
    assert "naming and configuration" in msg
    assert "https://" in msg
    assert "=" * 80 in msg


def test_settings_reactivity(settings_obj):
    """Test that dependent properties react to DATA_COLLECTION_NAME changes."""
    settings_obj.DATA_COLLECTION_NAME = "MultiplEYE_EN_UK_London_1_2026"
    assert settings_obj.LANGUAGE == "EN"
    assert settings_obj.COUNTRY == "UK"
    assert settings_obj.CITY == "London"
    assert settings_obj.LAB == "1"
    assert settings_obj.YEAR == "2026"
    assert "MultiplEYE_EN_UK_London_1_2026" in str(settings_obj.DATASET_DIR)
    assert "EN_UK_1" in str(settings_obj.PSYM_PARTICIPANT_CONFIGS)

    settings_obj.DATA_COLLECTION_NAME = "MultiplEYE_DE_DE_Berlin_2_2025"
    assert settings_obj.LANGUAGE == "DE"
    assert settings_obj.COUNTRY == "DE"
    assert settings_obj.CITY == "Berlin"
    assert settings_obj.LAB == "2"
    assert settings_obj.YEAR == "2025"
    assert "MultiplEYE_DE_DE_Berlin_2_2025" in str(settings_obj.DATASET_DIR)
    assert "DE_DE_2" in str(settings_obj.PSYM_PARTICIPANT_CONFIGS)


def test_settings_regex_reactivity(settings_obj):
    """Test that regexes react to column name changes."""
    settings_obj.TRIAL_COL = "my_trial"
    settings_obj.PAGE_COL = "my_page"

    pattern = settings_obj.START_RECORDING_REGEX.pattern
    assert "?P<my_trial>" in pattern
    assert "?P<my_page>" in pattern

    # Verify it works
    match = settings_obj.START_RECORDING_REGEX.match(
        "start_recording_trial_1_stimulus_Test_1_page_1"
    )
    assert match is not None
    assert match.group("my_trial") == "trial_1"
    assert match.group("my_page") == "page_1"


def test_settings_gaze_patterns_reactivity(settings_obj):
    """Test that GAZE_PATTERNS react to column name changes."""
    settings_obj.TRIAL_COL = "T"
    settings_obj.STIMULUS_COL = "S"
    settings_obj.PAGE_COL = "P"

    patterns = settings_obj.GAZE_PATTERNS
    # First pattern is the reading one
    assert "?P<T>" in patterns[0]
    assert "?P<S>" in patterns[0]
    assert "?P<P>" in patterns[0]

    # Dictionary patterns
    assert patterns[2]["column"] == "T"
    assert patterns[3]["column"] == "P"


def test_settings_manual_override(settings_obj):
    """Test that manual overrides take precedence over dynamic properties."""
    settings_obj.DATA_COLLECTION_NAME = "MultiplEYE_EN_UK_London_1_2026"
    assert settings_obj.LANGUAGE == "EN"

    settings_obj.LANGUAGE = "FR"
    assert settings_obj.LANGUAGE == "FR"

    # Changing collection name should not affect overridden LANGUAGE
    settings_obj.DATA_COLLECTION_NAME = "MultiplEYE_DE_DE_Berlin_2_2025"
    assert settings_obj.LANGUAGE == "FR"

    # But should affect other non-overridden ones
    assert settings_obj.COUNTRY == "DE"


@pytest.mark.parametrize(
    "key, value, attr",
    [
        ("expected_sampling_rate_hz", 1234, "EXPECTED_SAMPLING_RATE_HZ"),
        ("EXPECTED_SAMPLING_RATE_HZ", 4321, "expected_sampling_rate_hz"),
    ],
)
def test_settings_case_insensitivity(settings_obj, key, value, attr):
    """Test that settings can be accessed/updated with both cases."""
    settings_obj._loaded = True  # Prevent auto-loading legacy config
    settings_obj.update({key: value})
    assert getattr(settings_obj, attr) == value
