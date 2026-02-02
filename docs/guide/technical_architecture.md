(technical_architecture)=

# Technical Architecture

This section provides detailed technical specifications of the MultiplEYE preprocessing pipeline.
For user-facing instructions on how to run the preprocessing, please refer to the {ref}
`preprocessing_guide`.

(multiplEYE_data_structure)=

## The MultiplEYE Data Structure

Each MultiplEYE dataset contains the data for one language. The eye-tracking data is organised by
session. The stimulus information is available in a separate folder containing the aoi files for
each stimulus.

```text
MultiplEYE__languageISOcode]__countryISOcode]__city]__identifier]__yearDataCollectionEnd]
├── eye-tracking-sessions
│   ├── 001_…_…_…_ET1
│   │   ├── ….edf
│   │   └── ….asc
│   ├── 002_…_…_…_ET1
│   ├── 005_…_…_…_ET1
│   ├── pilot_sessions
│   │   └── …
│   └── test_sessions
│       └── …
└── stimuli_MultiplEYE__languageISOcode]__countryISOcode]__city]__identifier]__yearDataCollectionEnd]
    └── aoi__languageISOcode]__countryISOcode]__identifier]
        ├── _stimulus-name-id]_aoi.csv
        ├── _stimulus-name-id]_aoi_questions.csv
        └── …
```

### A Session Folder

Each session folder contains the raw files in .edf and .asc format in addition to some other files
that are not relevant for the preprocessing pipeline.

```text
001_…_…_…_ET1
├── _3-digit-P-ID]_languageISOcode]_countryISOcode]_identifier].asc
├── _3-digit-P-ID]_languageISOcode]_countryISOcode]_identifier].edf
├── …
```

### Preprocessing Pipeline Philosophy

The MultiplEYE preprocessing pipeline (and most pipelines) is applied on a **session-level.**
Settings can change between sessions. Each session should be summarised on session- and trial-level.
Information at the dataset-level is not relevant at this stage. This will only become relevant once
the data is published and all sessions have been preprocessed.

The initial input is the original gaze file, including some metadata on the session (experiment
details). The output from the previous step is always the input to the next step. However, each step
requires the specification of further input (i.e. parameters etc.) that has to be chosen by the
user on a session level!

Note that the **participant ID** is a three-digit number and the **session identifier** contains the
participant id including a language code, country code, and lab identifier. P-IDs are unique only
within a given dataset while session identifiers are unique across all MultiplEYE datasets. This
means that all MultipEYE sessions can be preprocessed in one go. In a MultiplEYE context these two
terms are occasionally used interchangeably in a less formal context.

(preprocessing_steps)=

## Preprocessing Pipeline Steps

(preprocessing_step_1)=

### Step 1: Parse .asc File into Sample .csv and Metadata

Input: .asc (eyelink specific, different for other devices) file containing samples and metadata
about the session (i.e. sampling frequency, eye-to-screen distance).
Output: .csv sample files and metadata .json files (content specified below) **split by trial (all
pages) and session**.

The (unstructured) .asc file should be parsed into a cleaned .csv file containing the gaze samples
and several metadata .json documents that contain all information found in the .asc file in addition
to the metadata provided as input.

#### Input Metadata at the Session Level

- Lab configuration
    - sampling frequency
    - eye-to-screen distance
    - resolution in px
    - screen size in mm
    - eye-tracker
    - *… tbd*

(step_1_file_formats)=

#### File Formats

(step_1_samples)=

##### Samples

Filename: p-id_stimulus-id_*samples*.csv

The samples file contains timestamp, pixel x, pixel y, pupil area/diameter, and page
number/identifier.

(step_1_metadata)=

##### Metadata

The metadata should be extracted on trial- and session-level.

Trial-level
*TBD: one file contains all trials (preferred) or one file per trial*

- stimulus item
- reading time
- answers to all 6 comprehension questions
- answers to all 3 rating questions
- last validation before stimulus + scores
- blinks (?)

Session-level
Filename: session-id_metadata.json

- trial-id to stimulus-id mapping inferred from .asc
- calibrations
    - total number
    - timestamps
- validations
    - scores for each
    - timestamps
    - total number
- number of (completed) trials
- number of pages read
- initial calibration (yes or no), i.e. before the first trial
- final validation, i.e. after the last trial
- lab config (can be different for a session within one dataset)
    - sampling frequency
    - tracked eye
    - eye-to-screen distance
    - device
    - …
- reading time
- time spent in breaks / non-reading
- stimuli (=> aoi files + stimulus metadata)
    - e.g. whether annotations are available, which
    -

(step_1_sanity_checks)=

#### Sanity Checks to be Performed

Input sampling frequency should match the found sampling frequency.
In general, lab settings provided should match what is found in the data files.

(step_1_data_quality_reports)=

