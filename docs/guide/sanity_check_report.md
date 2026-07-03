(sanity_check_report)=

# Sanity Check Report

**The sanity check report is a per-session markdown file produced by
{ref}`preprocessing_step_11`.** It is written to the session results directory as
`{session}_{city}_report.md`. This page describes every output field in the report, grouped by
section. Each field entry explains what the value means, what an example looks like, what the
acceptable range is, and what values signal a problem. Where code-configured thresholds exist, the
configuration key is noted.

---

## Metadata

The metadata section reports key session parameters checked against configurable thresholds. Each
line is a bullet prefixed with `✅` if the value passes, or blank if it does not.

- **Date:** Timestamp of when the experiment started, as measured by the host PC. Format is
  `{time}; {day}.{month}.{year}`, derived from the ASC file header.

  *Example:* `09:57:20; 23.Apr.2026`

  *Acceptable:* Any valid date and time.

  *Problematic:* Date far from expected session date.

- **Number of calibrations:** The actual number of calibrations performed. Must be at least 2
  (initial calibration + recalibration after break). Experimenters typically calibrate between
  trials, so counts above 3 are normal.

  *Example:* `11`

  *Acceptable:* 3–30 (`ACCEPTABLE_NUM_CALIBRATIONS`).

  *Problematic:* Fewer than 2 = no recalibration performed. More than 30 suggests a very long
  session or host-PC issues.

- **Number of validations:** The actual number of validations performed. A validation must be
  performed before every trial (one may be omitted between the two practice trials), plus one at
  the end of the session. Fewer than 12 is unacceptable.

  *Example:* `23`

  *Acceptable:* 13–30 (`ACCEPTABLE_NUM_VALIDATION`).

  *Problematic:* Fewer than 12 means trials ran without validation, so calibration quality cannot
  be assessed for those trials.

- **AVG validation scores:** Comma-separated list of average validation error scores, one per
  validation. The average angular error across all grid points, visible to the experimenter on the
  host PC. For MultiplEYE, the average should stay below 0.3.

  *Example:* `0.29, 0.22, 0.38, 0.33, 0.43, 0.31, ...`

  *Acceptable:* 0.0–0.8 per score (`ACCEPTABLE_AVG_VALIDATION_SCORES`).

  *Problematic:* Consistently above 0.3 means recalibration was needed but skipped.

- **MAX validation scores:** Comma-separated list of maximum validation error scores per
  validation. High max scores indicate poor accuracy at certain grid points even if the average
  was acceptable. [@saphjra]

  *Example:* `1.15, 0.46, 0.87, 0.61, 0.68, 0.86, ...`

  *Acceptable:* 0.0–1.5 per score (`ACCEPTABLE_MAX_VALIDATION_SCORES`).

  *Problematic:* Values above 1.5 mean the eye-tracker lost accuracy at certain positions.

- **Tracked eye:** The eye reported as tracked by the eye-tracker. Should stay the same across
  trials. May mismatch in technical cases or if the experimenter selected the wrong eye on the
  host PC. [@saphjra for acceptable list rationale]

  *Example:* `R`

  *Acceptable:* `L`, `R`, `LEFT`, `RIGHT` (`TRACKED_EYE`).

  *Problematic:* Inconsistent eye across validations. A value outside the accepted set indicates a
  configuration or hardware issue.

- **Validation tracked eyes:** Comma-separated list of which eye was tracked during each
  validation. Each entry corresponds to one validation event. All should match the tracked eye
  value above.

  *Example:* `right, right, right, right, ...` (23 entries)

  *Acceptable:* All values match `tracked_eye`.

  *Problematic:* Mixed left/right eyes indicates the eye-tracker switched mid-session.

- **Data loss ratio:** Proportion of missing (NaN) gaze samples relative to expected samples.
  Calculated by dividing NaN values by expected sample count. Rule of thumb: above 2% means
  suboptimal data quality. Out-of-screen ratio not yet included.

  *Example:* `1.393%`

  *Acceptable:* 0.0–10.0% (`ACCEPTABLE_DATA_LOSS_RATIOS`).

  *Problematic:* Above 2% is a warning signal. Above 10% is substantial.

