(participant_questionnaire)=

# Participant Questionnaire

The participant questionnaire (`{base_id}_pq_data.json`) is normalised against a
language-independent codebook. The pipeline contains no per-language code: each data collection
supplies its questionnaire workbook and language list, and the localised label mapping is
generated at runtime. The codebook and the generated mapping are written to the output folder so
the normalised values can be interpreted later.

## Input files

Place these in the data collection folder, for example in
`participant_questionnaire_<lang>_<country>_<lab>/`, or under
`documentation/questionnaire/`:

- `multipleye_questionnaire_questions_<lang>.xlsx`: question identifiers and localised answer
  options.
- `language_iso639_1_<lang>.xlsx`: `language_code` and `language_name` for the language questions.

Both files are copied to
`preprocessed_data/<data_collection_id>/documentation/questionnaire/`.

## Questionnaire output files

```text
preprocessed_data/<data_collection_id>/documentation/questionnaire/
├── pq_codebook.yaml
├── pq_mapping_<lang>.yaml
├── multipleye_questionnaire_questions_<lang>.xlsx
└── language_iso639_1_<lang>.xlsx
```

`pq_codebook.yaml` is language-independent and uses English-derived codes.
`pq_mapping_<lang>.yaml` maps the localised labels to those codes.

## Codebook (excerpt)

```yaml
schema_version: 1
canonical_language: en
fields:
  gender:
    type: categorical
    question: gender
    codes: [male, female, other, prefer_not_to_say]
  years_education:
    type: integer
    question: years_education
    min: 1
    max: 20
    open_ended:
      code: greater_than_20
      label: More than 20 years
  reading_time_bin:
    type: ordinal
    question: academic_reading_time
    codes:
      - {code: 0_hours, label: 0 hours, min_hours: 0, max_hours: 0}
      - {code: less_than_1_hour, label: Less than 1 hour, min_hours: 0, max_hours: 1}
      - {code: 1_to_3_hours, label: 1 to 3 hours, min_hours: 1, max_hours: 3}
      - {code: 3_to_5_hours, label: 3 to 5 hours, min_hours: 3, max_hours: 5}
      - {code: more_than_5_hours, label: More than 5 hours, min_hours: 5, max_hours: null}
  language:
    type: iso639_1
    questions:
      - native_language_1
      - native_language
      - use_language
      - dominant_language
      - additional_read_language
```

## Per-language mapping (excerpt)

```yaml
language: zd
fallback: false
labels:
  gender:
    männlich: male
    weiblich: female
    divers: other
    keine angabe: prefer_not_to_say
  years_education:
    ">20 jahre": greater_than_20
  reading_time_bin:
    0 stunden: 0_hours
    weniger als 1 stunde: less_than_1_hour
    1 bis 3 stunden: 1_to_3_hours
    3 bis 5 stunden: 3_to_5_hours
    mehr als 5 stunden: more_than_5_hours
languages:
  deutsch: de
  englisch: en
  dänisch: da
issues: []
```

For English, `pq_mapping_en.yaml` mirrors the codebook's English labels. It is still written so
every data collection has the same output files; the labels are mapped to the canonical codes
(for example `0 hours` -> `0_hours`).

## Normalised columns

Normalised values use `pq_*`; every raw key is kept as `pq_raw_*` during the transition.

| raw value | normalised column | value |
|---|---|---|
| `femeie` | `pq_gender` | `female` |
| `weiblich` | `pq_gender` | `female` |
| `Învățământ secundar superior` | `pq_level_education` | `upper_secondary` |
| `o singură limbă` | `pq_childhood_languages` | `one_language` |
| `română` | `pq_native_language_1` | `ro` |
| `Deutsch` | `pq_native_language_1` | `de` |
| `1 bis 3 Stunden` | `pq_native_language_1_academic_reading_time` | `1_to_3_hours` |
| `7 - somnoros, ...` | `pq_tiredness` | `7` |

Interval fields are stored as numbers: `pq_age` and `pq_years_education` are integers. The
open-ended `>20` option sets `pq_years_education_open_ended` instead of a numeric value.
Reading-time bins use self-descriptive codes; their bounds are documented in `pq_codebook.yaml`.
`pq_raw_*` is kept even when it equals the normalised value (common for English) so the original
labels remain available during the transition.

## Language fields

Language values are mapped to ISO 639-1 through the language list. The lookup order is:

1. `language_iso639_1_<lang>.xlsx` for the data collection language.
2. The list referenced by the questionnaire's `dropdown_file` question (for example French uses
   `language_iso639_1_en.xlsx`).
3. Any `language_iso639_1_*.xlsx` found next to the questionnaire.

If no language list is available and fallback is enabled, the localised name is kept in the
language of the processed data collection instead of an ISO code.

## Missing files and fallback

By default a missing questionnaire or language file is a preflight error that names the expected
path in the data collection folder. Set the following in the configuration to continue without
them:

```yaml
allow_pq_fallback: true
```

The missing file then becomes a warning, raw values are kept in `pq_raw_*`, and a mapping stub with
a `# FALLBACK` header is written to the output folder.

## Participants without eye tracking

The raw PQ file is located with `find_pq_data`, which searches the ET session folder first and
then `participant_questionnaire_*`. Filenames may use a short (`6_...`) or padded (`006_...`) PID.
This makes the normaliser usable for participants who only have questionnaire or psychometric
test data.
