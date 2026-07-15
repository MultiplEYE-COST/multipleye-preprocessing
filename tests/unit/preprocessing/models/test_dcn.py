import pytest
from preprocessing.models.dcn import Dcn


@pytest.mark.parametrize(
    "name_str, expected_lang, expected_country, expected_city, expected_lab, expected_year",
    [
        ("MultiplEYE_EN_UK_London_1_2026", "EN", "UK", "London", "1", "2026"),
        ("MultiplEYE_DA_DK_Aalborg_1_2026", "DA", "DK", "Aalborg", "1", "2026"),
        ("MultiplEYE_DE_DE_Berlin_LAB2_2025", "DE", "DE", "Berlin", "LAB2", "2025"),
    ],
)
def test_data_collection_name_init_from_str(
    name_str,
    expected_lang,
    expected_country,
    expected_city,
    expected_lab,
    expected_year,
):
    dcn = Dcn(name_str)
    assert dcn.prefix == "MultiplEYE"
    assert dcn.lang == expected_lang
    assert dcn.country == expected_country
    assert dcn.city == expected_city
    assert dcn.lab == expected_lab
    assert dcn.year == expected_year
    assert str(dcn) == name_str


@pytest.mark.parametrize(
    "kwargs, expected_str",
    [
        (
            {
                "lang": "EN",
                "country": "UK",
                "city": "London",
                "lab": "1",
                "year": "2026",
            },
            "MultiplEYE_EN_UK_London_1_2026",
        ),
    ],
)
def test_data_collection_name_init_from_components(kwargs, expected_str):
    dcn = Dcn(**kwargs)
    assert str(dcn) == expected_str
    assert dcn.lang == kwargs["lang"]
    assert dcn.country == kwargs["country"]
    assert dcn.city == kwargs["city"]
    assert dcn.lab == kwargs["lab"]
    assert dcn.year == kwargs["year"]


def test_data_collection_name_init_raises_both():
    with pytest.raises(
        ValueError,
        match="Pass either 'name' string or individual components, not both.",
    ):
        Dcn("MultiplEYE_EN_UK_London_1_2026", lang="EN")


def test_data_collection_name_init_raises_missing_components():
    with pytest.raises(ValueError, match="All components .* must be provided"):
        Dcn(lang="EN", country="UK")


@pytest.mark.parametrize(
    "invalid_name",
    [
        "MultiplEYE_E_UK_London_1_2026",  # lang too short
        "MultiplEYE_ENG_UK_London_1_2026",  # lang too long
        "MultiplEYE_EN_U_London_1_2026",  # country too short
        "MultiplEYE_EN_UKK_London_1_2026",  # country too long
        "MultiplEYE_EN_UK_London_1_26",  # year too short
        "MultiplEYE_EN_UK_London_1_20266",  # year too long
        "MultiplEYE_en_UK_London_1_2026",  # lowercase lang
        "MultiplEYE_EN_uk_London_1_2026",  # lowercase country
        "OtherPrefix_EN_UK_London_1_2026",  # wrong prefix
        "MultiplEYE_EN_UK_London_1",  # missing parts
    ],
)
def test_data_collection_name_init_raises_invalid_format(invalid_name):
    with pytest.raises(ValueError):
        Dcn(invalid_name)


def test_data_collection_name_is_valid():
    assert Dcn.is_valid("MultiplEYE_EN_UK_London_1_2026") is True
    assert Dcn.is_valid("invalid") is False
    assert Dcn.is_valid(None) is False
