import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ..auth import verify_api_key
from ..models import DayPlanUpdate
from .. import db

router = APIRouter()

PRIO_ORDER = {"urgent": 0, "high": 1, "normal": 2, "low": 3}


def _round_to_5min(minutes: int) -> int:
    """Round minutes to nearest 5-minute multiple."""
    return round(minutes / 5) * 5


def _fmt_time(minutes: int) -> str:
    """Format minutes as HH:MM."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _date_to_week_id(date_str: str) -> str:
    """Convert a date string 'YYYY-MM-DD' to ISO week ID 'YYYY-WNN'."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _date_to_day_name(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return d.strftime("%A").lower()


@router.get("/{date}")
def get_dayplan(date: str, _=Depends(verify_api_key)):
    plan = db.get_dayplan(date)
    if not plan:
        return {
            "date": date,
            "week_id": _date_to_week_id(date),
            "blocks": [],
            "day_capacity_hours": 8,
            "morning_briefing_sent": False,
            "midday_checkin_sent": False,
            "evening_summary_sent": False,
        }
    return plan


@router.post("/{date}/generate")
def generate_dayplan(date: str, _=Depends(verify_api_key)):
    """Auto-generate time blocks from tasks assigned to this date."""
    week_id = _date_to_week_id(date)
    day_name = _date_to_day_name(date)

    # Get tasks for this day
    tasks = db.get_tasks_for_week(week_id, day=day_name)
    active_tasks = [t for t in tasks if t.get("status") not in ("dropped", "done")]

    # Also get tasks assigned by date directly
    date_tasks = db.get_tasks_for_date(date)
    date_task_ids = {t["sk"] for t in date_tasks}
    for t in date_tasks:
        if t["sk"] not in {at["sk"] for at in active_tasks} and t.get("status") not in ("dropped", "done"):
            active_tasks.append(t)

    # Separate tasks that already have block times from those that don't
    scheduled = [t for t in active_tasks if t.get("block_start")]
    unscheduled = [t for t in active_tasks if not t.get("block_start")]

    # Sort unscheduled by priority
    unscheduled.sort(key=lambda t: PRIO_ORDER.get(t.get("priority", "normal"), 2))

    blocks = []

    # Add pre-scheduled blocks
    for t in scheduled:
        blocks.append({
            "start": t["block_start"],
            "end": t.get("block_end", ""),
            "task_id": t["sk"],
            "type": "work",
            "label": t.get("name", ""),
        })

    # Fill in unscheduled tasks around existing blocks
    current_minutes = 8 * 60  # Start at 08:00
    end_of_day = 18 * 60  # End at 18:00

    for task in unscheduled:
        hours = task.get("estimated_hours", 1)
        duration = _round_to_5min(int(hours * 60))
        if duration < 5:
            duration = 5

        # Skip to next available slot
        # Insert lunch break at noon if we cross it
        if current_minutes < 720 and current_minutes + duration > 720:
            # Add lunch break
            blocks.append({
                "start": "12:00",
                "end": "13:00",
                "task_id": None,
                "type": "break",
                "label": "Lunch",
            })
            current_minutes = 780  # 13:00

        if current_minutes >= end_of_day:
            break

        end_minutes = min(current_minutes + duration, end_of_day)
        end_minutes = _round_to_5min(end_minutes)

        blocks.append({
            "start": _fmt_time(current_minutes),
            "end": _fmt_time(end_minutes),
            "task_id": task["sk"],
            "type": "work",
            "label": task.get("name", ""),
        })

        current_minutes = end_minutes

        # Add 30-min break every 2.5 hours of work
        hours_since_start = (current_minutes - 480) / 60
        if hours_since_start > 0 and hours_since_start % 2.5 < 0.5 and current_minutes < end_of_day:
            break_end = _round_to_5min(current_minutes + 30)
            if current_minutes != 780:  # Don't double-add lunch break
                blocks.append({
                    "start": _fmt_time(current_minutes),
                    "end": _fmt_time(break_end),
                    "task_id": None,
                    "type": "break",
                    "label": "Break",
                })
                current_minutes = break_end

    # Sort blocks by start time
    blocks.sort(key=lambda b: b["start"])

    plan = {
        "pk": "DAYPLAN",
        "sk": date,
        "date": date,
        "week_id": week_id,
        "day_capacity_hours": 8,
        "blocks": blocks,
        "morning_briefing_sent": False,
        "midday_checkin_sent": False,
        "evening_summary_sent": False,
        "created_at": datetime.utcnow().isoformat(),
    }
    db.put_item(plan)
    return plan


@router.patch("/{date}")
def update_dayplan(date: str, body: DayPlanUpdate, _=Depends(verify_api_key)):
    updates = {}
    if body.blocks is not None:
        updates["blocks"] = [b.model_dump() for b in body.blocks]
    if body.day_capacity_hours is not None:
        updates["day_capacity_hours"] = body.day_capacity_hours

    if not updates:
        return db.get_dayplan(date) or {"date": date}

    existing = db.get_dayplan(date)
    if not existing:
        # Create new
        plan = {
            "pk": "DAYPLAN",
            "sk": date,
            "date": date,
            "week_id": _date_to_week_id(date),
            **updates,
            "created_at": datetime.utcnow().isoformat(),
        }
        db.put_item(plan)
        return plan

    return db.update_item("DAYPLAN", date, updates)
