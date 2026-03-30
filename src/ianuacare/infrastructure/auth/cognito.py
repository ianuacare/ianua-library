"""Cognito-backed user repository, login, registration, and account/session APIs."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any, NoReturn

from ianuacare.core.exceptions.errors import AuthenticationError, ValidationError

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


def _raise_cognito_sign_up_error(exc: Any) -> NoReturn:
    """Map Cognito ``SignUp`` failures."""
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        raise exc
    code = exc.response.get("Error", {}).get("Code", "")
    if code == "UsernameExistsException":
        raise ValidationError("Username already registered", code="username_exists") from exc
    if code == "InvalidPasswordException":
        raise ValidationError("Password does not meet policy", code="invalid_password") from exc
    if code == "InvalidParameterException":
        raise ValidationError("Invalid sign-up parameters", code="invalid_parameter") from exc
    if code == "TooManyRequestsException":
        raise AuthenticationError("Too many attempts", code="rate_limited") from exc
    if code == "UserLambdaValidationException":
        msg = exc.response.get("Error", {}).get("Message", "Registration validation failed")
        raise ValidationError(msg, code="user_lambda_validation") from exc
    raise ValidationError("Registration failed", code="cognito_error") from exc


def _raise_cognito_confirm_sign_up_error(exc: Any) -> NoReturn:
    """Map Cognito ``ConfirmSignUp`` failures."""
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        raise exc
    code = exc.response.get("Error", {}).get("Code", "")
    if code == "CodeMismatchException":
        raise ValidationError(
            "Invalid confirmation code",
            code="invalid_confirmation_code",
        ) from exc
    if code == "ExpiredCodeException":
        raise ValidationError(
            "Confirmation code expired",
            code="expired_confirmation_code",
        ) from exc
    if code == "NotAuthorizedException":
        raise ValidationError(
            "User cannot be confirmed or is already confirmed",
            code="confirm_not_allowed",
        ) from exc
    if code == "UserNotFoundException":
        raise ValidationError("Unknown user", code="user_not_found") from exc
    if code == "AliasExistsException":
        raise ValidationError("Alias already in use", code="alias_exists") from exc
    if code == "TooManyRequestsException":
        raise AuthenticationError("Too many attempts", code="rate_limited") from exc
    raise ValidationError("Confirmation failed", code="cognito_error") from exc


def _raise_cognito_forgot_password_error(exc: Any) -> NoReturn:
    """Map Cognito ``ForgotPassword`` failures."""
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        raise exc
    code = exc.response.get("Error", {}).get("Code", "")
    if code == "InvalidParameterException":
        raise ValidationError("Invalid password reset request", code="invalid_parameter") from exc
    if code == "LimitExceededException":
        raise AuthenticationError("Password reset limit exceeded", code="limit_exceeded") from exc
    if code == "TooManyRequestsException":
        raise AuthenticationError("Too many attempts", code="rate_limited") from exc
    if code == "UserNotFoundException":
        raise ValidationError("Unknown user", code="user_not_found") from exc
    raise ValidationError("Password reset request failed", code="cognito_error") from exc


def _raise_cognito_confirm_forgot_password_error(exc: Any) -> NoReturn:
    """Map Cognito ``ConfirmForgotPassword`` failures."""
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        raise exc
    code = exc.response.get("Error", {}).get("Code", "")
    if code == "CodeMismatchException":
        raise ValidationError(
            "Invalid confirmation code",
            code="invalid_confirmation_code",
        ) from exc
    if code == "ExpiredCodeException":
        raise ValidationError(
            "Confirmation code expired",
            code="expired_confirmation_code",
        ) from exc
    if code == "InvalidPasswordException":
        raise ValidationError("Password does not meet policy", code="invalid_password") from exc
    if code == "UserNotFoundException":
        raise ValidationError("Unknown user", code="user_not_found") from exc
    if code == "TooManyRequestsException":
        raise AuthenticationError("Too many attempts", code="rate_limited") from exc
    if code == "NotAuthorizedException":
        raise ValidationError(
            "Password reset cannot be completed",
            code="reset_not_allowed",
        ) from exc
    raise ValidationError("Password reset confirmation failed", code="cognito_error") from exc


def _raise_cognito_global_sign_out_error(exc: Any) -> NoReturn:
    """Map Cognito ``GlobalSignOut`` failures."""
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        raise exc
    code = exc.response.get("Error", {}).get("Code", "")
    if code in ("NotAuthorizedException", "PasswordResetRequiredException"):
        raise AuthenticationError("Invalid or expired access token", code="invalid_token") from exc
    if code == "TooManyRequestsException":
        raise AuthenticationError("Too many attempts", code="rate_limited") from exc
    raise AuthenticationError("Sign out failed", code="cognito_error") from exc


def _raise_cognito_change_password_error(exc: Any) -> NoReturn:
    """Map Cognito ``ChangePassword`` failures."""
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        raise exc
    code = exc.response.get("Error", {}).get("Code", "")
    if code == "InvalidPasswordException":
        raise ValidationError("Password does not meet policy", code="invalid_password") from exc
    if code == "NotAuthorizedException":
        raise AuthenticationError(
            "Current password incorrect or session invalid",
            code="invalid_credentials",
        ) from exc
    if code == "LimitExceededException":
        raise AuthenticationError("Attempt limit exceeded", code="limit_exceeded") from exc
    if code == "TooManyRequestsException":
        raise AuthenticationError("Too many attempts", code="rate_limited") from exc
    if code == "PasswordResetRequiredException":
        raise AuthenticationError(
            "Password reset required",
            code="password_reset_required",
        ) from exc
    raise ValidationError("Password change failed", code="cognito_error") from exc


def _raise_cognito_update_user_attributes_error(exc: Any) -> NoReturn:
    """Map Cognito ``UpdateUserAttributes`` failures."""
    from botocore.exceptions import ClientError

    if not isinstance(exc, ClientError):
        raise exc
    code = exc.response.get("Error", {}).get("Code", "")
    if code == "InvalidParameterException":
        raise ValidationError("Invalid profile attributes", code="invalid_parameter") from exc
    if code == "AliasExistsException":
        raise ValidationError("Alias already in use", code="alias_exists") from exc
    if code == "NotAuthorizedException":
        raise AuthenticationError("Invalid or expired access token", code="invalid_token") from exc
    if code == "TooManyRequestsException":
        raise AuthenticationError("Too many attempts", code="rate_limited") from exc
    raise ValidationError("Profile update failed", code="cognito_error") from exc


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


class CognitoRegistrationClient:
    """Self-service registration via Cognito ``SignUp`` / ``ConfirmSignUp``."""

    def __init__(
        self,
        region: str,
        app_client_id: str,
        *,
        client_secret: str | None = None,
    ) -> None:
        if boto3 is None:
            raise ImportError("CognitoRegistrationClient requires boto3")
        self._client_id = app_client_id
        self._client_secret = client_secret
        self._cognito = boto3.client("cognito-idp", region_name=region)

    def sign_up(
        self,
        username: str,
        password: str,
        *,
        attributes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Call ``sign_up`` and return the boto3 response dict."""
        user_attrs = [{"Name": k, "Value": v} for k, v in (attributes or {}).items()]
        kwargs: dict[str, Any] = {
            "ClientId": self._client_id,
            "Username": username,
            "Password": password,
            "UserAttributes": user_attrs,
        }
        if self._client_secret:
            kwargs["SecretHash"] = _cognito_secret_hash(
                username, self._client_id, self._client_secret
            )
        try:
            return self._cognito.sign_up(**kwargs)
        except Exception as exc:
            _raise_cognito_sign_up_error(exc)

    def confirm_sign_up(self, username: str, confirmation_code: str) -> None:
        """Call ``confirm_sign_up``."""
        kwargs: dict[str, Any] = {
            "ClientId": self._client_id,
            "Username": username,
            "ConfirmationCode": confirmation_code,
        }
        if self._client_secret:
            kwargs["SecretHash"] = _cognito_secret_hash(
                username, self._client_id, self._client_secret
            )
        try:
            self._cognito.confirm_sign_up(**kwargs)
        except Exception as exc:
            _raise_cognito_confirm_sign_up_error(exc)


