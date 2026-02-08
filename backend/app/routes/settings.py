from datetime import datetime

from fastapi import APIRouter, Depends

from ..auth import verify_api_key
from ..models import SettingsUpdate
from .. import db
from ..config import DEFAULT_SETTINGS

router = APIRouter()

DEFAULT_SUBTYPES = {
    "teaching": ["Lecture Content", "Slides", "Examples", "Labs", "Homework", "Grading", "Office Hours", "Student Issues"],
    "research": ["Planning", "Writing", "Analysis", "Experiments", "IRB", "Submissions", "Lit Review", "Collaboration"],
    "admin": ["Email", "Meetings", "Reports", "Committee", "Letters", "Scheduling"],
    "personal": ["Family", "House", "Finances", "Taxes", "Doctors", "Insurance", "Kids School", "Errands"],
}


@router.get("/")
def get_settings(_=Depends(verify_api_key)):
    return db.get_settings()


@router.get("/subtypes")
def get_subtypes(_=Depends(verify_api_key)):
    """Return merged subtypes (defaults + custom additions - removals)."""
    settings = db.get_settings()
    custom = settings.get("custom_subtypes", {})
    result = {}
    for area, defaults in DEFAULT_SUBTYPES.items():
        added = custom.get(area, {}).get("added", [])
        removed = custom.get(area, {}).get("removed", [])
        result[area] = [s for s in defaults if s not in removed] + added
    return result


@router.patch("/")
def update_settings(body: SettingsUpdate, _=Depends(verify_api_key)):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return db.get_settings()

    existing = db.get_item("SETTINGS", "USER")
    if not existing:
        # Create settings record
        item = {
            "pk": "SETTINGS",
            "sk": "USER",
            **DEFAULT_SETTINGS,
            **updates,
            "updated_at": datetime.utcnow().isoformat(),
        }
        db.put_item(item)
        return {k: v for k, v in item.items() if k not in ("pk", "sk")}

    updates["updated_at"] = datetime.utcnow().isoformat()
    result = db.update_item("SETTINGS", "USER", updates)
    return {k: v for k, v in result.items() if k not in ("pk", "sk")}
