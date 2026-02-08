import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_api_key
from ..models import BehaviorOverrideCreate
from .. import db

router = APIRouter()


@router.get("/")
def list_overrides(_=Depends(verify_api_key)):
    return db.list_active_behavior_overrides()


@router.post("/", status_code=201)
def create_override(body: BehaviorOverrideCreate, _=Depends(verify_api_key)):
    override_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    item = {
        "pk": "BEHAVIOR",
        "sk": override_id,
        "id": override_id,
        **body.model_dump(),
        "active": True,
        "created_at": now,
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)
    return item


@router.delete("/{override_id}")
def delete_override(override_id: str, _=Depends(verify_api_key)):
    existing = db.get_item("BEHAVIOR", override_id)
    if not existing:
        raise HTTPException(404, "Override not found")
    db.update_item("BEHAVIOR", override_id, {"active": False})
    return {"deleted": True}


@router.post("/reset")
def reset_all(_=Depends(verify_api_key)):
    overrides = db.list_active_behavior_overrides()
    for o in overrides:
        db.update_item("BEHAVIOR", o["sk"], {"active": False})
    return {"reset": True, "deactivated": len(overrides)}
