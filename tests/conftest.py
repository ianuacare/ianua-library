"""Shared fixtures for Ianuacare tests."""

from __future__ import annotations

import pytest

from ianuacare.ai.providers.callable import CallableProvider
from ianuacare.core.auth.repository import UserRepository
from ianuacare.core.auth.service import AuthService
from ianuacare.core.models.context import RequestContext
from ianuacare.core.models.user import User
from ianuacare.infrastructure.storage.bucket import InMemoryBucketClient
from ianuacare.infrastructure.storage.database import InMemoryDatabaseClient


@pytest.fixture
def user() -> User:
    return User(user_id="u1", role="clinician", permissions=["pipeline:run", "read:data"])


@pytest.fixture
def context(user: User) -> RequestContext:
    return RequestContext(user=user, product="test-product", metadata={"model_key": "stub"})


@pytest.fixture
def db() -> InMemoryDatabaseClient:
    return InMemoryDatabaseClient()


@pytest.fixture
def bucket() -> InMemoryBucketClient:
    return InMemoryBucketClient()


@pytest.fixture
def auth_repo() -> UserRepository:
    repo = UserRepository()
    repo.register_token(
        "tok-ok",
        {"user_id": "u1", "role": "clinician", "permissions": ["pipeline:run"]},
    )
    return repo


@pytest.fixture
def auth_service(auth_repo: UserRepository) -> AuthService:
    return AuthService(auth_repo)


@pytest.fixture
def provider() -> CallableProvider:
    return CallableProvider()
