"""Public wrapper for data access."""

from public.access_handler import AccessHandler, DataSourceError

# 旧社内DB実装を公開版のCSVデータソース実装へ委譲。
__all__ = ["AccessHandler", "DataSourceError"]

