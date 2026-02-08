"""WhatsApp webhook handler — the core of the agent."""
import traceback
import uuid
from datetime import datetime

from fastapi import APIRouter, Request, Response

from .. import db
from ..agents.intent_parser import parse_intent
from ..agents.responder import generate_response
from ..services.twilio_client import send_whatsapp
from ..services.task_service import (
    find_matching_task,
    get_next_task,
    create_task_from_intent,
    calculate_day_load,
    get_free_slots,
)

router = APIRouter()


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _week_id() -> str:
    d = datetime.utcnow()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _day_name() -> str:
    return datetime.utcnow().strftime("%A").lower()


def _build_context() -> dict:
    """Load all context needed for intent parsing."""
    today = _today()
    week_id = _week_id()
    day_name = _day_name()

    projects = db.list_projects(active_only=True)
    week_tasks = db.get_tasks_for_week(week_id)
    today_tasks = [t for t in week_tasks if t.get("day") == day_name and t.get("status") != "dropped"]
    recent_checkins = db.get_checkins_for_date(today)[-3:]
    pending = db.get_pending_task()
    agent_notes = db.list_active_agent_notes()
    behavior_overrides = db.list_active_behavior_overrides()
    settings = db.get_settings()
    dayplan = db.get_dayplan(today)

    return {
        "today": today,
        "week_id": week_id,
        "day_of_week": day_name.title(),
        "projects": projects,
        "week_tasks": week_tasks,
        "today_tasks": today_tasks,
        "recent_checkins": recent_checkins,
        "pending": pending,
        "agent_notes": agent_notes,
        "behavior_overrides": behavior_overrides,
        "settings": settings,
        "dayplan": dayplan,
    }


