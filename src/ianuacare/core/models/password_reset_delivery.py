"""Non-sensitive hints from Cognito after a password-reset request."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PasswordResetDelivery:
    """Where Cognito says it sent the reset code (masked destination)."""

    destination: str
    delivery_medium: str
