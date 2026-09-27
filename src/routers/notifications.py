from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from src.db import get_db
from src.auth import get_current_user, User
from src.models import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("/")
def get_notifications(db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    
    notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(20).all()
    
    return [
        {
            "id": n.id,
            "message": n.message,
            "action_link": n.action_link,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat()
        } for n in notifs
    ]

@router.get("/unread_count")
def get_unread_count(db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if not user:
        return {"count": 0}
    
    count = db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == False).count()
    return {"count": count}

@router.post("/{notification_id}/read")
def mark_as_read(notification_id: str, db: Session = Depends(get_db), user: User | None = Depends(get_current_user)):
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if notif:
        notif.is_read = True
        db.commit()
    
    return {"status": "ok"}
