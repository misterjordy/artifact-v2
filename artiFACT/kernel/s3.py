"""S3/MinIO client utility."""

from typing import Any

import boto3
from botocore.client import BaseClient
from botocore.config import Config as BotoConfig

from artiFACT.kernel.config import settings


def get_s3_client() -> BaseClient:
    """Create a boto3 S3 client configured for MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )


def upload_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Upload bytes to S3."""
    client = get_s3_client()
    client.put_object(
        Bucket=settings.S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def download_bytes(key: str) -> bytes:
    """Download bytes from S3."""
    client = get_s3_client()
    response = client.get_object(Bucket=settings.S3_BUCKET, Key=key)
    return response["Body"].read()  # type: ignore[no-any-return]  # boto3 response body


def upload_json(key: str, data: str) -> None:
    """Upload JSON string to S3."""
    upload_bytes(key, data.encode("utf-8"), content_type="application/json")


def download_json(key: str) -> str:
    """Download JSON string from S3."""
    return download_bytes(key).decode("utf-8")