#### Data Quality Reports

Data quality reports should be generated to validate the parsing process. ...

(preprocessing_step_2)=

### Step 2: Detect Gaze Events (Fixations and Saccades)

Input: sample .csv for each session and trial (not eyelink specific any more).
Output: gaze events .csv (this is ideal for reading) → both fixations and saccades in one file.

Detection of gaze events (fixation and saccades). The fixations and saccades should be in one file
containing features for both. The saccade features are mapped to the fixation before and after the
saccades. This will lead to some redundancies, but from a user perspective this is the ideal format.

It should be possible to adjust parameters for each individual session. That is, one function call
for each session. Which fixation and saccade features are calculated can be selected by user.

(step_2_file_formats)=

#### File Formats

Fixations and saccades are in ONE file, saccades are basically a feature of fixations, one line is
one fixation. Filename: p-id_stimulus-id_*events*.csv.

- fixation duration
- location x
- location y
- location std/stability
- incoming saccade duration
- outgoing saccade duration
- saccade length in px (for incoming and outgoing, also features below)
- saccade peak velocity (inc. & out.)
- saccade mean velocity (inc. & out.)
- s. peak acceleration (inc. & out.)
- s. mean acceleration (inc. & out.)
- blink before
- blink after

(step_2_sanity_checks)=

#### Sanity Checks to be Performed

Sanity checks should be performed to validate the event detection process. ...

(step_2_data_quality_reports)=

#### Data Quality Reports

Data quality reports should report data loss, everything that occurs during the detection of the
fixations that are not normal, RMS-S2 (for fixations) or median RMS-S2 (including saccades), and
check fixations on the bottom right dot (precision).

(preprocessing_step_3a)=

### Step 3a: AOI Mapping

Input: gaze event .csv + aoi files from the stimulus folder.
Output: fix indices mapped to word and char index.

Fixations are mapped to words and characters. Can be index based at this point and later be merged
with the actual characters and words.

(step_3a_file_formats)=

#### File Formats

Filename: p-id_stimulus-id_*aoi-mapping*.csv.

- fixation index
- char index
- word index
- line index
- incoming saccade landing position in character index in word == outgoing!
- incoming length in characters
- outgoing saccade length in characters

(step_3a_data_quality_reports)=

#### Data Quality Reports

Data quality reports should include aoi dwell time and proportion time on aoi/time on a background.

(step_3a_sanity_checks)=

#### Sanity Checks to be Performed

Sanity checks should be performed to validate the AOI mapping process.

(preprocessing_step_3b)=

### Step 3b: Scanpaths

Input: gaze events .csv and aoi mapping.
Output: gaze events + aois + other features (optional).

The goal is to have the fixations + the words and the character, line index, etc. in ONE file.
In addition, there should be some other features about the user, the experiment, the text, etc.
It should be possible to generate more minimalistic versions and more extensive versions of this.

(step_3b_file_formats)=

#### File Formats

Filename: p-id_stimulus-id_*events*.csv.

The file contains columns from aoi mapping + columns from fixations.

(step_3b_sanity_checks)=

#### Sanity Checks to be Performed

Sanity checks should be performed to validate the scanpath generation.

(step_3b_data_quality_reports)=

#### Data Quality Reports

Data quality reports should be generated to validate the scanpath process.

(preprocessing_step_4)=

### Step 4: Calculate Reading Measures / AOI-based Measures

Input: scanpath files (see above) + aoi files.
Output: .csv file for each session and trial containing reading measures and minimal information on
participant.

Reading measures (also called aoi-base measures, which is more general) are calculated on a word (or
general aoi-based) basis. In the case of reading, this means that for each word in the stimulus
texts, a set of measures is calculated. A list of common reading measures and their definition can
be found
here: [https://link.springer.com/article/10.3758/s13428-024-02536-8/tables/12](https://link.springer.com/article/10.3758/s13428-024-02536-8/tables/12)

(step_4_file_formats)=

#### File Formats

Filename: p-id_stimulus-id_*aoi-measures*.csv.

- word index
- _word] → this is not always necessary and heavily depends on copyright etc., but in any case it
  can be merged with the aois
- word-level annotation (i.e. word index in sentence, pos-tag, … line num.. )
- all reading measures from the table linked above

(step_4_sanity_checks)=

#### Sanity Checks to be Performed

Sanity checks should verify that total fixations durations are within an expected range and check
for outliers.

(step_4_data_quality_reports)=

#### Data Quality Reports

Data quality reports should include calculated word length effects, surprisal effects, and other
relevant metrics.

(output_folder_structure)=

## Output Folder Structure

By default, files should be written to the session folder the .asc file was taken from. But it
should be possible to change the path so that the files can be written to a folder containing only
the output data from the specific preprocessing step (i.e. fixations).

(the default now is another folder)
