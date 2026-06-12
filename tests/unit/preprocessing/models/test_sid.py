import pytest
from preprocessing.models.sid import Sid


@pytest.mark.parametrize(
    "sid_str, expected_pid, expected_lang, expected_country, expected_lab, expected_session, expected_postfix, expected_notes",
    [
        ("001_EN_UK_1_PT1", "001", "EN", "UK", "1", "PT1", "", ""),
        ("002_ZH_CH_LAB2_S2_restart", "002", "ZH", "CH", "LAB2", "S2", "restart", ""),
        (
            "003_DE_DE_1_ET1_full_restart",
            "003",
            "DE",
            "DE",
            "1",
            "ET1",
            "full_restart",
            "Session has been fully restarted.",
        ),
        (
            "004_FR_FR_1_PT1_start_after_trial_10",
            "004",
            "FR",
            "FR",
            "1",
            "PT1",
            "start_after_trial_10",
            "Session has been restarted after trial 10.",
        ),
        (
            "999_US_US_X_ET2_some_long_postfix_with_underscores",
            "999",
            "US",
            "US",
            "X",
            "ET2",
            "some_long_postfix_with_underscores",
            "",
        ),
    ],
)
def test_sid_init_from_str(
    sid_str,
    expected_pid,
    expected_lang,
    expected_country,
    expected_lab,
    expected_session,
    expected_postfix,
    expected_notes,
):
    sid = Sid(sid_str)
    assert sid.pid == expected_pid
    assert sid.lang == expected_lang
    assert sid.country == expected_country
    assert sid.lab == expected_lab
    assert sid.session == expected_session
    assert sid.postfix == expected_postfix
    assert sid.notes == expected_notes
    assert str(sid) == sid_str


def test_is_valid_pid_replacement():
    """Replacement for old is_valid_pid tests using Sid.is_valid_pid."""
    valid_pids = ["001", "123", "999"]
    invalid_pids = [
        "0",
        "00",
        "0001",
        "abc",
        "12a",
        "1.2",
        "-12",
        "",
        " 12",
        "12 ",
        None,
        123,
    ]

    for pid in valid_pids:
        assert Sid.is_valid_pid(pid) is True
    for pid in invalid_pids:
        assert Sid.is_valid_pid(pid) is False


@pytest.mark.parametrize(
    "kwargs, expected_str",
    [
        (
            {"pid": "001", "lang": "EN", "country": "UK", "lab": "1", "session": "PT1"},
            "001_EN_UK_1_PT1",
        ),
        (
            {
                "pid": "002",
                "lang": "ZH",
                "country": "CH",
                "lab": "LAB2",
                "session": "S2",
                "postfix": "restart",
            },
            "002_ZH_CH_LAB2_S2_restart",
        ),
    ],
)
def test_sid_init_from_components(kwargs, expected_str):
    sid = Sid(**kwargs)
    assert str(sid) == expected_str
    assert sid.pid == kwargs["pid"]
    assert sid.lang == kwargs["lang"]
    assert sid.country == kwargs["country"]
    assert sid.lab == kwargs["lab"]
    assert sid.session == kwargs["session"]
    assert sid.postfix == kwargs.get("postfix", "")


@pytest.mark.parametrize(
    "sid_str, pid, lang, country, lab, session",
    [
        ("001_EN_UK_1_PT1", "001", "EN", "UK", "1", "PT1"),
    ],
)
def test_sid_init_raises_both(sid_str, pid, lang, country, lab, session):
    with pytest.raises(
        ValueError, match="Pass either 'sid' string or individual components, not both."
    ):
        Sid(sid_str, pid=pid, lang=lang, country=country, lab=lab, session=session)


@pytest.mark.parametrize(
    "kwargs",
    [
        ({"pid": "001", "lang": "EN", "country": "UK", "lab": "1"}),  # missing session
        (
            {"pid": "001", "lang": "EN", "country": "UK", "session": "PT1"}
        ),  # missing lab
    ],
)
def test_sid_init_raises_missing_components(kwargs):
    with pytest.raises(ValueError, match="All components .* must be provided"):
        Sid(**kwargs)


