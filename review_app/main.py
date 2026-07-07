"""FastAPI app, route registration, and startup."""


from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import PREPROCESSED_DATA_DIR
from .routes.home import router as home_router
from .routes.collection import router as collection_router
from .routes.session import router as session_router


app = FastAPI(
    title="MultiplEYE Data Review",
    description="Review and annotate data quality for MultiplEYE preprocessing output.",
    version="2026.07.01",
)


@app.on_event("startup")
def _startup() -> None:
    """Ensure the preprocessed data directory exists on startup."""
    PREPROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)


app.include_router(home_router)
app.include_router(collection_router)
app.include_router(session_router)

# Mount the preprocessed data directory for static file serving (plots, reports, etc.)
# Files are served under /files/<dcn_name>/... with path validation in the routes.
if PREPROCESSED_DATA_DIR.exists():
    app.mount("/files", StaticFiles(directory=str(PREPROCESSED_DATA_DIR)), name="files")


def run() -> None:
    """Entry point for ``review_web`` CLI command.

    Launches the Uvicorn dev server. For production, use::

        uvicorn review_app.main:app --host 127.0.0.1 --port 8765
    """
    import uvicorn

    uvicorn.run(
        "review_app.main:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
    )
