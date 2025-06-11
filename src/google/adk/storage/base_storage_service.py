from abc import ABC, abstractmethod
from typing import Any, IO

class BaseStorageService(ABC):
    @abstractmethod
    def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        data: IO[Any],
        length: int,
        content_type: str | None = None,
    ) -> None:
        pass

    @abstractmethod
    def download_file(
        self,
        bucket_name: str,
        object_name: str,
    ) -> IO[Any]:
        pass

    @abstractmethod
    def delete_file(
        self,
        bucket_name: str,
        object_name: str,
    ) -> None:
        pass

    @abstractmethod
    def list_files(
        self,
        bucket_name: str,
        prefix: str | None = None,
    ) -> list[str]:
        pass 