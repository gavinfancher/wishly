"""Email rendering service (T4.2).

Turns an event type plus a render context into a fully-formed email:

* the **subject** and **HTML** are rendered with Jinja2 (HTML from the
  templates in :mod:`wishly.email.templates`, subject from a per-type string
  template),
* the HTML's ``<style>`` block is **inlined** onto elements with ``premailer``
  so it survives email clients that strip ``<head>`` styles,
* a **plaintext fallback** is derived from the rendered HTML.

``manage_url`` (an unsubscribe / preferences link, built from ``APP_BASE_URL``)
is ALWAYS injected into the context, so every rendered email carries a way to
manage or stop reminders — even if a caller forgets to pass one.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlencode

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from premailer import transform

from wishly.core.settings import settings

# Event types that have a dedicated HTML template; anything else falls back to
# the generic "custom" template so a new/unknown type still renders.
_TEMPLATE_BY_EVENT_TYPE = {
    "birthday": "birthday.html.j2",
    "anniversary": "anniversary.html.j2",
    "custom": "custom.html.j2",
}
_DEFAULT_TEMPLATE = "custom.html.j2"

# Subject lines are short enough to keep as inline string templates rather than
# separate files. ``days_phrase`` is precomputed in the context.
_SUBJECT_BY_EVENT_TYPE = {
    "birthday": "{{ title }} is {{ days_phrase }}",
    "anniversary": "{{ title }} is {{ days_phrase }}",
    "custom": "Reminder: {{ title }} is {{ days_phrase }}",
}
_DEFAULT_SUBJECT = "Reminder: {{ title }} is {{ days_phrase }}"


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    """The product of :func:`render_email` — ready to hand to the Resend client."""

    subject: str
    html: str
    text: str


def _build_environment() -> Environment:
    """Create the Jinja2 environment bound to the package's template directory.

    ``StrictUndefined`` makes a missing placeholder a hard error at render time
    (so a template typo fails loudly in tests rather than silently emitting a
    blank). HTML autoescaping is on for ``.html``/``.j2`` templates.
    """
    return Environment(
        loader=PackageLoader("wishly.email", "templates"),
        autoescape=select_autoescape(default_for_string=True, default=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


# Module-level singleton: building the environment scans the package once.
_ENV = _build_environment()

# Subjects are plaintext email headers; render them without HTML autoescaping so
# characters like apostrophes don't turn into entities (e.g. ``&#39;``).
_SUBJECT_ENV = Environment(autoescape=False, undefined=StrictUndefined)


def build_manage_url(user_id: str, *, base_url: str | None = None) -> str:
    """Build the unsubscribe/preferences URL embedded in every email.

    Derived from ``APP_BASE_URL`` (overridable for tests). The frontend
    preferences page (PLAN T6.5) resolves the ``u`` query parameter.
    """
    root = (base_url if base_url is not None else settings.app_base_url).rstrip("/")
    query = urlencode({"u": user_id})
    return f"{root}/preferences?{query}"


def _days_phrase(days_before: int) -> str:
    """A human phrase for the lead time used in subjects/headlines."""
    if days_before == 0:
        return "today"
    if days_before == 1:
        return "tomorrow"
    return f"in {days_before} days"


def _format_occurrence(occurrence_date: datetime.date) -> str:
    """Render the occurrence date as e.g. ``Monday, June 15``.

    Avoids the platform-specific ``%-d`` directive so output is identical on
    Linux and macOS.
    """
    return f"{occurrence_date:%A, %B} {occurrence_date.day}"


def _html_to_text(html: str) -> str:
    """Derive a readable plaintext fallback from rendered HTML.

    Drops ``<head>`` (styles/title), turns common block tags into line breaks,
    strips remaining tags, unescapes entities, and collapses whitespace.
    """
    # Remove head/style/script blocks wholesale — never wanted in plaintext.
    without_head = re.sub(
        r"<(head|style|script)\b[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    # Block-level boundaries become newlines so structure survives.
    with_breaks = re.sub(
        r"</?(p|div|br|h[1-6]|tr|li)\b[^>]*>",
        "\n",
        without_head,
        flags=re.IGNORECASE,
    )
    # Strip every remaining tag.
    stripped = re.sub(r"<[^>]+>", "", with_breaks)
    text = unescape(stripped)
    # Collapse runs of spaces/tabs, then trim each line and squeeze blank lines.
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    collapsed: list[str] = []
    for line in lines:
        if line:
            collapsed.append(line)
        elif collapsed and collapsed[-1] != "":
            collapsed.append("")
    return "\n".join(collapsed).strip()


def render_email(
    *,
    event_type: str,
    recipient_name: str,
    title: str,
    days_before: int,
    occurrence_date: datetime.date,
    manage_url: str,
    message: str | None = None,
) -> RenderedEmail:
    """Render a reminder email to subject + inlined HTML + plaintext.

    Args:
        event_type: ``birthday`` | ``anniversary`` | ``custom`` (unknown types
            fall back to the generic custom template).
        recipient_name: Name to greet (resolved by the caller to the account
            owner's name when the event has no explicit recipient).
        title: The occasion title, e.g. ``"Mom's birthday"``.
        days_before: Lead time in days (``0`` = the occasion is today).
        occurrence_date: The specific dated occurrence the reminder is for.
        manage_url: Unsubscribe/preferences link. Always rendered; a caller
            should build it with :func:`build_manage_url`.
        message: Optional user note shown in a callout.

    Returns:
        A :class:`RenderedEmail`.
    """
    context = {
        "recipient_name": recipient_name,
        "title": title,
        "days_before": days_before,
        "occurrence_date": _format_occurrence(occurrence_date),
        "days_phrase": _days_phrase(days_before),
        "message": message,
        # manage_url is ALWAYS present — injected here regardless of caller.
        "manage_url": manage_url,
    }

    template_name = _TEMPLATE_BY_EVENT_TYPE.get(event_type, _DEFAULT_TEMPLATE)
    subject_source = _SUBJECT_BY_EVENT_TYPE.get(event_type, _DEFAULT_SUBJECT)

    raw_html = _ENV.get_template(template_name).render(context)
    # The subject is an email header (plaintext), so it must NOT be HTML-escaped
    # — render it through a separate, non-autoescaping environment.
    subject = _SUBJECT_ENV.from_string(subject_source).render(context).strip()

    # Inline the <style> block onto elements; keep the original <style> too so
    # clients that DO honour it still work. ``base_url=None`` leaves links as-is.
    inlined_html = transform(
        raw_html,
        keep_style_tags=True,
        strip_important=False,
        disable_validation=True,
    )

    text = _html_to_text(inlined_html)
    return RenderedEmail(subject=subject, html=inlined_html, text=text)


__all__ = ["RenderedEmail", "build_manage_url", "render_email"]
