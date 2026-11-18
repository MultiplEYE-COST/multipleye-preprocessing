# Using the pEYEpline with datasets other than MultiplEYE

(custom_datasets_guide)=

To process a dataset that is not MultiplEYE/MeRID, a dataset creator fills in a small set of
plain-text template files rather than writing code. These live alongside the raw data, under
`data/<dataset_name>/`. Alongside processing MultiplEYE-style datasets, we offer this very simple interface
to process generic datasets. It is always possible to write a custom data collection class in Python,
but this is not necessary for most datasets.

## Required files

| File | Purpose |
| --- | --- |
| `eye-tracking-sessions/` | The raw recordings. This location is fixed -- the pipeline does not look elsewhere for session data. |
| `documentation/lab_config.yaml` | The recording setup: eye tracker model, sampling rate, screen/image resolution and size, and viewing distance. Needed to convert raw gaze coordinates into degrees of visual angle. |
| `documentation/metadata_form.yaml` | Descriptive/administrative information (institution, contact, language details, technical setup) used to build the dataset overview. |
| `documentation/preflight_spec.yaml` | Declares, by filename/pattern, which files must exist at the dataset level and per session before processing starts. |

A worked example of all three documentation files, filled in for the PoTeC dataset, is available
under `data/PoTeC/documentation/`.

## Optional: the experimenter documentation sheet

An experimenter documentation sheet is a log of what happened during each session (dominant eye,
calibration/validation notes, breaks, interruptions, technical issues, free-text comments). This sheet
was used for MultiplEYE and MeRID and can be reused for other data collections. It includes notes and several
hardware and calibration details which are sometimes reduandant with the metadata form,
but it is useful for cross-checking what was planned/administered against what was actually recorded. It
also includes information on the dominant eye of a participant, if the test was conducted and the result recorded.

**It is optional**: the pipeline runs without one. Without it:

- the dominant-eye lookup falls back to `"unknown"` instead of using the experimenter's record,
- the sheet-based cross-checks (do the sessions found on disk match what the sheet says was
  planned/administered?) are skipped.

Everything else in the pipeline is unaffected.

The template is
available in both a print-out version and a digital version from the MultiplEYE
[Forms and Documentation Hub](https://multipleye.eu/forms-and-documentation-hub/). Documents 8 and 9.
