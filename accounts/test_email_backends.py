from unittest.mock import Mock, patch

from django.core.mail import EmailMessage
from django.test import SimpleTestCase, override_settings

from .email_backends import (
    RESEND_EMAIL_ENDPOINT,
    RESEND_REQUEST_TIMEOUT,
    ResendAPIError,
    ResendEmailBackend,
)


@override_settings(
    RESEND_API_KEY="test-api-key",
    DEFAULT_FROM_EMAIL="Weatherpins <noreply@weatherpins.ru>",
)
class ResendEmailBackendTests(SimpleTestCase):
    @patch("accounts.email_backends.requests.post")
    def test_sends_email_through_resend_api(self, post):
        post.return_value = Mock(status_code=200)
        message = EmailMessage(
            subject="Восстановление пароля",
            body="Use the password reset link.",
            from_email="Weatherpins <noreply@weatherpins.ru>",
            to=["user@example.com"],
            cc=["copy@example.com"],
            bcc=["audit@example.com"],
        )

        sent_count = ResendEmailBackend().send_messages([message])

        self.assertEqual(sent_count, 1)
        post.assert_called_once_with(
            RESEND_EMAIL_ENDPOINT,
            headers={
                "Authorization": "Bearer test-api-key",
                "Content-Type": "application/json",
            },
            json={
                "from": "Weatherpins <noreply@weatherpins.ru>",
                "to": ["user@example.com"],
                "subject": "Восстановление пароля",
                "text": "Use the password reset link.",
                "cc": ["copy@example.com"],
                "bcc": ["audit@example.com"],
            },
            timeout=RESEND_REQUEST_TIMEOUT,
        )

    @patch("accounts.email_backends.requests.post")
    def test_uses_default_from_email_as_fallback(self, post):
        post.return_value = Mock(status_code=200)
        message = EmailMessage(
            subject="Subject",
            body="Body",
            from_email="",
            to=["user@example.com"],
        )

        ResendEmailBackend().send_messages([message])

        payload = post.call_args.kwargs["json"]
        self.assertEqual(
            payload["from"],
            "Weatherpins <noreply@weatherpins.ru>",
        )

    @patch("accounts.email_backends.requests.post")
    def test_api_error_raises_when_fail_silently_is_false(self, post):
        post.return_value = Mock(status_code=422)
        message = EmailMessage(
            subject="Subject",
            body="Body",
            to=["user@example.com"],
        )

        with self.assertRaisesMessage(ResendAPIError, "HTTP 422"):
            ResendEmailBackend(fail_silently=False).send_messages([message])

    @patch("accounts.email_backends.requests.post")
    def test_api_error_returns_zero_when_fail_silently_is_true(self, post):
        post.return_value = Mock(status_code=500)
        message = EmailMessage(
            subject="Subject",
            body="Body",
            to=["user@example.com"],
        )

        sent_count = ResendEmailBackend(fail_silently=True).send_messages([message])

        self.assertEqual(sent_count, 0)

    @override_settings(RESEND_API_KEY="")
    @patch("accounts.email_backends.requests.post")
    def test_missing_api_key_raises_clear_error(self, post):
        message = EmailMessage(
            subject="Subject",
            body="Body",
            to=["user@example.com"],
        )

        with self.assertRaisesMessage(ResendAPIError, "RESEND_API_KEY"):
            ResendEmailBackend().send_messages([message])

        post.assert_not_called()
