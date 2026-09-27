from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.db import SessionLocal, init_db
from src.seed import seed
from src.templating import templates

ROOT = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title="Hackforge")

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()

    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    from src.routers import admin, auth, judge, organizer, participant, public, notifications

    app.include_router(auth.router)
    app.include_router(participant.router)
    app.include_router(organizer.router)
    app.include_router(judge.router)
    app.include_router(admin.router)
    app.include_router(public.router)
    app.include_router(notifications.router)

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(request: Request, exc: StarletteHTTPException):
        accept = request.headers.get("accept", "")
        wants_html = "text/html" in accept and request.method == "GET"
        if wants_html and exc.status_code in (401, 403) and request.url.path not in ("/login",):
            if exc.status_code == 401:
                next_url = request.url.path
                return RedirectResponse(f"/login?next={next_url}", status_code=303)
        if wants_html:
            return templates.TemplateResponse(request=request, name="error.html", context=
                {"request": request, "status": exc.status_code, "detail": exc.detail, "event": None, "user": None, "role": "visitor"},
                status_code=exc.status_code,
            )
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return app


app = create_app()
