"""Shared Jinja2 templates instance for the review app."""

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


def render(name: str, **context) -> str:
    template = env.get_template(name)
    return template.render(**context)
