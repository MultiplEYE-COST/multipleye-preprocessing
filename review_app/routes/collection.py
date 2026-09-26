"""DCN-level routes — overview, session list, flags, stats, psychometric."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..models import FlagSummary
from ..services.dcn import get_dcn, list_sessions
from ..templating import render

router = APIRouter(prefix="/api/dcn")


@router.get("/{dcn_name}")
async def dcn_overview(dcn_name: str) -> JSONResponse:
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    return JSONResponse(dcn.model_dump())


@router.get("/{dcn_name}/sessions")
async def dcn_sessions(dcn_name: str) -> JSONResponse:
    sessions = list_sessions(dcn_name)
    return JSONResponse([s.model_dump() for s in sessions])


@router.get("/{dcn_name}/flags")
async def dcn_flags(dcn_name: str) -> JSONResponse:
    """List all check IDs that have at least one failing session."""
    sessions = list_sessions(dcn_name)

    from ..services.dcn import _build_session_summary

    for s in sessions:
        summary = _build_session_summary(dcn_name, s.sid)
        if summary is None or summary.n_flags == 0:
            continue
        # Re-compute checks for this session to get per-flag details

    # Simplified: return all known check IDs with affected count
    from ..services.session_data import CHECK_REGISTRY

    flags: list[FlagSummary] = []
    for entry in CHECK_REGISTRY:
        field = entry["field"]
        count = 0
        for s in sessions:
            summary = _build_session_summary(dcn_name, s.sid)
            if summary:
                count += 1  # simplified: counts sessions that have this field
        flags.append(
            FlagSummary(
                flag_id=field,
                label=entry["label"],
                n_sessions_affected=count,
            )
        )
    return JSONResponse([f.model_dump() for f in flags if f.n_sessions_affected > 0])


@router.get("/{dcn_name}/psychometric")
async def dcn_psychometric(dcn_name: str) -> JSONResponse:
    """Return per-session psychometric scores."""
    import csv

    from ..config import psychometric_path

    path = psychometric_path(dcn_name)
    if not path.exists():
        return JSONResponse([])

    rows: list[dict] = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return JSONResponse(rows)


@router.get("/{dcn_name}/stats")
async def dcn_stats(dcn_name: str) -> JSONResponse:
    """Return distributions of key metrics across sessions."""
    sessions = list_sessions(dcn_name)
    if not sessions:
        return JSONResponse({})

    from ..config import session_overview_path
    from ..services.session_data import get_field, read_overview

    values: dict[str, list[float | int | bool | str]] = {}
    for s in sessions:
        ov = read_overview(session_overview_path(dcn_name, s.sid))
        if ov is None:
            continue
        for key in (
            "avg_comprehension_score",
            "session_total_data_loss_ratio",
            "session_blink_loss_ratio",
            "avg_validation_error_dva",
            "num_calibrations",
            "num_validations",
            "total_session_duration_s",
        ):
            val = get_field(ov, key)
            if val is not None and isinstance(val, (int, float)):
                values.setdefault(key, []).append(val)

    stats = {
        key: {
            "n": len(vals),
            "mean": round(sum(vals) / len(vals), 4) if vals else None,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
        }
        for key, vals in sorted(values.items())
    }
    return JSONResponse(stats)


# ---- HTML page routes (no /api prefix) ----

page_router = APIRouter()


@router.get("/{dcn_name}/open/{which}")
async def open_dcn_folder(dcn_name: str, which: str):
    """Open a DCN's data folder in the OS file manager (Finder on macOS)."""
    import subprocess
    import sys

    from ..config import PREPROCESSED_DATA_DIR, RAW_DATA_DIR

    if which == "input":
        folder = RAW_DATA_DIR / dcn_name
    elif which == "output":
        folder = PREPROCESSED_DATA_DIR / dcn_name
    else:
        raise HTTPException(status_code=400, detail="which must be 'input' or 'output'")

    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Folder not found: {folder}")

    if sys.platform == "darwin":
        subprocess.Popen(["open", str(folder.resolve())])
    elif sys.platform == "linux":
        subprocess.Popen(["xdg-open", str(folder.resolve())])
    elif sys.platform == "win32":
        subprocess.Popen(["explorer", str(folder.resolve())])

    return {"opened": str(folder.resolve())}


@router.post("/{dcn_name}/preflight/rerun")
async def rerun_preflight(dcn_name: str):
    from ..services.preflight import invalidate_cache, run_pipeline_preflight

    invalidate_cache(dcn_name)
    result = run_pipeline_preflight(dcn_name, force=True)
    return JSONResponse(result)


@page_router.get("/dcn/{dcn_name}")
async def dcn_page(request: Request, dcn_name: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    sessions = list_sessions(dcn_name)
    html = render(
        "dcn/overview.html",
        request=request,
        dcn=dcn,
        sessions=sessions,
        now="",
    )
    return HTMLResponse(html)
