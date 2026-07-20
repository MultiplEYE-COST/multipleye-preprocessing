"""Swipe mode — per-plot judgments stored in per-DCN swipe_judgments.yaml."""

import yaml
import os
import tempfile
from pathlib import Path

from ..config import dcn_path, swipe_judgments_path
from .dcn import list_sessions, get_dcn
from .session_data import read_overview, compute_checks
from .thresholds import load_thresholds
from .review import load_review
from ..config import sanity_checks_path, session_overview_path
import pycountry

VALID_JUDGMENTS = {"keep", "flag", "skip"}

_NON_SCANPATH_KEYWORDS = frozenset(
    {
        "screen",
        "rating",
        "subject",
        "familiarity",
        "instruction",
        "debriefing",
        "consent",
        "demographic",
        "welcome",
        "goodbye",
    }
)


def _country_name(code: str) -> str:
    upper = code.upper()
    try:
        country = pycountry.countries.get(alpha_2=upper)
        if country is not None:
            return country.name
    except LookupError:
        pass
    return code


# ---------------------------------------------------------------------------
# File I/O (nested YAML: {sid: {plots: {name: judgment, ...}, comments: {name: str, ...}}})
# ---------------------------------------------------------------------------

def load_judgments(dcn_name: str) -> dict:
    """Load all swipe judgments for a DCN.

    Returns ``{sid: {plots: {name: judgment, ...}, comments: {name: str, ...}}}``.
    """
    path = swipe_judgments_path(dcn_name)
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
    return data if isinstance(data, dict) else {}


