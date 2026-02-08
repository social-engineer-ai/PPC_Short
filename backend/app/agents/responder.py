"""Generate WhatsApp response messages from intent execution results."""
import json
import traceback
from ..config import ANTHROPIC_API_KEY
from .. import db

_client = None

AREA_EMOJI = {
    "teaching": "\U0001F4DA",
    "research": "\U0001F52C",
    "admin": "\U0001F4CB",
    "personal": "\U0001F3E0",
}

PRIORITY_EMOJI = {
    "urgent": "\U0001F534",
    "high": "\U0001F7E0",
    "normal": "\U0001F7E1",
    "low": "\u26AA",
}


def generate_response(intent: dict, result: dict, context: dict) -> str:
    """Generate WhatsApp response. Uses templates for common cases, Claude for complex ones."""
    action = intent.get("intent", "unknown")

    try:
        # Template-based responses
        if action == "mark_done":
            return _resp_mark_done(result, context)
        elif action == "mark_doing":
            return _resp_mark_doing(result)
        elif action == "mark_skipped":
            return _resp_mark_skipped(result)
        elif action == "move_task":
            return _resp_move_task(result, intent)
        elif action == "push_tomorrow":
            return _resp_push_tomorrow(result)
        elif action == "add_task":
            return _resp_add_task(intent, result, context)
        elif action == "complete_pending":
            return _resp_complete_pending(result, context)
        elif action == "query_next":
            return _resp_query_next(result)
        elif action == "query_today":
            return _resp_query_today(context)
        elif action == "query_day":
            return _resp_query_day(result)
        elif action == "query_week":
            return _resp_query_week(context)
        elif action == "checkin_response":
            return _resp_checkin(intent, result, context)
        elif action == "acknowledge":
            return "\u2705"
        elif action == "set_reminder":
            return _resp_set_reminder(result)
        elif action == "list_reminders":
            return _resp_list_reminders(result)
        elif action == "delete_reminder":
            return _resp_delete_reminder(result)
        elif action == "modify_behavior":
            return _resp_modify_behavior(result)
        elif action == "add_note":
            return _resp_add_note(result)
        elif action == "log_food":
            return _resp_log_food(intent)
        elif action == "log_exercise":
            return _resp_log_exercise(intent)
        elif action == "log_sleep":
            return _resp_log_sleep(intent)
        elif action == "pause_agent":
            return _resp_pause(result)
        elif action == "manage_subtypes":
            return _resp_manage_subtypes(result)
        elif action == "chat":
            return _resp_chat(result)
        elif action == "unknown":
            return _resp_unknown(intent)
        else:
            return f"Got it. ({action})"
    except Exception as e:
        traceback.print_exc()
        return "Something went wrong processing that. Try again?"


def _resp_mark_done(result, context):
    task = result.get("task", {})
    name = task.get("name", "task")
    msg = f"\u2705 *{name}* marked done."
    next_task = result.get("next_task")
    if next_task:
        time_str = next_task.get("block_start", "")
        msg += f"\nNext up: *{next_task['name']}*"
        if time_str:
            msg += f" ({time_str})"
    return msg


def _resp_mark_doing(result):
    task = result.get("task", {})
    return f"\U0001F535 *{task.get('name', 'task')}* -- working on it."


def _resp_mark_skipped(result):
    task = result.get("task", {})
    return f"\u23ED *{task.get('name', 'task')}* skipped."


def _resp_move_task(result, intent):
    task = result.get("task", {})
    to_day = intent.get("to_day", "?")
    load = result.get("day_load", 0)
    msg = f"\U0001F4C5 *{task.get('name', 'task')}* moved to {to_day.title()}."
    if load > 0:
        msg += f"\n{to_day.title()} now at {load}h."
    return msg


def _resp_push_tomorrow(result):
    task = result.get("task", {})
    return f"\U0001F4C5 *{task.get('name', 'task')}* pushed to tomorrow."


