"""Cognito password login (core service + infra adapter)."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import ianuacare.infrastructure.auth.cognito as cognito_module
from ianuacare.core.auth.cognito_login import CognitoLoginService
from ianuacare.core.exceptions.errors import AuthenticationError


def test_cognito_login_success() -> None:
    mock_boto3 = MagicMock()
    cognito = MagicMock()
    cognito.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "at",
            "IdToken": "id",
            "RefreshToken": "rt",
            "TokenType": "Bearer",
            "ExpiresIn": 3600,
        }
    }
    mock_boto3.client.return_value = cognito

    with patch.object(cognito_module, "boto3", mock_boto3):
        svc = CognitoLoginService("eu-west-1", "client-id")
        tokens = svc.login("user@example.com", "secret")

    assert tokens.access_token == "at"
    assert tokens.id_token == "id"
    assert tokens.refresh_token == "rt"
    assert tokens.token_type == "Bearer"
    assert tokens.expires_in == 3600
    cognito.initiate_auth.assert_called_once()
    call_kw = cognito.initiate_auth.call_args[1]
    assert call_kw["AuthFlow"] == "USER_PASSWORD_AUTH"
    assert call_kw["ClientId"] == "client-id"
    assert call_kw["AuthParameters"]["USERNAME"] == "user@example.com"
    assert call_kw["AuthParameters"]["PASSWORD"] == "secret"
    assert "SECRET_HASH" not in call_kw["AuthParameters"]


def test_cognito_login_includes_secret_hash_when_client_secret_set() -> None:
    mock_boto3 = MagicMock()
    cognito = MagicMock()
    cognito.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "a",
            "IdToken": "i",
            "RefreshToken": "r",
            "TokenType": "Bearer",
            "ExpiresIn": 60,
        }
    }
    mock_boto3.client.return_value = cognito

    with patch.object(cognito_module, "boto3", mock_boto3):
        svc = CognitoLoginService(
            "eu-west-1",
            "client-id",
            client_secret="the-secret",
        )
        svc.login("alice", "pw")

    secret_hash = cognito.initiate_auth.call_args[1]["AuthParameters"]["SECRET_HASH"]
    assert isinstance(secret_hash, str)
    assert len(secret_hash) > 0


def test_cognito_login_invalid_credentials() -> None:
    mock_boto3 = MagicMock()
    cognito = MagicMock()
    cognito.initiate_auth.side_effect = ClientError(
        {"Error": {"Code": "NotAuthorizedException", "Message": "x"}},
        "InitiateAuth",
    )
    mock_boto3.client.return_value = cognito

    with patch.object(cognito_module, "boto3", mock_boto3):
        svc = CognitoLoginService("eu-west-1", "client-id")

    with pytest.raises(AuthenticationError) as ei:
        svc.login("u", "bad")
    assert ei.value.code == "invalid_credentials"


def test_cognito_login_challenge_raises() -> None:
    mock_boto3 = MagicMock()
    cognito = MagicMock()
    cognito.initiate_auth.return_value = {
        "ChallengeName": "NEW_PASSWORD_REQUIRED",
        "Session": "sess",
    }
    mock_boto3.client.return_value = cognito

    with patch.object(cognito_module, "boto3", mock_boto3):
        svc = CognitoLoginService("eu-west-1", "client-id")

    with pytest.raises(AuthenticationError) as ei:
        svc.login("u", "p")
    assert ei.value.code == "cognito_challenge"
