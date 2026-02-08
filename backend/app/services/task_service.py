import uuid
from datetime import datetime
from .. import db
from ..config import HOUR_DEFAULTS


def find_matching_task(match_string: str, tasks: list[dict]) -> dict | None:
    """Fuzzy match a user description to a task name."""
    if not match_string or not tasks:
        return None

    match_lower = match_string.lower().strip()
    best_match = None
    best_score = 0

    for task in tasks:
        name_lower = (task.get("name") or "").lower()
        if not name_lower:
            continue

        # Exact substring
        if match_lower in name_lower:
            score = len(match_lower) / len(name_lower) + 0.1
            if score > best_score:
                best_score = score
                best_match = task

        # Word overlap
        match_words = set(match_lower.split())
        name_words = set(name_lower.split())
        overlap = match_words & name_words
        if overlap:
            score = len(overlap) / max(len(match_words), len(name_words))
            if score > best_score:
                best_score = score
                best_match = task

    return best_match


def get_next_task(tasks: list[dict], dayplan: dict = None) -> dict | None:
    """Get the next undone task based on day plan order or priority."""
    active = [t for t in tasks if t.get("status") in ("todo", "doing")]
    if not active:
        return None

    # If dayplan has blocks, find the first undone block
    if dayplan and dayplan.get("blocks"):
        for block in dayplan["blocks"]:
            if block.get("task_id") and block["type"] == "work":
                task = next((t for t in active if (t.get("id") or t.get("sk")) == block["task_id"]), None)
                if task:
                    return task

    # Fall back to priority order
    prio = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    active.sort(key=lambda t: prio.get(t.get("priority", "normal"), 2))
    return active[0]


def calculate_day_load(tasks: list[dict], day: str) -> float:
    """Calculate total hours for a specific day."""
    return sum(
        t.get("estimated_hours", 0)
        for t in tasks
        if t.get("day") == day and t.get("status") not in ("dropped",)
    )


def get_free_slots(tasks: list[dict], daily_capacity: float = 8) -> dict:
    """Return free hours per day."""
    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    result = {}
    for day in days:
        used = calculate_day_load(tasks, day)
        free = max(0, daily_capacity - used)
        if free > 0:
            result[day] = free
    return result


def create_task_from_intent(task_data: dict, context: dict) -> dict:
    """Create a task from parsed WhatsApp intent data."""
    week_id = context.get("week_id", "")
    task_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Look up project
    project_id = task_data.get("project_id", "")
    if not project_id and task_data.get("project_candidates"):
        project_id = task_data["project_candidates"][0]

    # Estimate hours from subtype defaults if not provided
    hours = task_data.get("estimated_hours")
    if not hours:
        subtype = task_data.get("subtype", "")
        hours = HOUR_DEFAULTS.get(subtype, 1.0)

    # Compute date from day + week
    date = None
    day = task_data.get("day")
    if day and week_id:
        from ..routes.tasks import _week_id_to_dates
        dates = _week_id_to_dates(week_id)
        date = dates.get(day)

    item = {
        "pk": "TASK",
        "sk": task_id,
        "id": task_id,
        "week_id": week_id,
        "day": day,
        "project_id": project_id,
        "name": task_data.get("name", "Untitled"),
        "subtype": task_data.get("subtype", ""),
        "priority": task_data.get("priority", "normal"),
        "status": "todo",
        "estimated_hours": hours,
        "notes": task_data.get("notes", ""),
        "due_date": task_data.get("due_date"),
        "course_week": task_data.get("course_week"),
        "recurring": False,
        "is_time_block": task_data.get("is_time_block", False),
        "date": date,
        "created_at": now,
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)
    return item


def match_project_by_keywords(hint: str, projects: list[dict]) -> list[dict]:
    """Match a text hint against project keywords."""
    hint_lower = hint.lower()
    matches = []
    for p in projects:
        keywords = p.get("match_keywords", [])
        name_lower = p.get("name", "").lower()
        if hint_lower in name_lower:
            matches.append(p)
            continue
        for kw in keywords:
            if kw.lower() in hint_lower or hint_lower in kw.lower():
                matches.append(p)
                break
    return matches
