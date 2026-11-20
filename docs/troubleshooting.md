(troubleshooting_anchor)=

# Troubleshooting

This page lists all errors that can occur when running the pEYEpline. Most of them can be easily
solved. For some cases,
we recommend contacting the MultiplEYE team. Whenever you encounter an error, we ask you to check
this list first and
try to follow the instructions.

Please note that this page is under construction. It will be continually updated. If you encounter
an error that is not
on this list, please reach out.


---

```{eval-rst}
.. raw:: html

   <div class="faq-search-container">
       <input type="text" id="faq-search" placeholder="Search troubleshooting entries...">
   </div>
```

(errors_setup)=

## Setup and Data Folder Errors

:::{dropdown} CONFIGURATION REQUIRED: No configuration file was found.

The pipeline could not find a settings file. It creates a template named
`multipleye_settings_preprocessing.yaml` in the current working directory and stops before
processing any data. This is expected on the first run.

**What to do:**

- **Edit the template:** Open the generated file and set at least `data_collection_name` to your
  real collection name.
- **Use an explicit path:** Pass `--config_path path/to/your_config.yaml` to `run_preprocessing`,
  or set the `MULTIPLEYE_CONFIG` environment variable.
- **Check the working directory:** The default file is only found in the directory from which you
  run the pipeline, not in a parent directory.
- **Check the error text for `Config file not found: [Path]`:** This variant means an explicit
  path is wrong or the file was moved.

:::

:::{dropdown} INVALID CONFIGURATION: Invalid DATA_COLLECTION_NAME: 'REPLACE_WITH_YOUR_COLLECTION_NAME'.

The settings file still contains the placeholder from the template. The pipeline stops because it
cannot build data and output paths from a placeholder name.

**What to do:**

- **Set the real name:** Replace the placeholder with the collection name assigned by the
  MultiplEYE project.
- **Keep the six-part format:** Use `MultiplEYE_[LANG]_[COUNTRY]_[CITY]_[LAB_NO]_[YEAR]`, for
  example `MultiplEYE_EN_UK_London_1_2026`.
- **Rerun the pipeline:** The new name is validated when the settings are loaded.

:::

:::{dropdown} FileNotFoundError: The data collection folder '[DCN]' was not found in '[Path]'.

The raw data folder for the configured collection does not exist. It is also raised as
`Data folder [Path] does not exist. Please make sure to download the data and place it in the
correct folder.` by the main script.

**What to do:**

- **Download the full folder:** Make sure the complete protected folder was downloaded, not only
  individual files.
- **Extract the archive:** If the download produced a `.tar`, `.tar.gz` or `.zip` file, extract it
  so the collection folder itself, and not only the archive, is present.
- **Match the folder name:** The folder name must equal `data_collection_name` exactly, including
  language, country, city, lab number and year.
- **Check the location:** By default the folder belongs in `data/` in the repository. If you
  changed `dataset_dir`, confirm that it points to the folder containing the collection.

:::

:::{dropdown} FileNotFoundError: The data collection folder '[DCN]' exists but appears to be empty (or only contains log files).

The folder exists, but it has no usable entries besides hidden files and a preprocessing log.
This usually means an archive was extracted into the wrong level or the upload is incomplete.

**What to do:**

- **Look inside the folder:** You should see `eye-tracking-sessions/`, a stimulus folder, and
  usually `documentation/` and `psychometric-tests-sessions/`.
- **Extract one level higher:** Archive tools sometimes create
  `[DCN]/[DCN]/...`. Move the inner collection contents up so the expected folders are directly
  inside the collection folder.
- **Re-download if needed:** If expected folders are missing, request a fresh copy of the data
  collection.

:::

:::{dropdown} ValueError: Invalid data collection name: [Name]. Invalid data collection name format: '[Name]'. Expected 6 parts separated by '_'.

The configured folder name does not follow the MultiplEYE collection naming scheme. Related
messages identify the failing part, for example `Invalid language code: ... Must be 2 uppercase
letters.`, `Invalid country code`, `Invalid city`, `Invalid lab`, `Invalid year` or
`Invalid prefix: ... Must be 'MultiplEYE'.`

**What to do:**

- **Use the assigned name:** Copy the collection name from the MultiplEYE project instead of
  inventing one.
- **Check each part:** The format is `MultiplEYE_LANG_COUNTRY_CITY_LAB_YEAR`. Language and country
  are two uppercase letters, city and lab are alphanumeric, and the year is four digits.
- **Avoid extra separators:** Underscores inside the city or lab name split the name into too many
  parts.

:::

:::{dropdown} ValueError: Invalid experiment type: [Type]. Supported types: [MultiplEYE, MeRID]

The `experiment_type` setting contains an unsupported value.

**What to do:**

- **Use a supported value:** Set `experiment_type` to `MultiplEYE` or `MeRID`, matching the case
  used in the template.
- **Check for hidden characters:** Remove quotes, spaces or trailing comments that were copied
  into the value.

:::

:::{dropdown} ValueError: Eye tracker '[Name]' is not supported. Supported models are: ... Did you mean: ...?

The `Name_eye-tracker` value in the lab configuration JSON could not be mapped to a supported
model. Common spellings are normalized, so this is usually a typo or an unsupported device.

**What to do:**

- **Use a supported model:** `EyeLink 1000`, `EyeLink 1000 Plus`, `EyeLink II` or
  `EyeLink Portable Duo`.
- **Follow the suggestion:** If the message contains `Did you mean: ...?`, use that spelling.
- **Check the lab configuration:** The value is read from
  `config/MultiplEYE_<lang>_<country>_<city>_<lab>_<year>_lab_configuration.json` in the stimulus
  folder. Correct it there, or ask the team for a corrected stimulus package.
- **Do not invent a new model name:** A new eye-tracker model needs support in the pipeline.

:::

:::{dropdown} RuntimeError: The 'edf2asc' binary was not found on your system.

The pipeline needs the EyeLink `edf2asc` utility to convert `.edf` files to `.asc`, but it is not
on the `PATH`. The binary cannot be bundled because it is distributed by SR Research.

**What to do:**

- **Install the EyeLink Developers Kit:** Follow the installation instructions in
  {ref}`eyelink_dev_kit`.
- **Check the binary:** Run `edf2asc` in a terminal. It should print its version and usage
  information.
- **Restart the terminal:** `PATH` changes only take effect in new shells.
- **Rerun with reconversion if necessary:** Set `force_reconvert_asc: true` only when an earlier
  conversion produced incomplete files.
- **If only one session failed:** The log may contain
  `Failed to convert EDF to ASC for [Session]. Only processing comprehension answers.` In that
  case check that the `.edf` is not truncated, that the disk is not full, and that you can convert
  the file manually with `edf2asc`. The session still contributes comprehension answers but no
  eye-tracking outputs.

:::

:::{dropdown} FileNotFoundError: The 'eye-tracking-sessions' folder does not exist in '[Path]'.

The collection folder has no `eye-tracking-sessions/` directory. The session archives were
probably not unpacked, or they were unpacked into a nested folder.

**What to do:**

- **Unpack the session archives:** Extract the session archives in the cleaning step. The
  pipeline does not unpack session archives for you.
- **Flatten the structure:** Session folders must sit directly under
  `eye-tracking-sessions/`. Move folders out of `core_sessions/`, `core_dataset/` or similar
  nested folders.
- **Check the log for archive names:** If archives with the expected name are still present, the
  message names them. Unpack those first.

:::

:::{dropdown} FileNotFoundError: The stimulus config folder not found in '[Path]'.

A stimulus folder exists, but it has no `config/` subfolder. The stimulus package is incomplete or
was only partially extracted. A related assertion reports
`AssertionError: Found [N] stimulus config files: [...]. Please check that the stimulus folder exists.`

**What to do:**

- **Extract the complete package:** The stimulus folder must contain its `config/` folder, not only
  images or AOI files.
- **Check for duplicates:** There must be exactly one
  `config_<lang>_<country>_<city>_<lab>_<year>.py` file in `config/`. Remove backup copies or old
  versions from the same folder.
- **Check the version folder:** If you use `stimulus_versions`, the failing path names the version
  folder. Make sure the correct version package was extracted with the same suffix.

:::

:::{dropdown} ValueError: Unexpected number of AOI files ([N]) found in '[Path]'. Expected 12 (not split) or 24 (already split into texts and questions).

The AOI staging folder contains an unexpected number of CSV files. The preparation step expects
either the 12 original AOI files or the 24 split text and question files. Extra files, partial
copies or a previously interrupted preparation commonly cause this.

**What to do:**

- **Compare with the source package:** The source `aoi_stimuli_<lang>_<country>_<lab>/` folder
  should contain 12 CSV files.
- **Remove stray files:** Delete temporary CSVs and backup copies that do not belong to the
  package. Leave the `.fixed` marker alone unless you delete the whole staged folder.
- **Reset the staged folder:** Delete the prepared
  `preprocessed_data/<dcn>/stimuli_<dcn>/aoi_stimuli_<lang>_<country>_<lab>/` folder and rerun the
  preparation step.
- **Do not rename AOI files:** The file names and suffixes carry the stimulus and question
  assignment.

:::

:::{dropdown} ValueError: Missing required AOI columns: [...]

An AOI file is missing one or more coordinate or identifier columns needed to map fixations. The
pipeline normally splits and repairs the official AOI files during preparation, so this usually
means the source package is incomplete or was edited.

**What to do:**

- **Check the source AOI file:** The official file should contain page, line, word and character
  identifiers plus the AOI bounds.
- **Restore the original file:** Do not reconstruct AOI coordinates by hand.
- **Clear the staged copy:** Delete the prepared AOI folder in the output stimulus directory and
  rerun the preparation step so the source is copied again.
- **Ask the team for a corrected stimulus package if the source is malformed.**
- **Related messages:** `Source AOI path [Path] does not exist.` and
  `No AOI files found in '[Path]'.` mean the folder was not copied or is empty.
  `ValueError: AOIs DataFrame must not be empty` means the file has no AOI rows.

:::

:::{dropdown} KeyError: 'Name_eye-tracker'

The lab configuration JSON is missing a required key, or the Python stimulus config is missing a
required constant. The pipeline needs the eye-tracker name, screen resolution, screen size,
viewing distance and image geometry to interpret gaze coordinates.

**What to do:**

- **Check the lab configuration JSON:** Confirm that it contains `Name_eye-tracker` and the
  `Psychometric_tests` object, if tests were collected.
- **Check the Python config:** Constants such as `RESOLUTION`, `SCREEN_SIZE_CM`, `DISTANCE_CM`,
  `IMAGE_WIDTH_PX` and `IMAGE_HEIGHT_PX` must be present in the stimulus config file. Missing
  constants surface as an `AttributeError` naming the missing constant.
- **Ask for a corrected package:** These files are part of the stimulus upload and should not be
  reconstructed from memory.

:::

