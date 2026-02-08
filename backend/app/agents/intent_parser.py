"""Parse WhatsApp messages into structured intents using Claude API."""
import json
import traceback
from datetime import datetime

from ..config import ANTHROPIC_API_KEY, TIMEZONE

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def parse_intent(message: str, context: dict) -> dict:
    """Send user message + context to Claude, get structured intent JSON back."""
    if not ANTHROPIC_API_KEY:
        return _mock_parse(message)

    system_prompt = _build_system_prompt(context)

    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": message}],
        )
        text = response.content[0].text.strip()
        return _extract_json(text)
    except Exception as e:
        traceback.print_exc()
        return {"intent": "unknown", "raw": message, "error": str(e)}


def _extract_json(text: str) -> dict:
    """Extract JSON from Claude's response, handling code blocks."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    if "```" in text:
        parts = text.split("```")
        for part in parts[1::2]:  # Odd indices are inside code blocks
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue

    # Try finding JSON object in text
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return {"intent": "unknown", "raw": text}


def _build_system_prompt(ctx: dict) -> str:
    """Build the full system prompt with all context injected."""
    def _local_now():
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(TIMEZONE))
        except Exception:
            return datetime.utcnow()

    today = ctx.get("today", _local_now().strftime("%Y-%m-%d"))
    day_of_week = ctx.get("day_of_week", _local_now().strftime("%A"))
    settings = ctx.get("settings", {})
    persona = settings.get("agent_persona", "David Goggins")

    # Format projects
    projects_text = ""
    for p in ctx.get("projects", []):
        keywords = ", ".join(p.get("match_keywords", []))
        projects_text += f"- {p.get('name')} (area: {p.get('area')}, id: {p.get('id') or p.get('sk')}) [keywords: {keywords}]\n"

    # Format today's tasks
    tasks_text = ""
    for i, t in enumerate(ctx.get("today_tasks", []), 1):
        status = t.get("status", "todo")
        tasks_text += f"{i}. [{status}] {t.get('name')} ({t.get('estimated_hours', 0)}h, {t.get('priority', 'normal')})\n"
    if not tasks_text:
        tasks_text = "(no tasks scheduled for today)\n"

    # Format week schedule summary
    week_tasks = ctx.get("week_tasks", [])
    week_text = ""
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        day_tasks = [t for t in week_tasks if t.get("day") == day and t.get("status") not in ("dropped",)]
        hrs = sum(t.get("estimated_hours", 0) for t in day_tasks)
        done = len([t for t in day_tasks if t.get("status") == "done"])
        total = len(day_tasks)
        free = max(0, 8 - hrs)
        week_text += f"  {day.title()}: {hrs}h planned, {done}/{total} done, {free}h free\n"
        for t in day_tasks:
            week_text += f"    - {t.get('name')} ({t.get('status')}, {t.get('estimated_hours', 0)}h)\n"

    # Format pending task
    pending = ctx.get("pending")
    pending_text = "null"
    if pending:
        pending_text = json.dumps(pending.get("task", {}), indent=2)
        needs = pending.get("needs", [])
        pending_text += f"\nMissing fields: {needs}"

    # Format recent check-ins
    checkins_text = ""
    for ci in ctx.get("recent_checkins", [])[-3:]:
        checkins_text += f"- [{ci.get('type')}] {ci.get('message_sent', '')[:80]}...\n"
        if ci.get("response"):
            checkins_text += f"  User replied: {ci['response']}\n"
    if not checkins_text:
        checkins_text = "(no recent check-ins)\n"

    # Agent notes
    notes_text = ""
    for n in ctx.get("agent_notes", []):
        notes_text += f"- {n.get('note')} (until: {n.get('applies_until', 'indefinite')})\n"

    # Chat history
    chat_text = ""
    for msg in ctx.get("chat_history", [])[-15:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")[:200]
        chat_text += f"{'You' if role == 'user' else 'PCP'}: {content}\n"
    if not chat_text:
        chat_text = "(no prior messages today)\n"

    return f"""You are PCP, a personal productivity assistant for a teaching professor. You manage tasks AND have real conversations. Parse the user's WhatsApp message and return a JSON object with the intent and parameters.

PERSONALITY: {persona} — be warm, direct, concise, and human. You remember earlier messages and can discuss the user's work, day, ideas, or anything. Don't lecture. If the user shares a thought or wants to chat, have a real conversation — reference their tasks, projects, and earlier messages where relevant.

CURRENT DATE: {today}
CURRENT DAY: {day_of_week}

