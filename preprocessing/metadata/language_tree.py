"""Format the configured language node metadata.

The selected node is a Glottolog Glottocode. Validation against the pinned
Glottolog table happens in :mod:`preprocessing.metadata.glottolog` when the
settings are loaded. This module only checks the text shape and builds the
overview block. The EyeStore language tree is external and is not vendored by
the pipeline.
"""

from __future__ import annotations

__all__ = [
    "LAB_PSYCHOMETRIC_TEST_IDS",
    "PSYCHOMETRIC_TESTS_WITH_ITEMS",
    "PSYCHOMETRIC_TEST_IDS",
    "LanguageTreeError",
    "language_node_overview",
    "normalize_psychometric_test_id",
    "psychometric_language_node_overview",
    "psychometric_test_ids_from_lab_config",
]

#: Canonical psychometric test IDs used in the config and codebook.
PSYCHOMETRIC_TEST_IDS = (
    "plab",
    "ran",
    "stroop",
    "flanker",
    "lwmc",
    "wiki_vocab",
)

#: Tests whose item material has its own language node. Flanker uses arrows and
#: only exposes instructions.
PSYCHOMETRIC_TESTS_WITH_ITEMS = frozenset({"plab", "stroop", "lwmc", "wiki_vocab"})

#: Accepted aliases for config keys.
PSYCHOMETRIC_TEST_ALIASES = {"wmc": "lwmc"}

#: Lab-configuration test names mapped to canonical test IDs.
LAB_PSYCHOMETRIC_TEST_IDS = {
    "plab": ("plab",),
    "ran": ("ran",),
    "stroop_flanker": ("stroop", "flanker"),
    "wmc": ("lwmc",),
    "wiki_vocab": ("wiki_vocab",),
}


def normalize_psychometric_test_id(test_id: object) -> str:
    """Return the canonical psychometric test ID or raise an error.

    Parameters
    ----------
    test_id : object
        Test key from the config.

    Returns
    -------
    str
        Canonical test ID.

    Raises
    ------
    LanguageTreeError
        If the test ID is not supported.
    """
    text = str(test_id).strip().lower()
    text = PSYCHOMETRIC_TEST_ALIASES.get(text, text)
    if text not in PSYCHOMETRIC_TEST_IDS:
        supported = ", ".join(PSYCHOMETRIC_TEST_IDS)
        raise LanguageTreeError(
            f"Unknown psychometric test {test_id!r} in language_tree.psychometric_tests. "
            f"Supported tests: {supported}."
        )
    return text


def psychometric_test_ids_from_lab_config(names: object) -> tuple[str, ...]:
    """Return canonical test IDs for a lab-configuration test list."""
    if not names:
        return ()
    result: list[str] = []
    for name in names:
        key = str(name).strip().lower().replace(" ", "_")
        for test_id in LAB_PSYCHOMETRIC_TEST_IDS.get(key, ()):
            if test_id not in result:
                result.append(test_id)
    return tuple(result)


def psychometric_language_node_overview(
    et_node_id: str | None,
    overrides: dict[str, dict[str, str | None]] | None,
    available_tests: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    """Build the per-test language node list for the dataset overview.

    Parameters
    ----------
    et_node_id : str, optional
        Dataset eye-tracking Glottocode. Used as the fallback.
    overrides : dict, optional
        Mapping from canonical test ID to instructions and items overrides.
    available_tests : tuple of str, optional
        Tests present in the collection. When empty, configured tests are used.

    Returns
    -------
    list of dict
        One entry per test with resolved node IDs and sources.
    """
    overrides = overrides or {}
    test_ids = [
        test_id
        for test_id in PSYCHOMETRIC_TEST_IDS
        if test_id in available_tests or test_id in overrides
    ]
    if not available_tests:
        test_ids = [
            test_id for test_id in PSYCHOMETRIC_TEST_IDS if test_id in overrides
        ]

    entries: list[dict[str, str]] = []
    for test_id in test_ids:
        test_override = overrides.get(test_id, {})
        instructions = test_override.get("instructions_node_id") or et_node_id
        if instructions is None:
            continue
        entry = {
            "test_id": test_id,
            "instructions_node_id": instructions,
            "instructions_source": (
                "override" if test_override.get("instructions_node_id") else "dataset"
            ),
        }
        if test_id in PSYCHOMETRIC_TESTS_WITH_ITEMS:
            items = test_override.get("items_node_id") or et_node_id
            if items is not None:
                entry["items_node_id"] = items
                entry["items_source"] = (
                    "override" if test_override.get("items_node_id") else "dataset"
                )
        entries.append(entry)
    return entries


class LanguageTreeError(ValueError):
    """Raised when configured language node metadata is invalid."""


def _clean_text(value: object, field: str, source: str) -> str:
    """Validate one node ID, label or path segment and return it as text."""
    text = str(value)
    if text != text.strip():
        raise LanguageTreeError(
            f"{source} {field} {text!r} must not have leading or trailing spaces."
        )
    if "  " in text or "\t" in text or "\n" in text:
        raise LanguageTreeError(
            f"{source} {field} {text!r} must not contain extra spaces."
        )
    return text


def _clean_path(value: object, field: str, source: str) -> str:
    """Validate a slash separated path with optional single spaces."""
    text = _clean_text(value, field, source)
    if not text:
        raise LanguageTreeError(f"{source} {field} must not be empty.")
    if text.startswith("/") or text.endswith("/"):
        raise LanguageTreeError(
            f"{source} {field} {text!r} must not start or end with a slash."
        )
    for segment in text.split("/"):
        _clean_text(segment, field, source)
        if not segment:
            raise LanguageTreeError(
                f"{source} {field} {text!r} must not contain empty segments."
            )
    return text


def language_node_overview(
    node_id: str | None,
    tree_path: str | None = None,
    tree_version: str | None = None,
    node_label: str | None = None,
    tree_hash: str | None = None,
) -> dict[str, str | None] | None:
    """Return the dataset overview block for the configured language node.

    Parameters
    ----------
    node_id : str, optional
        Glottocode of the selected language node.
    tree_path : str, optional
        Display path from the EyeStore tree root to the node. It is not derived
        from Glottolog because the EyeStore tree may prune intermediate levels.
    tree_version : str, optional
        Version of the EyeStore language tree.
    node_label : str, optional
        Human readable node label. The settings loader fills this from the
        Glottolog name when it is not configured.
    tree_hash : str, optional
        Hash of the EyeStore language tree.

    Returns
    -------
    dict or None
        Overview fields for the node, or ``None`` when no node is configured.

    Raises
    ------
    LanguageTreeError
        If the node ID, path or label has leading, trailing or repeated spaces,
        or the path has empty segments.
    """
    if not node_id:
        return None

    selected = _clean_text(node_id, "node id", "configured")
    if "/" in selected:
        raise LanguageTreeError(
            f"Configured language node id {selected!r} must not contain a slash."
        )
    path = _clean_path(tree_path, "path", "configured") if tree_path else None
    label = _clean_text(node_label, "label", "configured") if node_label else None

    return {
        "language_node_id": selected,
        "language_node_path": path,
        "language_node_label": label,
        "language_tree_version": tree_version or None,
        "language_tree_hash": tree_hash or None,
    }
