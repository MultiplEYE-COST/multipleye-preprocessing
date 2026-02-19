
MESSAGES = {
    "other_screens": [
        "welcome_screen",
        "informed_consent_screen",
        "start_experiment",
        "stimulus_order_version",
        "showing_instruction_screen",
        "camera_setup_screen",
        "practice_text_starting_screen",
        "transition_screen",
        "final_validation",
        "show_final_screen",
        "optional_break_screen",
        "fixation_trigger:skipped_by_experimenter",
        "fixation_trigger:experimenter_calibration_triggered",
        "recalibration",
        "empty_screen",
        "obligatory_break",
        "optional_break",
    ],
    "break_msgs": [
        "optional_break_duration",
        "optional_break_end",
        "optional_break_",
        "obligatory_break_duration",
        "obligatory_break_endobligatory_break",
    ],
}

BREAK_REGEX = re.compile("|".join(map(re.escape, MESSAGES["break_msgs"])))
OTHER_SCREENS_REGEX = re.compile("|".join(map(re.escape, MESSAGES["other_screens"])))
