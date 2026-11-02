# Codebook

This is version 2.0-dev0 of the canonical CSV codebook for the MultiplEYE metadata outputs.
It builds on Codebook 1.1 by Marie-Luise Müller and Carlson Moses Büth.

The codebook describes the fields that the pipeline delivers and the fields that EyeStore
displays. CSV is the working format and the archival format.

This README belongs to the codebook package. It is not the README for a processed data
collection. Every processed data collection also needs its own root README and CITATION.cff for
the Zenodo record.

## Files

```text
codebook/
├── fields.csv
├── views.csv
├── relations.csv
├── display_groups.csv
├── display_group_members.csv
├── semantic_categories.csv
├── codebook_info.csv
└── README.md
```

`codebook_info.csv` records the codebook version and credit. It is included in the generated
flat bundle and copied with the structured package into every processed data collection.

`fields.csv` is the variable table. It contains source form fields and pipeline output fields.
Output fields are registered in code and generated into this table. Source form fields are
curated from Codebook v1.1 and the source forms.

`views.csv` defines the five fixed EyeStore views and their keys.

`relations.csv` defines how the views connect for filtering and switching.

`display_groups.csv` defines named column presets. It is not a data filter.

`display_group_members.csv` defines which variables belong to each display group. A variable can
belong to several groups.

### How display groups work across views

The codebook has five views. Each view has a key:

| View | Key field |
| --- | --- |
| dataset | `data_collection_name` |
| session | `session_identifier` |
| trial | `trial_id` |
| participant | `participant_id` |
| item | `text_id` |

A display group is a set of `variable_id` values. When EyeStore shows a view, it displays only the
group members whose `view_level` matches that view. Members from other views are ignored.

The scope of a group is derived from its members. There is no separate view column. A group that
has members in several views is a cross-view preset. A group that has members in one view is a
single-view preset.

Every group must include the key of every view it covers. This keeps the table readable after a
view switch. For example, the `quality` group covers dataset, session and trial, so it contains
`dataset.data_collection_name`, `session.session_identifier` and `trial.trial_id`. When the user
switches from session to trial, the session key is dropped and the trial key is shown.

If a group has no member in the active view, the group does not apply. EyeStore should not offer it
for that view and should fall back to `default`. `default` contains one key for every view, so it
always applies.

The current groups are:

| Group | Views | Purpose |
| --- | --- | --- |
| `default` | all | View keys, the universal fallback |
| `collection` | dataset | Collection identity, language and coverage |
| `provenance` | dataset | Codebook, pipeline and environment |
| `reading` | dataset, session, trial, item | Reading time and text size |
| `quality` | dataset, session, trial | Calibration, validation and data loss |
| `comprehension` | dataset, session, trial, item | Scores, questions and answers |
| `hardware` | dataset, session | Eye tracker and display setup |
| `stimulus` | dataset, trial, item | Stimulus identity and text properties |
| `annotations` | dataset, item | Annotation availability and package |
| `participant_profile` | participant | Demographics and questionnaire answers |
| `participant_psychometrics` | participant | Psychometric test scores |

### Adding a display group

1. Add a row to `display_groups.csv` with a unique `group_id`, a label, a description, an integer
   `order` and a boolean `default`. Only one group may be the default.
2. Add the members to `display_group_members.csv`.
3. Include the key of every view the group covers.
4. Keep the comparison meaningful. A dataset mean, a session value and a trial value can belong to
   the same cross-view group when they describe the same concept at different levels.
5. Run `uv run python -m preprocessing.scripts.build_codebook --check`.

Validation checks that every group has at least one member, that exactly one group is the default,
and that every covered view has its key in the group.

`semantic_categories.csv` defines the one semantic category assigned to each variable.

## Why CSV

CSV is transparent, diffable and easy to validate.

A single CSV with a record type column was rejected because fields, views, relations, display
groups and group members have different schemas. One table would need many empty columns and
would be harder to validate.

EyeStore receives a generated single JSON bundle so it does not need to parse the CSV package at
runtime. The CSV package remains the archival source.

## Field naming

Variable names are short and scalar. Hierarchy lives in `view_level`, `yaml_path` and
`section_path`. A name such as `technical_setup.eye_tracker_name` is not a variable name. The
variable name is `eye_tracker_name` and the path is `technical_setup.eye_tracker_name`.

`variable_id` is the stable reference used by display groups and relations. It must be unique.

## Value metadata

Three columns describe the values of a field:

* `unit` holds the physical unit, for example `ms`, `cm`, `dva`, `year` or `day`. Units are
  derived from the field-name suffix where the name carries one. Counts, ratios, scores and
  identifiers have no unit.
* `allowed_values` holds the canonical codes for categorical and boolean fields, separated by
  commas. Boolean fields always use `true,false`.
* `value_labels` holds the display labels as `code=label` pairs separated by ` | `, for example
  `male=Male | female=Female`. Every code in `allowed_values` must have exactly one label.

