"""Shared helpers for stimulus content versions.

A stimulus content version selects which stimulus folder a participant saw. It is
configured in the settings as ``stimulus_versions``::

    stimulus_versions:
      default_version: null   # suffix-less folder ``stimuli_<dcn>/``, or a suffix
      versions:
        v1:                   # suffix, matches ``stimuli_<dcn>_v1/``
          - "002"
          - "005"

The version is a participant-level property: all sessions of a participant use
the same content version. These helpers are the single source of truth for
mapping a participant to a version and for building version folder names, so the
pipeline, preparation and preflight stay consistent.
"""

from pathlib import Path


def configured_version_suffixes() -> list[str | None]:
    """Return the configured stimulus version suffixes.

    ``None`` denotes the suffix-less default folder (``stimuli_<dcn>``). The
    default version is always first, followed by the version buckets.

    Returns
    -------
    list[str | None]
        Version suffixes, for example ``[None]`` for single-folder mode or
        ``[None, "v1"]``.
    """
    from ..config import settings

    pid_map = settings.STIMULUS_VERSIONS_PID_MAP or {}
    default_version = settings.STIMULUS_VERSIONS_DEFAULT_VERSION

    if not pid_map and not default_version:
        return [None]

    suffixes: list[str | None] = [default_version] if default_version else [None]
    for version in pid_map:
        if version not in suffixes:
            suffixes.append(version)
    return suffixes


def default_version_suffix() -> str | None:
    """Return the configured default version suffix.

    ``None`` means the suffix-less folder (``stimuli_<dcn>``) is the default.
    """
    from ..config import settings

    return settings.STIMULUS_VERSIONS_DEFAULT_VERSION


def version_suffix_for_pid(pid: str) -> str | None:
    """Return the stimulus content version suffix for a participant ID.

    Participants that are not listed in any version bucket use the configured
    default version (``None`` for the suffix-less folder).

    Parameters
    ----------
    pid : str
        Participant ID (three-digit string, for example ``"002"``).

    Returns
    -------
    str | None
        The version suffix, or ``None`` for the default/suffix-less folder.
    """
    from ..config import settings

    return settings.STIMULUS_PID_VERSION_MAP.get(
        pid, settings.STIMULUS_VERSIONS_DEFAULT_VERSION
    )


def stimulus_folder_name(dcn_name: str, suffix: str | None) -> str:
    """Return the stimulus folder name for a content version suffix.

    Parameters
    ----------
    dcn_name : str
        Data collection name.
    suffix : str | None
        Version suffix, or ``None`` for the suffix-less default folder.

    Returns
    -------
    str
        ``stimuli_<dcn>`` or ``stimuli_<dcn>_<suffix>``.
    """
    if suffix is None:
        return f"stimuli_{dcn_name}"
    return f"stimuli_{dcn_name}_{suffix}"


def version_dir(base_stimulus_dir: Path, suffix: str | None) -> Path:
    """Return the stimulus folder for a content version.

    Parameters
    ----------
    base_stimulus_dir : Path
        The suffix-less stimulus folder (``stimuli_<dcn>``).
    suffix : str | None
        Version suffix, or ``None`` for the default/suffix-less folder.

    Returns
    -------
    Path
        ``base_stimulus_dir`` for ``None``, otherwise its sibling
        ``stimuli_<dcn>_<suffix>``.
    """
    if suffix is None:
        return base_stimulus_dir
    return Path(f"{base_stimulus_dir}_{suffix}")
