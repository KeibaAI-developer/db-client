"""DbClient.__init__の単体テスト."""

import pytest
from pytest_mock import MockerFixture

from db_client import DbClient
from db_client.exceptions import DsnNotConfiguredError

_ENV_VARS = {
    "DB_HOST": "host.docker.internal",
    "DB_PORT": "5432",
    "DB_NAME": "keibaai",
    "DB_USER": "postgres",
    "DB_PASSWORD": "postgres",
}


# 正常系
def test_init_with_dsn_uses_given_dsn(mocker: MockerFixture) -> None:
    """dsnを明示的に渡した場合はそのdsnでエンジンを生成する."""
    mock_create_engine = mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")

    DbClient(dsn="postgresql://user:pass@localhost:5432/test")

    mock_create_engine.assert_called_once_with("postgresql://user:pass@localhost:5432/test")


def test_init_without_dsn_uses_env_vars(mocker: MockerFixture) -> None:
    """dsn省略時は個別環境変数からDSNを構築する."""
    mock_create_engine = mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")
    mocker.patch.dict("os.environ", _ENV_VARS)

    DbClient()

    expected_dsn = "postgresql://postgres:postgres@host.docker.internal:5432/keibaai"
    mock_create_engine.assert_called_once_with(expected_dsn)


def test_init_dsn_takes_priority_over_env(mocker: MockerFixture) -> None:
    """dsnと個別環境変数が両方ある場合はdsnを優先する."""
    mock_create_engine = mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")
    mocker.patch.dict("os.environ", _ENV_VARS)

    DbClient(dsn="postgresql://explicit:pass@localhost:5432/test")

    mock_create_engine.assert_called_once_with("postgresql://explicit:pass@localhost:5432/test")


def test_init_default_port_is_5432(mocker: MockerFixture) -> None:
    """DB_PORTが未設定の場合はデフォルト5432を使用する."""
    mock_create_engine = mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")
    env_without_port = {k: v for k, v in _ENV_VARS.items() if k != "DB_PORT"}
    mocker.patch.dict("os.environ", env_without_port, clear=True)

    DbClient()

    expected_dsn = "postgresql://postgres:postgres@host.docker.internal:5432/keibaai"
    mock_create_engine.assert_called_once_with(expected_dsn)


# 準正常系
def test_init_raises_when_env_vars_missing(mocker: MockerFixture) -> None:
    """必要な環境変数が不足している場合はDsnNotConfiguredErrorを発生させる."""
    mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")
    mocker.patch.dict("os.environ", {}, clear=True)

    with pytest.raises(DsnNotConfiguredError):
        DbClient()


def test_init_raises_when_db_host_missing(mocker: MockerFixture) -> None:
    """DB_HOSTが未設定の場合はDsnNotConfiguredErrorを発生させる."""
    mocker.patch("db_client._client.create_engine")
    mocker.patch("db_client._client.load_dotenv")
    env_without_host = {k: v for k, v in _ENV_VARS.items() if k != "DB_HOST"}
    mocker.patch.dict("os.environ", env_without_host, clear=True)

    with pytest.raises(DsnNotConfiguredError):
        DbClient()
