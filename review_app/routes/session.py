"""Session-level routes — detail page, review save."""

from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..templating import render
from ..services.session_data import read_overview, build_session_detail
from ..services.thresholds import load_thresholds
from ..services.review import load_review, save_review
from ..services.swipe import load_plot_judgments_dict, load_plot_comments_dict, _NON_SCANPATH_KEYWORDS, list_plot_data


router = APIRouter()


@router.get("/dcn/{dcn}/session/{sid}")
async def session_page(
    request: Request,
    dcn: str,
    sid: str,
):
    from ..config import session_overview_path, sanity_checks_path
    from ..services.dcn import list_sessions

    sessions = list_sessions(dcn)

    ov = read_overview(session_overview_path(dcn, sid))
    if ov is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{sid}' not found in DCN '{dcn}'"
        )
    thresholds = load_thresholds(dcn)
    review = load_review(dcn, sid)
    detail = build_session_detail(ov, review, thresholds, dcn, sid)

    plots = list_plot_data(dcn, sid)
    plot_judgments = load_plot_judgments_dict(dcn, sid)
    plot_comments = load_plot_comments_dict(dcn, sid)
    for p in plots:
        p["judgment"] = plot_judgments.get(p["name"])
        p["comment"] = plot_comments.get(p["name"], "")

    html = render(
        "session/detail.html",
        request=request,
        detail=detail,
        dcn=dcn,
        sessions=sessions,
        plots=plots,
        plot_judgments=plot_judgments,
        plot_comments=plot_comments,
        now="",
        review_action="loaded",
    )
    return HTMLResponse(html)


@router.get("/dcn/{dcn}/session/{sid}/content")
async def session_content_partial(
    request: Request,
    dcn: str,
    sid: str,
):
    """Return just the session content HTML (no base template)."""
    from ..config import session_overview_path
    from ..services.dcn import list_sessions
    from ..services.swipe import load_plot_judgments_dict, load_plot_comments_dict, list_plot_data

    sessions = list_sessions(dcn)

    ov = read_overview(session_overview_path(dcn, sid))
    if ov is None:
        raise HTTPException(status_code=404, detail=f"Session '{sid}' not found in DCN '{dcn}'")
    thresholds = load_thresholds(dcn)
    review = load_review(dcn, sid)
    detail = build_session_detail(ov, review, thresholds, dcn, sid)

    plots = list_plot_data(dcn, sid)
    plot_judgments = load_plot_judgments_dict(dcn, sid)
    plot_comments = load_plot_comments_dict(dcn, sid)
    for p in plots:
        p["judgment"] = plot_judgments.get(p["name"])
        p["comment"] = plot_comments.get(p["name"], "")

    html = render(
        "session/_detail_content.html",
        request=request,
        detail=detail,
        dcn=dcn,
        sessions=sessions,
        plots=plots,
        plot_judgments=plot_judgments,
        plot_comments=plot_comments,
        now="",
        review_action="loaded",
    )
    return HTMLResponse(html)


# ---- API routes (HTMX) ----

api_router = APIRouter(prefix="/api/dcn/{dcn}/session")


@api_router.get("/{sid}")
async def session_detail(
    sid: str,
    dcn: str,
):
    from ..config import session_overview_path

    ov = read_overview(session_overview_path(dcn, sid))
    if ov is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{sid}' not found in DCN '{dcn}'"
        )
    thresholds = load_thresholds(dcn)
    review = load_review(dcn, sid)
    detail = build_session_detail(ov, review, thresholds, dcn, sid)
    return detail.model_dump()


def _open_folder(folder: Path):
    """Open a folder in the OS file manager."""
    import subprocess
    import sys

    if not folder.exists():
        raise HTTPException(
            status_code=404, detail=f"Folder not found: {folder}"
        )
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(folder.resolve())])
    elif sys.platform == "linux":
        subprocess.Popen(["xdg-open", str(folder.resolve())])
    elif sys.platform == "win32":
        subprocess.Popen(["explorer", str(folder.resolve())])
    return {"opened": str(folder.resolve())}


@api_router.get("/{sid}/open")
async def session_open_folder(
    dcn: str,
    sid: str,
):
    """Open the raw session data folder (asc, logs) in the OS file manager."""
    from ..config import RAW_DATA_DIR

    folder = RAW_DATA_DIR / dcn / "eye-tracking-sessions" / sid
    return _open_folder(folder)


@api_router.get("/{sid}/open-metadata")
async def session_open_metadata(
    dcn: str,
    sid: str,
):
    """Open the preprocessed metadata folder in the OS file manager."""
    from ..config import metadata_path

    folder = metadata_path(dcn, sid)
    return _open_folder(folder)


@api_router.get("/{sid}/open-sanity")
async def session_open_sanity(
    dcn: str,
    sid: str,
):
    """Open the sanity checks folder in the OS file manager."""
    from ..config import sanity_checks_path

    folder = sanity_checks_path(dcn, sid)
    return _open_folder(folder)


@api_router.get("/{sid}/open-comp-answers")
async def session_open_comp_answers(
    dcn: str,
    sid: str,
):
    """Open the comparative answers folder in the OS file manager."""
    from ..config import dcn_path

    folder = dcn_path(dcn) / "comp_answers" / sid
    return _open_folder(folder)


@api_router.post("/{sid}/review")
async def session_review_save(
    request: Request,
    dcn: str,
    sid: str,
    status: str = "unreviewed",
):
    from ..config import session_overview_path

    form = await request.form()
    comment = str(form.get("comment", request.query_params.get("comment", "")))
    reviewer = str(form.get("reviewer", request.query_params.get("reviewer", "")))
    type_of_issue = str(
        form.get("type_of_issue", request.query_params.get("type_of_issue", ""))
    )
    needs_reprocessing = form.get(
        "needs_reprocessing", request.query_params.get("needs_reprocessing", "false")
    ) in ("true", "True", "1")
    annotation = save_review(
        dcn,
        sid,
        status=status,
        reviewer=reviewer,
        comment=comment,
        type_of_issue=type_of_issue,
        needs_reprocessing=needs_reprocessing,
    )
    ov = read_overview(session_overview_path(dcn, sid))
    thresholds = load_thresholds(dcn)
    detail = build_session_detail(ov, annotation, thresholds, dcn, sid)
    html = render(
        "session/_review_form.html",
        request=request,
        detail=detail,
        dcn=dcn,
        review_action="saved",
    )
    return HTMLResponse(html)
