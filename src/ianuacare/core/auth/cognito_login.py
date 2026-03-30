"""Cognito username/password login (USER_PASSWORD_AUTH)."""

from __future__ import annotations

from ianuacare.core.exceptions.errors import AuthenticationError
from ianuacare.core.models.login_tokens import LoginTokens
from ianuacare.infrastructure.auth.cognito import CognitoPasswordAuthenticator


class CognitoLoginService:
    """Exchange Cognito credentials for tokens."""

    def __init__(
        self,
        region: str,
        app_client_id: str,
        *,
        client_secret: str | None = None,
    ) -> None:
        self._authenticator = CognitoPasswordAuthenticator(
            region,
            app_client_id,
            client_secret=client_secret,
        )

    def login(self, username: str, password: str) -> LoginTokens:
        """Return tokens on success or raise :class:`AuthenticationError`."""
        result = self._authenticator.initiate_user_password_auth(username, password)
        if "ChallengeName" in result:
            raise AuthenticationError(
                "Additional authentication step required",
                code="cognito_challenge",
            )
        auth = result.get("AuthenticationResult")
        if not auth:
            raise AuthenticationError("Unexpected Cognito response", code="cognito_error")
        return LoginTokens(
            access_token=str(auth["AccessToken"]),
            id_token=str(auth["IdToken"]),
            refresh_token=str(auth.get("RefreshToken", "")),
            token_type=str(auth.get("TokenType", "Bearer")),
            expires_in=int(auth["ExpiresIn"]) if auth.get("ExpiresIn") is not None else None,
        )