:::{dropdown} ValueError: data_collection_name is None. Please provide a valid data collection name as an argument or load a configuration via settings.load().

The preparation step was called without a collection name. This happens in notebooks or scripts
that do not load the settings file first.

**What to do:**

- **Load the settings:** Call `settings.load("path/to/your_config.yaml")` before preparing the
  folder.
- **Pass the name explicitly:** Call `prepare_language_folder("MultiplEYE_EN_UK_London_1_2026")`
  with the full collection name.
- **Use the CLI:** `run_preprocessing` loads the settings before it calls the preparation step.

:::

:::{dropdown} Stimulus assets have changed and are being recopied. Note that some outputs may be based on a previous stimuli version.

The source stimulus folder no longer matches the copy used for the last run. The preparation step
replaces the copied assets, but existing outputs were calculated with the previous stimuli.

**What to do:**

- **Check what changed:** A corrected upload, renamed file or new AOI version changes the checksum.
- **Recalculate the affected sessions:** Set `recalculate: true` so scanpaths and reading measures
  use the new AOIs and images.
- **Check the dataset overview:** The processing configuration records the run settings.
- **Do not mix outputs from different stimulus versions in one analysis.**

:::

---

(errors_processing)=

## Eye-tracking Data Processing Errors
:::{dropdown} ValueError: Both 'included_sessions' and 'excluded_sessions' are provided and not empty.

This error occurs when you have both `include_sessions` and `exclude_sessions` defined in your
configuration file (i.e. `multipleye_settings_preprocessing.yaml`). The pEYEpline only supports
using one type of filter at a time to avoid ambiguity.

**What to do:**

- **Decide on a Filter Type:** Determine if you want to use a whitelist (only process specific
  sessions)
  or a blacklist (skip specific sessions).
- **Update Configuration:**
    - If you want to process **only specific sessions**, fill `include_sessions` and leave
      `exclude_sessions` empty (i.e. `exclude_sessions: []`).
    - If you want to **skip specific sessions**, fill `exclude_sessions` and leave
      `include_sessions` empty (i.e. `include_sessions: []`).
    - If you want to process **all sessions**, leave both lists empty.

:::


:::{dropdown} ValueError: The reading times could not be computed properly for [Session]. Please check 1) if the completed stimulus file is alright (i.e. completed should be 1 for all, no missing values, etc.), 2) if anything happened during the session (crash or technical errors, e.g. check the end of the asc file if it looks normal), 3) contact the support team.

This error occurs when the reading times cannot be computed properly. As already indicated in the error message, there are a few things you can check:

**What to do:**
- **Completed Stimulus File:** Check the `completed_stimuli.csv` file for the session in question. Ensure that:
   - The `completed` column has a value of `1` for all rows, indicating that all stimuli were completed. If the last stimulus has a `0`,
  it means the session was ended unexpectedly, and the reading times cannot be computed. If this is the case, please confirm in the .asc file for this session that the message "show_final_screen" is really missing.
- **Check the documentation for the session:** Check the experimenter session documentation for any noteworthy points or mentions of technical failures during that specific session.
- **Contact Support:** If you have verified the above, please reach out to the MultiplEYE support team with details about the session and any findings from your checks.
- **Exclude Session:** If the session is indeed corrupted and cannot be processed, you can exclude it from processing by adding it to the `exclude_sessions` list in your configuration file.

:::

:::{dropdown} ValueError: No files found in folder [Session] that match the pattern .edf

The folder for the session does not contain any .edf files. Most likely this means the file has not been correctly transferred. The current pipeline reports the same condition at runtime as
`No EDF file found for [Session], only parsing comprehension answers.` and in the preflight check as
`PreflightError: EDF data file` followed by the session ID. The session is then processed for
comprehension answers only.

**What to do:**
- **Experimenter script**: if this is your own data collection, please make sure that all experimenters know that they should check for the presence of the .edf files
after each session and that they should transfer them to the server as soon as possible and make sure they are uploaded correctly.
- **Contact the experimenters**: If you are processing data that was collected by someone else, please reach out to the experimenters and ask them to check if the .edf files are present
on their local machines and if they can be transferred to the server. If the files were lost or corrupted, you may need to exclude this session from processing.
- **Check the conversion log:** If the EDF exists but no ASC was produced, look for
  `Failed to convert EDF to ASC for [Session].` and convert the file manually with `edf2asc`.
- **Accept the partial session:** If no eye-tracking data were recorded, the comprehension answers
  are still useful.
:::

:::{dropdown} ValueError: No sessions found (or none matching the ex-/inclusion criteria) in data folder [Path]

The pipeline found no folder that it recognizes as an eye-tracking session. The related message
`No sessions found in [Path].` has the same cause. Typical reasons are a missing
`eye-tracking-sessions/` level, a renamed session folder, or session filters that remove every
session.

**What to do:**

- **Check the folder level:** Session folders must be directly inside
  `eye-tracking-sessions/`, not inside `core_sessions/`, `core_dataset/` or an extracted archive
  folder.
- **Check the names:** Session folders must look like `003_EN_UK_1_ET1` or
  `003_EN_UK_1_PT1`, matching the language, country and lab number of the collection.
- **Check the filters:** If `include_sessions` is not empty, only the listed sessions are kept.
  If `exclude_sessions` is not empty, the listed sessions are removed.
- **Check pilot data:** Pilot sessions are only considered when `include_pilots: true`.
- **Read the warnings above the error:** The log lists folders that were skipped because they do
  not match the session naming pattern.

:::

:::{dropdown} ValueError: More than one file found in folder [Session] that match the pattern .edf

The session folder contains more than one `.edf` file. The pipeline cannot tell which recording is
the real session.

**What to do:**

- **Keep one EDF:** Move backups, renamed copies and test recordings out of the session folder.
- **Do not rename the real EDF:** The file name must stay consistent with the session identifier.
- **Ask the team if unsure:** If you cannot tell which file belongs to the session, ask the
  experimenters before deleting anything.

:::

:::{dropdown} Folder in eye-tracking-sessions '[Folder]' does not match the eye-tracking session regex pattern [Pattern]. Not considered an eye-tracking session.

A folder in `eye-tracking-sessions/` does not follow the expected session naming scheme, so it is
ignored. Related warnings report duplicate or pilot sessions, for example
`Skipping pilot session '[Session]' - a core session with the same identifier already exists.` and
`Removed duplicate session identifiers: [...]`.

**What to do:**

- **Rename the folder:** Use the session identifier from the experiment, for example
  `003_EN_UK_1_ET1`.
- **Remove unrelated folders:** Documentation, scripts and test folders do not belong in
  `eye-tracking-sessions/`.
- **Check pilot duplicates:** A pilot session with the same identifier as a core session is
  skipped in favour of the core session. Rename the pilot if both should be kept.
- **Check the log:** The pattern in the warning shows exactly which part of the name did not
  match.

:::

:::{dropdown} The following sessions were specified in 'include_sessions' but were not found in the data folder: [...]

A session listed in `include_sessions` or `exclude_sessions` does not exist under
`eye-tracking-sessions/`. The pipeline warns and continues with the sessions it did find. This is
usually a typo, a stale entry, or a session that is stored under a different name.

**What to do:**

- **Compare the full session ID:** Copy the folder name exactly, including the `ET1` or `PT1`
  suffix.
- **Check the filters:** A session cannot be both included and excluded.
- **Remove stale entries:** Delete IDs that are no longer part of the collection.
- **Check pilots:** A pilot session only matches when it is found in the pilot folder and
  `include_pilots` is enabled.

:::

:::{dropdown} ValueError: Could not find question order version in [Path].

The general logfile does not contain the marker that records the question order version. The
file may be truncated, may come from a different experiment version, or may not be the general
logfile at all.

**What to do:**

- **Open the logfile:** Search for the order-version line in `GENERAL_LOGFILE_*.txt` and compare
  it with a session that processes correctly.
- **Check the file selection:** The session folder should contain exactly one
  `GENERAL_LOGFILE_*.txt`.
- **Ask the team for the original logfile:** If the line is missing, the file was likely edited or
  truncated after the session. A fresh export is the safest fix.
- **Check the pipeline version:** A changed experiment script can change the message format. Report
  the mismatch if the logfile looks complete.

:::

:::{dropdown} ValueError: More than one or no logfile found in [Path]. Please check the logfiles carefully.

The session's `logfiles/` folder does not contain exactly one `EXPERIMENT_*.txt` file. This often
happens when an experiment crashed early and was restarted, leaving an old logfile next to the new
one.

**What to do:**

- **List the logfiles:** Open the session's `logfiles/` folder and compare the timestamps.
- **Keep the real run:** Move older logfiles to a backup folder outside the session folder. Keep
  the file that belongs to the completed session.
- **Check the other logfile types:** The same rule applies to `DATA_LOGFILE_*.txt` and
  `GENERAL_LOGFILE_*.txt`.
- **Rerun after cleanup:** If cached outputs exist, use `recalculate: true` for the affected
  session.

:::

:::{dropdown} ValueError: Could not read logfile [Path]. Most probably there is a line break in one of the answer options that is written to the file.

The experiment logfile cannot be parsed as a tab-separated table. A raw line break or an
unescaped quote inside an answer option usually splits one row into two.

**What to do:**

- **Open the logfile in a text editor:** Look for a row that continues on the next line, often in a
  free-text answer column.
- **Repair the row carefully:** Join the broken line and escape the quote, or replace the line
  break with a space. Keep the original file as a backup.
- **Cross-check with `completed_stimuli.csv`:** The repaired logfile must still describe the same
  trials.
- **Ask the team for a re-export:** If the file is large or the break is hard to find, request the
  original logfile.
- **Exclude the session as a last resort:** If the answers cannot be recovered, exclude the session
  explicitly instead of leaving a file that fails every run.

:::

:::{dropdown} ValueError: Stimulus order version in logfile ([N]) does not match the version extracted from the asc file ([M]) for participant ID [PID]. OR no version found in asc file.

The participant ID is missing from the stimulus order table, so the pipeline tries to recover the
version from the logfile and the ASC file. The two sources disagree, or the ASC has no version
marker. Continuing could map gaze data to the wrong stimuli and AOIs.

**What to do:**

- **Add the participant to the table:** Add exactly one row for the PID to
  `stimulus_order_versions_*.csv` with the version that was actually used.
- **Check the stimulus folder:** Confirm that the folder contains the stimuli that were presented
  to this participant.
- **Check the ASC marker:** Search the ASC for the stimulus-version message. A missing marker can
  indicate an incomplete conversion or an older experiment script.
- **Ask the team:** If the logfile and ASC disagree, the original session files or the stimulus
  upload are inconsistent. Request the correct stimulus folder before rerunning.

:::

:::{dropdown} Stimulus order version in logfile ([N]) does not match the version in the stimulus order versions file ([M]) for participant ID [PID]. Using the number from the csv.

