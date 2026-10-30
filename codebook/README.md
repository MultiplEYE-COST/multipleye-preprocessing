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

## Calculation availability

The codebook describes fields. It does not track development progress.

Each processed data collection contains an `availability.csv` file. It records whether a field
was calculated for that collection and why a field is unavailable. Reasons can be a missing
source, an optional test that was not collected or an annotation package that is still pending.

This keeps the codebook stable across data collections while still showing what was calculated
and what was not.

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

The validator checks field identifiers, view levels, YAML paths, semantic categories,
display group members, relations and aggregation references.

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
field is unavailable. The data collection YAML records the codebook version and hash.

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
