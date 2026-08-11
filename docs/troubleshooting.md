(troubleshooting_anchor)=

# Troubleshooting

This page lists all errors that can occur when running the pipeline. Most of them can be easily
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

(errors_processing)=

## Eye-tracking Data Processing Errors

:::{dropdown} ValueError: Raw data cannot be loaded as the folder for session XY does not contain the expected number of files. Please check and select overwrite.

This error means that there exists saved raw data for a session, but it does not contain the files
for
all stimuli. This means that the last time the files were generated something went wrong or was
interrupted.
In order to be sure, that now all files are correct, it is important to write all files again.
This can be done by changing the parameter `overwrite` to `True` in the configuration file. This
will make
sure that all files are generated again, and the error should not occur anymore even without
choosing overwrite.
:::

:::{dropdown} ValueError: Both 'included_sessions' and 'excluded_sessions' are provided and not empty.

This error occurs when you have both `include_sessions` and `exclude_sessions` defined in your
configuration file (i.e. `multipleye_settings_preprocessing.yaml`). The pipeline only supports
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
- **Completed Stimulus File:** Check the `completed_stimulus.tsv` file for the session in question. Ensure that:
   - The `completed` column has a value of `1` for all rows, indicating that all stimuli were completed. If the last stimulus has a `0`,
  it means the session was ended unexpectedly, and the reading times cannot be computed. If this is the case, please confirm in the .asc file for this session that the message "show_final_screen" is really missing.
- **Check the documentation for the session:** Check the experimenter session documentation for any noteworthy points or mentions of technical failures during that specific session.
- **Contact Support:** If you have verified the above, please reach out to the MultiplEYE support team with details about the session and any findings from your checks.
- **Exclude Session:** If the session is indeed corrupted and cannot be processed, you can exclude it from processing by adding it to the `exclude_sessions` list in your configuration file.

:::

:::{dropdown} ValueError: No files found in folder [Session] that match the pattern .edf

The folder for the session does not contain any .edf files. Most likely this means the file has not been correctly transferred.

**What to do:**
- **Experimenter script**: if this is your own data collection, please make sure that all experimenters know that they should check for the presence of the .edf files
after each session and that they should transfer them to the server as soon as possible and make sure they are uploaded correctly.
- **Contact the experimenters**: If you are processing data that was collected by someone else, please reach out to the experimenters and ask them to check if the .edf files are present
on their local machines and if they can be transferred to the server. If the files were lost or corrupted, you may need to exclude this session from processing.
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

(errors_preflight)=

## Preflight Check Errors

The preflight check validates all input files before the pipeline starts. When stimulus content
versions are configured, it additionally verifies that every configured version folder exists,
contains its `stimulus_order_versions_*.csv`, and that every session's participant ID is present
in the version it was assigned to. Failures are reported under the **Stimulus versions** group in
the `PreflightError` output.

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
`stimulus_order_versions_*.csv`.

**What to do:**

- **Add the PID to the CSV:** Add a row for the participant ID (with the correct version number)
  to the `stimulus_order_versions_*.csv` in the version folder's `config/` subfolder.
- **Check the Assignment:** If the participant did not actually use this version, reassign them to
  the correct version (or remove them from the map so they fall back to the default version) in
  `stimulus_versions.versions`.
- **Check for Typos:** Ensure the PID in the configuration exactly matches the `participant_id`
  entries in the CSV (e.g. leading zeros are required).

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
