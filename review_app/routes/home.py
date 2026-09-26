"""Home page — list all data collections."""

import os
import signal

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..config import PREPROCESSED_DATA_DIR
from ..services.dcn import list_dcns
from ..templating import render

router = APIRouter()


@router.get("/")
async def home(request: Request):
    dcns = list_dcns()
    html = render(
        "home.html",
        request=request,
        dcns=dcns,
        preprocessed_dir=str(PREPROCESSED_DATA_DIR),
        now="",
    )
    return HTMLResponse(html)


@router.post("/api/shutdown")
async def shutdown():
    """Kill the uvicorn reloader process to stop the server."""
    parent_pid = int(os.environ.get("REVIEW_APP_PARENT_PID", os.getpid()))
    os.kill(parent_pid, signal.SIGTERM)
    return {"status": "shutting down"}
