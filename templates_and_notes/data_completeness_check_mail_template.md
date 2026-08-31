<!--
HOW TO USE THIS TEMPLATE
- This is a modular template. Every numbered section below covers one recurring issue type
  found when checking a lab's upload after core data collection.
- Fill in the bracketed placeholders (data collection name, session names, participant/session
  IDs, file names).
- Delete any section that does not apply to this lab's check. Only send the sections that are
  relevant, in whatever order makes sense; the closing and README paragraphs at the end should
  stay.
- Placeholders used throughout:
    [DATA_COLLECTOR_NAME]   - contact person at the lab
    [DCN]                   - data collection name, e.g. MultiplEYE_ET_EE_Tartu_1_2025
    [SESSION_LABEL]         - session name(s) relevant to this collection, e.g. ET1, ET1/ET2
    [YOUR_NAME(S)]          - sign-off
- This template is for the file/folder completeness check run before preprocessing can start
  (not the data-quality check after pilots, see mail_template.md for that one).
-->

Dear [DATA_COLLECTOR_NAME],

Thank you for uploading the data for [DCN]. We have run our initial completeness check on the
drive before starting preprocessing, and found a few things that need to be resolved first.
Could you please have a look at the points below?

---

**1. Stimulus folder not re-uploaded / outdated**

The most recent stimulus folder on the drive is [stimuli_DCN_pid_X-Y], which suggests the
stimulus folder was not re-uploaded after the last participant(s). This matters because some
randomization and logging data is only written to the stimulus folder at the end of the
respective session, so we need the final version to proceed. This is also supported by missing
entries in the [stimulus_order_versions / question_order_versions] CSV for the following
participants:

- [PID] ([session_id]) — not found in [stimulus_order_versions / question_order_versions] CSV
- [PID] ([session_id]) — not found in [stimulus_order_versions / question_order_versions] CSV

Could you please re-upload the stimulus folder used for the final session(s), as described in
the README (see note at the end of this email)?

---

**2. Missing session files**

For the following sessions, we could not find the listed files. Could you please check whether
they exist on your end and, if so, upload them; if not, let us know what happened?

*Missing EDF files:*
- [session_id]
- [session_id]

*Missing `logfiles/` folder entirely:*
- [session_id]

*Missing `completed_stimuli.csv`:*
- [session_id]

*Missing `GENERAL_LOGFILE`:*
- [session_id]

*Missing `question_order_versions.csv`:*
- [session_id]

---

**3. Errors in configuration files**

We found the following issue(s) in [MultiplEYE_DCN_lab_configuration.json /
MultiplEYE_DCN.json]:

- [Field "X" should be renamed to "Y"]

Could you please correct this in both files and reupload them?

---

**4. Redundant or duplicate files to clean up**

We noticed multiple [logfiles / zip folders] for the following session(s), which suggests the
session was restarted:

- [session_id]

Could you confirm this was a restart, and let us know which redundant/outdated files she should move to the
`00_oldFiles_toBeDeleted` folder so it is clear which files belong to the final data collection?

---

**5. Sessions with only one session folder found (only relevant for MeRID**

The following participants only have one [ET/PT] session folder, although two are expected:

- [PID]
- [PID]

We checked the session documentation sheet but could not find an explanation for these. Could
you confirm whether the second session took place and, if so, upload the missing folder? If it
did not take place, could you let us know the reason (e.g., drop-out, technical issue)?

---

**6. Psychometric data unclear**

We found more than one folder that could be the final psychometric data for [PID(s) /
this collection], and it is not clear to us which one should be used:

- [folder name]
- [folder name]

Could you confirm which folder is the correct/final one, and move the others to
`00_oldFiles_toBeDeleted`?

---
**Metadata form**

Please uploade the final metadata form into the documentation folder

---

**7. Open questions**

A few additional clarifications before we can proceed:

- [e.g., "Are the zip ET folders for participants X–Y also meant to be included in the final data collection?"]
- [e.g., "Can you confirm the final stimulus folder to use is the one under [path]?"]

---

Please use the `README-Folder Structure and Data Upload.txt` in your switch drive folder for reference, which covers
where each type of file should live. Please tell us which files and folders should be move such that your folder is adhering to the readme to `00_oldFiles_toBeDeleted`
or inform us why additional data is needed and should stay in the current location.

Once these points are resolved, please let us know so we can proceed with preprocessing your
data.

If you have any questions or need clarification, feel free to reach out.

Thank you again for your valuable contributions to the MultiplEYE project!

Best regards,
