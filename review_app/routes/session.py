"""Session-level routes — detail page, review save."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..templating import render
from ..services.session_data import read_overview, build_session_detail
from ..services.thresholds import load_thresholds
from ..services.review import load_review, save_review


router = APIRouter()


@router.get("/dcn/{dcn}/session/{sid}")
async def session_page(
    request: Request,
    dcn: str,
    sid: str,
):
    from ..config import session_overview_path, sanity_checks_path

    ov = read_overview(session_overview_path(dcn, sid))
    if ov is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{sid}' not found in DCN '{dcn}'"
        )
    thresholds = load_thresholds(dcn)
    review = load_review(dcn, sid)
    detail = build_session_detail(ov, review, thresholds, dcn, sid)

    plots_dir = sanity_checks_path(dcn, sid) / f"{sid}_plots"
    plots: list[dict] = []
    if plots_dir.exists():
        plot_files = sorted(
            plots_dir.glob("*.png"),
            key=lambda p: ("0" if p.stem == "main_sequence" else "1", p.stem),
        )
        for png in plot_files:
            relative = png.relative_to(
                sanity_checks_path(dcn, sid).parent.parent.parent
            )
            url = f"/files/{relative}"
            name = png.stem
            if name == "main_sequence":
                plots.append(
                    {
                        "url": url,
                        "stimulus": "Main Sequence",
                        "page": "",
                        "activity": "",
                    }
                )
            else:
                parts = name.split("_")
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
                        stimulus = "_".join(parts[:-2]) if len(parts) >= 3 else name
                        activity = parts[-1]
                else:
                    stimulus = name
                plots.append(
                    {
                        "url": url,
                        "stimulus": stimulus,
                        "page": page,
                        "activity": activity,
                    }
                )

    html = render(
        "session/detail.html",
        request=request,
        detail=detail,
        dcn=dcn,
        plots=plots,
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
    annotation = save_review(
        dcn, sid, status=status, reviewer=reviewer, comment=comment
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
