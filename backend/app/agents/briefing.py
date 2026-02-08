"""Morning briefing builder — sent at 7 AM CT via EventBridge."""
import uuid
from datetime import datetime

from .. import db
from ..services.twilio_client import send_whatsapp
from ..services.scheduler import create_one_time_schedule

AREA_EMOJI = {
    "teaching": "\U0001F7E6",
    "research": "\U0001F7EA",
    "admin": "\U0001F7E8",
    "personal": "\U0001F7E9",
}


def send_morning_briefing():
    """Build and send the morning briefing message."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    day_name = datetime.utcnow().strftime("%A")
    iso = datetime.utcnow().isocalendar()
    week_id = f"{iso[0]}-W{iso[1]:02d}"

    settings = db.get_settings()
    projects = db.list_projects(active_only=True)
    project_map = {(p.get("id") or p.get("sk")): p for p in projects}

    # Get/generate day plan
    dayplan = db.get_dayplan(today)
    if not dayplan or not dayplan.get("blocks"):
        dayplan = _auto_generate_dayplan(today, week_id, day_name.lower())

    # Week stats
    week_tasks = db.get_tasks_for_week(week_id)
    active_week = [t for t in week_tasks if t.get("status") != "dropped"]
    done_week = [t for t in active_week if t.get("status") == "done"]
    week_total = len(active_week)
    week_done = len(done_week)
    week_pct = round(week_done / week_total * 100) if week_total else 0

    # Today's tasks from blocks
    blocks = dayplan.get("blocks", [])
    today_tasks = []
    for b in blocks:
        if b.get("task_id"):
            task = db.get_item("TASK", b["task_id"])
            if task:
                today_tasks.append({**task, "_block": b})

    # Build message
    lines = [
        f"Good morning. Here's {day_name}, {_format_date(today)}.",
        "",
        f"Week progress: {week_done}/{week_total} tasks done ({week_pct}%)",
        "",
        "*TODAY'S BLOCKS:*",
        "\u2501" * 15,
    ]

    total_hours = 0
    urgent_count = 0
    for b in blocks:
        if b["type"] == "break":
            lines.append(f"\U0001F37D {b['start']}\u2013{b['end']} | {b.get('label', 'Break')}")
            continue

        task = db.get_item("TASK", b["task_id"]) if b.get("task_id") else None
        if task:
            proj = project_map.get(task.get("project_id"), {})
            area = proj.get("area", "admin")
            emoji = AREA_EMOJI.get(area, "\U0001F7E8")
            hours = task.get("estimated_hours", 0)
            total_hours += hours
            if task.get("priority") == "urgent":
                urgent_count += 1
            lines.append(
                f"{emoji} {b['start']}\u2013{b['end']} | "
                f"{proj.get('name', '?')} \u2014 {task.get('name')} "
                f"[{task.get('subtype', 'General')}, {hours}h]"
            )
        else:
            lines.append(f"\u2B1C {b['start']}\u2013{b['end']} | Unassigned")

    lines.append("")

    # Summary line
    summary_parts = [f"\u23F1 {total_hours}h planned"]
    if urgent_count:
        summary_parts.append(f"\U0001F534 {urgent_count} urgent")

    # Check neglected areas
    areas_present = set()
    for t in active_week:
        proj = project_map.get(t.get("project_id"), {})
        areas_present.add(proj.get("area", ""))
    neglected = [a for a in ["teaching", "research", "admin", "personal"] if a not in areas_present]
    if neglected:
        summary_parts.append(f"\u26A0 {', '.join(a.title() for a in neglected)} has 0 tasks this week")

    lines.append(" | ".join(summary_parts))
    lines.extend([
        "",
        "Reply:",
        "\u2705 = ready to start",
        "\U0001F4CB = show full week",
        "\u2795 \"task name\" = quick add",
    ])

    msg = "\n".join(lines)

    # Send via WhatsApp
    send_whatsapp(msg)

    # Record check-in
    _record_checkin(today, None, "morning", msg)

    # Schedule dynamic block check-ins
    _schedule_block_checkins(dayplan, today)

    # Update dayplan
    db.update_item("DAYPLAN", today, {"morning_briefing_sent": True})

    return {"status": "sent", "blocks": len(blocks)}


def _auto_generate_dayplan(today: str, week_id: str, day_name: str) -> dict:
    """Auto-generate a day plan from assigned tasks."""
    tasks = db.get_tasks_for_week(week_id, day=day_name)
    active = [t for t in tasks if t.get("status") not in ("dropped", "done")]

    prio = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    active.sort(key=lambda t: prio.get(t.get("priority", "normal"), 2))

    blocks = []
    current_min = 480  # 08:00

    for task in active:
        hours = task.get("estimated_hours", 1)
        duration = int(hours * 60)

        # Lunch break
        if current_min < 720 and current_min + duration > 720:
            blocks.append({"start": "12:00", "end": "13:00", "task_id": None, "type": "break", "label": "Lunch"})
            current_min = 780

        if current_min >= 1080:  # 18:00
            break

        sh, sm = divmod(current_min, 60)
        eh, em = divmod(min(current_min + duration, 1080), 60)
        blocks.append({
            "start": f"{sh:02d}:{sm:02d}",
            "end": f"{eh:02d}:{em:02d}",
            "task_id": task.get("id") or task.get("sk"),
            "type": "work",
            "label": task.get("name", ""),
        })
        current_min += duration

    blocks.sort(key=lambda b: b["start"])

    plan = {
        "pk": "DAYPLAN", "sk": today,
        "date": today, "week_id": week_id,
        "day_capacity_hours": 8,
        "blocks": blocks,
        "morning_briefing_sent": False,
        "midday_checkin_sent": False,
        "evening_summary_sent": False,
        "created_at": datetime.utcnow().isoformat(),
    }
    db.put_item(plan)
    return plan


def _schedule_block_checkins(dayplan: dict, today: str):
    """Create one-time EventBridge schedules for each block end time."""
    for block in dayplan.get("blocks", []):
        if block["type"] != "work" or not block.get("task_id"):
            continue
        end_time = block["end"]
        schedule_name = f"pcp-block-{today}-{end_time.replace(':', '')}"
        schedule_dt = f"{today}T{end_time}:00"
        create_one_time_schedule(
            name=schedule_name,
            schedule_datetime=schedule_dt,
            payload={
                "action": "block_checkin",
                "task_id": block["task_id"],
                "block_end": end_time,
                "date": today,
            },
        )


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
