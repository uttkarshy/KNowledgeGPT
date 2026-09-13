"""
Thin S3 wrapper. Every file-processing service (upload API, Celery worker)
goes through this module rather than instantiating boto3 clients directly —
keeps LocalStack/MinIO swap-in for local dev to one place (AWS_S3_ENDPOINT_URL)
and gives one spot to add server-side encryption, bucket policies, etc.
"""

from __future__ import annotations

import logging

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)


class S3Error(Exception):
    pass


def get_s3_client(settings: Settings, *, public: bool = False):
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        endpoint_url=(settings.AWS_S3_PUBLIC_ENDPOINT_URL if public else None) or settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
            s3={
                "addressing_style": "path" if settings.AWS_S3_ENDPOINT_URL else "virtual",
            },
        ),
    )


def build_upload_key(*, settings: Settings, owner_id: str, document_id: str, filename: str) -> str:
    """Deterministic, collision-free key. Owner-scoped prefix means an IAM/
    bucket policy could restrict-by-prefix per tenant if ever needed."""
    safe_filename = filename.replace("/", "_").replace("\\", "_")
    return f"{settings.S3_UPLOAD_PREFIX}/{owner_id}/{document_id}/{safe_filename}"


def generate_presigned_put_url(*, settings: Settings, key: str, content_type: str, size_bytes: int) -> str:
    """Returns a presigned S3 PUT URL."""

    client = get_s3_client(settings, public=True)

    try:
        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": size_bytes,
            },
            ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRE_SECONDS,
        )


        return url

    except (ClientError, BotoCoreError) as e:
        raise S3Error(f"Failed to generate presigned upload URL: {e}") from e

def download_to_path(*, settings: Settings, key: str, destination_path: str) -> None:
    client = get_s3_client(settings)
    try:
        client.download_file(settings.S3_BUCKET_NAME, key, destination_path)
    except (ClientError, BotoCoreError) as e:
        raise S3Error(f"Failed to download s3://{settings.S3_BUCKET_NAME}/{key}: {e}") from e


def delete_object(*, settings: Settings, key: str) -> bool:
    """Called once embedding generation succeeds — enforces the "no permanent
    file storage" rule. Also called on any pipeline failure path that
    shouldn't retain the original (e.g. validation rejection)."""
    client = get_s3_client(settings)
    try:
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        return True
    except (ClientError, BotoCoreError) as e:
        # Deletion failure shouldn't crash the pipeline — log loudly so
        # CloudWatch alarms / the admin error dashboard can catch orphaned
        # objects, but don't block the user-facing success path on it.
        logger.error("Failed to delete s3://%s/%s: %s", settings.S3_BUCKET_NAME, key, e)
        return False


def head_object_size(*, settings: Settings, key: str) -> int:
    """Server-side authoritative file size check (never trust a
    client-reported Content-Length)."""
    client = get_s3_client(settings)
    try:
        resp = client.head_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        return resp["ContentLength"]
    except (ClientError, BotoCoreError) as e:
        raise S3Error(f"Failed to stat s3://{settings.S3_BUCKET_NAME}/{key}: {e}") from e