@pytest.mark.parametrize(
    "invalid_sid",
    [
        ("01_EN_UK_1_PT1"),  # pid too short
        ("001_EN_UK_1"),  # too few parts
        ("001_ENG_UK_1_PT1"),  # lang too long
        ("001_EN_UKK_1_PT1"),  # country too long
        ("001_EN_UK_1_S"),  # session identifier incomplete
        (
            "001_EN_UK_1_SQ"
        ),  # _SQ is not a valid session prefix for matching but is a valid part of a filename
    ],
)
def test_sid_init_raises_invalid_format(invalid_sid):
    with pytest.raises(ValueError):
        Sid(invalid_sid)


def test_sid_is_valid_sid():
    assert Sid.is_valid_sid("001_EN_UK_1_PT1") is True
    assert Sid.is_valid_sid("001_EN_UK_1_S1") is True
    assert Sid.is_valid_sid("invalid") is False
    assert Sid.is_valid_sid(None) is False


def test_sid_pid_property_backward_compatibility():
    """Ensures sid.pid works as expected (replacing pid_from_session)."""
    assert Sid("001_EN_UK_1_PT1").pid == "001"
    assert Sid("999_US_US_X_ET2").pid == "999"


def test_sid_base_id():
    """Tests sid.base_id property."""
    assert Sid("001_EN_UK_1_S1").base_id == "001_EN_UK_1"
    assert Sid("001_EN_UK_1_S1_extra").base_id == "001_EN_UK_1"
    assert Sid("017_DA_DK_1_ET1").base_id == "017_DA_DK_1"


@pytest.mark.parametrize(
    "sid_str, expected_no_postfix",
    [
        ("001_EN_UK_1_PT1", "001_EN_UK_1_PT1"),
        ("002_ZH_CH_LAB2_S2_restart", "002_ZH_CH_LAB2_S2"),
        ("003_DE_DE_1_ET1_full_restart", "003_DE_DE_1_ET1"),
        (
            "004_FR_FR_1_PT1_start_after_trial_10",
            "004_FR_FR_1_PT1",
        ),
    ],
)
def test_sid_id_no_postfix(sid_str, expected_no_postfix):
    assert Sid(sid_str).id_no_postfix == expected_no_postfix


@pytest.mark.parametrize(
    "session_idf, expected_save_name",
    [
        ("001_EN_UK_1_PT1", "001_EN_UK_1_PT1"),
        ("002_ZH_CH_LAB2_S2_restart", "002_ZH_CH_LAB2_S2"),
        ("003_DE_DE_1_ET1_full_restart", "003_DE_DE_1_ET1"),
        (
            "004_FR_FR_1_PT1_start_after_trial_10",
            "004_FR_FR_1_PT1",
        ),
        ("non_compliant_id_extra_part", "non_compliant_id_extra_part"),
        ("short", "short"),
    ],
)
def test_sid_get_session_save_name(session_idf, expected_save_name):
    assert Sid.get_session_save_name(session_idf) == expected_save_name


@pytest.mark.parametrize(
    "sid1_str, sid2_str, expected_match",
    [
        ("001_EN_UK_1_S1", "001_EN_UK_1_PT1", True),
        ("001_EN_UK_1_S1", "001_EN_UK_1_ET1", True),
        ("001_EN_UK_1_PT1", "001_EN_UK_1_ET1", True),
        ("001_EN_UK_1_S1", "001_EN_UK_1_S1", True),
        ("001_EN_UK_1_S1", "001_EN_UK_1_S2", False),  # different session number
        ("001_EN_UK_1_S1", "002_EN_UK_1_S1", False),  # different pid
        ("001_EN_UK_1_S1", "001_FR_UK_1_S1", False),  # different lang
        ("001_EN_UK_1_S1", "001_EN_US_1_S1", False),  # different country
        ("001_EN_UK_1_S1", "001_EN_UK_2_S1", False),  # different lab
        ("001_EN_UK_1_S1_restart", "001_EN_UK_1_PT1_restart", True),
        ("001_EN_UK_1_S1_restart", "001_EN_UK_1_S1_postfix", True),  # different postfix
    ],
)
def test_sid_equals_soft(sid1_str, sid2_str, expected_match):
    sid1 = Sid(sid1_str)
    sid2 = Sid(sid2_str)
    assert sid1.equals_soft(sid2) == expected_match
    assert sid2.equals_soft(sid1) == expected_match
