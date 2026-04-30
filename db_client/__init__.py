"""db-client: PostgreSQLとのデータ入出力を担う汎用ライブラリ."""

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("db-client")
except (PackageNotFoundError, ImportError):
    __version__ = "unknown"

from db_client._client import DbClient
from db_client.exceptions import DbClientError, DsnNotConfiguredError, EmptyWhereError

__all__ = ["DbClient", "DbClientError", "DsnNotConfiguredError", "EmptyWhereError"]
