import os
import uuid
import mimetypes
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from app.config import settings

logger = logging.getLogger("brandproof.storage")


class StorageError(Exception):
    """Raised when an object storage operation fails."""
    pass


class StorageBackend(ABC):
    """Abstract base class for BrandProof storage backends."""

    @abstractmethod
    def save_file(self, file_data: bytes, filename: str, content_type: Optional[str] = None) -> Tuple[str, int]:
        """Save a file and return (stored_key, file_size_bytes)."""
        pass

    @abstractmethod
    def get_file(self, file_key: str) -> Optional[bytes]:
        """Retrieve file bytes by key."""
        pass

    @abstractmethod
    def delete_file(self, file_key: str) -> bool:
        """Delete file by key."""
        pass

    @abstractmethod
    def get_file_path(self, file_key: str) -> Optional[str]:
        """Get local filesystem path if available, or None if remote."""
        pass

    @abstractmethod
    def exists(self, file_key: str) -> bool:
        """Check if file exists in storage."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage implementation for development & testing."""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or settings.STORAGE_DIR)
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve_path(self, file_key: str) -> str:
        # Prevent directory traversal attacks
        safe_key = os.path.basename(file_key)
        return os.path.join(self.base_dir, safe_key)

    def save_file(self, file_data: bytes, filename: str, content_type: Optional[str] = None) -> Tuple[str, int]:
        ext = os.path.splitext(filename)[1].lower()
        unique_key = f"{uuid.uuid4().hex}{ext}"
        target_path = os.path.join(self.base_dir, unique_key)

        try:
            with open(target_path, "wb") as f:
                f.write(file_data)
        except OSError as e:
            raise StorageError(f"Failed to write local file: {str(e)}")

        return unique_key, len(file_data)

    def get_file(self, file_key: str) -> Optional[bytes]:
        target_path = self._resolve_path(file_key)
        if not os.path.isfile(target_path):
            return None
        try:
            with open(target_path, "rb") as f:
                return f.read()
        except OSError as e:
            raise StorageError(f"Failed to read local file: {str(e)}")

    def delete_file(self, file_key: str) -> bool:
        target_path = self._resolve_path(file_key)
        if os.path.isfile(target_path):
            try:
                os.remove(target_path)
                return True
            except OSError as e:
                raise StorageError(f"Failed to delete local file: {str(e)}")
        return False

    def get_file_path(self, file_key: str) -> Optional[str]:
        target_path = self._resolve_path(file_key)
        if os.path.isfile(target_path):
            return target_path
        return None

    def exists(self, file_key: str) -> bool:
        target_path = self._resolve_path(file_key)
        return os.path.isfile(target_path)


class S3CompatibleStorageBackend(StorageBackend):
    """
    Production S3 storage adapter compatible with AWS S3, Cloudflare R2, MinIO,
    and Render object storage.
    Enforces real uploads, downloads, deletions, correct content-type handling,
    and fails safely if credentials are not configured.
    """

    def __init__(self):
        self.endpoint_url = settings.S3_ENDPOINT_URL.strip() or None
        self.bucket = settings.S3_BUCKET_NAME.strip()
        self.access_key = settings.S3_ACCESS_KEY.strip()
        self.secret_key = settings.S3_SECRET_KEY.strip()
        self.region = settings.S3_REGION.strip() or "us-east-1"
        self._s3_client = None

    def _get_client(self):
        if self._s3_client is not None:
            return self._s3_client

        if not self.access_key or not self.secret_key:
            raise StorageError(
                "S3 storage credentials not configured. In production, set S3_ACCESS_KEY, "
                "S3_SECRET_KEY, and S3_BUCKET_NAME environment variables."
            )

        try:
            import boto3
            from botocore.config import Config

            session = boto3.session.Session()
            client_kwargs = {
                "service_name": "s3",
                "aws_access_key_id": self.access_key,
                "aws_secret_access_key": self.secret_key,
                "region_name": self.region,
            }
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url
                client_kwargs["config"] = Config(signature_version="s3v4", s3={"addressing_style": "path"})
            else:
                client_kwargs["config"] = Config(signature_version="s3v4")

            self._s3_client = session.client(**client_kwargs)
            return self._s3_client
        except ImportError:
            raise StorageError("boto3 package is required for S3CompatibleStorageBackend. Please install boto3.")
        except Exception as e:
            raise StorageError(f"Failed to initialize S3 client: {str(e)}")

    def save_file(self, file_data: bytes, filename: str, content_type: Optional[str] = None) -> Tuple[str, int]:
        client = self._get_client()
        ext = os.path.splitext(filename)[1].lower()
        unique_key = f"documents/{uuid.uuid4().hex}{ext}"

        ct = content_type
        if not ct:
            ct = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        try:
            client.put_object(
                Bucket=self.bucket,
                Key=unique_key,
                Body=file_data,
                ContentType=ct,
                Metadata={"original_filename": filename[:100]},
            )
            return unique_key, len(file_data)
        except Exception as e:
            logger.error(f"S3 put_object failed for key '{unique_key}': {str(e)}")
            raise StorageError(f"Failed to upload document to S3 object storage: {str(e)}")

    def get_file(self, file_key: str) -> Optional[bytes]:
        client = self._get_client()
        from botocore.exceptions import ClientError

        try:
            response = client.get_object(Bucket=self.bucket, Key=file_key)
            return response["Body"].read()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ["NoSuchKey", "404", "NotFound"]:
                return None
            logger.error(f"S3 get_object failed for key '{file_key}': {str(e)}")
            raise StorageError(f"Failed to retrieve document from S3 object storage: {str(e)}")
        except Exception as e:
            logger.error(f"S3 get_object unexpected error for key '{file_key}': {str(e)}")
            raise StorageError(f"Failed to read file from S3: {str(e)}")

    def delete_file(self, file_key: str) -> bool:
        client = self._get_client()
        from botocore.exceptions import ClientError

        try:
            client.delete_object(Bucket=self.bucket, Key=file_key)
            return True
        except ClientError as e:
            logger.error(f"S3 delete_object failed for key '{file_key}': {str(e)}")
            raise StorageError(f"Failed to delete document from S3 object storage: {str(e)}")
        except Exception as e:
            logger.error(f"S3 delete_object unexpected error for key '{file_key}': {str(e)}")
            raise StorageError(f"Failed to delete file from S3: {str(e)}")

    def get_file_path(self, file_key: str) -> Optional[str]:
        # S3 storage is remote, no local path
        return None

    def exists(self, file_key: str) -> bool:
        client = self._get_client()
        from botocore.exceptions import ClientError
        try:
            client.head_object(Bucket=self.bucket, Key=file_key)
            return True
        except Exception:
            return False


def get_storage() -> StorageBackend:
    if settings.STORAGE_BACKEND.lower() == "s3":
        return S3CompatibleStorageBackend()
    return LocalStorageBackend()