The session logfile and the stimulus order table disagree about the question order version. The
pipeline trusts the table and continues. A MeRID collection logs the same warning but uses the
logfile version instead.

**What to do:**

- **Check the table row:** Confirm that the participant's row contains the version that was
  actually used.
- **Check the logfile:** Search for the version message and compare it with the table.
- **Check the stimulus folder:** The table and the stimulus package must describe the same
  version.
- **Rerun with recalculation after correcting the table.**

:::

:::{dropdown} ValueError: Stimulus order version [N] extracted from the ASC file or logfile cannot be found in the stimulus order versions CSV.

The pipeline recovered a version number from the session, but that version is not listed in the
stimulus order table. This happens when the table is incomplete or when the session used a
stimulus package that was never uploaded. A related warning says
`Using the stimulus order version from the ASC or logfile. The team should still upload the correct
stimulus folder!` and means the same correction is needed.

**What to do:**

- **Add the version to the table:** Add the rows for that version to
  `stimulus_order_versions_*.csv`, including the correct participant IDs and question order.
- **Use the correct stimulus folder:** If the version belongs to a corrected stimulus upload,
  place that folder in the collection and configure it if needed.
- **Ask the team to upload the used stimulus folder:** The pipeline cannot reconstruct the
  stimulus order from the ASC alone.

:::

:::{dropdown} ValueError: More than one or no entry found for participant ID [PID] in stimulus order versions.

The stimulus order table has no unique row for the participant. Either the PID is missing and the
version fallback found several matching rows, or the PID appears more than once.

**What to do:**

- **Search for the PID:** Open `stimulus_order_versions_*.csv` and search for the three-digit PID.
- **Keep one row:** A participant must appear exactly once. Remove duplicate rows or merge them if
  they are identical.
- **Keep leading zeros:** `003` and `3` are not interchangeable in every context. Use the same
  three-digit format as the other rows.
- **Check the version column:** The row must point to a version whose column values are present.

:::

:::{dropdown} KeyError: 'participant_id'

The stimulus order table has no `participant_id` column. The preflight coverage check skips a file
without this column, so the missing column can surface later as a raw `KeyError` when a session is
loaded.

**What to do:**

- **Add the column:** The CSV must contain `participant_id` next to `version_number` and the order
  columns.
- **Check the header:** A different spelling or a stray blank line at the top can hide the header.
- **Restore the original export:** Do not rename other columns to `participant_id`.
- **Rerun the preflight check after correcting the file.** It validates the stimulus order coverage
  when the column exists.

:::

:::{dropdown} ValueError: Crashed session stimulus order is not a subset of the stimuli order which was supposed to be completed.

The session was marked as restarted or crashed, so the pipeline keeps only the completed stimuli.
However, the completed stimuli do not fit into the stimulus order for the detected version. This
means the completed list, the restart marker and the stimulus order table disagree.

**What to do:**

- **Inspect `completed_stimuli.csv`:** Check the `completed` column, the restart row and the
  `trial_id` values.
- **Check the version:** Confirm that the session used the stimulus version recorded in the order
  table.
- **Do not simply remove the restart marker:** It protects the session from being processed as a
  complete session.
- **Exclude the session if the files are inconsistent:** If the original order cannot be
  reconstructed, exclude the session and document the reason.

:::

:::{dropdown} Participant ID [PID] not found in stimulus order versions. ... Extracting from asc or logfile. Gaze data may be mapped to the wrong stimuli/AOIs.

The PID is missing from `stimulus_order_versions_*.csv`. The pipeline recovers the version from
the ASC or logfile and continues, but the resulting stimulus and AOI mapping may be wrong. This
warning is intentionally prominent.

**What to do:**

- **Add the missing PID:** Add exactly one row with the correct version to the stimulus order
  table.
- **Verify the stimulus folder:** Check that the participant saw the stimuli in the folder that is
  currently used for the collection.
- **Rerun with recalculation:** After correcting the table, run with `recalculate: true` for the
  affected session so scanpaths and reading measures are rebuilt.
- **Check the output:** Compare a few trials with the experiment log before using the data.

:::

:::{dropdown} Stimulus order and completed stimuli do not match for session [Session]. Please check the files carefully.

The stimulus order table and `completed_stimuli.csv` describe different trials. This can happen
when the completed file was edited, when a crash was not marked as a restart, or when the wrong
stimulus version is configured.

**What to do:**

- **Compare both lists:** The completed stimulus IDs should follow the order defined for the
  participant's version.
- **Check the `completed` column:** Only rows with `completed = 1` are considered. A trailing `0`
  usually indicates an interrupted session.
- **Check the restart marker:** If the session was restarted, the last row may contain `restart`.
- **Check the stimulus version:** A mismatch can also mean that the session used a different
  stimulus folder than the table says.
- **Exclude the session if the files cannot be reconciled.**

:::

:::{dropdown} Stimulus order version is not updated with participants numbers. Please ask the team to upload the correct stimulus folder that has been used and changed during the experiment. Version will be extracted from the asc files.

The `stimulus_order_versions_*.csv` file is empty. Without it the pipeline can only recover the
version from the ASC files, which may be incomplete or wrong.

**What to do:**

- **Check the CSV:** The file must contain a header, one row per participant and the version
  columns.
- **Ask the team for the used stimulus folder:** The table belongs to the stimulus package and
  must describe the randomisation that was actually used.
- **Do not leave the file empty:** An empty table forces ASC-based recovery and can map gaze data
  to the wrong stimuli.
- **Rerun with recalculation after replacing the file.**

:::

:::{dropdown} Session [Session] has been restarted. Only the completed stimuli will be considered.

The `completed_stimuli.csv` file contains a restart marker. The pipeline keeps only the completed
stimuli and ignores the aborted part. Related warnings say
`Session [Session] started after a trial.` and have the same effect.

**What to do:**

- **Verify the marker:** Confirm that the restart row belongs to the session and was not added by
  mistake.
- **Check the completed column:** The trials that were actually finished should have
  `completed = 1`.
- **Expect partial outputs:** A restarted session has fewer trials and may trigger session
  completeness warnings. This is normal.
- **Do not treat the warning as corruption:** It documents that the pipeline handled the restart.

:::

:::{dropdown} Clamped [N] negative reading-time span(s) to 0 for [Session] (for example [Trial]). Check the order of the ASC start/stop messages.

A page or trial produced a negative reading-time span. The pipeline clamps the value to zero so
processing can continue, but the underlying ASC messages are out of order or duplicated.

**What to do:**

- **Inspect the ASC around the named trial:** Look for repeated `start_recording_*` or
  `stop_recording_*` messages, or a stop before a start.
- **Check for a restart:** A crashed and restarted session can produce overlapping messages.
- **Check the experiment version:** If the message format changed, the parser may pair the wrong
  start and stop events.
- **Report systematic cases:** If many sessions show this warning, report it with a redacted ASC
  excerpt.

:::

:::{dropdown} KeyError: Stimulus name [Name] not found in the trial mapping for session [Session]. Please check the completed_stimuli.csv file.

The session lists a completed stimulus that has no usable `trial_id` in `completed_stimuli.csv`.
The pipeline needs the trial mapping to load the stimulus and its AOIs.

**What to do:**

- **Open `completed_stimuli.csv`:** Check the row for the named stimulus.
- **Check `trial_id`:** The value must not be empty and must match the trial naming used in the
  session.
- **Check `stimulus_name`:** It must match the expected stimulus name for the collection.
- **Fix the file or ask the team:** If the trial mapping was lost during an interrupted session,
  a corrected export is the safest fix.

:::

:::{dropdown} ValueError: Stimulus with id [ID] not found in stimuli. Experiment did not run correctly. Please check manually.

A stimulus order entry refers to an ID that is not among the loaded stimuli. The experiment and
the stimulus package or order table are inconsistent.

**What to do:**

- **Check the completed stimuli:** Confirm that the ID exists in `completed_stimuli.csv` and in
  the stimulus definition.
- **Check the stimulus version:** The order table may refer to a version whose stimulus files are
  not the ones in the folder.
- **Check the sanity report:** The report lists the trials and messages the pipeline saw.
- **Exclude or re-export the session:** If the order and the presented stimuli cannot be matched,
  do not analyse the gaze data.

:::

:::{dropdown} Question order CSV for [Session] misses columns: [...]

The session's `question_order_versions.csv` is incomplete. Related warnings report unparsable rows
or that the file covers fewer completed trials than expected. The pipeline can continue, but
answer assignment may be incomplete.

**What to do:**

- **Check the required columns:** `question_order_version`, `local_question_1`,
  `local_question_2`, `bridging_question_1`, `bridging_question_2`, `global_question_1`,
  `global_question_2`.
- **Check coverage:** There should be one usable row for each completed trial.
- **Regenerate the file:** Ask the team for the original export instead of editing answers by hand.
- **Rerun the preflight check:** It reports the same structural problems before processing.

:::

:::{dropdown} Could not read answers CSV [Path]: [Error]

A cached answers file cannot be read. This is usually a corrupted or partially written output
file, or a file with an unexpected encoding.

**What to do:**

- **Check the file:** Open it in a text editor and confirm that it has a header and readable rows.
- **Delete the cached output:** Remove the affected `comp_answers/<session>/` folder and rerun the
  session.
- **Use recalculation:** `recalculate: true` rebuilds the answers from the ASC and logfile.
- **Report persistent failures:** If the file is rewritten and still unreadable, report the error
  with the file path.

:::

(errors_sessions)=

## Session Loading Errors and Warnings

:::{dropdown} ValueError: No sessions added. Please add sessions first.

The EDF to ASC conversion was called on a data collection without any sessions. This is normally
an internal notebook or API sequencing problem, not a data problem.

**What to do:**

- **Create the collection first:** Construct `MultipleyeDataCollection` from the data folder
  before calling `convert_edf_to_asc()`.
- **Check the preflight output:** If the collection is empty because no session folders matched,
  fix the folder names and filters first.
- **Use the CLI:** `run_preprocessing` performs the steps in the correct order.

:::

:::{dropdown} ValueError: Function [Method] is only supported for EyeLink data. You are using [Tracker]

A method that requires EyeLink-specific ASC content was called for a different eye-tracker brand.
The current pipeline supports EyeLink models only.

**What to do:**

- **Check the configured model:** Use one of the supported EyeLink models listed in the eye-tracker
  question in the {ref}`faq`.
- **Check the lab configuration:** Correct `Name_eye-tracker` in the lab configuration JSON.
- **Contact the maintainers:** Support for another brand requires code changes.

:::

:::{dropdown} KeyError: Session [Session] not found in [Path].

A requested session ID is not part of the loaded data collection. The session may have been
filtered out, may have a different name, or may not have been discovered at all. A related message
is `[SID] not in sessions or skipped_sessions of [DCN].`

**What to do:**

- **Check the exact ID:** Compare it with the folder names under `eye-tracking-sessions/`.
- **Check the filters:** Remove the session from `exclude_sessions`, or add it to
  `include_sessions`.
