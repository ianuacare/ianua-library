"""Object storage abstraction (protocol + in-memory implementation)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BucketClient(Protocol):
    """Contract for blob/object storage."""

    def upload(self, key: str, content: Any) -> dict[str, Any]:
        """Store ``content`` at ``key``."""
        ...

    def download(self, key: str) -> Any:
        """Load object at ``key``."""
        ...


class InMemoryBucketClient:
    """In-memory ``BucketClient`` for development and tests."""

    def __init__(self, files: dict[str, Any] | None = None) -> None:
        self._files: dict[str, Any] = dict(files) if files is not None else {}

    def upload(self, key: str, content: Any) -> dict[str, Any]:
        self._files[key] = content
        return {"ok": True, "key": key}

    def download(self, key: str) -> Any:
        if key not in self._files:
            msg = f"Object not found: {key}"
            raise KeyError(msg)
        return self._files[key]

    def generate_presigned_upload_url(
        self, object_key: str, *, mime_type: str, expires_in: int
    ) -> str:
        """Return a stable fake URL (for tests; production uses S3-style presigning)."""
        _ = mime_type, expires_in
        return f"inmemory:upload:{object_key}"

    def generate_presigned_download_url(self, object_key: str, *, expires_in: int) -> str:
        _ = expires_in
        return f"inmemory:download:{object_key}"

