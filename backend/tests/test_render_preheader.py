"""Preheader (inbox preview text) behaviour in the rendered reminder email.

The preheader is the only part of the email a recipient reads *before* opening
it, and it is easy to break invisibly: it must reach the client's preview line
while never rendering in the open email, and never leak into the plaintext part.
"""

from __future__ import annotations

import datetime
import re

import pytest

from wishly.email.render import render_email

_PREHEADER = re.compile(r'<div[^>]*class="[^"]*preheader"[^>]*>(.*?)</div>', re.DOTALL)


def _render(**overrides: object):
    kwargs: dict[str, object] = {
        "event_type": "birthday",
        "recipient_name": "Gavin",
        "title": "Mom's Bday",
        "days_before": 7,
        "occurrence_date": datetime.date(2027, 4, 3),
        "manage_url": "https://wishly.dev/preferences?u=user_1",
    }
    kwargs.update(overrides)
    return render_email(**kwargs)  # type: ignore[arg-type]


def _preheader_text(html: str) -> str:
    body = html.split("<body", 1)[1]
    match = _PREHEADER.search(body)
    assert match is not None, "no preheader in rendered email"
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()


def test_preheader_leads_the_body() -> None:
    """It must come before the wordmark, or the client scrapes that instead."""
    body = _render().html.split("<body", 1)[1]
    assert body.index('class="preheader"') < body.index('class="brand"')


def test_preheader_is_hidden_after_inlining() -> None:
    """premailer must carry display:none onto the element, not just leave it in
    the <style> block that Gmail may strip."""
    body = _render().html.split("<body", 1)[1]
    match = _PREHEADER.search(body)
    assert match is not None
    assert "display:none" in match.group(0).replace(" ", "")


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, "Saturday, April 3 — still time to plan something."),
        ({"days_before": 0}, "Saturday, April 3 — that’s today."),
        (
            {"message": "Get the good chocolate"},
            "Saturday, April 3 — your note: Get the good chocolate",
        ),
    ],
)
def test_preheader_copy(kwargs: dict[str, object], expected: str) -> None:
    """It leads with the weekday date — the thing the subject does not say."""
    assert _preheader_text(_render(**kwargs).html) == expected


@pytest.mark.parametrize("kwargs", [{}, {"days_before": 0}, {"message": "A note"}])
def test_preheader_absent_from_plaintext(kwargs: dict[str, object]) -> None:
    """A plaintext reader already has the subject; repeating it stutters, and
    the zero-width pad would arrive as mojibake."""
    rendered = _render(**kwargs)
    assert _preheader_text(rendered.html) not in rendered.text
    assert "‌" not in rendered.text
    assert rendered.text.startswith("wishly.")