- **Check the session regex warnings:** A folder that does not match the naming pattern is not
  loaded.
- **Use a loaded session:** Inspect the preflight summary or the log for the discovered sessions.

:::

:::{dropdown} ValueError: No raw data files found in [Path] with pattern [Pattern]

The loader expected cached raw trial CSVs but found none in the session's raw-data folder. This
happens when the raw data were never written, were deleted, or the output folder was moved without
its contents.

**What to do:**

- **Recalculate the session:** Set `recalculate: true` so the raw data are extracted from the ASC
  again.
- **Check the ASC:** The ASC must exist in the session's output folder.
- **Check the setup:** The pipeline first writes raw data per trial and then loads it in later
  stages. Do not run a later stage in isolation on an empty output folder.
- **Check the pattern:** A custom `raw_data_file_glob` must match the saved file names.

:::

:::{dropdown} ValueError: No reading measures files found in [Path]

The loader expected cached reading-measure CSVs but found none. The reading-measure stage either
did not run or its output was deleted.

**What to do:**

- **Check the stage flags:** `RUN_READING_MEASURES` must be enabled.
- **Check upstream outputs:** Reading measures need mapped fixations. If AOI mapping was skipped,
  reading measures cannot be calculated.
- **Recalculate the session:** Run with `recalculate: true` after fixing the upstream stage.
- **Check the file pattern:** A custom `reading_measures_glob` must match the saved files.

:::

:::{dropdown} ValueError: Invalid SID format: '[SID]'. Expected at least 5 parts separated by '_'.

A session identifier cannot be parsed. The SID must contain the participant, language, country,
lab and session parts. Related messages report
`Invalid session identifier: '[SID]'. Must start with S, PT, or ET followed by digits.`,
`Invalid PID: '[PID]'. Must be 3 digits.` or `Invalid language code` and `Invalid country code`.

**What to do:**

- **Use the full session ID:** For example `003_EN_UK_1_ET1`, with five underscore-separated
  parts.
- **Use a valid session suffix:** `S1`, `PT1` or `ET1`, followed by digits only.
- **Keep the three-digit PID:** Leading zeros are required.
- **Use two-letter language and country codes.**
- **Check participant group entries:** An invalid SID in `participant_groups` raises
  `Invalid session '[SID]' in participant group '[Label]': ...`.

:::

:::{dropdown} Gaze data missing for [Session]. Skipping event detection.

A later stage found no upstream output and skipped its work. Related warnings report
`Fixations missing for [Session]. Skipping AOI mapping/scanpaths.`,
`Gaze/Event data missing or not mapped for [Session]. Skipping reading measures.` and
`Gaze data missing for [Session]. Skipping sanity report.` The session is incomplete, but the run
continues.

**What to do:**

- **Find the first error:** Later stages skip because an earlier stage failed. Fix the earliest
  error in the log.
- **Check the ASC and raw data:** A session without usable gaze data cannot produce events.
- **Recalculate the session:** Run with `recalculate: true` after fixing the upstream input.
- **Do not analyse partial outputs:** A session with skipped stages has missing files, not empty
  results.

:::

:::{dropdown} Could not parse break duration '[Value]' for [Session].

A break duration message could not be converted to a number. The break is still recorded, but its
duration is left empty. Related warnings report
`Session [Session] did not finish a break properly, missing end message.`,
`Skipping trial [ID] in overview: missing stimulus_id.` and
`Could not read per-trial loss table [Path]: [Error]`.

**What to do:**

- **Check the ASC message:** Search for the break duration message and verify that it contains a
  numeric value in milliseconds.
- **Check the experiment version:** A changed message format can produce non-numeric values.
- **Check the completed stimuli file:** A trial without a `stimulus_id` cannot be added to the
  overview. Fix the row or remove it if the trial was aborted.
- **Regenerate the affected report:** Delete the session's report folder and rerun the sanity
  checks.

:::

(errors_answers)=

## Comprehension Answer Warnings

:::{dropdown} ASC messages are missing or empty. Falling back to parsing answers from the experiment logfile. Response time (onset-based) and image offset information will not be available.

The ASC file contains no usable experiment messages, so the pipeline reads answers from the
experiment logfile instead. Answers and correctness are still available, but onset-based response
times and image offsets are not.

**What to do:**

- **Check the ASC:** Confirm that the file is complete and contains `start_recording_*` and
  `answer_given_*` messages.
- **Check the conversion:** If the ASC was produced from a truncated EDF, reconvert the EDF.
- **Check the message patterns:** An older experiment version may use different message names.
- **Accept the fallback for collections without ASC messages:** Document that response times are
  unavailable for those sessions.

:::

:::{dropdown} No messages found in asc file of [Session].

The ASC file has no recognizable messages at all. Without messages the pipeline cannot determine
trials, pages or answer timing.

**What to do:**

- **Check the ASC header:** A valid EyeLink ASC starts with version information and contains
  `START` and `END` lines.
- **Reconvert the EDF:** Delete the cached ASC and run with `force_reconvert_asc: true`.
- **Check the file size:** A very small ASC usually indicates a failed conversion.
- **Exclude the session if the recording is empty.**

:::

:::{dropdown} Completed stimuli count ([N]) does not match trial map count ([M]). Stimulus enrichment might be limited.

The answer collection found a different number of completed stimuli and trial mapping entries.
Some answers may not receive the full stimulus and question metadata. A related warning reports
`Found [N] question(s) where final_answer_key differs from the last preliminary key press (data
anomaly).`

**What to do:**

- **Check `completed_stimuli.csv`:** Remove rows without a usable `trial_id` and verify the
  completed flags.
- **Check the answers file:** Compare the answer rows with the completed trials.
- **Check for restarts:** An interrupted session can have answers for trials that were not marked
  as completed.
- **Use the answers with caution:** If enrichment is incomplete, join the output on trial ID and
  verify a few rows manually.

:::

:::{dropdown} ValueError: Missing columns in question order csv: [...]

The answer collection needs the question order table to assign each answer to a question slot, but
the CSV is missing one or more required columns.

**What to do:**

- **Add the missing columns:** The required columns are listed in the
  `question_order_versions.csv` preflight entry.
- **Do not reorder answers manually:** The order columns encode which question was shown at each
  position.
- **Regenerate the file from the experiment export.**
- **Rerun the preflight check:** It reports the same missing columns before processing.

:::

:::{dropdown} ValueError: Could not extract numeric stimulus id from '[Name]'

An answer record contains a stimulus name without a numeric stimulus ID. The parser uses the ID to
join the answer to the stimulus definition.

**What to do:**

- **Check the ASC or logfile entry:** The stimulus name should follow the experiment's
  `stimulus_<name>_<id>` convention.
- **Check the completed stimuli file:** The same stimulus should have a numeric `stimulus_id`.
- **Check the experiment version:** A changed message format can produce names without IDs.
- **Restore the original session files if the ID was lost during editing.**

:::

(errors_events)=

## Event Detection and Signal Warnings

:::{dropdown} Skipping saccade detection for [N] trial/page group(s) because they have fewer than 2 valid velocity samples or zero variance

Some trial or page groups are too short or too noisy for saccade detection. The pipeline skips
those groups and continues with the rest of the session. Very short pages and heavy data loss are
the usual causes.

**What to do:**

- **Check data loss:** Look at the session data-loss ratio and the per-page loss table in the
  sanity report.
- **Check very short pages:** A page with only one or two samples cannot produce a saccade. This is
  expected and harmless for such pages.
- **Check the ASC:** If many normal pages are affected, inspect the samples around the page
  boundaries and reconvert the EDF.
- **Check calibration:** A failed calibration can leave a signal with almost no valid samples.

:::

:::{dropdown} ValueError: No valid saccade groups remain. Degenerate groups: [...]

Every trial and page group in the session was skipped, so the session cannot produce saccades.
This is a data quality problem rather than a configuration problem.

**What to do:**

- **Check the session quality report:** Look for failed calibration, very high data loss and a
  very short recording.
- **Check the ASC:** Confirm that the file contains sample lines and that the conversion was not
  truncated.
- **Check the sampling rate:** `expected_sampling_rate_hz` must match the recording. A wrong value
  distorts velocity and event detection.
- **Exclude the session if the eye-tracking data are unusable.** Comprehension answers can still
  be processed.

:::

:::{dropdown} ASC message order conflict at [Timestamp]: start_recording_* precedes stop_recording_* in the same timestamp. This can clear trial/page for following samples.

Two recording messages share a timestamp and are stored in the wrong order. The parser can then
clear the trial or page for subsequent samples. This often comes from a restarted session or a
duplicated message block.

**What to do:**

- **Inspect the ASC around the timestamp:** Look for duplicated or overlapping recording blocks.
- **Check the logfile:** Compare the same trial in the experiment logfile.
- **Reconvert the EDF:** A fresh conversion can resolve ordering artefacts.
- **Report the case:** If the ASC is complete and the conflict is reproducible, report it with a
  redacted excerpt.

:::

:::{dropdown} ASC page has only [N] sample(s): [...]. Groups with fewer than 2 samples can break saccade detection.

A page contains fewer samples than expected. One or two samples cannot form a fixation or
saccade, so detection for that page may be skipped.

**What to do:**

- **Check whether the page is genuinely short:** Some practice or instruction pages are very
  short.
- **Check data loss:** A page that should be long but has only a few samples often indicates a
  recording gap.
- **Compare with the logfile:** Confirm that the page was displayed for the expected duration.
- **Reconvert or exclude the session if many normal pages are affected.**

:::

:::{dropdown} Could not parse EyeLink [events|samples] FILTER value '[value]' in [Path].

A `FILTER` field on an EyeLink `EVENTS` or `SAMPLES` line is not an integer. The pipeline ignores
that filter value and continues.

**What to do:**

- **Inspect the named ASC line:** Check whether the line was truncated or edited.
- **Reconvert the EDF:** A clean `edf2asc` run restores valid filter values.
- **Check the edf2asc version:** Very old conversions may use an unexpected format.
- **Usually safe to ignore:** The warning affects filter metadata, not the gaze samples.

:::

(errors_fixation)=

## Fixation Correction Errors

:::{dropdown} ValueError: Fixation correction could not derive the final fixation dot from the stimulus config. The config needs IMAGE_WIDTH_PX, IMAGE_HEIGHT_PX, MIN_MARGIN_LEFT_PX, MIN_MARGIN_RIGHT_PX, FIX_DOT_X, RESOLUTION and SCREEN_SIZE_CM, or explicit POS_BOTTOM_DOT_X_PX, POS_BOTTOM_DOT_Y_PX and FIX_DOT_RADIUS.

Fixation correction is enabled, but the stimulus config does not contain enough geometry to
locate the final fixation dot. The pipeline validates this before processing sessions and stops
if any session's config is incomplete.

**What to do:**

- **Check the stimulus version:** The session may be mapped to the wrong stimulus folder. Confirm
  the folder and its `config/` contents.
