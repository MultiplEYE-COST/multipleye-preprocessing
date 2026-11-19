(review_app)=

# Review App

The review app is a local web interface for inspecting processed data collections and recording
quality reviews. It reads everything from `preprocessed_data/` and is driven by the codebook
package that is copied into each collection.

The app does not replace EyeStore. EyeStore receives the codebook and metadata YAML files. The
review app has access to the full processed collection, including sanity-check plots, reading
measures, answers and psychometric results.

## Running the app

Install the review extra and start the server:

```bash
uv sync --extra review
uv run review_web
```

The app binds to `127.0.0.1` on the first free port from `8765` and opens a browser tab. Set
`PREPROCESSED_DATA_DIR`, `RAW_DATA_DIR` and `REVIEW_DATA_DIR` to point at other locations. The
preprocessed directory defaults to `preprocessed_data/` in the repository root.

## Views

The collection page has five views. They are fixed:

- Dataset
- Session
- Trial
- Participant
- Item

The view names and keys come from `codebook/views.csv`. Columns are display-group presets from
`codebook/display_groups.csv` and `display_group_members.csv`. Field labels, descriptions,
units, allowed values and value labels come from `fields.csv`. The app does not keep a separate
hardcoded field registry.

Membership is evaluated against the union of processed collections. A field that exists in
another collection but not the current one is shown as unavailable. Availability comes from the
collection's `codebook/availability.csv`.

## Navigation and filters

The five views share one table. Switching a tab or display group updates the table without a full
page reload and updates the URL. Reloading or sharing the URL restores the view, group, search,
filters and page.

Filters are stored as `f` query parameters, for example:

```text
?f=dataset.administrative.country:eq:IT
```

Filters are mapped across views through the codebook relations. Dataset and session filters
restrict child views. Trial filters restrict their parent sessions and participants by matching
related trials. Dynamic recomputation of aggregate values after filtering is a later EyeStore
feature; the review app applies filters to the selected rows.

Session rows open the session review page with checks, gaze plots and the review form. Trial,
participant and item rows open detail pages with every codebook field for that view and links to
related records.

## Quality checks

Session checks use the codebook's session fields and `quality_thresholds.yaml`. Every threshold
entry is resolved to a codebook variable. The threshold comparator still supports ranges, scalar
upper bounds, list membership and exact strings. Fields in the session `quality` display group
are shown without a pass/fail status when no threshold is configured.

## Review data

Reviews are stored outside the processed collection:

```text
review_data/<dcn>/reviews.yaml
review_data/<dcn>/swipe_judgments.yaml
review_data/<dcn>/preflight_result.yaml
```

The review workflow and plot judgments are app-specific and are not part of the codebook.