USER'S PROJECTS:
{projects_text}
TODAY'S TASKS:
{tasks_text}
WEEK SCHEDULE:
{week_text}
PENDING TASK (if user is in middle of adding a task):
{pending_text}

CONVERSATION HISTORY (today):
{chat_text}
RECENT CHECK-INS:
{checkins_text}
ACTIVE NOTES:
{notes_text or "(none)"}

POSSIBLE INTENTS:

Task intake (smart — infer as much as possible):
- add_task: {{
    "intent": "add_task",
    "tasks": [
      {{
        "name": "...",
        "project_id": "..." or null (if ambiguous, set null and ask),
        "project_candidates": ["id1", "id2"] (if ambiguous),
        "subtype": "..." or null,
        "priority": "urgent|high|normal|low",
        "estimated_hours": N or null (use defaults: Grading 1.5, Slides 2, Writing 2, Email 0.5, Call 0.5, Meeting 1),
        "day": "monday|tuesday|...|saturday|sunday" or null,
        "time": "HH:MM" or null (24h format, 5-min multiples — e.g. "15:00" for 3pm, "09:30" for 9:30am, "14:45". Parse "3pm"→"15:00", "10am"→"10:00", "noon"→"12:00", "3:20pm"→"15:20"),
        "time_hint": "morning|afternoon|evening" or null,
        "due_date": "YYYY-MM-DD" or null,
        "course_week": "N" or null,
        "needs_clarification": ["project", "hours", "day"] (list of fields agent should ask about),
        "is_time_block": false (true if personal commitment, not work)
      }}
    ],
    "message_to_user": "..." (confirmation or clarification question)
  }}

- complete_pending: {{ "intent": "complete_pending", "field": "project|hours|day|confirm", "value": "..." }}

Task management:
- mark_done: {{ "intent": "mark_done", "task_match": "string to fuzzy match" }}
- mark_skipped: {{ "intent": "mark_skipped", "task_match": "..." }}
- mark_doing: {{ "intent": "mark_doing", "task_match": "..." }}
- move_task: {{ "intent": "move_task", "task_match": "...", "to_day": "wednesday" }}
- push_tomorrow: {{ "intent": "push_tomorrow", "task_match": "..." }}

Queries:
- query_next: {{ "intent": "query_next" }}
- query_today: {{ "intent": "query_today" }}
- query_day: {{ "intent": "query_day", "day": "monday|tuesday|...|saturday|sunday" }}
  Use this when user asks about a SPECIFIC day like "what's on wednesday", "what's due tomorrow", "show me friday", "tomorrow's schedule"
- query_week: {{ "intent": "query_week" }}

Conversational:
- chat: {{ "intent": "chat", "message": "...", "reply": "...", "save_as_note": true|false }}
  Use when the user shares a thought, asks a question, wants to discuss their day/work, or has a freeform conversation.
  "reply" = YOUR natural conversational response (1-3 sentences). Reference their tasks, projects, schedule, and CONVERSATION HISTORY.
  "save_as_note" = true only if the message contains a thought/idea worth remembering later. false for casual chat/questions.
  You have FULL access to the user's schedule, projects, and prior conversation. Use it to give informed, relevant responses.
  Examples:
    "how's my week looking" → reply with a summary of their week progress, busy days, and what's coming up
    "I had a rough class today" → empathize, reference which class if you can infer it
    "I haven't been exercising" → reply: "I see that. Want me to block some time for it this week?", save_as_note: true
    "what do you think I should focus on" → suggest based on their priorities, deadlines, and neglected areas
    "tell me about my research projects" → summarize their research projects and recent tasks
    "what's the dashboard link" → reply: "Dashboard: https://dm2iiyavn83ii.cloudfront.net", save_as_note: false
    "thanks" → reply: "Anytime.", save_as_note: false

SYSTEM INFO (for answering questions about PCP):
  Dashboard: https://dm2iiyavn83ii.cloudfront.net
  API: https://r8ggoea875.execute-api.us-east-1.amazonaws.com
  You can: add/manage tasks, set reminders, log food/exercise/sleep, save notes, manage subtypes
  Supported commands: "add [task]", "done with [task]", "what's next", "push [task] to thursday", "what's due tomorrow", "show week", "set reminder", "list subtypes"

Check-in responses:
- checkin_response: {{ "intent": "checkin_response", "status": "done|working|skipped|pushed" }}
- acknowledge: {{ "intent": "acknowledge" }}

Health tracking:
- log_food: {{ "intent": "log_food", "entry": "..." }}
- log_exercise: {{ "intent": "log_exercise", "entry": "...", "duration": "..." }}
- log_sleep: {{ "intent": "log_sleep", "hours": N, "notes": "..." }}