- **Add the explicit keys:** Newer configs should provide `POS_BOTTOM_DOT_X_PX`,
  `POS_BOTTOM_DOT_Y_PX` and `FIX_DOT_RADIUS`. Older configs must provide the image geometry,
  margins and top dot position listed in the error.
- **Ask the team for a corrected config:** Do not guess dot coordinates.
- **Disable correction only if acceptable:** Set `RUN_FIXATION_CORRECTION: false` to process
  without correction. Outputs then use uncorrected fixations and half-line-spacing AOI
  enlargement.

:::

:::{dropdown} ValueError: Final fixation dot radius must be positive, got [Radius].

The configured final-dot radius is zero or negative. The radius is used to decide which fixations
belong to the dot.

**What to do:**

- **Check `FIX_DOT_RADIUS`:** Set it to a positive pixel value.
- **Remove an invalid override:** If the explicit value was added by mistake, remove it and let
  the pipeline derive the radius from the image geometry.
- **Check the correct version folder:** A config from another stimulus version may contain an
  unexpected value.
- **Rerun with recalculation:** Cached fixation correction outputs must be rebuilt after changing
  the geometry.

:::

:::{dropdown} ValueError: script_direction 'btt' is not supported. Use 'ttb' for top-to-bottom text.

The lab configuration sets `Script_direction` to `btt` (bottom to top). The current stimulus
generator and correction code support `ltr`, `rtl` and `ttb` only. The related message
`Unsupported script_direction [value]. Supported values are: [...]` covers typos and unknown
values.

**What to do:**

- **Correct the lab configuration:** Set `Script_direction` to `ltr`, `rtl` or `ttb` in the
  stimulus config for the active version.
- **Check the session's version:** A session assigned to the wrong version can pick up the wrong
  direction.
- **Do not use `btt` as a synonym:** Use `ttb` for top-to-bottom text, where the fixed coordinate
  is x rather than y.
- **Rerun after correction.**

:::

:::{dropdown} Fixation correction setting does not match the cached fixations for [Session]. Enable fixation detection or recalculate to apply it.

Cached fixation files were created with a different correction setting or algorithm. The pipeline
does not silently mix corrected and uncorrected outputs.

**What to do:**

- **Recalculate the session:** Run with `recalculate: true` or delete the session's cached
  fixations and downstream outputs.
- **Enable fixation detection:** If fixation detection was disabled, turn it on for the run.
- **Check the settings:** Compare `RUN_FIXATION_CORRECTION`, `fixation_correction_algorithm` and
  `fixation_correction_kwargs` with the values in the dataset overview.
- **Do not mix cached stages:** Rebuild scanpaths and reading measures together with fixations.

:::

(errors_restructuring)=

## Psychometric Tests Restructuring Errors

:::{dropdown} !!! MISSING DATA !!!: Participant [ID] is marked for [Test] in participant configuration ([Config]), but the data folder does not exist at: [Path].

This warning occurs during the restructuring of psychometric tests when a test is marked as `True`
in the participant's YAML configuration file, but the corresponding data folder was not found in the
source directory.

**What to do:**

- **Check Data Collection:** Ask the data collection team or the lab if the test was actually
  performed or if it was interrupted/failed. Check the experimenter session documentation for any
  noteworthy points.
- **Restarted Tests:** If the psychometric tests were restarted, the participant YAML configuration
  might have been overwritten. This could lead to discrepancies where the configuration suggests
  fewer tests were expected than were actually executed (or vice versa).
- **Verify Paths:** Ensure the data was unzipped correctly and is located in the expected
  subfolder (e.g., `core_data/WMC/`, `core_data/RAN/`, etc.).
- **Update Configuration:** If the test was not supposed to be run for this participant (e.g., it
  was skipped intentionally), you can update the participant's YAML configuration file by setting
  the corresponding test flag to `false` to silence this warning.

:::

:::{dropdown} Participant [ID] has data for [Test], but it is marked as False (or missing) in participant config ([Config]). Copying anyway.

This warning indicates that the script found a data folder for a specific test, but that test is
either explicitly marked as `false` or is missing from the participant's YAML configuration file.

**Explanation:**
The script will still copy this data to the output folder to ensure no data is lost. This is
generally fine and often happens if more tests were collected than originally planned in the
configuration.

**What to do:**

- **Check Documentation:** Check the experimenter session documentation for any noteworthy points.
- **Restarted Tests:** If the psychometric tests were restarted, the participant YAML configuration
  might have been overwritten. This could lead to discrepancies where the configuration suggests
  fewer tests were expected than were actually executed.
- **Silence the Warning:** If you want to officially include the test and stop the warning, update
  the participant's YAML configuration file by setting the corresponding test flag to `true`.
- **Verify Consistency:** If the test should not have been run, you might want to investigate why
  data exists for it. However, the data will still be processed if it exists.

:::

:::{dropdown} FileNotFoundError: data_folder does not exist: [Path]

The standalone restructuring tool cannot find its input folders. Related messages report
`config_folder does not exist: [Path]` or
`No configuration files ('*.yaml') found in [Path].`

**What to do:**

- **Check the paths:** The config folder must contain the participant YAML files, and the data
  folder must contain the task-first test folders.
- **Use the settings:** Run `restructure_psychometric_tests` without arguments to use
  `PSYM_PARTICIPANT_CONFIGS` and `PSYCHOMETRIC_TESTS_DIR` from your settings.
- **Check the folder level:** The expected structure is documented in
  {ref}`preparing_data`.
- **Fix permissions:** The tool must be able to move files into the output folder.

:::

:::{dropdown} No participant config for [N] session(s); restructured data anyway (no config generated): [...]

Data folders exist for sessions without a matching participant YAML file. The tool still moves
the data so nothing is lost, but no configuration is generated. Related warnings report leftover
files that were not matched to a session config and data that is not part of the test mapping.

**What to do:**

- **Check the participant configs:** Make sure each session has a YAML file with the expected test
  flags.
- **Check the session IDs:** A config file name that is not SID-compliant is not matched.
- **Check for intentionally unmapped tests:** Data for tests outside the configured mapping is kept
  in the source folder and logged. This is expected.
- **Create the missing YAML only if you know the test flags.** Guessing can hide missing data.

:::

:::{dropdown} Configuration file name is not SID-compliant: [File]. Attempting to process anyway.

A participant YAML file name cannot be parsed as a session identifier. The validator warns and
tries to continue, but the data folder may not be matched to the config. A related error is
`Error reading configuration file [File]: [Error]` when the YAML itself cannot be parsed.

**What to do:**

- **Rename the config file:** Use the full SID, for example `003_EN_UK_1_PT1.yaml`.
- **Check the YAML syntax:** Fix indentation, quotes and list markers. An unreadable YAML is skipped.
- **Check the participant ID:** The file name must start with a three-digit PID.
- **Rerun the restructuring or validation after renaming.**

:::

(errors_calculation)=

## Psychometric Tests Calculation Warnings

:::{dropdown} [Participant ID] [Test] test skipped: [Error Message]

This warning occurs when the script attempts to calculate summary metrics for a psychometric test,
but the data is missing, incomplete, or malformed.

**Contextual Information:**
The warning includes additional context based on the participant's YAML configuration:

- **(Expected per participant config):** The test was explicitly marked as `true` in the
  configuration file. This is a critical failure that should be investigated (e.g., corrupted files,
  missing columns).
- **(Note: Marked as False or missing in participant config):** The test was marked as `false` or
  was missing from the YAML. In this case, the failure to process the data is less critical because
  the researcher already indicated that the test might not be valid or was not intended to be used.

**What to do:**

- **Investigate Data Integrity:** Check the mentioned CSV or data files for the specific
  participant. Ensure they are not empty and contain the expected headers.
- **Review Experimenter Documentation:** Check the experimenter session documentation for any
  noteworthy points or mentions of technical failures during that specific test.
- **Update Configuration:** If the test failed but was not intended to be used anyway, you can set
  the flag to `false` in the participant's YAML configuration. This will clarify the intent,
  although the technical skip warning may still appear if the data folder exists.

:::

:::{dropdown} No recognizable psychometric test data found in [Path]. Psychometric tests stage will be skipped.

The psychometric test stage found no usable data folder. Related messages report
`No 'psychometric-tests-sessions' folder found at [Path]`, `Archives found in [Path]: [...]` or
`No psychometric tests session folder for [Session] could be found. Please check.` The rest of the
pipeline continues.

**What to do:**

- **Check whether tests were collected:** If the collection has no psychometric tests, set
  `RUN_PSYCHOMETRIC_TESTS: false` to stop the warning.
- **Unpack the data:** Archives in `psychometric-tests-sessions/` must be extracted before the run.
- **Check the structure:** The expected task-first and session-first layouts are documented in
  {ref}`preparing_data`.
- **Check the language, country and lab number:** Folder names use
  `psychometric_test_<lang>_<country>_<lab>` and
  `participant_configs_<lang>_<country>_<lab>`.

:::

:::{dropdown} Not yet implemented: loading psychometric tests for MeRID data collection.

MeRID collections do not support loading psychometric tests in the current pipeline. The warning
is expected and the psychometric stage is skipped for this experiment type.

**What to do:**

- **Set `RUN_PSYCHOMETRIC_TESTS: false`:** This stops the stage from being attempted for a MeRID
  collection.
- **Process psychometric tests separately:** Use the standalone tools only if the data layout is
  compatible.
- **Contact the maintainers if you need MeRID psychometric support.**

:::

:::{dropdown} Auto-restructuring psychometric tests failed: [Error]. You can run 'restructure_psychometric_tests' CLI manually.

The pipeline detected task-first psychometric test data and tried to convert it to the
session-first layout, but the conversion failed. Common causes are permissions, files locked by
another program, duplicate targets, or malformed participant configs.

**What to do:**

- **Read the error:** The message after `Auto-restructuring psychometric tests failed:` contains the
  underlying reason.
- **Run the CLI manually:** `restructure_psychometric_tests --help` shows the path overrides.
- **Check write permissions:** The process must be able to create and move folders inside
  `psychometric-tests-sessions/`.
- **Check for duplicate session folders:** Remove or rename duplicates before retrying.
- **Do not keep both layouts:** After a failed move, the source and target may both exist. Verify
  which one is complete before rerunning.

:::

:::{dropdown} Session folder '[SID]' has no YAML config file.

A session-first psychometric test folder has no participant YAML file, or the folder is missing a
test subfolder. Related messages report
`Session folder '[SID]' is missing test folder: [Test]`. These are warnings, not fatal errors.

**What to do:**

- **Add the participant config:** Place `<sid>.yaml` in the session folder with the test flags
  that were actually collected.
- **Check the test folder:** If the test was collected, copy or restructure its data into the
  session folder. If it was not collected, a missing folder is expected.
