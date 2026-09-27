from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.auth import require_role
from src.context import base_context
from src.db import get_db
from src.templating import templates
from src.models import Event, User
from src.queries import default_event

router = APIRouter()


@router.get("/admin/dashboard")
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    events = db.query(Event).order_by(Event.name.asc()).all()
    return templates.TemplateResponse(request=request, name="admin/dashboard.html", context=
        base_context(request=request, event=default_event(db), user=user, role="admin", events=events),
    )
