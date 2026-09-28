from __future__ import annotations

import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.db import SessionLocal
from src.timeutil import as_utc, utcnow

# Server secret for signing judge records and webhook verification
SERVER_SIGNING_SECRET = "hackforge-dogfood-2026-cryptographic-master-key"


def sign_payload(secret: str, payload_bytes: bytes) -> str:
    """Generate HMAC-SHA256 signature header formatted as sha256=<hex>."""
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def generate_judge_record_signature(
    judge_id: str, event_id: str, scores_count: int, issued_at: datetime | str | int
) -> str:
    """Cryptographically sign a judge participation record."""
    if isinstance(issued_at, datetime):
        utc_dt = as_utc(issued_at)
        ts = int(utc_dt.timestamp())
    elif isinstance(issued_at, (int, float)):
        ts = int(issued_at)
    else:
        try:
            clean_str = str(issued_at).replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            utc_dt = as_utc(dt)
            ts = int(utc_dt.timestamp())
        except Exception:
            ts = str(issued_at)
    message = f"{judge_id}:{event_id}:{scores_count}:{ts}"
    return hmac.new(
        SERVER_SIGNING_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_judge_record_signature(
    signature: str, judge_id: str, event_id: str, scores_count: int, issued_at: datetime | str | int
) -> bool:
    """Verify cryptographic authenticity of a judge record."""
    expected = generate_judge_record_signature(
        judge_id, event_id, scores_count, issued_at
    )
    return hmac.compare_digest(signature, expected)


def _deliver_to_subscription(
    sub_id: str, target_url: str, secret: str, event_id: str, event_name: str, payload: dict[str, Any]
) -> None:
    db = SessionLocal()
    try:
        from src.models import WebhookDelivery

        payload_bytes = json.dumps(payload, default=str).encode("utf-8")
        signature = sign_payload(secret, payload_bytes)

        req = urllib.request.Request(target_url, data=payload_bytes, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "HackForge-Webhook-Engine/1.0")
        req.add_header("X-HackForge-Event", event_name)
        req.add_header("X-HackForge-Signature", signature)
        req.add_header("X-HackForge-Delivery", str(uuid.uuid4()))

        status = 0
        resp_body = ""
        success = False

        try:
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                status = resp.status
                resp_body = resp.read()[:500].decode("utf-8", "replace")
                success = 200 <= status < 300
        except urllib.error.HTTPError as e:
            status = e.code
            resp_body = e.read()[:500].decode("utf-8", "replace")
        except Exception as e:
            resp_body = f"{type(e).__name__}: {e}"

        delivery = WebhookDelivery(
            id=f"del_{uuid.uuid4().hex[:10]}",
            subscription_id=sub_id,
            event_id=event_id,
            event_name=event_name,
            payload_json=json.dumps(payload, default=str),
            response_status=status,
            response_body=resp_body,
            delivered_at=utcnow(),
            success=success,
        )
        db.add(delivery)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()


def dispatch_webhook(event_id: str, event_name: str, data: dict[str, Any]) -> None:
    """Asynchronously dispatch webhooks to all active subscribers for the event."""
    def _worker():
        db = SessionLocal()
        try:
            from src.models import WebhookSubscription

            subs = (
                db.query(WebhookSubscription)
                .filter(
                    WebhookSubscription.event_id == event_id,
                    WebhookSubscription.is_active.is_(True),
                )
                .all()
            )

            payload = {
                "id": f"evt_{uuid.uuid4().hex[:12]}",
                "event": event_name,
                "event_id": event_id,
                "timestamp": utcnow().isoformat(),
                "data": data,
            }

            for sub in subs:
                events_list = [e.strip() for e in sub.events.split(",")]
                if "*" in events_list or event_name in events_list:
                    _deliver_to_subscription(
                        sub.id, sub.target_url, sub.secret, event_id, event_name, payload
                    )
        except Exception:
            pass
        finally:
            db.close()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