def _resp_add_task(intent, result, context):
    # If the intent itself has a message_to_user (e.g., clarification question)
    if intent.get("message_to_user") and result.get("pending"):
        return intent["message_to_user"]

    tasks_results = result.get("tasks_results", [])
    if not tasks_results:
        return intent.get("message_to_user", "Task noted.")

    msgs = []
    for tr in tasks_results:
        if tr.get("pending"):
            return tr.get("message", intent.get("message_to_user", "Need more info. What else?"))
        if tr.get("created"):
            t = tr["task"]
            project = _get_project_name(t.get("project_id"), context)
            area = _get_area(t.get("project_id"), context)
            emoji = AREA_EMOJI.get(area, "\U0001F4CB")
            day = t.get("day", "unscheduled")
            prio = t.get('priority', 'normal')
            prio_emoji = PRIORITY_EMOJI.get(prio, '\U0001F7E1')
            time_str = ""
            if t.get("block_start"):
                time_str = f" @ {t['block_start']}"
                if t.get("block_end"):
                    time_str += f"-{t['block_end']}"
            msgs.append(
                f"\u2705 Added to *{day.title() if day else 'Unscheduled'}*{time_str}:\n"
                f"{emoji} *{project}* \u2014 {t.get('name')}\n"
                f"\U0001F4C1 {t.get('subtype') or 'General'} | "
                f"\u23F1 {t.get('estimated_hours', 1)}h | "
                f"{prio_emoji} {prio}"
            )

    if len(msgs) == 1:
        return msgs[0]
    return "\n\n".join(f"{i+1}. {m}" for i, m in enumerate(msgs))


def _resp_complete_pending(result, context):
    if result.get("created"):
        t = result["task"]
        project = _get_project_name(t.get("project_id"), context)
        day = t.get("day", "unscheduled")
        return (
            f"\u2705 Added:\n"
            f"*{project}* \u2014 {t.get('name')}\n"
            f"\u23F1 {t.get('estimated_hours', 1)}h | \U0001F4C5 {day.title() if day else 'Unscheduled'}"
        )
    if result.get("needs_more"):
        return result.get("question", "Need more info.")
    return "Got it."


def _resp_query_next(result):
    task = result.get("next_task")
    if not task:
        return "Nothing left for today. You're done!"
    time_str = task.get("block_start", "")
    return f"Next: *{task.get('name')}*" + (f" ({time_str})" if time_str else "")


def _resp_query_today(context):
    tasks = context.get("today_tasks", [])
    if not tasks:
        return "No tasks scheduled for today."
    active = [t for t in tasks if t.get("status") not in ("dropped",)]
    done = [t for t in active if t.get("status") == "done"]
    lines = [f"*TODAY* \u2014 {len(done)}/{len(active)} done\n"]
    for t in active:
        icon = "\u2705" if t["status"] == "done" else "\U0001F535" if t["status"] == "doing" else "\u2B1C"
        lines.append(f"{icon} {t.get('name')} ({t.get('estimated_hours', 0)}h)")
    return "\n".join(lines)


def _resp_query_week(context):
    tasks = context.get("week_tasks", [])
    active = [t for t in tasks if t.get("status") not in ("dropped",)]
    done = len([t for t in active if t.get("status") == "done"])
    total = len(active)
    pct = round(done / total * 100) if total else 0

    lines = [f"*WEEK* \u2014 {done}/{total} ({pct}%)\n"]
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        dt = [t for t in active if t.get("day") == day]
        hrs = sum(t.get("estimated_hours", 0) for t in dt)
        d = len([t for t in dt if t.get("status") == "done"])
        lines.append(f"*{day[:3].upper()}*: {d}/{len(dt)} | {hrs}h")
    return "\n".join(lines)


def _resp_query_day(result):
    tasks = result.get("tasks", [])
    day = result.get("day", "")
    day_label = day.title() if day else "that day"
    if not tasks:
        return f"Nothing scheduled for *{day_label}*."
    active = [t for t in tasks if t.get("status") not in ("dropped",)]
    if not active:
        return f"Nothing scheduled for *{day_label}*."
    done = [t for t in active if t.get("status") == "done"]
    lines = [f"*{day_label.upper()}* \u2014 {len(done)}/{len(active)} done\n"]
    for t in active:
        icon = "\u2705" if t["status"] == "done" else "\U0001F535" if t["status"] == "doing" else "\u2B1C"
        lines.append(f"{icon} {t.get('name')} ({t.get('estimated_hours', 0)}h)")
    return "\n".join(lines)


def _resp_chat(result):
    reply = result.get("reply", "")
    if reply:
        prefix = "\U0001F4CC " if result.get("saved") else ""
        return f"{prefix}{reply}"
    return "\U0001F4AC Got it."


