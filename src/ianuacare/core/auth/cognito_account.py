"""Cognito account maintenance: reset password, logout, change password, profile."""

from __future__ import annotations

from ianuacare.core.models.password_reset_delivery import PasswordResetDelivery
from ianuacare.infrastructure.auth.cognito import CognitoAccountClient


class CognitoAccountService:
    """Forgot/reset password, global sign-out, change password, update attributes."""

    def __init__(
        self,
        region: str,
        app_client_id: str,
        *,
        client_secret: str | None = None,
    ) -> None:
        self._client = CognitoAccountClient(
            region,
            app_client_id,
            client_secret=client_secret,
        )

    def request_password_reset(self, username: str) -> PasswordResetDelivery:
        """Start forgot-password (Cognito sends code by email/SMS per pool policy)."""
        raw = self._client.forgot_password(username)
        details = raw.get("CodeDeliveryDetails") or {}
        dest = str(details.get("Destination", ""))
        medium = str(details.get("DeliveryMedium", ""))
        return PasswordResetDelivery(destination=dest, delivery_medium=medium)

    def confirm_password_reset(
        self,
        username: str,
        confirmation_code: str,
        new_password: str,
    ) -> None:
        """Complete forgot-password with code and new password."""
        self._client.confirm_forgot_password(username, confirmation_code, new_password)

    def logout(self, access_token: str) -> None:
        """Global sign-out: revoke refresh tokens.

        The access token may remain valid until it expires.
        """
        self._client.global_sign_out(access_token)

    def change_password(
        self,
        access_token: str,
        previous_password: str,
        new_password: str,
    ) -> None:
        """Change password for an authenticated session."""
        self._client.change_password(access_token, previous_password, new_password)

    def update_profile_attributes(
        self,
        access_token: str,
        attributes: dict[str, str],
    ) -> None:
        """Update standard or custom Cognito attributes (e.g. email, name, custom:role)."""
        self._client.update_user_attributes(access_token, attributes)
