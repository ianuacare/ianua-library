"""Cognito-backed user repository and password login."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any, NoReturn

from ianuacare.core.exceptions.errors import AuthenticationError

try:  # Optional dependencies
    import boto3
    from jose import jwt
except Exception:  # pragma: no cover - import-time optional dependency handling
    boto3 = None  # type: ignore[assignment]
    jwt = None  # type: ignore[assignment]


def _cognito_secret_hash(username: str, client_id: str, client_secret: str) -> str:
    """Compute SECRET_HASH for confidential app clients (USER_PASSWORD_AUTH)."""
    msg = bytes(username + client_id, "utf-8")
    key = bytes(client_secret, "utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _raise_cognito_initiate_auth_error(exc: Any) -> NoReturn:
    """Map Cognito ``InitiateAuth`` failures to :class:`AuthenticationError`."""
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        raise exc
    code = exc.response.get("Error", {}).get("Code", "")
    if code in ("NotAuthorizedException", "UserNotFoundException"):
        raise AuthenticationError(
            "Invalid username or password",
            code="invalid_credentials",
        ) from exc
    if code == "TooManyRequestsException":
        raise AuthenticationError("Too many attempts", code="rate_limited") from exc
    raise AuthenticationError("Authentication failed", code="cognito_error") from exc


class CognitoUserRepository:
    """Resolve users by validating Cognito-issued JWT access tokens."""

    def __init__(self, region: str, user_pool_id: str, app_client_id: str) -> None:
        if boto3 is None or jwt is None:
            raise ImportError("CognitoUserRepository requires boto3 and python-jose")
        self._region = region
        self._user_pool_id = user_pool_id
        self._app_client_id = app_client_id
        self._cognito = boto3.client("cognito-idp", region_name=region)

    def get_user_by_token(self, token: str) -> dict[str, Any]:
        """Return a user record from token claims."""
        claims = jwt.get_unverified_claims(token)
        user_info = self._cognito.get_user(AccessToken=token)
        username = user_info.get("Username") or claims.get("sub") or "unknown"
        role = str(claims.get("custom:role", claims.get("cognito:groups", ["user"])[0]))
        permissions_raw = claims.get("custom:permissions", "")
        permissions = [p for p in str(permissions_raw).split(",") if p]
        return {
            "user_id": str(username),
            "role": role,
            "permissions": permissions,
        }


class CognitoPasswordAuthenticator:
    """USER_PASSWORD_AUTH against a Cognito app client."""

    def __init__(
        self,
        region: str,
        app_client_id: str,
        *,
        client_secret: str | None = None,
    ) -> None:
        if boto3 is None:
            raise ImportError("CognitoPasswordAuthenticator requires boto3")
        self._client_id = app_client_id
        self._client_secret = client_secret
        self._cognito = boto3.client("cognito-idp", region_name=region)

    def initiate_user_password_auth(self, username: str, password: str) -> dict[str, Any]:
        """Call ``InitiateAuth`` and return the boto3 response dict."""
        auth_params: dict[str, str] = {
            "USERNAME": username,
            "PASSWORD": password,
        }
        if self._client_secret:
            auth_params["SECRET_HASH"] = _cognito_secret_hash(
                username, self._client_id, self._client_secret
            )
        try:
            return self._cognito.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                ClientId=self._client_id,
                AuthParameters=auth_params,
            )
        except Exception as exc:
            _raise_cognito_initiate_auth_error(exc)
