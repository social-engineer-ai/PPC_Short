"""Evening summary builder — sent at 6 PM CT via EventBridge."""
import uuid
from datetime import datetime, timedelta

from .. import db
from ..services.twilio_client import send_whatsapp


def send_evening_summary():
    """Build and send the evening summary message."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    day_name = datetime.utcnow().strftime("%A")
    iso = datetime.utcnow().isocalendar()
    week_id = f"{iso[0]}-W{iso[1]:02d}"

    settings = db.get_settings()
    projects = db.list_projects(active_only=True)
    project_map = {(p.get("id") or p.get("sk")): p for p in projects}

    # Get today's tasks
    day_lower = day_name.lower()
    tasks = db.get_tasks_for_week(week_id, day=day_lower)
    active = [t for t in tasks if t.get("status") != "dropped"]

    # Categorize
    done = [t for t in active if t.get("status") == "done"]
    doing = [t for t in active if t.get("status") == "doing"]
    skipped = [t for t in active if t.get("status") == "skipped"]
    todo = [t for t in active if t.get("status") == "todo"]

    lines = [
        f"*Day summary* \u2014 {day_name}, {_format_date(today)}.",
        "",
    ]

    # List each task with status
    for t in active:
        status = t.get("status", "todo")
        if status == "done":
            icon = "\u2705"
            suffix = "done"
        elif status == "doing":
            icon = "\U0001F535"
            suffix = "in progress"
        elif status == "skipped":
            icon = "\u23ED"
            suffix = "skipped"
        else:
            icon = "\u274C"
            suffix = "not done"

        proj = project_map.get(t.get("project_id"), {})
        lines.append(f"{icon} {proj.get('name', '?')} \u2014 {t.get('name')} \u2014 {suffix}")

    lines.append("")

    # Score
    complete = len(done)
    total = len(active)
    carried = len(todo) + len(doing)
    lines.append(f"Score: {complete}/{total} complete | {carried} carried forward | {len(skipped)} skipped")

    # Tomorrow preview
    tomorrow = (datetime.utcnow() + timedelta(days=1))
    tomorrow_day = tomorrow.strftime("%A").lower()
    tomorrow_tasks = db.get_tasks_for_week(week_id, day=tomorrow_day)
    tomorrow_active = [t for t in tomorrow_tasks if t.get("status") not in ("dropped", "done")]
    tomorrow_hours = sum(t.get("estimated_hours", 0) for t in tomorrow_active)

    if tomorrow_active:
        lines.extend([
            "",
            f"Tomorrow has {tomorrow_hours}h planned across {len(tomorrow_active)} tasks.",
        ])

    # Check for overdue/behind tasks
    behind_tasks = []
    all_week = db.get_tasks_for_week(week_id)
    for t in all_week:
        if t.get("status") in ("todo", "doing") and t.get("priority") in ("urgent", "high"):
            if t.get("day") and t["day"] < day_lower:
                behind_tasks.append(t)

    if behind_tasks:
        lines.extend([
            "",
            f"\u26A0 *{len(behind_tasks)} task(s) behind schedule:*",
        ])
        for t in behind_tasks[:3]:
            proj = project_map.get(t.get("project_id"), {})
            lines.append(f"  \u2022 {proj.get('name', '?')} \u2014 {t.get('name')} (was {t.get('day', '?')})")

    # Health check - food and exercise
    checkins = db.get_checkins_for_date(today)
    food_logs = [c for c in checkins if c.get("type") == "log_food"]
    exercise_logs = [c for c in checkins if c.get("type") == "log_exercise"]

    lines.append("")
    if exercise_logs:
        lines.append(f"\U0001F3CB Exercise: {len(exercise_logs)} logged today")
    else:
        lines.append("\U0001F3CB No exercise logged today.")

    if food_logs:
        lines.append(f"\U0001F37D Food: {len(food_logs)} entries logged")
    else:
        lines.append("\U0001F37D No food logged today. How was your eating?")

    # Sleep reminder
    lines.extend([
        "",
        "\U0001F4A4 *Sleep reminder:* Start winding down. No tea, no late-night food. Target 7h sleep.",
    ])

    msg = "\n".join(lines)
    send_whatsapp(msg)

    _record_checkin(today, None, "evening", msg)
    db.update_item("DAYPLAN", today, {"evening_summary_sent": True})

    return {"status": "sent", "score": f"{complete}/{total}"}


def _record_checkin(date, task_id, check_type, message):
    ci_id = str(uuid.uuid4())
    item = {
        "pk": f"CHECKIN#{date}",
        "sk": ci_id,
        "id": ci_id,
        "date": date,
        "task_id": task_id,
        "type": check_type,
        "message_sent": message[:500],
        "created_at": datetime.utcnow().isoformat(),
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)


def _format_date(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.strftime("%b %d")
