import os
from typing import Any, IO, Optional, List, Tuple # List, Tuple might be used by MinioService
from io import BytesIO
from minio import Minio
from minio.error import S3Error
from mc import LoadBalancer # Use the installed package

from .base_storage_service import BaseStorageService
import logging

logger = logging.getLogger(__name__)

class MinioService(BaseStorageService):
    def __init__(self, bucket_name: Optional[str] = None) -> None:
        minio_endpoints_str = os.getenv("MINIO_ENDPOINTS")
        
        endpoints = []
        if minio_endpoints_str:
            endpoints = [ep.strip() for ep in minio_endpoints_str.split(',') if ep.strip()]
        
        if not endpoints:
            raise ValueError("MINIO_ENDPOINTS environment variable not set or empty. Please provide a comma-separated list of MinIO server addresses.")

        self.minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        self.minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        self.minio_secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.bucket_name = bucket_name if bucket_name else os.getenv("MINIO_BUCKET_NAME")
        self.local_store = os.getenv("LOCAL_STORE")

        if not self.bucket_name:
            raise ValueError("MINIO_BUCKET_NAME environment variable not set.")
       
        logger.info(f"Initializing MinioService with endpoints: {endpoints}")

        load_balancer_kwargs = {
            "endpoints": endpoints,
            "access_key": self.minio_access_key,
            "secret_key": self.minio_secret_key,
            "secure": self.minio_secure,
        }

        health_check_duration_str = os.getenv("MINIO_HEALTH_CHECK_DURATION")
        if health_check_duration_str is not None:
            try:
                health_check_seconds = int(health_check_duration_str)
                load_balancer_kwargs["health_check_timeout_seconds"] = health_check_seconds
                logger.info(f"Using MINIO_HEALTH_CHECK_DURATION: {health_check_seconds} seconds.")
            except ValueError:
                logger.warning(
                    f"Invalid value for MINIO_HEALTH_CHECK_DURATION: '{health_check_duration_str}'. "
                    f"LoadBalancer will use its default health check timeout."
                )
        else:
            logger.info("MINIO_HEALTH_CHECK_DURATION not set. LoadBalancer will use its default health check timeout.")

        self.load_balancer = LoadBalancer(**load_balancer_kwargs)

    @property
    def chosen_endpoint_for_url(self) -> str:
        """Returns the first configured endpoint, suitable for base URL construction."""
        if self.load_balancer.endpoints:
            # Strip http:// or https:// for consistent URL construction later
            endpoint = self.load_balancer.endpoints[0]
            return endpoint.replace("https://", "").replace("http://", "")
        # Fallback or raise error if no endpoints, though __init__ should prevent this
        raise ValueError("No MinIO endpoints configured for URL generation.")

    @property
    def is_secure_for_url(self) -> bool:
        """Returns the secure status used by the load balancer."""
        return self.load_balancer.secure

    def _get_active_client(self) -> Minio:
        """Helper method to get an active client from the load balancer."""
        _, client = self.load_balancer.get_client()
        if not client:
            # Consider a more specific exception or re-raising if get_client can raise one
            raise S3Error("No healthy MinIO server available.") 
        return client

    def ensure_folder_exists(self, folder_prefix: str) -> None:
        client = self._get_active_client()
        if not folder_prefix:
            return
        
        if not folder_prefix.endswith('/'):
            folder_prefix += '/'
        
        try:
            try:
                client.stat_object(self.bucket_name, folder_prefix)
                print(f"Folder {folder_prefix} already exists in bucket {self.bucket_name}.")
                return
            except S3Error as e:
                if e.code == "NoSuchKey":
                    pass 
                else:
                    raise 

            print(f"Creating folder {folder_prefix} in bucket {self.bucket_name}...")
            client.put_object(
                bucket_name=self.bucket_name,
                object_name=folder_prefix,
                data=BytesIO(b""), 
                length=0, 
                content_type="application/octet-stream" 
            )
            print(f"Folder {folder_prefix} created successfully in bucket {self.bucket_name}.")
        except S3Error as e:
            print(f"MinIO S3 Error during folder creation/check for {folder_prefix}: {e}")
            raise

    def upload_file(
        self,
        object_name: str,
        data: IO[Any],
        length: int,
        content_type: str | None = None,
    ) -> None:
        try:
            client = self._get_active_client()
            client.put_object(
                self.bucket_name,
                object_name,
                data,
                length,
                content_type=content_type,
            )
        except S3Error as e:
            print(f"MinIO S3 Error during upload: {e}")
            raise

    def download_file(
        self,
        object_name: str,
    ) -> IO[Any]:
        try:
            client = self._get_active_client()
            response = client.get_object(self.bucket_name, object_name)
            return response
        except S3Error as e:
            print(f"MinIO S3 Error during download: {e}")
            raise

    def delete_file(
        self,
        object_name: str,
    ) -> None:
        try:
            client = self._get_active_client()
            client.remove_object(self.bucket_name, object_name)
        except S3Error as e:
            print(f"MinIO S3 Error during delete: {e}")
            raise

    def list_files(
        self,
        prefix: str | None = None,
    ) -> list[str]:
        try:
            client = self._get_active_client()
            objects = client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            print(f"MinIO S3 Error during list: {e}")
            raise 