"""DbClient.__init__の単体テスト."""

import pytest
from pytest_mock import MockerFixture

from db_client import DbClient
from db_client.exceptions import DsnNotConfiguredError


# 正常系
def test_init_with_dsn_uses_given_dsn(mocker: MockerFixture) -> None:
    """dsnを明示的に渡した場合はそのdsnでエンジンを生成する."""
    mock_create_engine = mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")

    DbClient(dsn="postgresql://user:pass@localhost:5432/test")

    mock_create_engine.assert_called_once_with("postgresql://user:pass@localhost:5432/test")


def test_init_without_dsn_uses_database_url_env(mocker: MockerFixture) -> None:
    """dsn省略時はDATABASE_URL環境変数を使用する."""
    mock_create_engine = mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")
    mocker.patch.dict("os.environ", {"DATABASE_URL": "postgresql://env:pass@localhost:5432/test"})

    DbClient()

    mock_create_engine.assert_called_once_with("postgresql://env:pass@localhost:5432/test")


def test_init_dsn_takes_priority_over_env(mocker: MockerFixture) -> None:
    """dsnとDATABASE_URLが両方ある場合はdsnを優先する."""
    mock_create_engine = mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")
    mocker.patch.dict("os.environ", {"DATABASE_URL": "postgresql://env:pass@localhost:5432/test"})

    DbClient(dsn="postgresql://explicit:pass@localhost:5432/test")

    mock_create_engine.assert_called_once_with("postgresql://explicit:pass@localhost:5432/test")


# 準正常系
def test_init_raises_when_neither_dsn_nor_env_is_set(mocker: MockerFixture) -> None:
    """dsnもDATABASE_URLも設定されていない場合はDsnNotConfiguredErrorを発生させる."""
    mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")
    mocker.patch.dict("os.environ", {}, clear=True)

    with pytest.raises(DsnNotConfiguredError):
        DbClient()
