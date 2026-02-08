import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import verify_api_key
from ..models import TaskCreate, TaskUpdate
from .. import db

router = APIRouter()

DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "weekend"]


def _week_id_to_dates(week_id: str) -> dict:
    """Convert week_id like '2026-W06' to a map of day name -> date string."""
    from datetime import timedelta
    year, week_num = week_id.split("-W")
    year, week_num = int(year), int(week_num)
    # ISO week: Monday of week 1 contains Jan 4
    jan4 = datetime(year, 1, 4)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    monday = start_of_week1 + timedelta(weeks=week_num - 1)
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return {name: (monday + timedelta(days=i)).strftime("%Y-%m-%d") for i, name in enumerate(day_names)}


def _shift_week(week_id: str, direction: int) -> str:
    parts = week_id.split("-W")
    year, week = int(parts[0]), int(parts[1])
    week += direction
    if week < 1:
        year -= 1
        week = 52
    elif week > 52:
        year += 1
        week = 1
    return f"{year}-W{week:02d}"


@router.get("/")
def list_tasks(
    week_id: str = Query(...),
    day: str = Query(None),
    status: str = Query(None),
    _=Depends(verify_api_key),
):
    tasks = db.get_tasks_for_week(week_id, day=day)
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return tasks


@router.post("/", status_code=201)
def create_task(body: TaskCreate, _=Depends(verify_api_key)):
    # Check week lock
    week_lock = db.get_week_lock(body.week_id)
    is_locked = week_lock and week_lock.get("locked", False)

    if is_locked and not body.drop_task_id:
        # Return 409 with droppable tasks
        current_tasks = db.get_tasks_for_week(body.week_id)
        droppable = [
            {"id": t["sk"], "name": t["name"], "project_id": t.get("project_id", ""),
             "priority": t.get("priority", "normal"), "hours": t.get("estimated_hours", 0)}
            for t in current_tasks
            if t.get("status") not in ("done", "dropped")
        ]
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Week is locked. Must drop a task to add a new one.",
                "droppable_tasks": droppable,
            },
        )

    # If trading, drop the specified task first
    if is_locked and body.drop_task_id:
        existing = db.get_item("TASK", body.drop_task_id)
        if existing:
            db.update_item("TASK", body.drop_task_id, {
                "status": "dropped",
                "updated_at": datetime.utcnow().isoformat(),
            })

    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Compute date from day + week_id if day is provided
    date = body.date
    if not date and body.day and body.week_id:
        dates_map = _week_id_to_dates(body.week_id)
        if body.day in dates_map:
            date = dates_map[body.day]

    item = {
        "pk": "TASK",
        "sk": task_id,
        "id": task_id,
        "week_id": body.week_id,
        "day": body.day,
        "block_start": body.block_start,
        "block_end": body.block_end,
        "project_id": body.project_id,
        "name": body.name,
        "subtype": body.subtype,
        "priority": body.priority,
        "status": body.status,
        "estimated_hours": body.estimated_hours,
        "notes": body.notes,
        "due_date": body.due_date,
        "course_week": body.course_week,
        "recurring": body.recurring,
        "is_time_block": body.is_time_block,
        "carried_from_week": body.carried_from_week,
        "date": date,
        "created_at": now,
    }
    # Remove None values to keep DynamoDB clean
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)
    return item


@router.patch("/{task_id}")
def update_task(task_id: str, body: TaskUpdate, _=Depends(verify_api_key)):
    existing = db.get_item("TASK", task_id)
    if not existing:
        raise HTTPException(404, "Task not found")

    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return existing

    # Track status transitions
    if "status" in updates:
        new_status = updates["status"]
        if new_status == "doing" and not existing.get("started_at"):
            updates["started_at"] = datetime.utcnow().isoformat()
        elif new_status == "done":
            updates["completed_at"] = datetime.utcnow().isoformat()

    # Update date if day changed
    if "day" in updates and existing.get("week_id"):
        dates_map = _week_id_to_dates(existing["week_id"])
        if updates["day"] in dates_map:
            updates["date"] = dates_map[updates["day"]]

    updates["updated_at"] = datetime.utcnow().isoformat()
    return db.update_item("TASK", task_id, updates)


@router.delete("/{task_id}")
def delete_task(task_id: str, _=Depends(verify_api_key)):
    existing = db.get_item("TASK", task_id)
    if not existing:
        raise HTTPException(404, "Task not found")
    db.delete_item("TASK", task_id)
    return {"deleted": True}


@router.post("/copy-recurring")
def copy_recurring(week_id: str = Query(...), _=Depends(verify_api_key)):
    """Copy recurring tasks from previous week to this week."""
    prev_week = _shift_week(week_id, -1)
    prev_tasks = db.get_tasks_for_week(prev_week)
    recurring = [t for t in prev_tasks if t.get("recurring")]
    current_tasks = db.get_tasks_for_week(week_id)

    created = []
    for t in recurring:
        # Skip if already exists
        if any(
            c.get("name") == t.get("name") and c.get("project_id") == t.get("project_id")
            for c in current_tasks
        ):
            continue

        new_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Compute new date if day is set
        date = None
        if t.get("day") and week_id:
            dates_map = _week_id_to_dates(week_id)
            if t["day"] in dates_map:
                date = dates_map[t["day"]]

        new_task = {
            "pk": "TASK",
            "sk": new_id,
            "id": new_id,
            "week_id": week_id,
            "day": t.get("day"),
            "project_id": t.get("project_id"),
            "name": t.get("name"),
            "subtype": t.get("subtype", ""),
            "priority": t.get("priority", "normal"),
            "status": "todo",
            "estimated_hours": t.get("estimated_hours", 1),
            "notes": t.get("notes", ""),
            "due_date": None,
            "course_week": None,
            "recurring": True,
            "is_time_block": t.get("is_time_block", False),
            "date": date,
            "created_at": now,
        }
        new_task = {k: v for k, v in new_task.items() if v is not None}
        db.put_item(new_task)
        created.append(new_task)

    return {"copied": len(created), "tasks": created}


@router.post("/{task_id}/carry-forward")
def carry_forward(
    task_id: str,
    target_week: str = Query(None),
    _=Depends(verify_api_key),
):
    """Copy task to next week with carry counter."""
    task = db.get_item("TASK", task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    target = target_week or _shift_week(task["week_id"], 1)
    carry_count = int(task.get("carried_from_week") or "0") + 1

    new_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    new_task = {
        "pk": "TASK",
        "sk": new_id,
        "id": new_id,
        "week_id": target,
        "project_id": task.get("project_id"),
        "name": task.get("name"),
        "subtype": task.get("subtype", ""),
        "priority": task.get("priority", "normal"),
        "status": "todo",
        "estimated_hours": task.get("estimated_hours", 1),
        "notes": task.get("notes", ""),
        "due_date": task.get("due_date"),
        "recurring": task.get("recurring", False),
        "is_time_block": task.get("is_time_block", False),
        "carried_from_week": str(carry_count),
        "created_at": now,
    }
    new_task = {k: v for k, v in new_task.items() if v is not None}
    db.put_item(new_task)

    # Mark original as dropped
    db.update_item("TASK", task_id, {
        "status": "dropped",
        "updated_at": now,
    })

    return new_task
