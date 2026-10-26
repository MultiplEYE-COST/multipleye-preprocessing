"""Locate raw participant questionnaire files across data sources."""

from __future__ import annotations

from pathlib import Path


def _pid_matches(filename: str, pid: int) -> bool:
    prefix = filename.split("_", 1)[0]
    try:
        return int(prefix) == pid
    except ValueError:
        return False


def find_pq_data(
    participant_id: str | int,
    session_dirs: list[Path] | tuple[Path, ...] = (),
    questionnaire_dirs: list[Path] | tuple[Path, ...] = (),
) -> Path | None:
    """Find the raw ``*_pq_data.json`` for a participant.

    ET session folders are searched first, then ``participant_questionnaire_*``
    folders. Filenames may use a short PID form (``6_...``) or the padded form
    (``006_...``).

    Parameters
    ----------
    participant_id : str | int
        Participant ID, for example ``8``, ``"008"`` or ``"8"``.
    session_dirs : sequence of Path
        ET session folders to search.
    questionnaire_dirs : sequence of Path
        Participant questionnaire folders to search.

    Returns
    -------
    Path | None
        The first matching questionnaire file, or ``None``.
    """
    try:
        pid = int(participant_id)
    except (TypeError, ValueError):
        return None

    for directory in session_dirs:
        directory = Path(directory)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*_pq_data.json")):
            if _pid_matches(path.name, pid):
                return path

    for directory in questionnaire_dirs:
        directory = Path(directory)
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*_pq_data.json")):
            if _pid_matches(path.name, pid):
                return path

    return None


__all__ = ["find_pq_data"]
