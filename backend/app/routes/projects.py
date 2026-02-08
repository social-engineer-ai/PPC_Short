import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_api_key
from ..models import ProjectCreate, ProjectUpdate
from .. import db

router = APIRouter()


@router.get("/")
def list_projects(active: bool = None, _=Depends(verify_api_key)):
    projects = db.list_projects(active_only=False)
    if active is not None:
        projects = [p for p in projects if p.get("active") == active]
    return projects


@router.post("/", status_code=201)
def create_project(body: ProjectCreate, _=Depends(verify_api_key)):
    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    item = {
        "pk": "PROJECT",
        "sk": project_id,
        "id": project_id,
        **body.model_dump(),
        "active": True,
        "created_at": now,
        "updated_at": now,
    }
    db.put_item(item)
    return item


@router.patch("/{project_id}")
def update_project(project_id: str, body: ProjectUpdate, _=Depends(verify_api_key)):
    existing = db.get_item("PROJECT", project_id)
    if not existing:
        raise HTTPException(404, "Project not found")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return existing
    updates["updated_at"] = datetime.utcnow().isoformat()
    return db.update_item("PROJECT", project_id, updates)


@router.delete("/{project_id}")
def delete_project(project_id: str, _=Depends(verify_api_key)):
    existing = db.get_item("PROJECT", project_id)
    if not existing:
        raise HTTPException(404, "Project not found")
    db.delete_item("PROJECT", project_id)
    return {"deleted": True}