Participant questionnaire fields use the canonical codes from the questionnaire codebook, never
the localised option text. Language fields have no fixed value list because the ISO 639-1
inventory is open.

Localised questionnaire labels stay in `documentation/questionnaire/pq_mapping_<lang>.yaml`.
When the questionnaire workbook is missing, that file may record a fallback and keep raw answers
in `pq_raw_*`. The codebook does not carry fallback values.

## Calculation availability

The codebook describes fields. It does not track development progress.

Each processed data collection contains an `availability.csv` file. It records whether a field
was calculated for that collection and why a field is unavailable.

The file has three columns:

```text
variable_id
available
reason
```

`available` is one of `true`, `false` or `not_applicable`. A field that is not in the overlay is
`true` by default. Every field with `false` or `not_applicable` must also have a reason. A `true`
field must not have a reason.

The allowed reason categories are:

```text
missing_source
optional_test_not_collected
annotation_pending
external
```

This keeps the codebook stable across data collections while still showing what was calculated
and what was not.

The overlay is driven by the `availability` block in the preprocessing configuration for each
collection. The block maps a `variable_id` to an availability state, or to a state and reason:

```yaml
availability:
  overrides:
    item.annotation_layers: ["false", annotation_pending]
    trial.trial_id: true
    participant.pq_age:
      available: not_applicable
      reason: optional_test_not_collected
```

The v1 annotation fields `item.annotation_layers` and `item.annotation_package` default to
`false` with reason `annotation_pending`. A collection that ships annotations overrides them in
the same block. Unknown field IDs are rejected when the package is written.

## Field registry

Output fields are registered in `preprocessing/metadata/registry/`, with one module per view.
Curated source form rows stay in `fields.csv`. The build step merges the registry with the
curated rows and validates the package.

Check the committed table:

```bash
uv run python -m preprocessing.scripts.build_codebook --check
```

Update `fields.csv` after adding or changing a registered field:

```bash
uv run python -m preprocessing.scripts.build_codebook --write
```

The validator checks field identifiers, view levels, YAML paths, semantic categories, units,
allowed values, value labels, display group members, relations and aggregation references.

## Dynamic aggregation

Aggregate fields declare how EyeStore can recompute them after filtering. The declaration uses the
`aggregation_*` columns in `fields.csv`:

* `aggregation_base_level`
* `aggregation_method`
* `aggregation_input`
* `aggregation_weight`
* `aggregation_denominator`
* `aggregation_behavior`
* `aggregation_notes`
* `dynamic_equivalent`

`aggregation_behavior` is one of `recompute_from_filtered_rows`, `precomputed_only`, `static` or
`not_applicable`. A field marked `recompute_from_filtered_rows` must declare its base level, method
and input. A `weighted_mean` field must also declare a weight.

The precomputed values stay in the YAML files for download and offline use. EyeStore recomputes
only when a filter requires it. Session aggregates use trials as the base level. Dataset aggregates
use sessions. Item aggregates use trials.

## Pipeline connection

The pipeline code registers output fields. A build step merges those registrations with the
curated source form metadata and writes the CSV package and the generated bundle.

The repository contains only the structured CSV package. Generated output is not stored here.

Every processed data collection receives this folder:

```text
preprocessed_data/<dcn>/
├── codebook.csv
└── codebook/
    ├── fields.csv
    ├── views.csv
    ├── relations.csv
    ├── display_groups.csv
    ├── display_group_members.csv
    ├── semantic_categories.csv
    ├── codebook_info.csv
    ├── environment.csv
    ├── availability.csv
    ├── README.md
    └── generated/
        ├── codebook_bundle.json
        └── codebook_bundle.zip
```

The processed data collection root also contains `codebook.csv`. This is a flat copy of
`fields.csv` with the variable definitions and no observation data. It is generated from the same
source and exists for direct discovery and FAIR reuse without opening the structured package.
The matching `codebook_info.csv` is copied into the codebook folder and included in the generated
flat bundle.

`environment.csv` records the codebook version and the pipeline, edf2asc, Python and pymovements
versions used for that processed data collection. The same information is kept in the data
collection YAML.

The `availability.csv` file records which fields were calculated for that collection and why a
field is unavailable. It is written automatically during processing. It contains one row for
every field in `fields.csv`, so the overlay always covers the full package. Fields default to
`true`. A collection marks an unavailable field explicitly with `false` or `not_applicable` and a
reason. The file is included in `codebook_bundle.zip`. The data collection YAML records the
codebook version and hash.

`codebook_bundle.json` is the single flat codebook file for EyeStore and for FAIR reuse. It
contains the resolved fields, views, relations, display groups and categories.
`codebook_bundle.zip` contains the structured CSV package, the README and the flat bundle for
offline archival.

Both generated files are produced automatically during processing or build. They are not read
back into preprocessing.

## Language tree

The canonical language tree is owned by EyeStore. The pipeline stores the selected language node
ID, the full path to the node and the tree version or hash in the data collection YAML. A pinned
tree snapshot can be copied for offline use.

Do not parse session identifiers to derive language, country or city. Those are separate fields.
