import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


RESEND_EMAIL_ENDPOINT = "https://api.resend.com/emails"
RESEND_REQUEST_TIMEOUT = 10


class ResendAPIError(RuntimeError):
    """Raised when an email cannot be sent through the Resend API."""


class ResendEmailBackend(BaseEmailBackend):
    """Send Django email messages through the Resend HTTPS API."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            if self.fail_silently:
                return 0
            raise ResendAPIError(
                "RESEND_API_KEY is not configured for the Resend email backend."
            )

        sent_count = 0
        for message in email_messages:
            if not message.recipients():
                continue

            try:
                response = requests.post(
                    RESEND_EMAIL_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=self._message_payload(message),
                    timeout=RESEND_REQUEST_TIMEOUT,
                )
                if not 200 <= response.status_code < 300:
                    raise ResendAPIError(
                        "Resend email API returned "
                        f"HTTP {response.status_code}."
                    )
            except (requests.RequestException, ResendAPIError):
                if not self.fail_silently:
                    raise
            else:
                sent_count += 1

        return sent_count

    @staticmethod
    def _message_payload(message):
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to or []),
            "subject": message.subject,
            "text": message.body,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        return payload
