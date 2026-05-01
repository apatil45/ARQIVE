"""
Storage connector: local filesystem, S3, or MinIO (boto3).
Read-only for document access; write for uploads to company's storage.
Documents never copied to ARQIVE node — read into memory only during ingestion.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)


class StorageConnector(Protocol):
    """Protocol for storage backends. Path = object key (S3) or relative path (local)."""

    def read_bytes(self, path: str) -> bytes:
        """Read object/file into memory. Raises FileNotFoundError if missing."""
        ...

    def write_bytes(self, path: str, data: bytes) -> None:
        """Write bytes to path (e.g. upload). Overwrites if exists."""
        ...

    def exists(self, path: str) -> bool:
        """Return True if path exists."""
        ...

    def delete(self, path: str) -> None:
        """Remove object/file. No-op or raise if missing."""
        ...


class LocalStorageConnector:
    """Local filesystem under STORAGE_LOCAL_PATH. Path is relative to base."""

    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path).resolve()

    def _full_path(self, path: str) -> Path:
        # Avoid path traversal
        full = (self._base / path).resolve()
        if not str(full).startswith(str(self._base)):
            raise ValueError("Path outside storage base")
        return full

    def read_bytes(self, path: str) -> bytes:
        p = self._full_path(path)
        if not p.is_file():
            raise FileNotFoundError(path)
        return p.read_bytes()

    def write_bytes(self, path: str, data: bytes) -> None:
        p = self._full_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def exists(self, path: str) -> bool:
        try:
            return self._full_path(path).exists()
        except ValueError:
            return False

    def delete(self, path: str) -> None:
        try:
            p = self._full_path(path)
            if p.is_file():
                p.unlink()
        except ValueError:
            pass


class S3StorageConnector:
    """S3 or MinIO via boto3. Same API; endpoint_url set for MinIO."""

    def __init__(
        self,
        bucket: str,
        region: str = "eu-west-2",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url or None
        self._access_key = access_key
        self._secret_key = secret_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config
            kwargs = {
                "service_name": "s3",
                "region_name": self._region,
                "config": Config(signature_version="s3v4"),
            }
            if self._endpoint_url:
                kwargs["endpoint_url"] = self._endpoint_url
            if self._access_key and self._secret_key:
                kwargs["aws_access_key_id"] = self._access_key
                kwargs["aws_secret_access_key"] = self._secret_key
            self._client = boto3.client(**kwargs)
        return self._client

    def _norm_key(self, path: str) -> str:
        return path.lstrip("/")

    def read_bytes(self, path: str) -> bytes:
        key = self._norm_key(path)
        try:
            resp = self._get_client().get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except Exception as e:
            try:
                err_code = e.response["Error"]["Code"]
            except (AttributeError, KeyError, TypeError):
                err_code = ""
            if err_code in ("404", "NoSuchKey"):
                raise FileNotFoundError(path) from e
            raise

    def write_bytes(self, path: str, data: bytes) -> None:
        key = self._norm_key(path)
        self._get_client().put_object(Bucket=self._bucket, Key=key, Body=data)

    def exists(self, path: str) -> bool:
        key = self._norm_key(path)
        try:
            self._get_client().head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception as e:
            try:
                if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    return False
            except (AttributeError, KeyError, TypeError):
                pass
            raise

    def delete(self, path: str) -> None:
        key = self._norm_key(path)
        self._get_client().delete_object(Bucket=self._bucket, Key=key)


def get_storage_connector() -> StorageConnector:
    """Return connector for configured backend (local | s3 | minio)."""
    settings = get_settings()
    backend = (settings.STORAGE_BACKEND or "local").lower()
    if backend == "local":
        return LocalStorageConnector(settings.STORAGE_LOCAL_PATH)
    if backend in ("s3", "minio"):
        return S3StorageConnector(
            bucket=settings.S3_BUCKET_NAME,
            region=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
        )
    raise ValueError(f"Unknown STORAGE_BACKEND: {settings.STORAGE_BACKEND}")