- **Check the session ID:** The folder name and YAML file name must be SID-compliant.
- **Rerun the psychometric stage:** The warnings disappear once the structure is complete.

:::

:::{dropdown} Multiple CSV files with data were found in '[Path]': [...]. It is ambiguous which one reflects the actual run. Using the most recent one: '[File]'.

A test folder contains more than one CSV that could be the results file. The pipeline chooses the
most recently dated file so it can continue, but this is a guess.

**What to do:**

- **Check the experimenter documentation:** Ask which run is the real measurement.
- **Keep one file:** Move old runs, practice runs and copies out of the test folder.
- **Rerun the test or the stage:** With one candidate left, no ambiguity remains.
- **Compare the chosen file:** Verify that the selected file has the expected columns and a
  plausible number of trials.

:::

:::{dropdown} ValueError: Could not decode CSV file: [Path]

A psychometric test CSV cannot be read as UTF-8 or Latin-1. This usually means the export uses a
different encoding or contains binary data.

**What to do:**

- **Re-export the file:** Open it in the experiment software or a spreadsheet program and save it
  as UTF-8 CSV.
- **Check the file type:** A `.psydat` or `.log` file renamed to `.csv` is not a CSV.
- **Check the delimiter:** Semicolon-separated exports may need to be converted to comma-separated
  files.
- **Restore the original export if the file was edited.**

:::

:::{dropdown} LWMC partially preprocessed for '[SID]': missing [Tasks].

One or more working-memory subtasks (MU, OS, SentS, SSTM) could not be scored. The other subtasks
are kept and the total score is left empty because it requires all four subtasks.

**What to do:**

- **Check the missing subtask files:** Look for the corresponding `.dat` or CSV files in the WMC
  folder.
- **Check the file contents:** A malformed SSTM file or a WMC CSV without trial markers cannot be
  scored.
- **Check for an interrupted test:** Partial results are expected if the participant stopped early.
- **Use the subtask flags:** `LWMC_<task>_Done` shows which scores are valid. Do not interpret the
  total score when it is empty.

:::

:::{dropdown} Cannot merge sessions for participant [PID] ([BaseSID]): overlapping results for [Test].

The same test produced results in more than one psychometric session for a participant, so the
merged overview cannot combine the rows without ambiguity. The per-session table still contains
both results.

**What to do:**

- **Check which session is correct:** Use the experimenter documentation and the test timestamps.
- **Use the per-session table:** `psychometric_results_<dcn>.csv` keeps the rows separate.
- **Correct the participant configs:** Remove the test flag from the session where it was not
  collected, or fix the folder assignment.
- **Do not force a merge:** Overlapping results usually indicate a data organisation problem.

:::

:::{dropdown} Participants missing expected psychometric tests (marked as expected in config, but no results were preprocessed)

A consolidated report lists participants whose YAML config marks a test as expected, but no test
results were produced. A related report lists
`Participants with psychometric test data but marked as absent (or missing) in config`.

**What to do:**

- **Read the per-test lines:** The report groups participants by test and shows a truncated list.
- **Check the participant YAML:** Compare the test flags with the data that was actually collected.
- **Check the test data:** Missing folders, malformed CSVs and restarted tests are common causes.
- **Check the detailed skip messages:** Run with a debug log level to see the underlying test error
  for each session.
- **Update the YAML if the test was not collected.**

:::

---

(errors_config)=

## Configuration Errors

:::{dropdown} ValueError: Participant ID '008' is mapped to multiple stimulus versions: 'v2' and 'v3'. A participant cannot have sessions in different stimulus versions.

This error occurs when the same participant ID (PID) is listed under more than one version
bucket in the `stimulus_versions` section of your configuration file
(`multipleye_settings_preprocessing.yaml`). A single participant cannot have collected data on
more than one stimulus content version, so this is never valid.

**What to do:**

- **Find the Duplicate PID:** Look at the `stimulus_versions.versions` map in your configuration
  file and search for the participant ID mentioned in the error message. It appears in more than
  one list.
- **Decide on the Correct Version:** Check your lab documentation or the experimenter session
  documentation to determine which stimulus folder that participant actually saw.
- **Keep One Entry:** Leave the PID in exactly one version bucket and remove it from all others.

:::

:::{dropdown} ValueError: Participant group label '[Label]' must be a 3-digit ID.

A `participant_groups` entry has an invalid or missing label. Related messages report
`Duplicate participant group label '[Label]'`, `Participant group '[Label]' has no PIDs.` or
`Invalid PID '[PID]' in participant group '[Label]'.`

**What to do:**

- **Use a unique three-digit label:** Copy the participant ID or choose an unused three-digit ID.
  Labels are strings, so keep leading zeros.
- **List at least one PID:** The `pids` list must not be empty.
- **Use numeric PIDs:** Each PID must be one to three digits. The pipeline pads short PIDs with
  leading zeros internally.
- **Check the YAML indentation:** Each group must be a mapping with `label` and `pids` keys. A list
  item that is not a mapping triggers `TypeError: Each participant group must be a mapping.`

:::

:::{dropdown} ValueError: PID '[PID]' is in both participant groups '[A]' and '[B]'.

A participant ID appears in more than one `participant_groups` entry. A PID can belong to only one
group, because the grouping decides which sessions become one participant row.

**What to do:**

- **Remove the PID from one group:** Decide which participant row should own the sessions.
- **Use `sessions` to split a PID:** If a PID really spans two participants, list the PID in both
  groups but give each group an explicit `sessions` list. The related message
  `Session '[SID]' in participant group '[Label]' has PID '[PID]', which is not in the group's
  pids.` means an explicit session does not match the group's PID list.
- **Check session IDs:** Session IDs must be valid SIDs, for example `010_EN_UK_1_ET1`.
- **Check for a duplicate row label:** If a PID is split and its remaining sessions would collide
  with the group label, the pipeline reports
  `Duplicate participant row label. A PID is split across a configured group and an ungrouped row;
  give the remaining sessions an explicit group with a unique 3-digit label.`

:::

:::{dropdown} TypeError: availability.overrides must be a mapping

A configuration block has the wrong YAML shape. Related messages report
`The language_tree config block must be a mapping.`,
`language_tree.psychometric_tests must be a mapping keyed by test.`,
`language_tree.psychometric_tests.[test] must be a mapping.` and
`Each participant group must be a mapping.`

**What to do:**

- **Use a mapping, not a list:** A mapping uses `key: value` lines. A list uses `- item` lines.
- **Check indentation:** The error names the block. Wrong indentation often turns a nested mapping
  into a list or into top-level keys.
- **Compare with the template:** The settings template shows the expected shapes for
  `language_tree`, `availability`, `stimulus_versions` and `participant_groups`.
- **Remove empty blocks or set them to `null` only where the documentation allows it.**

:::

:::{dropdown} ValueError: Invalid availability overrides: ...

The `availability.overrides` block contains an invalid state, an invalid reason, or an unavailable
field without a reason. The message lists every issue after the first line. Related `TypeError`
messages report `[Variable]: availability state must be a string or boolean`,
`[Variable]: availability reason must be a string` or
`[Variable]: availability value must be a state, a two item list, a (state, reason) tuple or a
mapping`.

**What to do:**

- **Use a valid state:** `true`, `false` or `not_applicable`.
- **Use a valid reason for unavailable fields:** `missing_source`, `optional_test_not_collected`,
  `annotation_pending` or `external`.
- **Leave the reason empty when the state is `true`.**
- **Check the field ID:** A field ID that is not known to the codebook is checked when the codebook
  package is written. Use the `variable_id` from `codebook/fields.csv` or the metadata guide.
- **Check the value shape:** A two-item list must contain exactly state and reason. A mapping must
  use `available` and `reason`.

:::

:::{dropdown} TypeError: language_tree.snapshot was removed. Language nodes are validated against Glottolog.

An older settings file still contains the removed `language_tree.snapshot` key. The pipeline no
longer reads a local snapshot and cannot ignore the stale key silently.

**What to do:**

- **Remove the `snapshot` key:** Delete it from the `language_tree` block.
- **Keep `glottolog_check`:** Use `glottolog_check: true` to validate the node against Glottolog
  5.3, or `false` for offline processing without validation.
- **Check `glottolog_cache`:** Set it when the table is stored outside the default cache.
- **Rerun after saving the file.**

:::

:::{dropdown} TypeError: Unsupported key(s) for psychometric test '[Test]': [Keys]. Allowed keys: ...

A `language_tree.psychometric_tests` entry uses a key that the test does not support. Related
messages report
`Unknown psychometric test '[Test]' in language_tree.psychometric_tests. Supported tests: ...` and
`language_tree.psychometric_tests requires language_tree.node_id as the fallback language node.`

**What to do:**

- **Use canonical test IDs:** `plab`, `ran`, `stroop`, `flanker`, `lwmc` and `wiki_vocab`. The key
  `wmc` is accepted as an alias for `lwmc`.
- **Use only supported keys:** `instructions_node_id` for every test. `items_node_id` is only
  supported for `plab`, `stroop`, `lwmc` and `wiki_vocab`; RAN and Flanker have no item node.
- **Set `language_tree.node_id`:** It is the fallback for tests without an explicit override.
- **Remove empty overrides instead of inventing new keys.**

:::

:::{dropdown} GlottologError: Language node '[Code]' is not a Glottolog 5.3 Glottocode.

The configured `language_tree.node_id` is not present in the pinned Glottolog 5.3 table. The
related message
`Language node '[Code]' is a Glottolog '[level]' row. Only language and dialect rows can be
assigned to a data collection.` means the code exists but points at a family or another
non-assignable level.

**What to do:**

- **Use a valid Glottocode:** Check the code in the Glottolog catalogue and use the code for the
  language or dialect actually tested.
- **Do not use a family code:** A collection must be assigned to a language or dialect row, not to
  a family.
- **Check for typos and case:** Glottocodes are lowercase.
- **Set `glottolog_check: false` only when needed:** This skips validation for offline processing
  but does not make an invalid code correct.

:::

:::{dropdown} GlottologError: Could not download the Glottolog languoid table to [Path] (cache directory [Path]): [Error].

The pinned Glottolog table is not cached and could not be downloaded, or the cached file cannot be
read. Related messages report `Glottolog languoid table not found at [Path]`,
`Downloaded Glottolog table checksum mismatch` or
`Glottolog table [Path] has checksum [Actual], expected [Expected]. Delete the file and run again.`

**What to do:**

- **Check the network connection:** The first validation downloads the table from the Glottolog
  archive.
- **Check the cache path:** Use `language_tree.glottolog_cache` or
  `MULTIPLEYE_GLOTTOLOG_CACHE` to point at a writable directory.
- **Delete a corrupted cache:** If the checksum fails, delete the cached
  `glottolog_languoid.csv.zip` and rerun so it is downloaded again.
- **Process offline:** Set `language_tree.glottolog_check: false` to continue without validation
  when the cache is unavailable.
