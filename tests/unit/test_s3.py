"""S3 adapter."""

from unittest.mock import MagicMock, patch

import ianuacare.infrastructure.storage.s3 as s3_module
from ianuacare.infrastructure.storage.s3 import S3BucketClient


def test_s3_upload_download() -> None:
    mock_boto3 = MagicMock()
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"data")}
    mock_boto3.client.return_value = s3

    with patch.object(s3_module, "boto3", mock_boto3):
        bucket = S3BucketClient("my-bucket", "eu-west-1")
        out = bucket.upload("k", {"a": 1})
        assert out["ok"] is True
        assert bucket.download("k") == b"data"


def test_s3_presigned_urls_and_download_to_file(tmp_path) -> None:
    mock_boto3 = MagicMock()
    s3 = MagicMock()
    s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"binary")}
    s3.generate_presigned_url.return_value = "https://example.com/signed"
    mock_boto3.client.return_value = s3

    with patch.object(s3_module, "boto3", mock_boto3):
        bucket = S3BucketClient("my-bucket", "eu-west-1")
        up = bucket.generate_presigned_upload_url("k", mime_type="audio/wav")
        down = bucket.generate_presigned_download_url("k")
        saved = bucket.download_to_file("k", str(tmp_path / "a.wav"))
        assert up.startswith("https://")
        assert down.startswith("https://")
        assert (tmp_path / "a.wav").read_bytes() == b"binary"
        assert saved.endswith("a.wav")
