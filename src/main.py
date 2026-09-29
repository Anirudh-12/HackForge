from __future__ import annotations

import logging
import os
from pathlib import Path

class _UvicornHostFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        replacement_host = os.environ.get("DISPLAY_HOST", "localhost")
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            if record.args[1] == "0.0.0.0":
                args = list(record.args)
                args[1] = replacement_host
                record.args = tuple(args)
        if isinstance(record.msg, str) and "0.0.0.0" in record.msg:
            record.msg = record.msg.replace("0.0.0.0", replacement_host)
        if hasattr(record, "color_message") and isinstance(record.color_message, str) and "0.0.0.0" in record.color_message:
            record.color_message = record.color_message.replace("0.0.0.0", replacement_host)
        return True

_host_filter = _UvicornHostFilter()
logging.getLogger("uvicorn.error").addFilter(_host_filter)
logging.getLogger("uvicorn").addFilter(_host_filter)

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.db import SessionLocal, init_db
from src.seed import seed
from src.templating import templates

ROOT = Path(__file__).resolve().parent

API_DESCRIPTION = """
# HackForge REST API

Welcome to the **HackForge API**, the open-source, self-hostable hackathon submission and judging platform.

## Architecture & Role Enforcement
HackForge implements **strict backend role isolation** across 5 distinct personas:
* **Visitor / Public**: Unauthenticated exploration of project gallery, event tracks, and cryptographic verification of records.
* **Participant**: Team formation, submission drafts, deadline enforcement, peer community voting, and comments.
* **Judge**: Rubric scoring, evaluations, conflict-of-interest recusal, and verifiable judging credentials. Peer score isolation is strictly enforced at the database query layer (HTTP 403 Forbidden).
* **Organizer / Admin**: Track & rubric configuration, judge assignment, real-time progress dashboard, normalized ranking computation, CSV/JSON exports, webhooks, and bulk imports.

## Authentication Protocols
Authentication is performed via session cookies or bearer authorization headers:
* **Cookie Header**: `Cookie: session=<token>`
* **Authorization Header**: `Authorization: Bearer <token>`

*Test accounts seeded from `fixtures.json` accept any password at `/login`.*

## Tier Capabilities
* **T1 Core**: Public gallery, fixture project display, deadline enforcement.
* **T2 Judging**: Judge assignments, configurable rubric, peer score isolation, live organizer dashboard, CSV export.
* **T3 Public & Community**: Authenticated peer voting, threaded project comments, results suppression during voting, randomized ballot ordering, rate-limiting & audit trails.
* **T4 Stretch**: Webhooks with HMAC-SHA256 signature verification, verifiable certificate generation, signed judge participation records, embeddable gallery widget, and bulk data import/export.
"""

TAGS_METADATA = [
    {
        "name": "organizer",
        "description": "Event management, judge assignment, rubric configuration, progress monitoring, and results publication.",
    },
    {
        "name": "judge",
        "description": "Scoring rubric evaluations, project scoring, and peer score isolation.",
    },
    {
        "name": "participant",
        "description": "Team registration, project submission, and participant dashboard operations.",
    },
    {
        "name": "voting",
        "description": "Authenticated peer community voting, vote status querying, rate limiting, and project comments.",
    },
    {
        "name": "t4-stretch",
        "description": "T4 Stretch: Webhooks, Certificates, Signed Judge Records, Embeddable Gallery Widget, and Bulk Import/Export.",
    },
    {
        "name": "public",
        "description": "Public project gallery, search/filter, and tamper-evident record verification.",
    },
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="HackForge API",
        version="1.0.0",
        description=API_DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()

    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    from src.routers import (
        admin,
        auth,
        judge,
        notifications,
        organizer,
        participant,
        public,
        t4,
        voting,
    )

    app.include_router(auth.router)
    app.include_router(participant.router)
    app.include_router(organizer.router)
    app.include_router(judge.router)
    app.include_router(admin.router)
    app.include_router(public.router)
    app.include_router(notifications.router)
    app.include_router(voting.router)
    app.include_router(t4.router)

    # Custom OpenAPI Schema with Security Schemes
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=TAGS_METADATA,
        )
        openapi_schema["components"] = openapi_schema.get("components", {})
        openapi_schema["components"]["securitySchemes"] = {
            "CookieAuth": {
                "type": "apiKey",
                "in": "cookie",
                "name": "session",
                "description": "Session token cookie (e.g. session=org_1...)",
            },
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "Bearer token header",
            },
        }
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    @app.exception_handler(StarletteHTTPException)
    async def http_exc(request: Request, exc: StarletteHTTPException):
        accept = request.headers.get("accept", "")
        wants_html = "text/html" in accept and request.method == "GET"
        if wants_html and exc.status_code in (401, 403) and request.url.path not in ("/login",):
            if exc.status_code == 401:
                next_url = request.url.path
                return RedirectResponse(f"/login?next={next_url}", status_code=303)
        if wants_html:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={
                    "request": request,
                    "status": exc.status_code,
                    "detail": exc.detail,
                    "event": None,
                    "user": None,
                    "role": "visitor",
                },
                status_code=exc.status_code,
            )
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return app


app = create_app()