- **Data loss ratio due to blinks:** Proportion of samples lost to blinks specifically. Should be
  a fraction of total data loss; discrepancies suggest non-blink sources of missing data.

  *Example:* `1.065%`

  *Acceptable:* 0.0–10.0% (shares `ACCEPTABLE_DATA_LOSS_RATIOS`).

  *Problematic:* Above 2% or exceeding total data loss ratio.

- **Total recording duration:** Time from the first trial's start message to the last question's
  end message, reported in minutes.

  *Example:* `50.56`

  *Acceptable:* 600–7200 seconds (`ACCEPTABLE_RECORDING_DURATIONS`).

  *Problematic:* <10 minutes = incomplete session. >120 minutes = extended pauses or host-PC
  issues.

- **Sampling rate:** Measured sampling frequency of the eye-tracker hardware. Expected 1000 Hz
  for the EyeLink 1000 Plus. [@saphjra]

  *Example:* `1000.0`

  *Acceptable:* 1000 Hz (`EXPECTED_SAMPLING_RATE_HZ`).

  *Problematic:* Deviations from 1000 Hz indicate hardware issues or configuration mismatches.

---

## Logfile

**Checks that all stimulus pages, questions, and rating screens are recorded in the experiment
logfile.** For each stimulus, verifies that the logfile contains entries for every page, every
comprehension question, and every rating screen defined in the stimulus configuration. Missing
items are reported as bullet entries; an empty section means everything is present.

*Example:* (empty -- entries only appear on failure)

*Acceptable:* Empty section (no missing entries).

*Problematic:* Missing pages are most critical -- the stimulus presentation was not logged.
[@saphjra for detailed field descriptions]

---

## Gaze Frame

**Checks that all stimulus pages, questions, and ratings are present in the ASC gaze data file.**
Analogous to the logfile check but covers the eye-tracking data stream. Verifies pages, questions,
and ratings per stimulus. Only failures are reported.

*Example:* (empty -- entries only appear on failure)

*Acceptable:* Empty section (all screens present in ASC).

*Problematic:* Missing pages means no gaze data for that stimulus. Missing questions or ratings
affect comprehension answer extraction. [@saphjra for detailed field descriptions]

---

## ASC Messages

**Analyses messages embedded in the ASC file to report trial durations, one-time screens,
optional screens, breaks, and recalibrations.** Output varies by sub-check; most failures produce
bullet entries.

### Trial durations

Duration of each trial in minutes, plus break durations. Trials should be ~5–9 minutes; the
obligatory break must be at least 5 minutes.

*Example:*

```
- 1: Lit_Solaris: 9.76 minutes
- 2: Arg_PISACowsMilk: 6.80 minutes
- obligatory break: 16.28 minutes
```

*Acceptable:* Trials 5–9 minutes, obligatory break ≥5 minutes.

*Problematic:* Trials under 3 minutes suggest a rushed experiment. Break under 5 minutes means the
protocol was not followed.

### Missing message patterns

Flags absent ASC message patterns: `start_recording`, `screen_image_onset`, `screen_image_offset`,
and `stop_recording`.

*Example:* `Lit_Solaris: Missing start_recording Messages in ASC file`

*Acceptable:* Empty (all expected messages present).

*Problematic:* Any missing pattern disrupts gaze-to-stimulus alignment.

### One-time screens

Checks that all one-time experiment screens appear in the ASC file. Screens checked include:
`welcome_screen`, `informed_consent_screen`, `start_experiment`, `stimulus_order_version`,
instruction screens (1–3), `camera_setup_screen`, `practice_text_starting_screen`, practice trial
recordings, `transition_screen`, `final_validation`, `show_final_screen`, `obligatory_break`, and
`obligatory_break_end`. Only missing screens are reported.

*Example:* `Missing one time screen welcome_screen in asc file`

*Acceptable:* Empty (all one-time screens present).

*Problematic:* Missing consent or practice trials indicates the experiment was not run as designed.

### Optional screens and breaks

Reports on optional break screens, obligatory break, fixation trigger events, and recalibration
screens. Count and duration are always reported; absence is noted explicitly.

*Example:*

```
- fixation_trigger:skipped_by_experimenter not found
- fixation_trigger:experimenter_calibration_triggered not found
- optional_break found 8 times
- optional_break_duration: lasting 56.27 seconds found at 3610707
- obligatory_break found 1 times
- obligatory_break_duration: lasting 939.35 seconds found at 6107427
- recalibration not found
```

