"""DCN-level JSON routes and folder actions."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..services.dcn import get_dcn, list_sessions

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
