"""Thin wrapper over the Resend Python SDK (T4.3).

Exposes a single :class:`ResendClient` with :meth:`~ResendClient.send_email`,
which builds the Resend payload, sends, and returns the provider message id.
Any failure is normalised to a typed :class:`EmailSendError` so callers (the
Dagster send op) never have to know Resend's exception taxonomy.

Configuration (``RESEND_API_KEY``, ``EMAIL_FROM``) is read from
:data:`wishly.core.settings.settings`; nothing is hard-coded. The SDK is
imported lazily inside the client so importing this module never requires the
key to be set, and so tests can patch ``resend`` cleanly.
"""

from __future__ import annotations

import resend
import resend.exceptions

from wishly.core.settings import settings


class EmailSendError(RuntimeError):
    """Raised when sending an email via Resend fails.

    ``transient`` marks errors worth retrying (rate limits / upstream 5xx);
    the Dagster op's retry policy can use it to avoid retrying, say, a hard
    validation error forever.
    """

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


# Resend errors that represent a temporary condition (retry may succeed).
_TRANSIENT_ERRORS: tuple[type[Exception], ...] = (resend.exceptions.RateLimitError,)


class ResendClient:
    """Stateful sender holding the API key + ``from`` address.

    Args:
        api_key: Resend API key; defaults to ``settings.resend_api_key``.
        email_from: ``From`` address; defaults to ``settings.email_from``.
    """

    def __init__(self, *, api_key: str | None = None, email_from: str | None = None) -> None:
        self._api_key = api_key if api_key is not None else settings.resend_api_key
        self._email_from = email_from if email_from is not None else settings.email_from

    def send_email(self, *, to: str, subject: str, html: str, text: str) -> str:
        """Send one email and return the Resend message id.

        Args:
            to: Recipient address.
            subject: Email subject line.
            html: Rendered (CSS-inlined) HTML body.
            text: Plaintext fallback body.

        Returns:
            The Resend message id (``resend_id``).

        Raises:
            EmailSendError: if the key is missing, the SDK raises, or the
                response carries no id.
        """
        if not self._api_key:
            raise EmailSendError("RESEND_API_KEY is not configured")

        # The SDK reads the key from its module-level global; set it per-send so
        # a process can hold differently-configured clients without interference.
        resend.api_key = self._api_key

        params: resend.Emails.SendParams = {
            "from": self._email_from,
            "to": to,
            "subject": subject,
            "html": html,
            "text": text,
        }

        try:
            response = resend.Emails.send(params)
        except resend.exceptions.ResendError as exc:
            raise EmailSendError(
                f"Resend rejected the send: {exc}",
                transient=isinstance(exc, _TRANSIENT_ERRORS),
            ) from exc
        except Exception as exc:  # network/transport errors surface as transient.
            raise EmailSendError(f"Resend send failed: {exc}", transient=True) from exc

        resend_id = _extract_id(response)
        if not resend_id:
            raise EmailSendError(f"Resend response missing an id: {response!r}")
        return resend_id


def _extract_id(response: object) -> str | None:
    """Pull the message id out of a Resend send response.

    The SDK returns a ``TypedDict`` (mapping) ``{"id": ...}``, but we also accept
    an object with an ``id`` attribute to be defensive across SDK versions.
    """
    value = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)
    return value if isinstance(value, str) and value else None


__all__ = ["EmailSendError", "ResendClient"]