*Acceptable:* Fixation triggers should not be found. Recalibration should be present if validation
scores exceeded threshold.

*Problematic:* Fixation trigger events mean the experimenter manually intervened. Missing
recalibration with high validation scores means poor calibration was not addressed.

### Rating screens

Checks that the three rating screens are present: `showing_subject_difficulty_screen`,
`showing_familiarity_rating_screen_1`, and `showing_familiarity_rating_screen_2`.

*Example:* `Missing rating showing_subject_difficulty_screen in asc file`

*Acceptable:* Empty (all rating screens present).

*Problematic:* Missing ratings mean subjective responses were not captured.

---

## Validation & Calibration

**A chronological timeline of validations and stimulus boundaries, followed by a structured
summary of validation quality.** Uses thresholds: Good (<0.305), Moderate (0.305–<0.45), Bad
(≥0.45). Configured in code, not via config keys.

### Per-trial timeline

Interleaved timeline sorted by timestamp showing good validations (✅), stimulus starts and ends.
Moderate and bad validations are omitted from the timeline and appear only in the summary.

*Example:*

```
- ✅ Good validation at 2764156.0 with score 0.29
- Enc_WikiMoon_start at 2787707.0
- Enc_WikiMoon_end at 2893105.0
- ✅ Good validation at 3043008.0 with score 0.22
```

*Acceptable:* All validations good. Stimulus starts immediately follow a good validation.

*Problematic:* Validations after the last stimulus (⚠️) means the experimenter kept validating
without running a trial. Calibration after last stimulus (❌) invalidates the final validation.

### Validation/calibration summary

Counts of good, moderate, and bad validations, followed by sub-sections flagging quality concerns.
Each sub-section only appears when issues are found.

*Example:*

```
Good validations: 8/23
Moderate validations: 7/23
Bad validations: 3/23
```

**Summary sub-sections:**

- **Stimulus start after bad/moderate validation** -- ❌/⚠️ Trials that started after a non-good
  validation, meaning the experimenter did not recalibrate before running the trial.
- **Missing calibrations after bad/moderate validations** -- ⚠️ Bad or moderate validations not
  followed by a recalibration.
- **Necessary calibrations after bad validations** -- ✅ Forced recalibrations performed after a
  bad validation.
- **No validation before stimulus start** -- ⚠️ A trial started with no prior validation at all.
- **Validation/calibration during stimulus presentation** -- ⚠️ A validation or calibration
  occurred while a stimulus was running, meaning the experimenter interrupted a trial.
- **Bad validations** -- Individual listing (❌) of all bad validations with scores.
- **Moderate validations** -- Individual listing (⚠️) of all moderate validations with scores.
- **Final validation** -- `✅ Final validation` if present, `❌ No final validation!` if missing.

*Acceptable:* Good validations should be the majority. No stimulus start after bad or moderate
validations. Final validation present without intervening calibration.

*Problematic:* Any bad validations. Stimulus starts after bad/moderate validations. Missing final
validation. Validations during stimulus presentation.

---

## Comprehension Answers

**Per-stimulus count of correctly answered comprehension questions, plus an overall accuracy
ratio.** Practice trials have 2 questions; main trials have 6. Stimulus names are bold.

*Example:*

```
- Correct answers for **Lit_Solaris**: 6 out of 6 answers
- Correct answers for **Lit_Alchemist**: 5 out of 6 answers

**Overall correct answers**: 52 out of 64 (0.81)
```

*Acceptable:* >70% overall.

*Problematic:* Below 50% suggests disengagement. Stimuli with 0 correct answers warrant manual
review.

---

## Emoji Legend

**Legend block appearing at the bottom of the report after a `---` horizontal rule.**

*Example:*

```
---
**Legend:** ✅ Pass | ❌ Fail | ⚠️ Warning
```

| Emoji | Meaning | Usage                                                                                                                                                                                  |
|-------|---------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `✅`   | Pass    | Metadata in range; good validation; necessary calibration found; final validation present                                                                                              |
| `❌`   | Fail    | Stimulus after bad validation; bad validation score; calibration after last stimulus; no final validation                                                                              |
| `⚠️`  | Warning | Moderate validation; start after moderate validation; missing calibration after bad; no validation before start; validation/calibration during stimulus; post-last-stimulus validation |
