"""FastAPI app, route registration, and startup."""

from pathlib import Path
import urllib.request

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import PREPROCESSED_DATA_DIR
from .routes.home import router as home_router
from .routes.collection import (
    router as collection_router,
    page_router as collection_page_router,
)
from .routes.session import router as session_router, api_router as session_api_router
from .routes.swipe import router as swipe_router

_HTMX_URL = "https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js"
_HTMX_PATH = Path(__file__).parent / "static" / "htmx.min.js"


def _ensure_htmx() -> None:
    """Download HTMX on first use so it is available offline later."""
    if not _HTMX_PATH.exists():
        try:
            data = urllib.request.urlopen(_HTMX_URL, timeout=10).read()
            _HTMX_PATH.write_bytes(data)
        except Exception as exc:
            print(
                f"WARNING: could not download HTMX ({exc}); CDN will be used as fallback."
            )


app = FastAPI(
    title="MultiplEYE Data Review",
    description="Review and annotate data quality for MultiplEYE preprocessing output.",
    version="2026.07.01",
)

app.include_router(home_router)
app.include_router(collection_router)
app.include_router(collection_page_router)
app.include_router(session_router)
app.include_router(session_api_router)
app.include_router(swipe_router)

if PREPROCESSED_DATA_DIR.exists():
    app.mount("/files", StaticFiles(directory=str(PREPROCESSED_DATA_DIR)), name="files")

_ensure_htmx()
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)


@app.on_event("startup")
def _startup() -> None:
    PREPROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    import asyncio

    def _run_preflight_for_all_dcns() -> None:
        from .config import RAW_DATA_DIR
        from .services.preflight import run_pipeline_preflight
        from preprocessing.models import Dcn

        if not RAW_DATA_DIR.exists():
            return
        for entry in sorted(RAW_DATA_DIR.iterdir()):
            if not entry.is_dir():
                continue
            try:
                Dcn(entry.name)
            except (ValueError, TypeError):
                continue
            try:
                run_pipeline_preflight(entry.name)
            except Exception as exc:
                print(f"[startup] preflight failed for {entry.name}: {exc}")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _run_preflight_for_all_dcns)


def _pick_port(preferred: int = 8765) -> int:
    """Return the first free port starting from *preferred*."""
    import socket

    for port in range(preferred, preferred + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No free port found")


def run() -> None:
    """Entry point for ``review_web`` CLI command.

    Launches the Uvicorn dev server and opens a browser tab.
    For production, use::

        uvicorn review_app.main:app --host 127.0.0.1 --port 8765
    """
    import os
    import threading
    import time
    import webbrowser

    # Store the original PID so the shutdown endpoint can kill the whole process tree.
    os.environ["REVIEW_APP_PARENT_PID"] = str(os.getpid())

    port = _pick_port()
    url = f"http://127.0.0.1:{port}"

    def _open_browser() -> None:
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    import uvicorn

    uvicorn.run(
        "review_app.main:app",
        host="127.0.0.1",
        port=port,
        reload=True,
    )
