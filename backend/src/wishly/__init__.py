"""Wishly backend package.

The FastAPI API and the reminder send pipeline over one PostgreSQL database.
One process runs both: the send is a background task started by an hourly
EventBridge rule POSTing to ``/internal/runs/send-reminders``. See
``docs/PLAN.md``.
"""
