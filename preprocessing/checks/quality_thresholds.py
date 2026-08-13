from pathlib import Path

import yaml

from ..config import settings


def write_quality_thresholds(output_dir: str | Path) -> None:
    """Export the pipeline's sanity check thresholds to a machine-readable YAML file.

    The web review UI reads this file to compute pass/warn/fail status at runtime,
    avoiding redundant storage of threshold status per session. The file is written
    once per data collection during preprocessing.

    :param output_dir: Path to the preprocessed data output directory.
    """
    thresholds = {
        "num_calibrations": list(settings.ACCEPTABLE_NUM_CALIBRATIONS),
        "num_validations": list(settings.ACCEPTABLE_NUM_VALIDATION),
        "avg_validation_error": list(settings.ACCEPTABLE_AVG_VALIDATION_SCORES),
        "max_validation_error": list(settings.ACCEPTABLE_MAX_VALIDATION_SCORES),
        "validation_errors": list(settings.ACCEPTABLE_VALIDATION_ERRORS),
        "total_data_loss_ratio": list(settings.ACCEPTABLE_DATA_LOSS_RATIOS),
        "blink_loss_ratio": list(settings.ACCEPTABLE_DATA_LOSS_RATIOS),
        "total_session_duration": list(settings.ACCEPTABLE_RECORDING_DURATIONS),
        "num_practice_trials": settings.ACCEPTABLE_NUM_PRACTICE_TRIALS,
        "num_experiment_trials": settings.ACCEPTABLE_NUM_TRIALS,
        "num_completed_trials": [settings.ACCEPTABLE_NUM_COMPLETED_TRIALS, 12],
        "expected_sampling_rate_hz": settings.EXPECTED_SAMPLING_RATE_HZ,
        "single_validation_good_max": settings.SINGLE_VALIDATION_GOOD_MAX,
        "single_validation_moderate_max": settings.SINGLE_VALIDATION_MODERATE_MAX,
    }

    out_path = Path(output_dir) / "quality_thresholds.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(thresholds, f, default_flow_style=False, sort_keys=False)
