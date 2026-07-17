import json
import random
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


def _judgments_path(dcn_name: str) -> Path:
    return swipe_judgments_path(dcn_name)


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


def _list_plot_data(dcn_name: str, sid: str) -> list[dict]:
    plots_dir = sanity_checks_path(dcn_name, sid) / f"{sid}_plots"
    plots = []
    if plots_dir.exists():
        for png in sorted(plots_dir.glob("*.png")):
            if png.stem == "main_sequence":
                continue
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


def load_judgments(dcn_name: str) -> dict[str, str]:
    path = _judgments_path(dcn_name)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_judgment(dcn_name: str, sid: str, judgment: str) -> dict[str, str]:
    if judgment not in VALID_JUDGMENTS:
        raise ValueError(f"Invalid judgment: {judgment}")
    path = _judgments_path(dcn_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    judgments = load_judgments(dcn_name)
    judgments[sid] = judgment
    with open(path, "w") as f:
        json.dump(judgments, f, indent=2)
    return judgments


def remove_judgment(dcn_name: str, sid: str) -> dict[str, str]:
    path = _judgments_path(dcn_name)
    judgments = load_judgments(dcn_name)
    judgments.pop(sid, None)
    with open(path, "w") as f:
        json.dump(judgments, f, indent=2)
    return judgments


def swipe_queue(dcn_name: str) -> list[dict]:
    sessions = list_sessions(dcn_name)
    judgments = load_judgments(dcn_name)
    dcn_summary = get_dcn(dcn_name)
    language_name = ""
    country_name_str = ""
    if dcn_summary:
        language_name = dcn_summary.language
        country_name_str = _country_name(dcn_summary.country)

    thresholds = load_thresholds(dcn_name)

    queue = []
    for s in sessions:
        overview = read_overview(session_overview_path(dcn_name, s.sid))
        if overview is None:
            continue
        review = load_review(dcn_name, s.sid)

        all_plots = _list_plot_data(dcn_name, s.sid)

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

        queue.append(
            {
                "sid": s.sid,
                "pid": s.pid,
                "is_pilot": s.is_pilot,
                "language": language_name,
                "country": country_name_str,
                "num_calibrations": overview.get("num_calibrations", 0),
                "num_validations": overview.get("num_validations", 0),
                "n_flags": s.n_flags,
                "flagged_checks": flagged,
                "review_status": s.review_status,
                "needs_reprocessing": review.needs_reprocessing,
                "type_of_issue": review.type_of_issue,
                "plots": all_plots,
                "judgment": judgments.get(s.sid),
            }
        )
    judged = [s for s in queue if s["judgment"] in ("keep", "flag")]
    unjudged = [s for s in queue if s["judgment"] is None or s["judgment"] == "skip"]
    random.shuffle(unjudged)
    random.shuffle(judged)
    return unjudged + judged


def swipe_stats(dcn_name: str) -> dict:
    judgments = load_judgments(dcn_name)
    counts = {"keep": 0, "flag": 0, "skip": 0}
    for j in judgments.values():
        if j in counts:
            counts[j] += 1
    all_sessions = list_sessions(dcn_name)
    return {
        "keep": counts["keep"],
        "flag": counts["flag"],
        "skip": counts["skip"],
        "total": len(all_sessions),
        "judged": len(judgments),
        "progress_pct": round(len(judgments) / len(all_sessions) * 100, 1)
        if all_sessions
        else 0,
    }