Subtypes management:
- manage_subtypes: {{ "intent": "manage_subtypes", "action": "add|remove|list", "area": "teaching|research|admin|personal", "subtype": "..." }}
  Examples: "add subtype Peer Review to research", "list subtypes for teaching", "remove subtype Labs from teaching"

Reminders & agent config:
- set_reminder: {{ "intent": "set_reminder", "message": "...", "date": "...", "time": "...", "recurring": null | "daily" | "weekly:day" | "monthly:N" }}
- delete_reminder: {{ "intent": "delete_reminder", "reminder_number": N }}
- list_reminders: {{ "intent": "list_reminders" }}
- modify_behavior: {{ "intent": "modify_behavior", "setting": "...", "value": "...", "duration": "today|tomorrow|this_week|permanent" }}
- add_note: {{ "intent": "add_note", "note": "...", "applies_until": "...", "tagged_project": "project_id or null", "tagged_task": "fuzzy task name or null", "new_project_name": "name or null", "new_project_area": "teaching|research|admin|personal or null" }}
  Use for thoughts/ideas the user wants to save, optionally tagged to a project or task.
  If the user references a project that exists, set tagged_project to its id.
  If they reference a project that DOESN'T exist, set new_project_name and new_project_area so we create it.
  If they reference a task, set tagged_task to a fuzzy match string.
  Examples:
    "note for 358: maybe add a kaggle competition" → tagged_project: BADM 358's id
    "thought on signaling paper: add robustness checks" → tagged_project: Signaling Theory's id
    "idea for a new course on AI ethics" → new_project_name: "AI Ethics Course", new_project_area: "teaching"
    "just a random thought: need to reorganize my office" → no tags
- pause_agent: {{ "intent": "pause_agent", "until": "..." }}

Fallback:
- unknown: {{ "intent": "unknown", "raw": "..." }}

RULES:
- IMPORTANT: Not everything is a task. If the user shares a thought, feeling, observation, or reflection (e.g. "I haven't been exercising", "feeling overwhelmed", "had a great class today"), use the "chat" intent — do NOT turn it into add_task.
- Only use add_task if the user is clearly asking to CREATE or SCHEDULE something specific (e.g. "add slides for 358", "need to grade homework by friday")
- For "what's tomorrow", "what's due tomorrow", "show wednesday" etc → use query_day with the appropriate day name. Convert "tomorrow" to the actual day name based on CURRENT DAY.
- For add_task: ALWAYS try to infer project from keywords. Match "358" to BADM 358, "signaling" to Signaling Theory, "dentist" to Health, "taxes" to Finances, etc.
- For add_task: infer subtype from action words: "grade" → Grading, "write/draft" → Writing, "slides/lecture" → Slides, "call/book" → Doctors or Errands
- For add_task: if user says "by friday" or "due friday", set due_date AND day=friday
- For add_task: if user's message contains MULTIPLE tasks, return multiple items in the tasks array
- If a PENDING TASK exists and the user's reply looks like an answer to a question (a number, a day name, "yes", an hour amount), use complete_pending intent
- If the message is just an emoji (✅, 👍), interpret as acknowledge or checkin_response
- For task matching, be fuzzy — "slides" matches "Prepare Week 6 slides"
- If user mentions food, tea, meals, protein, sugar → use log_food
- If user mentions exercise, gym, run, walk, workout → use log_exercise
- Return ONLY a valid JSON object"""


def _mock_parse(message: str) -> dict:
    """Simple rule-based parser for local dev without Claude API."""
    msg = message.lower().strip()

    if msg in ("✅", "👍", "yes", "y", "ok", "done"):
        return {"intent": "checkin_response", "status": "done"}
    if msg in ("🔵", "still working"):
        return {"intent": "checkin_response", "status": "working"}
    if msg in ("⏭", "skip", "skipped"):
        return {"intent": "checkin_response", "status": "skipped"}
    if msg in ("🔄", "push", "pushed"):
        return {"intent": "checkin_response", "status": "pushed"}
    if "what's next" in msg or "whats next" in msg:
        return {"intent": "query_next"}
    if msg in ("today", "what's today", "show today"):
        return {"intent": "query_today"}
    if msg in ("week", "show week"):
        return {"intent": "query_week"}
    if msg.startswith("done with "):
        return {"intent": "mark_done", "task_match": msg[10:]}
    if msg.startswith("push ") and " to " in msg:
        parts = msg[5:].rsplit(" to ", 1)
        return {"intent": "move_task", "task_match": parts[0], "to_day": parts[1]}

    return {"intent": "unknown", "raw": message}
