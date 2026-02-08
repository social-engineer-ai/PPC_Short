import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

TABLE_NAME = os.getenv("TABLE_NAME", "pcp-workboard")
PCP_API_KEY = os.getenv("PCP_API_KEY", "dev-key")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
WHATSAPP_TO = os.getenv("WHATSAPP_TO", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TIMEZONE = os.getenv("TIMEZONE", "America/Chicago")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
LOCAL_DYNAMODB_URL = os.getenv("LOCAL_DYNAMODB_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
LAMBDA_ARN = os.getenv("LAMBDA_ARN", "")
SCHEDULER_ROLE_ARN = os.getenv("SCHEDULER_ROLE_ARN", "")

DEFAULT_SETTINGS = {
    "weekly_capacity_hours": 40,
    "daily_capacity_hours": 8,
    "morning_briefing_time": "07:00",
    "midday_checkin_time": "13:00",
    "evening_summary_time": "18:00",
    "block_duration_minutes": 120,
    "nudge_delay_minutes": 30,
    "whatsapp_number": "",
    "timezone": "America/Chicago",
    "agent_persona": "David Goggins",
}

HOUR_DEFAULTS = {
    "Lecture Content": 2.0,
    "Slides": 2.0,
    "Examples": 1.0,
    "Labs": 2.0,
    "Homework": 1.5,
    "Grading": 1.5,
    "Office Hours": 1.0,
    "Writing": 2.0,
    "Analysis": 2.0,
    "Experiments": 3.0,
    "IRB": 1.0,
    "Submissions": 1.0,
    "Lit Review": 2.0,
    "Email": 0.5,
    "Meetings": 1.0,
    "Doctors": 0.5,
    "Errands": 1.0,
    "Taxes": 1.5,
    "Finances": 1.5,
}
