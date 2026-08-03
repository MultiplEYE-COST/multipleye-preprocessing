"""Shared Jinja2 templates instance for the review app."""

from pathlib import Path

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


env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(),
)

env.globals["lang_name"] = lang_name


def render(name: str, **context) -> str:
    template = env.get_template(name)
    return template.render(**context)
