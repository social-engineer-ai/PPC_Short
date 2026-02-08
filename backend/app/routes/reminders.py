import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_api_key
from ..models import ReminderCreate
from .. import db

router = APIRouter()


@router.get("/")
def list_reminders(_=Depends(verify_api_key)):
    return db.list_active_reminders()


@router.post("/", status_code=201)
def create_reminder(body: ReminderCreate, _=Depends(verify_api_key)):
    reminder_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    item = {
        "pk": "REMINDER",
        "sk": reminder_id,
        "id": reminder_id,
        **body.model_dump(),
        "active": True,
        "created_at": now,
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)
    return item


@router.delete("/{reminder_id}")
def delete_reminder(reminder_id: str, _=Depends(verify_api_key)):
    existing = db.get_item("REMINDER", reminder_id)
    if not existing:
        raise HTTPException(404, "Reminder not found")
    db.update_item("REMINDER", reminder_id, {"active": False})
    return {"deleted": True}
