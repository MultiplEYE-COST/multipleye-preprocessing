"""Shared Jinja2 templates instance for the review app."""

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Non-ISO-639 language codes used in the MultiplEYE dataset.
_EXTRA_LANGUAGES = {
    "YU": "Cantonese",
    "ZD": "Zurich (Swiss) German",
    "BD": "Bern (Swiss) German",
    "WD": "Wallis (Swiss) German",
}


def lang_name(code: str) -> str:
    """Return the full English language name for a given ISO 639-1 code.

    Handles standard ISO 639-1 codes via pycountry and MultiplEYE-specific
    dialect codes (ZD, BD, WD, YU) via a built-in map.
    """
    upper = code.upper()
    if upper in _EXTRA_LANGUAGES:
        return _EXTRA_LANGUAGES[upper]
    try:
        import pycountry

        lang = pycountry.languages.get(alpha_2=upper)
        if lang is not None:
            return lang.name
    except LookupError:
        pass
    return code


def _format_primitive(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return str(value)


def format_value(value: Any, field: Any = None) -> str:
    """Render a field value for a table cell."""
    if value is None:
        return "\u2014"
    if isinstance(value, bool):
        label = getattr(field, "value_labels", {}).get(str(value).lower())
        return label or ("true" if value else "false")
    if isinstance(value, (list, tuple)):
        if not value:
            return "\u2014"
        text = ", ".join(_format_primitive(item) for item in value)
        return text if len(text) <= 160 else text[:157] + "..."
    if isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return text if len(text) <= 120 else text[:117] + "..."
    if field is not None:
        labels = getattr(field, "value_labels", {})
        if labels and str(value) in labels:
            return labels[str(value)]
    return _format_primitive(value)


def format_value_long(value: Any, field: Any = None) -> str:
    """Render a field value for a detail page without truncation."""
    if value is None:
        return "\u2014"
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if isinstance(value, (list, tuple)):
        if value and all(isinstance(item, dict) for item in value):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return ", ".join(_format_primitive(item) for item in value) or "\u2014"
    return format_value(value, field)


def field_label(field: Any) -> str:
    return getattr(field, "feature_label", None) or getattr(field, "variable_name", "")


def sort_checks(checks: list[Any]) -> list[Any]:
    """Sort check results for the "All Checks" table.

    Order is: checks with a threshold first, then checks without a
    threshold, and finally checks whose value is "unknown". The sort is
    stable, so the original registry order is preserved within each group.

    :param checks: List of CheckResult-like objects.
    :returns: A sorted copy of the list.
    """
    return sorted(
        checks,
        key=lambda c: (
            2 if str(c.value).lower() == "unknown" else (0 if c.threshold else 1)
        ),
    )


env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(),
)

env.globals["lang_name"] = lang_name
env.filters["sort_checks"] = sort_checks
env.filters["format_value"] = format_value
env.filters["format_value_long"] = format_value_long
env.filters["field_label"] = field_label


def render(name: str, **context) -> str:
    template = env.get_template(name)
    return template.render(**context)
