"""Telegram bot webhook handler — mirrors WhatsApp agent logic."""
import traceback

from fastapi import APIRouter, Request

from .. import db
from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from ..agents.intent_parser import parse_intent
from ..agents.responder import generate_response
from ..services.telegram_client import send_telegram
from .whatsapp import _build_context, _execute_intent, _record_checkin

router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram bot messages."""
    try:
        update = await request.json()
        message = update.get("message", {})
        text = message.get("text", "").strip()
        chat_id = str(message.get("chat", {}).get("id", ""))

        if not text:
            return {"ok": True}

        # Save chat_id on first message so we can send proactive messages later
        if chat_id and not TELEGRAM_CHAT_ID:
            _save_telegram_chat_id(chat_id)

        # Load context (shared with WhatsApp)
        context = _build_context()

        # Save user message to chat log
        db.save_chat_message(context["today"], "user", text)

        # Parse intent via Claude
        intent = parse_intent(text, context)

        # Execute intent
        result = _execute_intent(intent, context)

        # Generate response
        response_text = generate_response(intent, result, context)

        # Send response via Telegram
        send_telegram(response_text, chat_id=chat_id)

        # Save agent response to chat log
        action = intent.get("intent", "unknown")
        db.save_chat_message(context["today"], "assistant", response_text, intent=action)

        # Log the check-in
        _record_checkin(
            context["today"],
            result.get("task", {}).get("sk") or result.get("task", {}).get("id"),
            "user_message",
            f"User: {text[:100]} | Agent: {response_text[:100]}",
            response=text,
        )

    except Exception as e:
        traceback.print_exc()
        try:
            if chat_id:
                send_telegram("Something went wrong. Try again in a moment.", chat_id=chat_id)
        except Exception:
            pass

    return {"ok": True}


@router.post("/set-webhook")
async def set_telegram_webhook(request: Request):
    """Set the Telegram bot webhook URL."""
    import urllib.request
    import json

    body = await request.json()
    webhook_url = body.get("url", "")
    if not webhook_url:
        return {"error": "No URL provided"}

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = json.dumps({"url": webhook_url}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    return result


def _save_telegram_chat_id(chat_id: str):
    """Save Telegram chat ID to settings for proactive messages."""
    try:
        db.update_item("SETTINGS", "USER", {"telegram_chat_id": chat_id})
    except Exception:
        pass