def _write_judgments(dcn_name: str, data: dict) -> None:
    path = swipe_judgments_path(dcn_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".yaml", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def save_plot_judgment(dcn_name: str, sid: str, plot_name: str, judgment: str) -> dict:
    """Record a per-plot judgment. Returns the full judgments dict."""
    if judgment not in VALID_JUDGMENTS:
        raise ValueError(f"Invalid judgment: {judgment}")
    data = load_judgments(dcn_name)
    session_entry = data.setdefault(sid, {"plots": {}, "comments": {}})
    session_entry["plots"][plot_name] = judgment
    _write_judgments(dcn_name, data)
    return data


def remove_plot_judgment(dcn_name: str, sid: str, plot_name: str) -> dict:
    """Remove a per-plot judgment. Returns the full judgments dict."""
    data = load_judgments(dcn_name)
    session_entry = data.get(sid)
    if session_entry and "plots" in session_entry:
        session_entry["plots"].pop(plot_name, None)
        if not session_entry["plots"]:
            data.pop(sid, None)
    _write_judgments(dcn_name, data)
    return data


def save_plot_comment(dcn_name: str, sid: str, plot_name: str, comment: str) -> dict:
    """Save a comment for a specific plot. Returns the full judgments dict."""
    data = load_judgments(dcn_name)
    session_entry = data.setdefault(sid, {"plots": {}, "comments": {}})
    if comment:
        session_entry["comments"][plot_name] = comment
    else:
        session_entry["comments"].pop(plot_name, None)
    _write_judgments(dcn_name, data)
    return data


# ---------------------------------------------------------------------------
# Plot enumeration (now includes main_sequence)
# ---------------------------------------------------------------------------

def _parse_plot_name(stem: str) -> dict:
    """Extract stimulus, page, and activity from a plot filename stem."""
    if stem == "main_sequence":
        return {"stimulus": "Main Sequence", "page": "", "activity": ""}
    parts = stem.split("_")
    activity = ""
    page = ""
    if len(parts) >= 2:
        last = parts[-1]
        if last.startswith("q") and last[1:].isdigit():
            page = f"question {last[1:]}"
            stimulus = "_".join(parts[:-1])
        elif last.isdigit():
            page = f"page {last}"
            stimulus = "_".join(parts[:-1])
        else:
            stimulus = "_".join(parts[:-2]) if len(parts) >= 3 else stem
            activity = parts[-1]
    else:
        stimulus = stem
    return {"stimulus": stimulus, "page": page, "activity": activity}


def list_plot_data(dcn_name: str, sid: str) -> list[dict]:
    """List all gaze plot PNGs for a session, including main_sequence.

    Returns a list of ``{url, name, stimulus, page, activity}`` sorted
    with main_sequence first, then by filename.
    """
    plots_dir = sanity_checks_path(dcn_name, sid) / f"{sid}_plots"
    plots = []
    if plots_dir.exists():
        files = sorted(
            plots_dir.glob("*.png"),
            key=lambda p: ("0" if p.stem == "main_sequence" else "1", p.stem),
        )
        for png in files:
            meta = _parse_plot_name(png.stem)
            if meta["page"].startswith("question"):
                continue
            stimulus_parts = meta["stimulus"].lower().split("_")
            if any(kw in stimulus_parts for kw in _NON_SCANPATH_KEYWORDS):
                continue
            relative = png.relative_to(dcn_path(dcn_name).parent)
            plots.append(
                {
                    "url": f"/files/{relative}",
                    "name": png.stem,
                    "stimulus": meta["stimulus"],
                    "page": meta["page"],
                    "activity": meta["activity"],
                }
            )
    return plots


# ---------------------------------------------------------------------------
# Swipe queue — all sessions with their plots, natural order, no shuffle
# ---------------------------------------------------------------------------

def _compute_stats(data: dict, all_sessions: list, enriched_sessions: list) -> dict:
    total_plots = sum(s["n_plots"] for s in enriched_sessions)
    plots_judged = sum(1 for s in enriched_sessions for p in s["plots"] if p.get("judgment"))
    keep = sum(1 for s in enriched_sessions for p in s["plots"] if p.get("judgment") == "keep")
    flag = sum(1 for s in enriched_sessions for p in s["plots"] if p.get("judgment") == "flag")
    skip = sum(1 for s in enriched_sessions for p in s["plots"] if p.get("judgment") == "skip")
    sessions_complete = sum(
        1 for s in enriched_sessions
        if s["n_plots"] > 0 and all(p.get("judgment") for p in s["plots"])
    )
    sessions_judged = {sid for sid, entry in data.items() if entry.get("plots")}
    sessions_skipped = len([s for s in enriched_sessions if s["sid"] in sessions_judged and not all(p.get("judgment") for p in s["plots"])])
    return {
        "plots_judged": plots_judged,
        "total_plots": total_plots,
        "keep": keep,
        "flag": flag,
        "skip": skip,
        "sessions_complete": sessions_complete,
        "sessions_skipped": sessions_skipped,
        "total_sessions": len(all_sessions),
        "progress_pct": round(plots_judged / total_plots * 100, 1) if total_plots else 0,
    }


def swipe_data(dcn_name: str) -> dict:
    """Return all sessions with plot-level judgment state (natural order, no shuffle).

    Returns ``{"sessions": [...], "stats": {...}}``.
    """
    sessions = list_sessions(dcn_name)
    judgments = load_judgments(dcn_name)
    dcn_summary = get_dcn(dcn_name)
    language_name = ""
    country_name_str = ""
    if dcn_summary:
        language_name = dcn_summary.language
        country_name_str = _country_name(dcn_summary.country)

    thresholds = load_thresholds(dcn_name)

    enriched = []
    for s in sessions:
        overview = read_overview(session_overview_path(dcn_name, s.sid))
        if overview is None:
            continue
        review = load_review(dcn_name, s.sid)

        plots = list_plot_data(dcn_name, s.sid)
        plot_judgments = judgments.get(s.sid, {}).get("plots", {})
        plot_comments = judgments.get(s.sid, {}).get("comments", {})

        for p in plots:
            p["judgment"] = plot_judgments.get(p["name"])
            p["comment"] = plot_comments.get(p["name"], "")

        checks = compute_checks(overview, thresholds)
        flagged = [
            {
                "label": c.label,
                "value": str(c.value) if c.value is not None else "",
                "threshold": c.threshold,
                "status": c.status,
            }
            for c in checks
            if c.status != "pass"
        ]

        enriched.append(
            {
                "sid": s.sid,
                "pid": s.pid,
                "is_pilot": s.is_pilot,
                "language": language_name,
                "country": country_name_str,
                "num_calibrations": overview.get("num_calibrations", 0),
                "num_validations": overview.get("num_validations", 0),
                "n_flags": s.n_flags,
                "n_fail_flags": s.n_fail_flags,
                "n_warn_flags": s.n_warn_flags,
                "flagged_checks": flagged,
                "review_status": s.review_status,
                "reviewer": s.reviewer,
                "comment_preview": s.comment_preview,
                "needs_reprocessing": review.needs_reprocessing,
                "type_of_issue": review.type_of_issue,
                "n_plots": len(plots),
                "plots": plots,
            }
        )

    stats = _compute_stats(judgments, sessions, enriched)
    return {"sessions": enriched, "stats": stats}


def swipe_stats(dcn_name: str) -> dict:
    """Quick stats without building the full queue."""
    sessions = list_sessions(dcn_name)
    judgments = load_judgments(dcn_name)
    total_plots = 0
    for s in sessions:
        plots = list_plot_data(dcn_name, s.sid)
        total_plots += len(plots)
    plots_judged = sum(len(entry.get("plots", {})) for entry in judgments.values())
    counts = {"keep": 0, "flag": 0, "skip": 0}
    for entry in judgments.values():
        for j in entry.get("plots", {}).values():
            if j in counts:
                counts[j] += 1
    sessions_complete = 0
    sessions_skipped = 0
    for s in sessions:
        plots = list_plot_data(dcn_name, s.sid)
        n_plots = len(plots)
        if n_plots == 0:
            continue
        judged = judgments.get(s.sid, {}).get("plots", {})
        n_judged = len(judged)
        if n_judged == n_plots:
            sessions_complete += 1
        elif n_judged > 0:
            sessions_skipped += 1
    return {
        "plots_judged": plots_judged,
        "total_plots": total_plots,
        "keep": counts["keep"],
        "flag": counts["flag"],
        "skip": counts["skip"],
        "sessions_complete": sessions_complete,
        "sessions_skipped": sessions_skipped,
        "total_sessions": len(sessions),
        "progress_pct": round(plots_judged / total_plots * 100, 1) if total_plots else 0,
    }


# ---------------------------------------------------------------------------
# Legacy support — wrapped from routes/session.py that reads per-session judgments
# ---------------------------------------------------------------------------

def load_session_judgment(dcn_name: str, sid: str) -> str | None:
    """Load a single session's plot judgments. Returns None if none."""
    data = load_judgments(dcn_name)
    entry = data.get(sid, {})
    plots = entry.get("plots", {})
    if not plots:
        return None
    judgments = list(plots.values())
    if all(j == "keep" for j in judgments):
        return "keep"
    if all(j == "flag" for j in judgments):
        return "flag"
    if all(j == "skip" for j in judgments):
        return "skip"
    # Mixed — show strongest (flag > skip > keep)
    if "flag" in judgments:
        return "flag"
    return "mixed"


def load_plot_judgments_dict(dcn_name: str, sid: str) -> dict:
    """Load per-plot judgments dict for a session, keyed by plot name."""
    data = load_judgments(dcn_name)
    entry = data.get(sid, {})
    return entry.get("plots", {})


def load_plot_comments_dict(dcn_name: str, sid: str) -> dict:
    """Load per-plot comments dict for a session, keyed by plot name."""
    data = load_judgments(dcn_name)
    entry = data.get(sid, {})
    return entry.get("comments", {})