- **Related table errors:** `Glottolog languoid table [Path] has no rows`,
  `Could not read Glottolog languoid table [Path]` and
  `Glottolog parent [Code] is missing from the table` mean the cached archive is corrupt. Delete it
  and download it again.

:::

:::{dropdown} LanguageTreeError: Configured language node id '[ID]' must not contain a slash.

A language node ID, label or path in `language_tree` has invalid spacing, a slash in the node ID,
an empty segment, or a leading or trailing slash. Related messages report
`[source] [field] [value] must not have leading or trailing spaces.`,
`must not contain extra spaces`, `must not contain empty segments` and
`must not start or end with a slash.`

**What to do:**

- **Fix the node ID:** It is a single Glottocode with no slashes and no spaces.
- **Fix the display path:** Use slash-separated segments with single spaces inside a segment.
  Remove leading, trailing and repeated slashes.
- **Fix the label:** Remove leading or trailing spaces and repeated spaces.
- **Compare with the metadata guide:** The expected `language_tree` format is documented in
  {ref}`metadata_yaml` (see the `language_node` section).

:::

:::{dropdown} Psychometric language nodes configured for tests not present in the collection: [Tests]

The `language_tree.psychometric_tests` block configures a language node for a test that is not in
the collection's lab configuration. The node is ignored and the dataset overview does not include
it.

**What to do:**

- **Check the lab configuration:** The `Psychometric_tests` object lists the tests that were
  collected.
- **Remove the unused override:** Delete the test from `language_tree.psychometric_tests`, or add
  the test to the lab configuration if it was actually collected.
- **Check the test ID:** Use the canonical names `plab`, `ran`, `stroop`, `flanker`, `lwmc` or
  `wiki_vocab`.

:::

(errors_metadata_warnings)=

## Metadata YAML Warnings

:::{dropdown} Answer-option shuffling check: identical option keys

The DCN overview writes `processing.answer_option_shuffling` and adds a warning when the shuffled
answer-option keys look repeated. A set is flagged when at least two sessions share one canonical
JSON content and either all readable files in the set are identical or at least half of the
sessions use the same content. A one-versus-one split is not flagged.

**What to do:**

- **Read the set statistics:** `num_sessions`, `num_versions` and `num_unique` show whether only a
  few used versions repeat or the whole set is affected. `all_files_identical` covers every
  readable file, including unused versions.
- **Check how the option keys were generated:** the check detects repeated content, but it cannot
  tell whether the repetition came from a broken seed, an intentional reuse, or duplicated input
  files.
- **Regenerate or replace the affected set:** if the repetition was not intended, regenerate the
  shuffled option keys and rerun the preprocessing.
- **Do not filter sessions by this flag alone:** inspect the option keys and the collection
  documentation first.

:::

:::{dropdown} Metadata form JSON not found: [Path]

The preflight check could not find the data-collection metadata form under `documentation/`. This
is a warning: processing continues, but metadata fields that come from the form stay empty.

**What to do:**

- **Add the form if it exists:** Place the form JSON in the collection's `documentation/` folder
  using the expected file name.
- **Check extraction:** The documentation folder must be extracted together with the rest of the
  collection.
- **Expect empty fields if the form was never collected:** Do not invent values. The affected
  metadata fields are documented in {ref}`metadata_yaml`.
- **Do not confuse a missing form with a parse error:** A form that exists but cannot be parsed is
  a preflight error, not a warning.

:::

:::{dropdown} ValueError: The experimenter documentation workbook has no sheet named '[Sheet]'.

The experimenter documentation workbook is present, but it lacks the expected `ET` or `PT` sheet.
The workbook layout does not match the template used by the pipeline.

**What to do:**

- **Check the sheet names:** The workbook must contain a sheet for eye-tracking sessions and one
  for psychometric test sessions.
- **Use the current template:** Ask the MultiplEYE team for the current experimenter documentation
  template.
- **Rename with care:** Do not rename a data sheet to a similar but non-matching name.
- **Remove empty placeholder workbooks:** A workbook with only a title sheet cannot be parsed.

:::

:::{dropdown} ValueError: Could not locate the header row in the experimenter documentation sheet. Expected a row with 'Date (dd-mm-yyyy)', 'Session ID' and 'Participant ID'.

The parser scans the sheet for the documentation header row and could not find it. Rows above the
header are allowed, but the header itself must contain the expected labels.

**What to do:**

- **Check the first rows:** Look for a row containing `Date (dd-mm-yyyy)`, `Session ID` and
  `Participant ID`.
- **Restore the header:** If the header was deleted or renamed, copy it from the template.
- **Remove merged cells:** Merged title rows can hide the header from the parser.
- **Do not use a screenshot or PDF export:** The input must be an `.xlsx` workbook.

:::

:::{dropdown} ValueError: No data available for the '[Sheet]' sheet.

The sheet exists but contains no data rows below the header, or the parsed sheet has no
`participant_id` column. Related messages report
`The '[Sheet]' sheet has no 'participant_id' column after parsing.`

**What to do:**

- **Check the sheet contents:** Add the session rows below the header, or remove an empty
  placeholder sheet.
- **Check the header:** The participant column must be recognizable as `Participant ID`.
- **Check merged cells and hidden rows:** They can make the parser read an empty body.
- **Remove unused sheets only if the workbook template allows it.**

:::

:::{dropdown} ValueError: Could not map all required columns in sheet '[Sheet]'. Missing: [...]. Found [N] columns; expected one of the known layouts or matching headers.

The workbook has a header row, but one or more required columns could not be matched to the
expected names, and the column count does not match a known fallback layout.

**What to do:**

- **Compare the headers with the template:** Small differences such as extra spaces, line breaks
  or renamed columns prevent matching.
- **Restore missing columns:** Add the columns named in `Missing: [...]`.
- **Remove lab-specific columns from the middle of the sheet:** Extra columns are allowed at the
  end, but reordering required columns can break the fallback layout.
- **Ask the lab for the original workbook:** Do not rebuild the sheet from memory.

:::

:::{dropdown} Experimenter documentation has [N] rows for session [Session]. Dominant-eye values are only used when duplicate rows agree.

The documentation sheet contains multiple rows for the same session. The pipeline uses a
dominant-eye value only when all duplicate rows agree, and otherwise leaves it as `unknown`.

**What to do:**

- **Find the duplicate rows:** Search the ET sheet for the session ID.
- **Keep one correct row:** Remove accidental duplicates or merge them into one row.
- **Check the dominant-eye columns:** If the rows intentionally describe different eyes, resolve
  the conflict in the sheet.
- **Rerun the participant table:** The warning disappears once the rows agree or are removed.

:::

:::{dropdown} Participant [PID] in documentation sheet not in session data. Please check!

The experimenter sheet lists a participant or session that has no matching eye-tracking,
psychometric or questionnaire data. Related messages report
`Participant ID [ID] in the Experimenter documentation sheet could not be converted to an integer`
and `No experimenter documentation sheet found. If this is a full data collection, please reach
out to the lab!`

**What to do:**

- **Check the PID:** Fix typos and keep the three-digit format.
- **Check the session ID:** A session ID that does not exist in the data folder is reported as
  missing.
- **Check for an aborted session:** Rows marked as aborted are expected to have no data. The
  completeness check skips them.
- **Add the workbook if it is missing:** Without it, cross-source completeness cannot be checked.

:::

:::{dropdown} TypeError: 'Psychometric_tests' in lab configuration JSON must be an object (dict), got [Type].

The lab configuration JSON contains a `Psychometric_tests` value that is not an object. The
pipeline expects a mapping of test names and flags, not a list or a string.

**What to do:**

- **Use a JSON object:** The value must use `{ ... }` with test keys, for example
  `"Psychometric_tests": {"PLAB": true, "RAN": true}`.
- **Remove the key if no tests were collected:** An empty object or a missing key means no tests.
- **Check the JSON syntax:** A trailing comma or an unquoted key can change the parsed type.
- **Ask the team for a corrected file if the upload is malformed.**

:::

:::{dropdown} CodebookValidationError: Unknown field ID: [Variable ID]

An `availability.overrides` entry references a field ID that is not part of the codebook. The
override is checked when the codebook package is written, not when the settings are loaded.

**What to do:**

- **Use a known `variable_id`:** Copy it from `codebook/fields.csv` or the metadata guide.
- **Check spelling and dots:** Field IDs use dots, for example
  `item.annotation_layers`.
- **Remove stale overrides:** A field may have been renamed or removed in a newer pipeline
  version.
- **Rerun the output stage after correcting the settings.**

:::

(errors_preflight)=

## Preflight Check Errors

The preflight check validates all input files before the pipeline starts. When stimulus content
versions are configured, it additionally verifies that every configured version folder exists,
contains its `stimulus_order_versions_*.csv`, and that every session's participant ID is present
in the version it was assigned to. Failures are reported under the relevant group in the
`PreflightError` output.

:::{dropdown} PreflightError: Metadata form JSON parse error

This error occurs when the data-collection metadata form is present in the `documentation/`
folder but cannot be parsed as a JSON object. Real uploads often contain raw line breaks inside
string values or a trailing comma before a closing `}` or `]`. The loader first tries strict
JSON, then JSON that allows raw control characters, and finally removes trailing commas outside
strings. If all attempts fail, preprocessing stops because the DCN overview cannot read the form
fields.

**What to do:**

- **Check the reported position:** Fix the JSON syntax around the line and column in the error
  message.
- **Look for the usual causes:** Raw line breaks inside string values and trailing commas before
  a closing bracket.
- **Do not simply delete the form:** A missing form is only a warning, but the DCN overview then
  loses the tested language's script and family and the collection dates.

:::

:::{dropdown} PreflightError: Stimulus folder for version 'v2' does not exist: /path/to/data/stimuli_MultiplEYE_EN_UK_London_1_2025_v2

This error occurs when a version suffix is listed in `stimulus_versions.versions` in your
configuration, but the corresponding stimulus folder does not exist in your data directory.

The pipeline looks for a sibling of the default folder, named by appending the version suffix:
`stimuli_<dcn>_v2/` next to `stimuli_<dcn>/`.

**What to do:**

- **Check the Folder Name:** Make sure the folder on disk is named exactly
  `stimuli_<dcn>_v2` (matching the version key in your configuration).
- **Extract Missing Data:** If the folder was never created or the archive was not extracted,
  unzip the correct stimulus package so the folder exists alongside the default one.
- **Remove Unused Versions:** If the version is no longer needed, delete it from the
  `stimulus_versions.versions` map instead of leaving a dangling entry.

:::

:::{dropdown} PreflightError: Stimulus versions: /path/to/data/stimuli_MultiplEYE_EN_UK_London_1_2025_v2/config/stimulus_order_versions_EN_UK_1.csv

This error occurs when a versioned stimulus folder exists, but its `config/` subfolder is missing
the `stimulus_order_versions_*.csv` file. This file is required to map each participant to the
correct stimulus order for that content version.

**What to do:**

