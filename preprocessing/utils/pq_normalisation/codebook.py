"""Canonical codebook for the participant questionnaire.

The codebook is language-independent. Per-language label maps are generated from
the questionnaire workbook that ships with each data collection.
"""

from __future__ import annotations

CODEBOOK: dict = {
    "schema_version": 1,
    "canonical_language": "en",
    "fields": {
        "gender": {
            "type": "categorical",
            "question": "gender",
            "codes": ["male", "female", "other", "prefer_not_to_say"],
        },
        "years_education": {
            "type": "integer",
            "question": "years_education",
            "min": 1,
            "max": 20,
            "open_ended": {"code": "greater_than_20", "label": "More than 20 years"},
        },
        "level_education": {
            "type": "ordinal",
            "question": "level_education",
            "codes": [
                "less_than_primary",
                "primary",
                "lower_secondary",
                "upper_secondary",
                "post_secondary_non_tertiary",
                "short_cycle_tertiary",
                "bachelor",
                "master",
                "doctoral",
            ],
        },
        "age": {
            "type": "integer",
            "question": "age",
            "min": 18,
            "max": 120,
        },
        "socio_economic_status": {
            "type": "categorical",
            "question": "socio_economic_status",
            "codes": [
                "below_average",
                "average",
                "above_average",
                "prefer_not_to_say",
            ],
        },
        "childhood_languages": {
            "type": "categorical",
            "question": "childhood_languages",
            "codes": ["one_language", "two_languages", "three_languages"],
        },
        "reading_time_bin": {
            "type": "ordinal",
            "question": "academic_reading_time",
            "codes": [
                {
                    "code": "0_hours",
                    "label": "0 hours",
                    "min_hours": 0,
                    "max_hours": 0,
                },
                {
                    "code": "less_than_1_hour",
                    "label": "Less than 1 hour",
                    "min_hours": 0,
                    "max_hours": 1,
                },
                {
                    "code": "1_to_3_hours",
                    "label": "1 to 3 hours",
                    "min_hours": 1,
                    "max_hours": 3,
                },
                {
                    "code": "3_to_5_hours",
                    "label": "3 to 5 hours",
                    "min_hours": 3,
                    "max_hours": 5,
                },
                {
                    "code": "more_than_5_hours",
                    "label": "More than 5 hours",
                    "min_hours": 5,
                    "max_hours": None,
                },
            ],
        },
        "tiredness": {
            "type": "ordinal",
            "question": "tiredness",
            "min": 1,
            "max": 9,
        },
        "eyewear": {
            "type": "categorical",
            "question": "eyewear",
            "codes": ["glasses", "lenses", "no"],
        },
        "alcohol": {
            "type": "categorical",
            "question": "alcohol_yesterday",
            "codes": ["no", "yes", "prefer_not_to_answer"],
        },
        "language": {
            "type": "iso639_1",
            "questions": [
                "native_language_1",
                "native_language",
                "use_language",
                "dominant_language",
                "additional_read_language",
            ],
        },
    },
}

READING_TIME_QUESTIONS = [
    "academic_reading_time",
    "magazine_reading_time",
    "newspaper_reading_time",
    "email_reading_time",
    "fiction_reading_time",
    "nonfiction_reading_time",
    "internet_reading_time",
    "other_reading_time",
]

DIRECT_FIELDS = {
    "gender": "gender",
    "level_education": "level_education",
    "socio_economic_status": "socio_economic_status",
    "childhood_languages": "childhood_languages",
    "eyewear": "eyewear",
    "alcohol_yesterday": "alcohol",
    "alcohol_today": "alcohol",
}
