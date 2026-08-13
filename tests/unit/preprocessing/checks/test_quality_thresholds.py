from pathlib import Path

import yaml

from preprocessing.checks.quality_thresholds import write_quality_thresholds


def test_write_quality_thresholds_creates_yaml(tmp_path: Path) -> None:
    output_dir = tmp_path / "preprocessed"
    output_dir.mkdir()

    write_quality_thresholds(output_dir)

    yaml_path = output_dir / "quality_thresholds.yaml"
    assert yaml_path.exists()

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    assert data["num_calibrations"] == [3, 30]
    assert data["num_validations"] == [13, 30]
    assert data["avg_validation_error"][1] <= 0.8
    assert data["expected_sampling_rate_hz"] == 1000
    assert data["single_validation_good_max"] == 0.305
    assert data["single_validation_moderate_max"] == 0.45
    assert data["total_data_loss_ratio"][1] <= 0.1


def test_write_quality_thresholds_overwrites(tmp_path: Path) -> None:
    output_dir = tmp_path / "preprocessed"
    output_dir.mkdir()

    write_quality_thresholds(output_dir)
    write_quality_thresholds(output_dir)

    yaml_path = output_dir / "quality_thresholds.yaml"
    assert yaml_path.exists()
