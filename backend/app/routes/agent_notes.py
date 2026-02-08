import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_api_key
from ..models import AgentNoteCreate
from .. import db

router = APIRouter()


@router.get("/")
def list_notes(_=Depends(verify_api_key)):
    return db.list_active_agent_notes()


@router.post("/", status_code=201)
def create_note(body: AgentNoteCreate, _=Depends(verify_api_key)):
    note_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    item = {
        "pk": "AGENTNOTE",
        "sk": note_id,
        "id": note_id,
        **body.model_dump(),
        "active": True,
        "created_at": now,
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)
    return item


@router.delete("/{note_id}")
def delete_note(note_id: str, _=Depends(verify_api_key)):
    existing = db.get_item("AGENTNOTE", note_id)
    if not existing:
        raise HTTPException(404, "Note not found")
    db.update_item("AGENTNOTE", note_id, {"active": False})
    return {"deleted": True}
