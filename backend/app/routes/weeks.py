from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_api_key
from .. import db

router = APIRouter()


@router.get("/{week_id}")
def get_week(week_id: str, _=Depends(verify_api_key)):
    lock = db.get_week_lock(week_id)
    tasks = db.get_tasks_for_week(week_id)
    active = [t for t in tasks if t.get("status") != "dropped"]
    done = [t for t in active if t.get("status") == "done"]
    total_hours = sum(t.get("estimated_hours", 0) for t in active)
    done_hours = sum(t.get("estimated_hours", 0) for t in done)

    return {
        "week_id": week_id,
        "locked": lock.get("locked", False) if lock else False,
        "locked_at": lock.get("locked_at") if lock else None,
        "task_count": len(active),
        "done_count": len(done),
        "total_hours": total_hours,
        "done_hours": done_hours,
        "tasks": tasks,
    }


@router.post("/{week_id}/lock")
def lock_week(week_id: str, _=Depends(verify_api_key)):
    db.put_item({
        "pk": "WEEK",
        "sk": week_id,
        "week_id": week_id,
        "locked": True,
        "locked_at": datetime.utcnow().isoformat(),
    })
    return {"locked": True}


@router.post("/{week_id}/unlock")
def unlock_week(week_id: str, _=Depends(verify_api_key)):
    existing = db.get_item("WEEK", week_id)
    if existing:
        db.update_item("WEEK", week_id, {"locked": False, "locked_at": None})
    else:
        db.put_item({
            "pk": "WEEK",
            "sk": week_id,
            "week_id": week_id,
            "locked": False,
        })
    return {"locked": False}


@router.get("/{week_id}/stats")
def week_stats(week_id: str, _=Depends(verify_api_key)):
    tasks = db.get_tasks_for_week(week_id)
    active = [t for t in tasks if t.get("status") != "dropped"]
    projects = db.list_projects(active_only=False)
    project_map = {p["sk"]: p for p in projects}

    # Per-area stats
    areas = {}
    for t in active:
        proj = project_map.get(t.get("project_id"), {})
        area = proj.get("area", "unknown")
        if area not in areas:
            areas[area] = {"total": 0, "done": 0, "hours": 0, "done_hours": 0}
        areas[area]["total"] += 1
        areas[area]["hours"] += t.get("estimated_hours", 0)
        if t.get("status") == "done":
            areas[area]["done"] += 1
            areas[area]["done_hours"] += t.get("estimated_hours", 0)

    # Per-day stats
    days = {}
    for t in active:
        day = t.get("day") or "unscheduled"
        if day not in days:
            days[day] = {"tasks": 0, "hours": 0, "done": 0}
        days[day]["tasks"] += 1
        days[day]["hours"] += t.get("estimated_hours", 0)
        if t.get("status") == "done":
            days[day]["done"] += 1

    # Neglected areas (no tasks)
    all_areas = ["teaching", "research", "admin", "personal"]
    neglected = [a for a in all_areas if a not in areas or areas[a]["total"] == 0]

    # Stale tasks (carried forward 3+ weeks)
    stale = [
        {"id": t["sk"], "name": t.get("name"), "carried_weeks": int(t.get("carried_from_week", 0))}
        for t in active
        if int(t.get("carried_from_week") or 0) >= 3
    ]

    return {
        "areas": areas,
        "days": days,
        "neglected": neglected,
        "stale": stale,
    }
