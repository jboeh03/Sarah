"""Delivery: turn a digest into something deliverable (email payload)."""

from .gmail import build_email_payload, EmailPayload

__all__ = ["build_email_payload", "EmailPayload"]
