"""Load quality thresholds YAML and compare values."""

from typing import Any

import yaml

from ..models import CheckStatus


def load_thresholds(dcn_name: str) -> dict[str, Any] | None:
    """Load quality_thresholds.yaml for a data collection.

    :param dcn_name: Data collection name.
    :returns: Dict of threshold specs, or None if file not found.
    """
    from ..config import quality_thresholds_path

    path = quality_thresholds_path(dcn_name)
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def compare(value: Any, threshold_spec: Any) -> CheckStatus:
    """Compare a value against its threshold spec and return pass/warn/fail.

    Supported threshold formats:
      - [min, max]: numeric range
      - scalar: value must be >= threshold
      - list of values: value must be in list
      - string: value must match exactly

    :param value: The raw value from the overview YAML.
    :param threshold_spec: Threshold definition from quality_thresholds.yaml.
    :returns: 'pass', 'warn', or 'fail'.
    """
    if threshold_spec is None:
        return "pass"

    if isinstance(threshold_spec, list) and len(threshold_spec) == 2:
        lo, hi = threshold_spec
        if isinstance(value, (int, float)):
            if lo <= value <= hi:
                return "pass"
            # Warn if within 10% of boundary
            margin = (hi - lo) * 0.1
            if lo - margin <= value <= hi + margin:
                return "warn"
            return "fail"
        return "pass"

    if isinstance(threshold_spec, list):
        return "pass" if value in threshold_spec else "fail"

    if isinstance(threshold_spec, (int, float)):
        if isinstance(value, (int, float)):
            if value <= threshold_spec:
                return "pass"
            margin = threshold_spec * 0.1
            if value <= threshold_spec + margin:
                return "warn"
            return "fail"
        return "pass"

    if isinstance(threshold_spec, str):
        return "pass" if str(value) == threshold_spec else "fail"

    return "pass"


def check_value(
    name: str, value: Any, thresholds: dict[str, Any] | None
) -> tuple[Any, CheckStatus]:
    """Look up the threshold for *name* and compare.

    :returns: (threshold_value, status) where threshold_value is the spec or None.
    """
    if thresholds is None:
        return None, "pass"
    spec = thresholds.get(name)
    if spec is None:
        return None, "pass"
    return spec, compare(value, spec)