- **Copy the Default CSV:** Copy the `stimulus_order_versions_*.csv` from the default stimulus
  folder's `config/` subfolder into the version folder's `config/` subfolder.
- **Verify the Version Numbers:** If the version uses a different stimulus order, make sure the
  copied CSV lists the correct version number for each participant assigned to this content
  version.

:::

:::{dropdown} PreflightError: 003_EN_UK_1_ET1 (PID 003) — not found in stimulus_order_versions CSV for version 'v2'

This error occurs when a session's participant ID is assigned to a content version in
`stimulus_versions.versions`, but that PID does not appear in the version folder's
`stimulus_order_versions_*.csv`. The same check reports the message without
`for version 'v2'` when the default, suffix-less stimulus folder is used.

**What to do:**

- **Add the PID to the CSV:** Add a row for the participant ID (with the correct version number)
  to the `stimulus_order_versions_*.csv` in the version folder's `config/` subfolder.
- **Check the Assignment:** If the participant did not actually use this version, reassign them to
  the correct version (or remove them from the map so they fall back to the default version) in
  `stimulus_versions.versions`.
- **Check for Typos:** Ensure the PID in the configuration exactly matches the `participant_id`
  entries in the CSV (e.g. leading zeros are required).

:::

:::{dropdown} PreflightError: Stimulus folder does not exist: [Path]

The preflight check cannot find the stimulus folder for the collection. It also reports
`Stimulus folder is empty: [Path]` when the folder exists but contains no extractable entries.
When an archive is found in the parent directory, the message names it.

**What to do:**

- **Extract the stimulus archive:** The stimulus package must be extracted into
  `data/<dcn>/stimuli_<dcn>/`, not left as an archive.
- **Check the folder name:** It must be `stimuli_<dcn>`, or `stimuli_<dcn>_<version>` for a
  configured content version.
- **Check the extraction level:** The contents of the package must be directly inside the
  stimulus folder, including `config/`, the XLSX files and the image folders.
- **Re-download if the archive is corrupt.**

:::

:::{dropdown} PreflightError: Stimulus definition xlsx not found: [Path]

A required file shared by all sessions is missing from the stimulus folder. The same group reports
missing `Comprehension questions xlsx`, `Participant instructions CSV`, `Config python file`,
`Lab configuration JSON` and `Stimulus order versions CSV` entries.

**What to do:**

- **Compare the folder with the uploaded package:** Restore the missing file from the original
  stimulus upload.
- **Check the file names:** The expected names include the language, country and lab number, for
  example `multipleye_stimuli_experiment_<lang>.xlsx` and
  `stimulus_order_versions_<lang>_<country>_<lab>.csv`.
- **Check case and extensions:** File matching is case-insensitive, but `.xls` is not a substitute
  for `.xlsx`, and `.json` is not a substitute for `.py`.
- **Do not create empty placeholders:** An empty file passes existence checks but fails later.

:::

:::{dropdown} PreflightError: Image folder: stimuli_images_[lang]_[country]_[lab] not found: [Path]

A required image folder is missing from the stimulus folder. The same group reports missing
`question_images_*`, `participant_instructions_images_*` and `aoi_stimuli_*` folders. The AOI
overlay folders `aoi_stimuli_images_*` and `aoi_question_images_*` are warnings only.

**What to do:**

- **Restore the complete image set:** Extract all image folders from the stimulus package.
- **Check the folder names:** The suffix must match the collection's language, country and lab
  number.
- **Check optional overlay settings:** Missing AOI overlay images only warn because they are only
  needed when `copy_aoi_images_overlay` is enabled and plotting uses them.
- **Do not rename image folders to fix a single missing folder.**

:::

:::{dropdown} PreflightError: Logfiles folder - [N]:

One or more sessions have no `logfiles/` folder. Without it the pipeline cannot read the completed
stimuli, the experiment logfile or the question order.

**What to do:**

- **Check the session folder:** It must contain the `.edf` file and a `logfiles/` subfolder.
- **Extract the full session archive:** A partial extraction often leaves out `logfiles/`.
- **Check case:** Folder matching is case-insensitive, but the folder must be named `logfiles`.
- **Ask the experimenters for the missing logs if they were never uploaded.**

:::

:::{dropdown} PreflightError: EXPERIMENT_*.txt - [N]:

A session's `logfiles/` folder is missing a required logfile. The same section reports missing
`DATA_LOGFILE_*.txt` and `GENERAL_LOGFILE_*.txt` files.

**What to do:**

- **Check the logfiles folder:** It must contain exactly one `EXPERIMENT_*.txt`, one
  `DATA_LOGFILE_*.txt` and one `GENERAL_LOGFILE_*.txt`.
- **Restore missing files:** Copy them from the original session export or ask the experimenters.
- **Check the storage:** Some uploads split logfiles into a separate archive. Extract it into the
  session folder.
- **Do not rename logfiles:** The prefixes and suffixes are part of the expected structure.

:::

:::{dropdown} PreflightError: Multiple EXPERIMENT_*.txt logfiles - [N]:

A session has more than one experiment, data or general logfile. This typically happens when the
experiment crashed and was restarted.

**What to do:**

- **Compare timestamps:** Keep the logfiles that belong to the completed session.
- **Move older runs out of the session folder:** Keep them for documentation, but not in
  `logfiles/`.
- **Check all three logfile types:** The same duplicate rule applies to `EXPERIMENT_*.txt`,
  `DATA_LOGFILE_*.txt` and `GENERAL_LOGFILE_*.txt`.
- **Rerun the preflight check after cleanup.**

:::

:::{dropdown} PreflightError: completed_stimuli.csv - [N]:

`completed_stimuli.csv` is missing from a session's `logfiles/` folder, cannot be parsed, or is
missing required columns. The entry after the session ID gives the specific reason.

**What to do:**

- **Check the file exists:** It belongs in `logfiles/completed_stimuli.csv`.
- **Check the columns:** The required columns are `stimulus_id`, `stimulus_name`, `trial_id` and
  `completed`.
- **Check the encoding and separators:** The file must be comma-separated and readable as UTF-8.
- **Remove broken rows:** Rows with an empty `trial_id` cannot be mapped to a stimulus.
- **Restore the original export if the file is corrupted.**

:::

:::{dropdown} PreflightError: question_order_versions.csv - [N]:

`question_order_versions.csv` is missing, cannot be parsed, or is missing required columns. The
entry after the session ID gives the specific reason.

**What to do:**

- **Check the file exists:** It belongs in `logfiles/question_order_versions.csv`.
- **Check the columns:** The required columns are `question_order_version`, `local_question_1`,
  `local_question_2`, `bridging_question_1`, `bridging_question_2`, `global_question_1` and
  `global_question_2`.
- **Check the row count:** There should be one usable row per completed trial.
- **Restore the original export if the file was edited or truncated.**

:::

:::{dropdown} PreflightError: [Session] (PID [PID], [N] entries) - duplicate entries in stimulus_order_versions CSV

The session's participant ID appears more than once in the stimulus order table. The pipeline
cannot decide which version and order apply.

**What to do:**

- **Keep one row per PID:** Remove duplicate rows, or merge them if they are identical.
- **Check the version number:** The remaining row must point to the version that was actually used.
- **Check for a PID listed in two versions:** Each PID must appear in only one version bucket in
  the configuration and in only one row of the CSV.
- **Rerun the preflight check.**

:::

:::{dropdown} PreflightError: Questionnaire workbook not found. Place multipleye_questionnaire_questions_[lang].xlsx in the data collection folder ...

The participant questionnaire workbook is missing. The same group reports
`Language-code workbook not found. Place language_iso639_1_[lang].xlsx next to the questionnaire
workbook.` By default this is an error; with `allow_pq_fallback: true` it becomes a warning.

**What to do:**

- **Add the questionnaire workbook:** Place it in a
  `participant_questionnaire_<lang>_<country>_<lab>/` folder inside the collection, or under
  `documentation/questionnaire/`.
- **Add the language workbook:** `language_iso639_1_<lang>.xlsx` must be next to the questionnaire
  workbook.
- **Use fallback only deliberately:** Set `allow_pq_fallback: true` to continue with raw values.
  Language fields then stay in the collection language instead of ISO 639-1 codes.
- **Check the language code:** The `<lang>` part must match the collection.

:::

:::{dropdown} Session completeness: [X]/[Y] participants have all [N] expected ET sessions.

A preflight warning reports that some participants have fewer or more eye-tracking sessions than
expected. MeRID collections normally expect two sessions per participant. Participants with extra
sessions are also reported with a hint to check `experiment_type`.

**What to do:**

- **Check `experiment_type`:** Use `MultiplEYE` for one session and `MeRID` for two sessions per
  participant.
- **Check missing session folders:** A participant may have only `ET1` because `ET2` was not
  uploaded.
- **Check the experimenter sheet:** Confirm whether the missing session was conducted or aborted.
- **This is a warning, not a failure.** Processing continues with the sessions that exist.

:::

:::{dropdown} Cross-source completeness: [Participant]: missing sources: ...; missing sessions: ...; missing sheet rows: ...; missing tests: ...

The participant table found mismatches between eye-tracking sessions, psychometric tests, the
participant questionnaire and the experimenter documentation sheet. Only the non-empty parts are
shown.

**What to do:**

- **Read the categories:** `missing sources` means ET, PT or PQ data is absent. `missing sessions`
  means a session listed in the sheet has no data. `missing sheet rows` means data exists without a
  matching sheet row. `missing tests` means an expected test has no result.
- **Check the experimenter sheet:** Correct PIDs and session IDs, and add rows for data that exists.
- **Check `participant_groups`:** A group that merges PIDs must include the sessions that belong to
  it.
- **Check the psychometric data:** Missing test folders and restarted tests are common causes.
- **This is a warning, not a failure.**

:::

:::{dropdown} Participant questionnaire JSON missing for [Session]

A session has no `<base_id>_pq_data.json` file, either in the session folder or in a questionnaire
folder. The questionnaire fields for this participant stay empty.

**What to do:**

- **Check whether the questionnaire was collected:** If not, an empty row is expected.
- **Check the file name:** The file uses the base participant and session ID, for example
  `003_EN_UK_1_pq_data.json`, with leading zeros.
- **Check where the preflight check looks:** It only checks the session folder for this warning.
  The participant table additionally searches `participant_questionnaire_*` and `documentation/`,
  so a file placed there can still populate the participant row without silencing the preflight
  warning.
- **Ask the team for the export if the file should exist.**

:::

---

```{eval-rst}
.. raw:: html

   <div id="faq-no-results" class="faq-no-results" style="display: none;">
       No results found. Try a different search term.
   </div>
```

```{eval-rst}
.. raw:: html

   <div id="faq-fallback" class="faq-fallback">
       <em>If none of this works, maybe look on the <a href="../faq">FAQ</a> page for answers. Finally, you can reach out to the maintainers.</em>
   </div>
```