class CognitoAccountClient:
    """Forgot/reset password, sign-out, change password, and profile attributes."""

    def __init__(
        self,
        region: str,
        app_client_id: str,
        *,
        client_secret: str | None = None,
    ) -> None:
        if boto3 is None:
            raise ImportError("CognitoAccountClient requires boto3")
        self._client_id = app_client_id
        self._client_secret = client_secret
        self._cognito = boto3.client("cognito-idp", region_name=region)

    def forgot_password(self, username: str) -> dict[str, Any]:
        """Call ``forgot_password``; response may include ``CodeDeliveryDetails``."""
        kwargs: dict[str, Any] = {
            "ClientId": self._client_id,
            "Username": username,
        }
        if self._client_secret:
            kwargs["SecretHash"] = _cognito_secret_hash(
                username, self._client_id, self._client_secret
            )
        try:
            return self._cognito.forgot_password(**kwargs)
        except Exception as exc:
            _raise_cognito_forgot_password_error(exc)

    def confirm_forgot_password(
        self,
        username: str,
        confirmation_code: str,
        new_password: str,
    ) -> None:
        """Call ``confirm_forgot_password``."""
        kwargs: dict[str, Any] = {
            "ClientId": self._client_id,
            "Username": username,
            "ConfirmationCode": confirmation_code,
            "Password": new_password,
        }
        if self._client_secret:
            kwargs["SecretHash"] = _cognito_secret_hash(
                username, self._client_id, self._client_secret
            )
        try:
            self._cognito.confirm_forgot_password(**kwargs)
        except Exception as exc:
            _raise_cognito_confirm_forgot_password_error(exc)

    def global_sign_out(self, access_token: str) -> None:
        """Call ``global_sign_out`` (revoke refresh tokens for this user)."""
        try:
            self._cognito.global_sign_out(AccessToken=access_token)
        except Exception as exc:
            _raise_cognito_global_sign_out_error(exc)

    def change_password(
        self,
        access_token: str,
        previous_password: str,
        proposed_password: str,
    ) -> None:
        """Call ``change_password`` (authenticated user)."""
        try:
            self._cognito.change_password(
                AccessToken=access_token,
                PreviousPassword=previous_password,
                ProposedPassword=proposed_password,
            )
        except Exception as exc:
            _raise_cognito_change_password_error(exc)

    def update_user_attributes(
        self,
        access_token: str,
        attributes: dict[str, str],
    ) -> None:
        """Call ``update_user_attributes``."""
        user_attrs = [{"Name": k, "Value": v} for k, v in attributes.items()]
        try:
            self._cognito.update_user_attributes(
                AccessToken=access_token,
                UserAttributes=user_attrs,
            )
        except Exception as exc:
            _raise_cognito_update_user_attributes_error(exc)
