from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from src.auth import get_current_user, require_login
from src.context import base_context, role_for
from src.db import get_db
from src.models import (
    AuditLog,
    Certificate,
    Comment,
    Event,
    EventMember,
    JudgeRecord,
    JudgeTrack,
    Project,
    RubricCriteria,
    Score,
    Team,
    TeamMember,
    Track,
    User,
    Vote,
    WebhookDelivery,
    WebhookSubscription,
)
from src.queries import default_event, user_team
from src.templating import templates
from src.timeutil import utcnow
from src.webhooks import (
    dispatch_webhook,
    generate_judge_record_signature,
    verify_judge_record_signature,
)

router = APIRouter(tags=["t4-stretch"])


def _check_organizer(db: Session, user: User, event_id: str) -> None:
    membership = (
        db.query(EventMember)
        .filter(EventMember.user_id == user.id, EventMember.event_id == event_id)
        .first()
    )
    if not membership or membership.role not in ("organizer", "admin"):
        any_admin = (
            db.query(EventMember)
            .filter(EventMember.user_id == user.id, EventMember.role == "admin")
            .first()
        )
        if not any_admin:
            raise HTTPException(
                status_code=403, detail="Organizer or Admin permissions required"
            )


# ---------------------------------------------------------------------------
# Pydantic Schemas for Swagger / ReDoc
# ---------------------------------------------------------------------------


class WebhookCreate(BaseModel):
    target_url: str = Field(..., description="Destination HTTP POST endpoint")
    events: str = Field(
        default="*",
        description="Comma-separated event names or '*' for all. Example: 'project.submitted,score.submitted'",
    )


class WebhookResponse(BaseModel):
    id: str
    event_id: str
    target_url: str
    secret: str
    events: str
    is_active: bool
    created_at: str


class CertificateResponse(BaseModel):
    id: str
    event_id: str
    user_id: str
    recipient_name: str
    recipient_type: str
    title: str
    track_name: Optional[str] = None
    placement: Optional[str] = None
    verification_code: str
    verification_url: str
    issued_at: str


class JudgeRecordResponse(BaseModel):
    id: str
    event_id: str
    event_name: str
    judge_id: str
    judge_name: str
    scores_count: int
    tracks_judged: str
    issued_at: str
    signature: str
    is_valid: bool
    verification_url: str


# ---------------------------------------------------------------------------
# 1. WEBHOOKS (T4 Stretch)
# ---------------------------------------------------------------------------