@router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Handle incoming Twilio WhatsApp messages."""
    try:
        form_data = await request.form()
        message_body = form_data.get("Body", "").strip()
        from_number = form_data.get("From", "")

        if not message_body:
            return Response(content="<Response></Response>", media_type="application/xml")

        # Load context
        context = _build_context()

        # Parse intent via Claude
        intent = parse_intent(message_body, context)

        # Execute intent
        result = _execute_intent(intent, context)

        # Generate response
        response_text = generate_response(intent, result, context)

        # Send response via Twilio
        send_whatsapp(response_text)

        # Log the check-in
        _record_checkin(
            context["today"],
            result.get("task", {}).get("sk") or result.get("task", {}).get("id"),
            "user_message",
            f"User: {message_body[:100]} | Agent: {response_text[:100]}",
            response=message_body,
        )

    except Exception as e:
        traceback.print_exc()
        try:
            send_whatsapp("Something went wrong. Try again in a moment.")
        except Exception:
            pass

    # Always return 200 to Twilio
    return Response(content="<Response></Response>", media_type="application/xml")


@router.post("/status")
async def whatsapp_status(request: Request):
    """Twilio delivery status callback."""
    return {"ok": True}


@router.post("/test-message")
async def test_message(request: Request):
    """Simulate a WhatsApp message for local testing (no Twilio signature needed)."""
    body = await request.json()
    message = body.get("message", "")
    if not message:
        return {"error": "No message provided"}

    context = _build_context()
    intent = parse_intent(message, context)
    result = _execute_intent(intent, context)
    response_text = generate_response(intent, result, context)

    return {
        "intent": intent,
        "result": result,
        "response": response_text,
    }


def _execute_intent(intent: dict, context: dict) -> dict:
    """Execute the parsed intent and return result data."""
    action = intent.get("intent", "unknown")

    if action == "add_task":
        return _handle_add_task(intent, context)
    elif action == "complete_pending":
        return _handle_complete_pending(intent, context)
    elif action == "mark_done":
        return _handle_status_change(intent, context, "done")
    elif action == "mark_doing":
        return _handle_status_change(intent, context, "doing")
    elif action == "mark_skipped":
        return _handle_status_change(intent, context, "skipped")
    elif action == "move_task":
        return _handle_move_task(intent, context)
    elif action == "push_tomorrow":
        return _handle_push_tomorrow(intent, context)
    elif action == "query_next":
        return _handle_query_next(context)
    elif action == "query_today":
        return {"tasks": context.get("today_tasks", [])}
    elif action == "query_day":
        return _handle_query_day(intent, context)
    elif action == "query_week":
        return {"tasks": context.get("week_tasks", [])}
    elif action == "chat":
        return _handle_chat(intent, context)
    elif action == "checkin_response":
        return _handle_checkin_response(intent, context)
    elif action == "acknowledge":
        return {"acknowledged": True}
    elif action == "set_reminder":
        return _handle_set_reminder(intent)
    elif action == "delete_reminder":
        return _handle_delete_reminder(intent)
    elif action == "list_reminders":
        return {"reminders": db.list_active_reminders()}
    elif action == "modify_behavior":
        return _handle_modify_behavior(intent)
    elif action == "add_note":
        return _handle_add_note(intent)
    elif action in ("log_food", "log_exercise", "log_sleep"):
        return _handle_health_log(intent, context)
    elif action == "pause_agent":
        return _handle_pause_agent(intent)
    elif action == "manage_subtypes":
        return _handle_manage_subtypes(intent)
    else:
        return {"unknown": True}


def _handle_add_task(intent: dict, context: dict) -> dict:
    """Handle smart task intake."""
    tasks_data = intent.get("tasks", [])
    results = []

    for td in tasks_data:
        needs = td.get("needs_clarification", [])

        if needs:
            # Save as pending
            db.save_pending_task({
                "task": td,
                "needs": needs,
                "candidates": {"project": td.get("project_candidates", [])},
            })
            results.append({
                "pending": True,
                "needs": needs,
                "message": intent.get("message_to_user", "Need more info."),
            })
        else:
            # Create the task
            task = create_task_from_intent(td, context)
            results.append({"created": True, "task": task})

    return {"tasks_results": results, "pending": any(r.get("pending") for r in results)}


def _handle_complete_pending(intent: dict, context: dict) -> dict:
    """Complete a pending task by filling in a missing field."""
    pending = context.get("pending")
    if not pending:
        return {"error": "No pending task found."}

    field = intent.get("field", "")
    value = intent.get("value", "")
    task_data = pending.get("task", {})
    needs = pending.get("needs", [])

    # Fill in the field
    if field == "project" and pending.get("candidates", {}).get("project"):
        candidates = pending["candidates"]["project"]
        try:
            idx = int(value) - 1
            if 0 <= idx < len(candidates):
                task_data["project_id"] = candidates[idx]
        except (ValueError, IndexError):
            # Try matching by name
            for pid in candidates:
                proj = db.get_item("PROJECT", pid)
                if proj and value.lower() in proj.get("name", "").lower():
                    task_data["project_id"] = pid
                    break
    elif field == "hours":
        try:
            task_data["estimated_hours"] = float(value)
        except ValueError:
            pass
    elif field == "day":
        task_data["day"] = value.lower()
    elif field == "confirm":
        pass  # Just confirming

    # Remove filled field from needs
    if field in needs:
        needs.remove(field)

    if needs:
        # Still needs more info
        db.save_pending_task({"task": task_data, "needs": needs, "candidates": pending.get("candidates", {})})
        return {"needs_more": True, "needs": needs, "question": f"Got it. Now, what about {needs[0]}?"}

    # All fields filled — create the task
    db.clear_pending_task()
    task = create_task_from_intent(task_data, context)
    return {"created": True, "task": task}


def _handle_status_change(intent: dict, context: dict, new_status: str) -> dict:
    """Handle mark_done, mark_doing, mark_skipped."""
    match_str = intent.get("task_match", "")
    today_tasks = context.get("today_tasks", [])
    task = find_matching_task(match_str, today_tasks)

    if not task:
        # Try all week tasks
        task = find_matching_task(match_str, context.get("week_tasks", []))

    if not task:
        return {"error": f"No matching task found for '{match_str}'."}

    task_id = task.get("id") or task.get("sk")
    updates = {"status": new_status}
    if new_status == "done":
        updates["completed_at"] = datetime.utcnow().isoformat()
    elif new_status == "doing":
        updates["started_at"] = datetime.utcnow().isoformat()

    db.update_item("TASK", task_id, updates)
    task["status"] = new_status

    # Get next task
    remaining = [t for t in today_tasks if (t.get("id") or t.get("sk")) != task_id and t.get("status") in ("todo", "doing")]
    next_task = get_next_task(remaining, context.get("dayplan"))

    return {"task": task, "next_task": next_task}


def _handle_move_task(intent: dict, context: dict) -> dict:
    match_str = intent.get("task_match", "")
    to_day = intent.get("to_day", "")
    task = find_matching_task(match_str, context.get("week_tasks", []))
    if not task:
        return {"error": f"No matching task for '{match_str}'."}

    task_id = task.get("id") or task.get("sk")
    db.update_item("TASK", task_id, {"day": to_day})
    task["day"] = to_day

    load = calculate_day_load(context.get("week_tasks", []), to_day)
    return {"task": task, "day_load": load + task.get("estimated_hours", 0)}


def _handle_push_tomorrow(intent: dict, context: dict) -> dict:
    match_str = intent.get("task_match", "")
    task = find_matching_task(match_str, context.get("today_tasks", []))
    if not task:
        task = find_matching_task(match_str, context.get("week_tasks", []))
    if not task:
        return {"error": f"No matching task for '{match_str}'."}

    # Determine tomorrow's day name
    from datetime import timedelta
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%A").lower()
    task_id = task.get("id") or task.get("sk")
    db.update_item("TASK", task_id, {"day": tomorrow})
    task["day"] = tomorrow
    return {"task": task}


def _handle_query_next(context: dict) -> dict:
    next_task = get_next_task(context.get("today_tasks", []), context.get("dayplan"))
    return {"next_task": next_task}


def _handle_checkin_response(intent: dict, context: dict) -> dict:
    """Handle emoji/text responses to block check-ins."""
    status = intent.get("status", "done")

    # Find the most recent unresponded check-in
    checkins = context.get("recent_checkins", [])
    last_checkin = None
    for ci in reversed(checkins):
        if ci.get("type") in ("block_end", "morning") and not ci.get("response"):
            last_checkin = ci
            break

    task = None
    if last_checkin and last_checkin.get("task_id"):
        task = db.get_item("TASK", last_checkin["task_id"])

    if task:
        task_id = task.get("id") or task.get("sk")
        if status == "done":
            db.update_item("TASK", task_id, {"status": "done", "completed_at": datetime.utcnow().isoformat()})
            task["status"] = "done"
        elif status == "working":
            db.update_item("TASK", task_id, {"status": "doing"})
            task["status"] = "doing"
        elif status == "skipped":
            db.update_item("TASK", task_id, {"status": "skipped"})
            task["status"] = "skipped"
        elif status == "pushed":
            from datetime import timedelta
            tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%A").lower()
            db.update_item("TASK", task_id, {"day": tomorrow, "status": "todo"})
            task["day"] = tomorrow

    # Update the check-in record
    if last_checkin:
        ci_id = last_checkin.get("sk") or last_checkin.get("id")
        ci_pk = f"CHECKIN#{context['today']}"
        db.update_item(ci_pk, ci_id, {
            "response": status,
            "response_at": datetime.utcnow().isoformat(),
        })

    next_task = get_next_task(
        [t for t in context.get("today_tasks", []) if t.get("status") in ("todo", "doing")],
        context.get("dayplan"),
    )

    return {"task": task or {}, "next_task": next_task, "status": status}


def _handle_set_reminder(intent: dict) -> dict:
    reminder_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    item = {
        "pk": "REMINDER",
        "sk": reminder_id,
        "id": reminder_id,
        "type": "recurring" if intent.get("recurring") else "one_time",
        "message": intent.get("message", ""),
        "trigger_date": intent.get("date"),
        "trigger_time": intent.get("time", "09:00"),
        "recurrence": intent.get("recurring"),
        "active": True,
        "created_at": now,
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)
    return {"reminder": item}


def _handle_delete_reminder(intent: dict) -> dict:
    num = intent.get("reminder_number", 0)
    reminders = db.list_active_reminders()
    if 0 < num <= len(reminders):
        r = reminders[num - 1]
        db.update_item("REMINDER", r["sk"], {"active": False})
        return {"message": r.get("message", "reminder")}
    return {"error": "Invalid reminder number."}


def _handle_modify_behavior(intent: dict) -> dict:
    override_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    duration = intent.get("duration", "permanent")

    applies_until = None
    if duration == "today":
        applies_until = _today()
    elif duration == "tomorrow":
        from datetime import timedelta
        applies_until = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

    item = {
        "pk": "BEHAVIOR",
        "sk": override_id,
        "id": override_id,
        "setting": intent.get("setting", ""),
        "value": intent.get("value", ""),
        "applies_from": _today(),
        "applies_until": applies_until,
        "active": True,
        "created_at": now,
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)
    return {"message": f"{intent.get('setting', 'Setting')} updated to {intent.get('value', '')} ({duration})."}


def _handle_add_note(intent: dict) -> dict:
    note_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Auto-create project if referenced but doesn't exist
    new_project = None
    project_id = intent.get("tagged_project")
    if not project_id and intent.get("new_project_name"):
        proj_id = str(uuid.uuid4())
        area = intent.get("new_project_area", "admin")
        new_project = {
            "pk": "PROJECT",
            "sk": proj_id,
            "id": proj_id,
            "name": intent["new_project_name"],
            "area": area,
            "description": "",
            "match_keywords": [],
            "active": True,
            "created_at": now,
            "updated_at": now,
        }
        db.put_item(new_project)
        project_id = proj_id

    # Fuzzy-match tagged task
    tagged_task_id = None
    tagged_task_name = None
    if intent.get("tagged_task"):
        from ..services.task_service import find_matching_task
        week_tasks = db.get_tasks_for_week(_week_id())
        matched = find_matching_task(intent["tagged_task"], week_tasks)
        if matched:
            tagged_task_id = matched.get("id") or matched.get("sk")
            tagged_task_name = matched.get("name")

    item = {
        "pk": "AGENTNOTE",
        "sk": note_id,
        "id": note_id,
        "note": intent.get("note", ""),
        "applies_from": _today(),
        "applies_until": intent.get("applies_until"),
        "affects": "general",
        "active": True,
        "tagged_project_id": project_id,
        "tagged_task_id": tagged_task_id,
        "created_at": now,
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)

    return {
        "note": intent.get("note", ""),
        "tagged_project_id": project_id,
        "tagged_task_name": tagged_task_name,
        "new_project": new_project,
    }


def _handle_health_log(intent: dict, context: dict) -> dict:
    """Log food, exercise, or sleep as a check-in record."""
    log_type = intent.get("intent", "log_food")
    entry = intent.get("entry", "")
    _record_checkin(
        context["today"],
        None,
        log_type,
        entry,
    )
    return {"logged": True}


def _handle_pause_agent(intent: dict) -> dict:
    until = intent.get("until", "end of day")
    override_id = str(uuid.uuid4())
    db.put_item({
        "pk": "BEHAVIOR",
        "sk": override_id,
        "id": override_id,
        "setting": "paused",
        "value": "true",
        "applies_from": _today(),
        "applies_until": until if until != "end of day" else _today(),
        "active": True,
        "created_at": datetime.utcnow().isoformat(),
    })
    return {"until": until}


def _handle_manage_subtypes(intent: dict) -> dict:
    """Add, remove, or list subtypes for an area."""
    from ..config import DEFAULT_SETTINGS
    action = intent.get("action", "list")
    area = intent.get("area", "")
    subtype = intent.get("subtype", "")

    # Get current subtypes from settings
    settings = db.get_settings()
    custom_subtypes = settings.get("custom_subtypes", {})

    # Default subtypes per area
    defaults = {
        "teaching": ["Lecture Content", "Slides", "Examples", "Labs", "Homework", "Grading", "Office Hours", "Student Issues"],
        "research": ["Planning", "Writing", "Analysis", "Experiments", "IRB", "Submissions", "Lit Review", "Collaboration"],
        "admin": ["Email", "Meetings", "Reports", "Committee", "Letters", "Scheduling"],
        "personal": ["Family", "House", "Finances", "Taxes", "Doctors", "Insurance", "Kids School", "Errands"],
    }

    if action == "list":
        result = {}
        for a in (["teaching", "research", "admin", "personal"] if not area else [area]):
            base = list(defaults.get(a, []))
            added = custom_subtypes.get(a, {}).get("added", [])
            removed = custom_subtypes.get(a, {}).get("removed", [])
            final = [s for s in base if s not in removed] + added
            result[a] = final
        return {"action": "list", "subtypes": result}

    if not area or not subtype:
        return {"error": "Need both area and subtype name."}

    if area not in custom_subtypes:
        custom_subtypes[area] = {"added": [], "removed": []}

    if action == "add":
        if subtype not in custom_subtypes[area].get("added", []):
            custom_subtypes[area].setdefault("added", []).append(subtype)
        # If it was previously removed from defaults, un-remove it
        if subtype in custom_subtypes[area].get("removed", []):
            custom_subtypes[area]["removed"].remove(subtype)
    elif action == "remove":
        # If it's a custom one, remove from added list
        if subtype in custom_subtypes[area].get("added", []):
            custom_subtypes[area]["added"].remove(subtype)
        # If it's a default, add to removed list
        elif subtype in defaults.get(area, []):
            custom_subtypes[area].setdefault("removed", []).append(subtype)

    db.update_item("SETTINGS", "USER", {"custom_subtypes": custom_subtypes})

    # Return the updated list for this area
    base = list(defaults.get(area, []))
    added = custom_subtypes.get(area, {}).get("added", [])
    removed = custom_subtypes.get(area, {}).get("removed", [])
    final = [s for s in base if s not in removed] + added

    return {"action": action, "area": area, "subtype": subtype, "subtypes": {area: final}}


def _handle_query_day(intent: dict, context: dict) -> dict:
    """Return tasks for a specific day of the week."""
    day = intent.get("day", "").lower()
    week_tasks = context.get("week_tasks", [])
    day_tasks = [t for t in week_tasks if t.get("day") == day and t.get("status") != "dropped"]
    return {"tasks": day_tasks, "day": day}


def _handle_chat(intent: dict, context: dict) -> dict:
    """Handle conversational messages. Optionally save as a note."""
    message = intent.get("message", "")
    reply = intent.get("reply", "")
    save = intent.get("save_as_note", False)

    if save and message:
        note_id = str(uuid.uuid4())
        db.put_item({
            "pk": "AGENTNOTE",
            "sk": note_id,
            "id": note_id,
            "note": message,
            "applies_from": _today(),
            "affects": "general",
            "active": True,
            "created_at": datetime.utcnow().isoformat(),
        })
    return {"reply": reply, "saved": save}


def _record_checkin(date: str, task_id: str | None, check_type: str, message: str, response: str = None):
    """Record a check-in in DynamoDB."""
    ci_id = str(uuid.uuid4())
    item = {
        "pk": f"CHECKIN#{date}",
        "sk": ci_id,
        "id": ci_id,
        "date": date,
        "task_id": task_id,
        "type": check_type,
        "message_sent": message,
        "response": response,
        "response_at": datetime.utcnow().isoformat() if response else None,
        "created_at": datetime.utcnow().isoformat(),
    }
    item = {k: v for k, v in item.items() if v is not None}
    db.put_item(item)
