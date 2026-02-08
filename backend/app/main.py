import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from .routes import projects, tasks, weeks, dayplans, settings

app = FastAPI(title="PCP Workboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 1 routes
app.include_router(projects.router, prefix="/projects", tags=["projects"])
app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
app.include_router(weeks.router, prefix="/weeks", tags=["weeks"])
app.include_router(dayplans.router, prefix="/dayplan", tags=["dayplans"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])

# Phase 2 routes (imported when available)
try:
    from .routes import whatsapp, telegram, reminders, agent_notes, behavior
    app.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
    app.include_router(telegram.router, prefix="/telegram", tags=["telegram"])
    app.include_router(reminders.router, prefix="/reminders", tags=["reminders"])
    app.include_router(agent_notes.router, prefix="/agent-notes", tags=["agent-notes"])
    app.include_router(behavior.router, prefix="/behavior", tags=["behavior"])
except ImportError:
    pass


@app.get("/health")
def health():
    return {"status": "ok", "service": "pcp-workboard"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Mangum adapter for Lambda
mangum_handler = Mangum(app, lifespan="off", api_gateway_base_path="/api")


def handler(event, context):
    """Single Lambda handler: routes API Gateway requests vs EventBridge scheduled events."""
    if isinstance(event, dict) and "action" in event:
        return _handle_scheduled_action(event, context)
    return mangum_handler(event, context)


def _handle_scheduled_action(event, context):
    """Route EventBridge scheduled events to appropriate handlers."""
    action = event.get("action")
    try:
        if action == "morning_briefing":
            from .agents.briefing import send_morning_briefing
            return send_morning_briefing()
        elif action == "midday_checkin":
            from .agents.checkin import send_midday_checkin
            return send_midday_checkin()
        elif action == "evening_summary":
            from .agents.summary import send_evening_summary
            return send_evening_summary()
        elif action == "block_checkin":
            from .agents.checkin import send_block_checkin
            return send_block_checkin(event["task_id"], event["block_end"])
        elif action == "nudge_check":
            from .agents.checkin import check_and_send_nudges
            return check_and_send_nudges()
        elif action == "reminder":
            from .agents.reminders import send_reminder
            return send_reminder(event["reminder_id"])
        else:
            return {"statusCode": 400, "body": f"Unknown action: {action}"}
    except Exception as e:
        traceback.print_exc()
        return {"statusCode": 500, "body": str(e)}
