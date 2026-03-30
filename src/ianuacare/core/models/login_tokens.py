"""Tokens returned by identity-provider login flows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LoginTokens:
    """OAuth-style tokens from Cognito (or compatible IdPs)."""

    access_token: str
    id_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
