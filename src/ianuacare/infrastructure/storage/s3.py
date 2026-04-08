"""S3 object storage adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:  # Optional dependency
    import boto3
except Exception:  # pragma: no cover - import-time optional dependency handling
    boto3 = None  # type: ignore[assignment]


class S3BucketClient:
    """Store and retrieve payloads in an S3 bucket."""

    def __init__(self, bucket_name: str, region: str | None = None) -> None:
        if boto3 is None:
            raise ImportError("S3BucketClient requires boto3")
        self._bucket_name = bucket_name
        self._s3 = boto3.client("s3", region_name=region)

    def upload(self, key: str, content: Any) -> dict[str, Any]:
        body = content if isinstance(content, (bytes, bytearray)) else json.dumps(content).encode()
        self._s3.put_object(Bucket=self._bucket_name, Key=key, Body=body)
        return {"ok": True, "key": key, "bucket": self._bucket_name}

    def download(self, key: str) -> Any:
        response = self._s3.get_object(Bucket=self._bucket_name, Key=key)
        return response["Body"].read()

    def generate_presigned_upload_url(
        self,
        key: str,
        *,
        mime_type: str = "application/octet-stream",
        expires_in: int = 900,
    ) -> str:
        return str(
            self._s3.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self._bucket_name,
                    "Key": key,
                    "ContentType": mime_type,
                },
                ExpiresIn=expires_in,
            )
        )

    def generate_presigned_download_url(self, key: str, *, expires_in: int = 900) -> str:
        return str(
            self._s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self._bucket_name, "Key": key},
                ExpiresIn=expires_in,
            )
        )

    def download_to_file(self, key: str, local_path: str) -> str:
        body = self.download(key)
        path = Path(local_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = body if isinstance(body, (bytes, bytearray)) else bytes(body)
        path.write_bytes(data)
        return str(path)
