"""Send messages via Telegram Bot API."""
import urllib.request
import urllib.parse
import json

from ..config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def send_telegram(text: str, chat_id: str = None, parse_mode: str = "Markdown") -> dict | None:
    """Send a Telegram message. Returns API response or None in dev mode."""
    if not TELEGRAM_BOT_TOKEN:
        print(f"\n[TELEGRAM] To: {chat_id or TELEGRAM_CHAT_ID}")
        print(f"{text}")
        print("---")
        return None

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id or TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        # If Markdown fails, retry without parse_mode
        if parse_mode:
            return send_telegram(text, chat_id, parse_mode=None)
        print(f"[TELEGRAM ERROR] {e}")
        return None
