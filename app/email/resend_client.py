import resend

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailClient:
    def __init__(self) -> None:
        settings = get_settings()
        resend.api_key = settings.resend_api_key
        self._from = f"{settings.resend_from_name} <{settings.resend_from_email}>"

    async def send_booking_confirmation(
        self,
        to: str,
        name: str,
        meeting_start: str,
        meeting_url: str | None = None,
    ) -> str:
        body = f"""Hi {name},

Your discovery call with LevelOne Agency has been confirmed.

📅 {meeting_start}
{"🔗 " + meeting_url if meeting_url else ""}

We'll send a calendar invite shortly. Looking forward to speaking with you!

Best,
Alex
LevelOne Agency
"""
        params: resend.Emails.SendParams = {
            "from": self._from,
            "to": [to],
            "subject": "Your Discovery Call with LevelOne Agency — Confirmed",
            "text": body,
        }
        resp = resend.Emails.send(params)
        email_id = resp.get("id", "")
        logger.info("email_sent", email_id=email_id, to=to, type="booking_confirmation")
        return email_id

    async def send_followup(self, to: str, name: str, summary: str) -> str:
        body = f"""Hi {name},

Thank you for calling LevelOne Agency today. Here's a quick summary of what we discussed:

{summary}

Feel free to reach out if you have any questions — we'd love to help.

Best,
Alex
LevelOne Agency
"""
        params: resend.Emails.SendParams = {
            "from": self._from,
            "to": [to],
            "subject": "Thanks for calling LevelOne Agency",
            "text": body,
        }
        resp = resend.Emails.send(params)
        email_id = resp.get("id", "")
        logger.info("email_sent", email_id=email_id, to=to, type="followup")
        return email_id
