import logging
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
        ("EXPECTED_SAMPLING_RATE_HZ", 1000),
        ("FIXATION", "fixation"),
        ("SACCADE", "saccade"),
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


def test_settings_validation_error(settings_obj):
    """Test that missing required fields raise an error."""
    with pytest.raises(ValueError, match="DATA_COLLECTION_NAME is required"):
        settings_obj._validate()


def test_prepare_language_folder_none_error():
    """Test that prepare_language_folder raises a ValueError when name is None and no config."""
    from preprocessing.scripts.prepare_language_folder import prepare_language_folder
    from preprocessing.config import Settings
    import preprocessing

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
        ("CITY", "LON"),
        ("LAB", "LAB1"),
        ("YEAR", "2025"),
    ],
)
def test_settings_dynamic_properties(settings_obj, name, expected):
    """Test that dynamic properties are correctly computed."""
    settings_obj.DATA_COLLECTION_NAME = "ME_EN_UK_LON_LAB1_2025"
    settings_obj._loaded = True  # Prevent auto-loading legacy config

    assert getattr(settings_obj, name) == expected
    assert "ME_EN_UK_LON_LAB1_2025" in str(settings_obj.DATASET_DIR)


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
