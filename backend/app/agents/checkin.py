"""Block check-ins, midday status, and nudge logic."""
import uuid
from datetime import datetime, timedelta

from .. import db
from ..services.twilio_client import send_whatsapp

AREA_EMOJI = {
    "teaching": "\U0001F7E6",
    "research": "\U0001F7EA",
    "admin": "\U0001F7E8",
    "personal": "\U0001F7E9",
}


def send_block_checkin(task_id: str, block_end: str):
    """Send block boundary check-in. Called by one-time EventBridge schedule."""
    task = db.get_item("TASK", task_id)
    if not task:
        return {"status": "task_not_found"}

    # Don't check in on already-done tasks
    if task.get("status") == "done":
        return {"status": "already_done"}

    today = datetime.utcnow().strftime("%Y-%m-%d")

    msg = (
        f"\u23F0 Block check-in.\n"
        f"*{task.get('name', 'Task')}* \u2014 done?\n\n"
        f"Reply: \u2705 done | \U0001F535 still working | \u23ED skipped | \U0001F504 pushed to tomorrow"
    )
    send_whatsapp(msg)

    _record_checkin(today, task_id, "block_end", msg)
    return {"status": "sent"}


def send_midday_checkin():
    """1 PM midday status. Shows morning results + afternoon plan."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    day_name = datetime.utcnow().strftime("%A").lower()
    iso = datetime.utcnow().isocalendar()
    week_id = f"{iso[0]}-W{iso[1]:02d}"

    dayplan = db.get_dayplan(today)
    if not dayplan:
        return {"status": "no_dayplan"}

    projects = db.list_projects(active_only=True)
    project_map = {(p.get("id") or p.get("sk")): p for p in projects}

    blocks = dayplan.get("blocks", [])
    morning_blocks = [b for b in blocks if b["type"] == "work" and b["start"] < "13:00"]
    afternoon_blocks = [b for b in blocks if b["start"] >= "13:00"]

    # Count morning results
    done_count = 0
    skipped_count = 0
    total_morning = 0
    for b in morning_blocks:
        if not b.get("task_id"):
            continue
        total_morning += 1
        task = db.get_item("TASK", b["task_id"])
        if task and task.get("status") == "done":
            done_count += 1
        elif task and task.get("status") == "skipped":
            skipped_count += 1

    lines = [
        f"\U0001F4CA Midday check: {done_count}/{total_morning} blocks done"
        + (f", {skipped_count} skipped" if skipped_count else "") + ".",
        "",
        "*AFTERNOON:*",
    ]

    for b in afternoon_blocks:
        if b["type"] == "break":
            lines.append(f"\U0001F37D {b['start']}\u2013{b['end']} | {b.get('label', 'Break')}")
            continue
        task = db.get_item("TASK", b["task_id"]) if b.get("task_id") else None
        if task:
            proj = project_map.get(task.get("project_id"), {})
            area = proj.get("area", "admin")
            emoji = AREA_EMOJI.get(area, "\U0001F7E8")
            lines.append(f"{emoji} {b['start']}\u2013{b['end']} | {task.get('name', '?')}")
        else:
            lines.append(f"\u2B1C {b['start']}\u2013{b['end']} | Unassigned")

    lines.extend(["", "Anything changed? Reply \U0001F44D to continue or tell me what shifted."])

    msg = "\n".join(lines)
    send_whatsapp(msg)

    _record_checkin(today, None, "midday", msg)
    db.update_item("DAYPLAN", today, {"midday_checkin_sent": True})

    return {"status": "sent"}


def check_and_send_nudges():
    """Runs every 15 minutes. Sends nudges for unacknowledged check-ins."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    settings = db.get_settings()
    nudge_delay = settings.get("nudge_delay_minutes", 30)

    # Check if agent is paused
    overrides = db.list_active_behavior_overrides()
    for o in overrides:
        if o.get("setting") == "paused" and o.get("value") == "true":
            return {"status": "paused"}

    checkins = db.get_checkins_for_date(today)
    now = datetime.utcnow()

    nudges_sent = 0
    for ci in checkins:
        if ci.get("type") != "block_end":
            continue
        if ci.get("response") is not None:
            continue

        # Check if already nudged
        ci_id = ci.get("sk") or ci.get("id")
        already_nudged = any(
            c.get("type") == "nudge" and c.get("message_sent", "").startswith(f"nudge:{ci_id}")
            for c in checkins
        )
        if already_nudged:
            continue

        # Check time
        created = ci.get("created_at", "")
        if not created:
            continue
        try:
            sent_at = datetime.fromisoformat(created)
        except ValueError:
            continue

        elapsed = (now - sent_at).total_seconds()
        if elapsed < nudge_delay * 60:
            continue

        # Send nudge
        task = db.get_item("TASK", ci.get("task_id", "")) if ci.get("task_id") else None
        task_name = task.get("name", "your last block") if task else "your last block"

        msg = f"\U0001F44B Hey \u2014 *{task_name}* block ended {nudge_delay} min ago. Working on it or did something come up?"
        send_whatsapp(msg)

        _record_checkin(today, ci.get("task_id"), "nudge", f"nudge:{ci_id} {msg[:200]}")
        nudges_sent += 1

    # Also clean up expired pending tasks
    pending = db.get_pending_task()
    # get_pending_task already handles expiry

    return {"status": "ok", "nudges_sent": nudges_sent}


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