@router.post(
    "/api/events/{event_id}/webhooks",
    response_model=WebhookResponse,
    summary="Register Webhook Subscription",
    description="Registers an HTTP POST callback target URL for real-time hackathon events.",
)
def create_webhook(
    event_id: str,
    payload: WebhookCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    _check_organizer(db, user, event_id)
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    secret = f"whsec_{uuid.uuid4().hex}"
    sub = WebhookSubscription(
        id=f"sub_{uuid.uuid4().hex[:10]}",
        event_id=event_id,
        target_url=payload.target_url,
        secret=secret,
        events=payload.events or "*",
        is_active=True,
        created_at=utcnow(),
    )
    db.add(sub)
    db.add(
        AuditLog(
            event_id=event_id,
            actor_id=user.id,
            message=f"Created webhook subscription {sub.id} targeting {sub.target_url}",
            created_at=utcnow(),
        )
    )
    db.commit()

    return WebhookResponse(
        id=sub.id,
        event_id=sub.event_id,
        target_url=sub.target_url,
        secret=sub.secret,
        events=sub.events,
        is_active=sub.is_active,
        created_at=sub.created_at.isoformat(),
    )


@router.get(
    "/api/events/{event_id}/webhooks",
    response_model=List[WebhookResponse],
    summary="List Webhooks",
    description="Lists all active and configured webhooks for an event (Organizer only).",
)
def list_webhooks(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    _check_organizer(db, user, event_id)
    subs = (
        db.query(WebhookSubscription)
        .filter(WebhookSubscription.event_id == event_id)
        .order_by(WebhookSubscription.created_at.desc())
        .all()
    )
    return [
        WebhookResponse(
            id=s.id,
            event_id=s.event_id,
            target_url=s.target_url,
            secret=s.secret,
            events=s.events,
            is_active=s.is_active,
            created_at=s.created_at.isoformat(),
        )
        for s in subs
    ]


@router.delete(
    "/api/events/{event_id}/webhooks/{sub_id}",
    summary="Delete Webhook",
    description="Removes an existing webhook subscription.",
)
def delete_webhook(
    event_id: str,
    sub_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    _check_organizer(db, user, event_id)
    sub = db.get(WebhookSubscription, sub_id)
    if not sub or sub.event_id != event_id:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")

    db.delete(sub)
    db.add(
        AuditLog(
            event_id=event_id,
            actor_id=user.id,
            message=f"Deleted webhook subscription {sub_id}",
            created_at=utcnow(),
        )
    )
    db.commit()
    return {"success": True, "deleted_id": sub_id}


@router.post(
    "/api/events/{event_id}/webhooks/{sub_id}/test",
    summary="Test Webhook Ping",
    description="Dispatches a test ping event to verify the target endpoint and HMAC signature.",
)
def test_webhook(
    event_id: str,
    sub_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    _check_organizer(db, user, event_id)
    sub = db.get(WebhookSubscription, sub_id)
    if not sub or sub.event_id != event_id:
        raise HTTPException(status_code=404, detail="Webhook subscription not found")

    test_payload = {
        "action": "ping",
        "message": "HackForge test ping delivery",
        "sender": user.name,
        "event_id": event_id,
    }
    dispatch_webhook(event_id, "ping", test_payload)
    return {"success": True, "message": "Test ping queued for dispatch"}


# ---------------------------------------------------------------------------
# 2. CERTIFICATES & RECORD GENERATION (T4 Stretch)
# ---------------------------------------------------------------------------


def _is_certificate_eligible(db: Session, cert: Certificate) -> bool:
    """Participation certificates are only valid/issued if the participant's team submitted an eligible project."""
    if cert.recipient_type == "participant":
        team = user_team(db, cert.user_id, cert.event_id)
        if not team:
            return False
        proj = (
            db.query(Project)
            .filter(
                Project.team_id == team.id,
                Project.event_id == cert.event_id,
                Project.is_draft.is_(False),
                Project.is_disqualified.is_(False),
            )
            .first()
        )
        if not proj:
            return False
    return True


@router.post(
    "/api/events/{event_id}/certificates/generate",
    summary="Generate Event Certificates",
    description="Bulk generates verifiable participation (for participants with submitted projects) and judging certificates for all judges in the event.",
)
def generate_event_certificates(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    _check_organizer(db, user, event_id)
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    created_count = 0

    # 1. Purge any obsolete/ineligible participant certificates (where no submitted project exists)
    existing_participant_certs = (
        db.query(Certificate)
        .filter(Certificate.event_id == event_id, Certificate.recipient_type == "participant")
        .all()
    )
    for c in existing_participant_certs:
        if not _is_certificate_eligible(db, c):
            db.delete(c)
    db.flush()

    # 2. Generate for Participants ONLY if their team submitted a project
    participant_members = (
        db.query(EventMember)
        .options(joinedload(EventMember.user))
        .filter(EventMember.event_id == event_id, EventMember.role == "participant")
        .all()
    )

    for pm in participant_members:
        team = user_team(db, pm.user_id, event_id)
        if not team:
            continue

        proj = (
            db.query(Project)
            .filter(
                Project.team_id == team.id,
                Project.event_id == event_id,
                Project.is_draft.is_(False),
                Project.is_disqualified.is_(False),
            )
            .first()
        )
        if not proj:
            continue

        existing = (
            db.query(Certificate)
            .filter(
                Certificate.event_id == event_id,
                Certificate.user_id == pm.user_id,
                Certificate.recipient_type == "participant",
            )
            .first()
        )
        if not existing:
            track_name = proj.track.name if proj.track else None

            code = f"CERT-PRT-{uuid.uuid4().hex[:8].upper()}"
            cert = Certificate(
                id=f"cert_{uuid.uuid4().hex[:10]}",
                event_id=event_id,
                user_id=pm.user_id,
                recipient_name=pm.user.name,
                recipient_type="participant",
                title="Certificate of Participation",
                track_name=track_name,
                placement="Finalist" if event.results_published else "Participant",
                verification_code=code,
                issued_at=utcnow(),
                metadata_json=json.dumps({"team_name": team.name if team else None}),
            )
            db.add(cert)
            created_count += 1

    # 2. Generate for Judges
    judge_members = (
        db.query(EventMember)
        .options(joinedload(EventMember.user))
        .filter(EventMember.event_id == event_id, EventMember.role == "judge")
        .all()
    )

    for jm in judge_members:
        existing = (
            db.query(Certificate)
            .filter(
                Certificate.event_id == event_id,
                Certificate.user_id == jm.user_id,
                Certificate.recipient_type == "judge",
            )
            .first()
        )
        if not existing:
            code = f"CERT-JDG-{uuid.uuid4().hex[:8].upper()}"
            cert = Certificate(
                id=f"cert_{uuid.uuid4().hex[:10]}",
                event_id=event_id,
                user_id=jm.user_id,
                recipient_name=jm.user.name,
                recipient_type="judge",
                title="Certificate of Judging Excellence",
                track_name="Evaluation Committee",
                placement="Official Judge",
                verification_code=code,
                issued_at=utcnow(),
            )
            db.add(cert)
            created_count += 1

    db.add(
        AuditLog(
            event_id=event_id,
            actor_id=user.id,
            message=f"Generated {created_count} event certificates",
            created_at=utcnow(),
        )
    )
    db.commit()
    total_certs = db.query(Certificate).filter(Certificate.event_id == event_id).count()

    return {
        "success": True,
        "certificates_generated": created_count,
        "total_certificates": total_certs,
        "message": f"Successfully generated {created_count} verifiable certificates (Total: {total_certs})",
    }


@router.get(
    "/api/certificates/{cert_id}",
    response_model=CertificateResponse,
    summary="Get Certificate Metadata",
    description="Retrieves structured certificate details and public verification URL.",
)
def get_certificate_data(
    cert_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cert = db.get(Certificate, cert_id)
    if not cert or not _is_certificate_eligible(db, cert):
        raise HTTPException(status_code=404, detail="Certificate not found")

    base = str(request.base_url).rstrip("/")
    return CertificateResponse(
        id=cert.id,
        event_id=cert.event_id,
        user_id=cert.user_id,
        recipient_name=cert.recipient_name,
        recipient_type=cert.recipient_type,
        title=cert.title,
        track_name=cert.track_name,
        placement=cert.placement,
        verification_code=cert.verification_code,
        verification_url=f"{base}/verify/certificate/{cert.verification_code}",
        issued_at=cert.issued_at.isoformat(),
    )


@router.get(
    "/api/certificates/{cert_id}/download",
    summary="Download Certificate SVG",
    description="Returns a standalone vector SVG rendering of the verifiable certificate suitable for export and printing.",
)
def download_certificate_svg(
    cert_id: str,
    db: Session = Depends(get_db),
):
    cert = (
        db.query(Certificate)
        .options(joinedload(Certificate.event))
        .filter(Certificate.id == cert_id)
        .first()
    )
    if not cert or not _is_certificate_eligible(db, cert):
        raise HTTPException(status_code=404, detail="Certificate not found")

    event_name = cert.event.name if cert.event else "HackForge Hackathon"
    date_str = cert.issued_at.strftime("%B %d, %Y")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700" width="100%" height="100%">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a" />
      <stop offset="100%" stop-color="#1e293b" />
    </linearGradient>
    <linearGradient id="gold" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f59e0b" />
      <stop offset="50%" stop-color="#fbbf24" />
      <stop offset="100%" stop-color="#d97706" />
    </linearGradient>
  </defs>

  <!-- Border & Frame -->
  <rect x="20" y="20" width="960" height="660" rx="16" fill="url(#bg)" stroke="url(#gold)" stroke-width="4"/>
  <rect x="35" y="35" width="930" height="630" rx="10" fill="none" stroke="#334155" stroke-width="1.5" stroke-dasharray="6,4"/>

  <!-- Brand Emblem -->
  <text x="500" y="110" font-family="sans-serif" font-size="28" font-weight="900" fill="url(#gold)" text-anchor="middle" letter-spacing="4">HACKFORGE</text>
  <text x="500" y="140" font-family="sans-serif" font-size="14" fill="#94a3b8" text-anchor="middle" letter-spacing="2">OFFICIAL EVENT RECORD</text>

  <!-- Title -->
  <text x="500" y="220" font-family="Georgia, serif" font-size="38" font-weight="bold" fill="#ffffff" text-anchor="middle">{cert.title}</text>
  <text x="500" y="260" font-family="sans-serif" font-size="16" fill="#94a3b8" text-anchor="middle">This is proudly presented to</text>

  <!-- Recipient -->
  <text x="500" y="330" font-family="sans-serif" font-size="44" font-weight="bold" fill="url(#gold)" text-anchor="middle">{cert.recipient_name}</text>
  <line x1="300" y1="355" x2="700" y2="355" stroke="url(#gold)" stroke-width="1.5"/>

  <!-- Body -->
  <text x="500" y="405" font-family="sans-serif" font-size="18" fill="#e2e8f0" text-anchor="middle">
    For distinguished participation and excellence in <tspan font-weight="bold" fill="#38bdf8">{event_name}</tspan>
  </text>
  <text x="500" y="435" font-family="sans-serif" font-size="16" fill="#94a3b8" text-anchor="middle">
    Track: {cert.track_name or "General Open Track"} • Distinction: {cert.placement or "Verified Attendee"}
  </text>

  <!-- Verification Seal & QR Area -->
  <circle cx="200" cy="540" r="45" fill="#1e293b" stroke="url(#gold)" stroke-width="2"/>
  <text x="200" y="535" font-family="sans-serif" font-size="12" font-weight="bold" fill="url(#gold)" text-anchor="middle">VERIFIED</text>
  <text x="200" y="555" font-family="sans-serif" font-size="10" fill="#94a3b8" text-anchor="middle">TAMPER-PROOF</text>

  <!-- Signatures -->
  <line x1="680" y1="560" x2="880" y2="560" stroke="#475569" stroke-width="1.5"/>
  <text x="780" y="585" font-family="sans-serif" font-size="14" fill="#94a3b8" text-anchor="middle">Hackathon Chair</text>
  <text x="780" y="545" font-family="Georgia, cursive" font-size="20" fill="#38bdf8" text-anchor="middle">HackForge Committee</text>

  <!-- Footer Verification Code -->
  <text x="500" y="640" font-family="monospace" font-size="13" fill="#64748b" text-anchor="middle">
    Verification ID: {cert.verification_code}  •  Issued: {date_str}
  </text>
</svg>"""

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'attachment; filename="{cert.verification_code}.svg"'
        },
    )


# ---------------------------------------------------------------------------
# 3. SIGNED JUDGE PARTICIPATION RECORDS (T4 Stretch)
# ---------------------------------------------------------------------------


@router.get(
    "/api/judge/{event_id}/record",
    response_model=JudgeRecordResponse,
    summary="Get Signed Judge Participation Record",
    description="Generates and cryptographically signs a participation record for a judge proving their evaluations.",
)
def get_judge_signed_record(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Verify judge role in this event
    membership = (
        db.query(EventMember)
        .filter(EventMember.user_id == user.id, EventMember.event_id == event_id)
        .first()
    )
    if not membership or membership.role not in ("judge", "organizer", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only assigned judges can generate participation records",
        )

    # Compute actual scores given
    scores_count = (
        db.query(Score)
        .filter(Score.event_id == event_id, Score.judge_id == user.id)
        .count()
    )

    # Compute assigned tracks
    tracks = (
        db.query(Track.name)
        .join(JudgeTrack, JudgeTrack.track_id == Track.id)
        .filter(JudgeTrack.event_id == event_id, JudgeTrack.judge_id == user.id)
        .all()
    )
    tracks_str = ", ".join(t[0] for t in tracks) if tracks else "General"

    # Find or create record
    rec = (
        db.query(JudgeRecord)
        .filter(JudgeRecord.event_id == event_id, JudgeRecord.judge_id == user.id)
        .first()
    )

    now = utcnow()
    if not rec:
        sig = generate_judge_record_signature(user.id, event_id, scores_count, now)
        rec = JudgeRecord(
            id=f"rec_{uuid.uuid4().hex[:10]}",
            event_id=event_id,
            judge_id=user.id,
            judge_name=user.name,
            event_name=event.name,
            scores_count=scores_count,
            tracks_judged=tracks_str,
            issued_at=now,
            signature=sig,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
    else:
        # Update with latest evaluation tally & re-sign
        rec.scores_count = scores_count
        rec.tracks_judged = tracks_str
        rec.signature = generate_judge_record_signature(
            user.id, event_id, scores_count, rec.issued_at
        )
        db.commit()

    base = str(request.base_url).rstrip("/")
    is_valid = verify_judge_record_signature(
        rec.signature,
        rec.judge_id,
        rec.event_id,
        rec.scores_count,
        rec.issued_at,
    )

    return JudgeRecordResponse(
        id=rec.id,
        event_id=rec.event_id,
        event_name=rec.event_name,
        judge_id=rec.judge_id,
        judge_name=rec.judge_name,
        scores_count=rec.scores_count,
        tracks_judged=rec.tracks_judged,
        issued_at=rec.issued_at.isoformat(),
        signature=rec.signature,
        is_valid=is_valid,
        verification_url=f"{base}/verify/record/{rec.id}",
    )


# ---------------------------------------------------------------------------
# 4. PUBLIC VERIFICATION PAGES (T4 Stretch)
# ---------------------------------------------------------------------------


@router.get(
    "/verify/record/{record_id}",
    response_class=HTMLResponse,
    summary="Verify Judge Record",
    description="Public tamper-proof cryptographic verification page for judging records.",
)
def public_verify_judge_record(
    record_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    rec = db.get(JudgeRecord, record_id)
    if not rec:
        return templates.TemplateResponse(
            request=request,
            name="verify_record.html",
            context=base_context(
                request=request,
                event=default_event(db),
                user=user,
                role="visitor",
                record=None,
                is_valid=False,
                error="Record not found",
            ),
            status_code=404,
        )

    is_valid = verify_judge_record_signature(
        rec.signature,
        rec.judge_id,
        rec.event_id,
        rec.scores_count,
        rec.issued_at,
    )

    return templates.TemplateResponse(
        request=request,
        name="verify_record.html",
        context=base_context(
            request=request,
            event=default_event(db),
            user=user,
            role="visitor",
            record=rec,
            is_valid=is_valid,
            error=None,
        ),
    )


@router.get(
    "/verify/certificate/{code}",
    response_class=HTMLResponse,
    summary="Verify Certificate",
    description="Public verification page confirming authenticity of attendee and judging certificates.",
)
def public_verify_certificate(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    cert = (
        db.query(Certificate)
        .options(joinedload(Certificate.event))
        .filter(Certificate.verification_code == code.upper().strip())
        .first()
    )

    if cert and not _is_certificate_eligible(db, cert):
        cert = None

    return templates.TemplateResponse(
        request=request,
        name="verify_cert.html",
        context=base_context(
            request=request,
            event=cert.event if cert else default_event(db),
            user=user,
            role="visitor",
            certificate=cert,
            is_valid=cert is not None,
        ),
        status_code=200 if cert else 404,
    )


# ---------------------------------------------------------------------------
# 5. EMBEDDABLE GALLERY WIDGET (T4 Stretch)
# ---------------------------------------------------------------------------


@router.get(
    "/embed/gallery/{event_id}",
    response_class=HTMLResponse,
    summary="Embeddable Gallery Widget",
    description="A responsive, standalone gallery widget designed for <iframe> embedding on external websites.",
)
def embed_gallery_widget(
    event_id: str,
    request: Request,
    theme: str = Query("dark", description="'dark' or 'light' theme"),
    track: Optional[str] = Query(None, description="Filter by track ID"),
    limit: int = Query(50, description="Max projects to display"),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    query = (
        db.query(Project)
        .options(joinedload(Project.team), joinedload(Project.track))
        .filter(
            Project.event_id == event_id,
            Project.is_draft.is_(False),
            Project.is_disqualified.is_(False),
        )
    )
    if track:
        query = query.filter(Project.track_id == track)

    projects = query.order_by(Project.title.asc()).limit(limit).all()
    tracks = db.query(Track).filter(Track.event_id == event_id).all()

    return templates.TemplateResponse(
        request=request,
        name="embed_gallery.html",
        context={
            "request": request,
            "event": event,
            "projects": projects,
            "tracks": tracks,
            "theme": theme,
            "selected_track": track or "",
            "base_url": str(request.base_url).rstrip("/"),
        },
    )


# ---------------------------------------------------------------------------
# 6. BULK IMPORT & EXPORT (T4 Stretch)
# ---------------------------------------------------------------------------


@router.get(
    "/api/events/{event_id}/export/full.json",
    summary="Full Event JSON Export",
    description="Comprehensive export of the entire hackathon: metadata, tracks, teams, projects, scores, normalized results, comments, and audit logs.",
)
def export_event_full_json(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    _check_organizer(db, user, event_id)
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    tracks = [
        {"id": t.id, "name": t.name, "prize": t.prize} for t in event.tracks
    ]
    rubrics = [
        {"id": r.id, "name": r.name, "weight": r.weight}
        for r in db.query(RubricCriteria).filter_by(event_id=event_id).all()
    ]
    projects = [
        {
            "id": p.id,
            "title": p.title,
            "summary": p.summary,
            "repo_url": p.repo_url,
            "demo_url": p.demo_url,
            "track_id": p.track_id,
            "team_id": p.team_id,
            "tech_stack": p.tech_stack,
            "submitted_at": p.submitted_at.isoformat() if p.submitted_at else None,
        }
        for p in event.projects
        if not p.is_draft
    ]
    scores = [
        {
            "judge_id": s.judge_id,
            "project_id": s.project_id,
            "criteria_id": s.criteria_id,
            "value": s.value,
            "comment": s.comment,
        }
        for s in db.query(Score).filter_by(event_id=event_id).all()
    ]
    comments = [
        {
            "id": c.id,
            "project_id": c.project_id,
            "user_id": c.user_id,
            "content": c.content,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in db.query(Comment).filter_by(event_id=event_id).all()
    ]
    votes_count = db.query(Vote).filter_by(event_id=event_id).count()
    audit_records = [
        {
            "id": l.id,
            "actor_id": l.actor_id,
            "message": l.message,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in db.query(AuditLog).filter_by(event_id=event_id).order_by(AuditLog.created_at.asc()).all()
    ]

    payload = {
        "event": {
            "id": event.id,
            "name": event.name,
            "tagline": event.tagline,
            "submissions_close": (
                event.submissions_close.isoformat() if event.submissions_close else None
            ),
            "results_published": event.results_published,
        },
        "tracks": tracks,
        "rubric": rubrics,
        "projects_count": len(projects),
        "projects": projects,
        "scores_count": len(scores),
        "scores": scores,
        "comments_count": len(comments),
        "comments": comments,
        "community_votes_total": votes_count,
        "audit_logs_count": len(audit_records),
        "audit_logs": audit_records,
        "exported_at": utcnow().isoformat(),
        "exported_by": user.email,
    }

    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="{event.id}_full_export.json"'
        },
    )


@router.get(
    "/api/events/{event_id}/export/projects.csv",
    summary="Export Projects CSV",
    description="Exports all event submissions in CSV format for spreadsheet analysis.",
)
def export_projects_csv(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    _check_organizer(db, user, event_id)
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    projects = (
        db.query(Project)
        .options(joinedload(Project.team), joinedload(Project.track))
        .filter(Project.event_id == event_id, Project.is_draft.is_(False))
        .all()
    )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "project_id",
            "title",
            "summary",
            "team_name",
            "track_name",
            "tech_stack",
            "repo_url",
            "demo_url",
            "submitted_at",
        ]
    )

    for p in projects:
        writer.writerow(
            [
                p.id,
                p.title,
                p.summary,
                p.team.name if p.team else "",
                p.track.name if p.track else "",
                p.tech_stack or "",
                p.repo_url or "",
                p.demo_url or "",
                p.submitted_at.isoformat() if p.submitted_at else "",
            ]
        )

    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{event.id}_projects.csv"'
        },
    )


@router.post(
    "/api/events/{event_id}/import/projects",
    summary="Bulk Import Projects",
    description="Bulk imports projects from a JSON payload or uploaded file (Organizer only).",
)
async def bulk_import_projects(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    _check_organizer(db, user, event_id)
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    content_type = request.headers.get("content-type", "")
    items = []

    if "application/json" in content_type:
        body = await request.json()
        items = body if isinstance(body, list) else body.get("projects", [])
    else:
        # Form data or raw body
        raw = await request.body()
        try:
            parsed = json.loads(raw.decode("utf-8"))
            items = parsed if isinstance(parsed, list) else parsed.get("projects", [])
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid import payload: expected JSON array of project objects",
            )

    imported_count = 0
    default_track = db.query(Track).filter_by(event_id=event_id).first()

    for item in items:
        title = item.get("title", "").strip()
        if not title:
            continue

        p_id = item.get("id") or f"prj_{uuid.uuid4().hex[:8]}"
        existing = db.get(Project, p_id)
        if existing:
            continue

        team_name = item.get("team_name") or f"Team {title[:12]}"
        team = Team(
            id=f"tm_{uuid.uuid4().hex[:8]}",
            event_id=event_id,
            name=team_name,
            leader_id=user.id,
        )
        db.add(team)
        db.add(TeamMember(team_id=team.id, user_id=user.id))
        db.flush()

        proj = Project(
            id=p_id,
            event_id=event_id,
            team_id=team.id,
            track_id=item.get("track_id")
            or (default_track.id if default_track else None),
            title=title,
            summary=item.get("summary", ""),
            repo_url=item.get("repo_url", ""),
            demo_url=item.get("demo_url", ""),
            tech_stack=item.get("tech_stack", "Python, FastAPI"),
            cover_image_path=item.get("cover_image_path") or "/static/projects/default.jpg",
            is_draft=False,
            submitted_at=utcnow(),
        )
        db.add(proj)
        imported_count += 1

    db.add(
        AuditLog(
            event_id=event_id,
            actor_id=user.id,
            message=f"Bulk imported {imported_count} projects",
            created_at=utcnow(),
        )
    )
    db.commit()

    return {
        "success": True,
        "imported_count": imported_count,
        "message": f"Successfully imported {imported_count} projects",
    }


# ---------------------------------------------------------------------------
# 7. INTERACTIVE ROLE-BASED API DOCUMENTATION PORTAL
# ---------------------------------------------------------------------------


@router.get(
    "/api/docs",
    response_class=HTMLResponse,
    summary="Interactive Role-Based API Documentation Hub",
    description="Renders a dedicated, role-tailored API documentation portal with pre-filled cURL examples for Organizers, Judges, and Participants.",
)
def interactive_api_docs(
    request: Request,
    role: Optional[str] = Query(
        None, description="Preset tab: organizer, judge, participant, public"
    ),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    event = default_event(db)
    current_role = role_for(EventMember(role="visitor"))
    if user:
        from src.auth import membership_for

        mem = membership_for(db, user, event.id if event else None)
        current_role = role_for(mem)

    # Calculate active session token if logged in
    from src.auth import make_session_token

    active_cookie = f"Cookie: session={make_session_token(user.id)}" if user else None

    return templates.TemplateResponse(
        request=request,
        name="api_docs.html",
        context=base_context(
            request=request,
            event=event,
            user=user,
            role=current_role,
            selected_tab=role or current_role or "participant",
            active_cookie=active_cookie,
            base_url=str(request.base_url).rstrip("/"),
        ),
    )


# ---------------------------------------------------------------------------
# 8. ROLE-SPECIFIC CERTIFICATE VIEWS
# ---------------------------------------------------------------------------


@router.get(
    "/participant/{event_id}/certificate",
    response_class=HTMLResponse,
    summary="Participant Certificate View",
    description="Allows a participant to view and print their official participation certificate.",
)
def participant_certificate_view(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    event = db.get(Event, event_id) or default_event(db)

    # Check if participant belongs to a team with a submitted project
    team = user_team(db, user.id, event_id)
    has_submitted_project = False
    if team:
        proj = (
            db.query(Project)
            .filter(
                Project.team_id == team.id,
                Project.event_id == event_id,
                Project.is_draft.is_(False),
                Project.is_disqualified.is_(False),
            )
            .first()
        )
        if proj:
            has_submitted_project = True

    cert = None
    if has_submitted_project:
        cert = (
            db.query(Certificate)
            .options(joinedload(Certificate.event))
            .filter(
                Certificate.event_id == event_id,
                Certificate.user_id == user.id,
                Certificate.recipient_type == "participant",
            )
            .first()
        )

    return templates.TemplateResponse(
        request=request,
        name="certificate.html",
        context=base_context(
            request=request,
            event=event,
            user=user,
            role="participant",
            certificate=cert,
            recipient_type="participant",
            has_submitted_project=has_submitted_project,
        ),
    )


@router.get(
    "/judge/{event_id}/certificate",
    response_class=HTMLResponse,
    summary="Judge Certificate View",
    description="Allows a judge to view, print, and verify their official judging certificate.",
)
def judge_certificate_view(
    event_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    cert = (
        db.query(Certificate)
        .options(joinedload(Certificate.event))
        .filter(
            Certificate.event_id == event_id,
            Certificate.user_id == user.id,
            Certificate.recipient_type == "judge",
        )
        .first()
    )

    event = db.get(Event, event_id) or default_event(db)

    return templates.TemplateResponse(
        request=request,
        name="certificate.html",
        context=base_context(
            request=request,
            event=event,
            user=user,
            role="judge",
            certificate=cert,
            recipient_type="judge",
            has_submitted_project=True,
        ),
    )
