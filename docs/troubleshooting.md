(troubleshooting)=

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

## Processing Errors

:::{dropdown} ValueError: Raw data cannot be loaded as the folder for session XY does not contain
the expected number of files. Please check and select overwrite.

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


---


(errors_restructuring)=

## Psychometric Tests Restructuring Errors

::::{dropdown} !!! MISSING DATA !!!: Participant [ID] is marked for [Test] in participant
configuration ([Config]), but the data folder does not exist at: [Path].

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
  ::::

::::{dropdown} Participant [ID] has data for [Test], but it is marked as False (or missing) in
participant config ([Config]). Copying anyway.

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
  ::::

---

(errors_calculation)=

## Psychometric Tests Calculation Warnings

:::::{dropdown} [Participant ID] [Test] test skipped: [Error Message]

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
  :::::

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
