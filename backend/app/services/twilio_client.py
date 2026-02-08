from ..config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, WHATSAPP_TO

_client = None


def get_client():
    global _client
    if _client is None:
        from twilio.rest import Client
        _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _client


def send_whatsapp(body: str, to: str = None) -> str | None:
    """Send a WhatsApp message via Twilio. Returns message SID or None in dev mode."""
    if not TWILIO_ACCOUNT_SID:
        print(f"\n[WHATSAPP] To: {to or WHATSAPP_TO}")
        print(f"{body}")
        print("---")
        return None

    client = get_client()
    message = client.messages.create(
        body=body,
        from_=TWILIO_WHATSAPP_FROM,
        to=to or WHATSAPP_TO,
    )
    return message.sid
