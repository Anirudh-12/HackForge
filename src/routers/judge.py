from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.auth import require_role
from src.context import base_context
from src.db import get_db
from src.templating import templates
from src.models import Event, User

router = APIRouter()


@router.get("/judge/{event_id}/dashboard")
def judge_dashboard(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("judge", "organizer", "admin")),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return templates.TemplateResponse(request=request, name="judge/dashboard.html", context=
        base_context(request=request, event=event, user=user, role="judge"),
    )