def _resp_checkin(intent, result, context):
    status = intent.get("status", "done")
    task = result.get("task", {})
    if status == "done":
        msg = f"\u2705 *{task.get('name', 'task')}* done."
        next_task = result.get("next_task")
        if next_task:
            msg += f"\nNext: *{next_task['name']}*"
        return msg
    elif status == "working":
        return f"\U0001F535 Still on *{task.get('name', 'it')}*. Keep going."
    elif status == "skipped":
        return f"\u23ED Skipped. Moving on."
    elif status == "pushed":
        return f"\U0001F4C5 Pushed to tomorrow."
    return "\U0001F44D"


def _resp_set_reminder(result):
    r = result.get("reminder", {})
    if r.get("recurrence"):
        return f"\U0001F501 Recurring reminder set: {r.get('message')} \u2014 {r.get('recurrence')}, {r.get('trigger_time', '')}"
    return f"\u23F0 Reminder set: {r.get('message', '')} \u2014 {r.get('trigger_date', '')} {r.get('trigger_time', '')}"


def _resp_list_reminders(result):
    reminders = result.get("reminders", [])
    if not reminders:
        return "No active reminders."
    lines = ["Your active reminders:"]
    for i, r in enumerate(reminders, 1):
        prefix = "\U0001F501" if r.get("recurrence") else "\u23F0"
        lines.append(f"{i}. {prefix} {r.get('message')} \u2014 {r.get('trigger_date', '')} {r.get('trigger_time', '')}")
    lines.append("\nReply with number to delete.")
    return "\n".join(lines)


def _resp_delete_reminder(result):
    return f"\u2705 Deleted: {result.get('message', 'reminder')}"


def _resp_modify_behavior(result):
    return f"\u2705 {result.get('message', 'Behavior updated.')}"


def _resp_add_note(result):
    note = result.get("note", "")
    msg = f"\U0001F4CC Noted: {note}"

    if result.get("new_project"):
        proj = result["new_project"]
        msg += f"\n\u2795 Created new project: *{proj.get('name')}* ({proj.get('area')})"

    if result.get("tagged_task_name"):
        msg += f"\n\U0001F3F7 Tagged to task: *{result['tagged_task_name']}*"
    elif result.get("tagged_project_id"):
        msg += f"\n\U0001F3F7 Tagged to project"

    return msg


def _resp_log_food(intent):
    return f"\U0001F4DD Food logged: {intent.get('entry', '')}"


def _resp_log_exercise(intent):
    duration = intent.get("duration", "")
    return f"\U0001F3CB Exercise logged: {intent.get('entry', '')}" + (f" ({duration})" if duration else "")


def _resp_log_sleep(intent):
    hours = intent.get("hours", "?")
    return f"\U0001F4A4 Sleep logged: {hours}h" + (f" \u2014 {intent.get('notes', '')}" if intent.get("notes") else "")


def _resp_pause(result):
    until = result.get("until", "further notice")
    return f"\U0001F515 Agent paused until {until}."


def _resp_manage_subtypes(result):
    action = result.get("action", "list")
    subtypes = result.get("subtypes", {})
    if action == "list":
        lines = ["*Subtypes:*"]
        for area, types in subtypes.items():
            lines.append(f"\n*{area.title()}:*")
            lines.append(", ".join(types) if types else "(none)")
        return "\n".join(lines)
    elif action == "add":
        area = result.get("area", "")
        subtype = result.get("subtype", "")
        return f"\u2705 Added subtype *{subtype}* to {area.title()}."
    elif action == "remove":
        area = result.get("area", "")
        subtype = result.get("subtype", "")
        return f"\u2705 Removed subtype *{subtype}* from {area.title()}."
    return "Subtypes updated."


def _resp_unknown(intent):
    return "I didn't understand that. Try:\n\u2022 \"done with [task]\"\n\u2022 \"what's next\"\n\u2022 \"add [task description]\"\n\u2022 \"push [task] to thursday\""


def _get_project_name(project_id: str, context: dict) -> str:
    if not project_id:
        return "Unknown"
    for p in context.get("projects", []):
        if (p.get("id") or p.get("sk")) == project_id:
            return p.get("name", "Unknown")
    return "Unknown"


def _get_area(project_id: str, context: dict) -> str:
    if not project_id:
        return "admin"
    for p in context.get("projects", []):
        if (p.get("id") or p.get("sk")) == project_id:
            return p.get("area", "admin")
    return "admin"
