"""drop_tableメソッドの単体テスト."""

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import Engine

from db_client import DbClient


@pytest.fixture
def mock_engine(mocker: MockerFixture) -> Engine:
    """モック済みのSQLAlchemyエンジン."""
    return mocker.MagicMock(spec=Engine)


@pytest.fixture
def client(mocker: MockerFixture, mock_engine: Engine) -> DbClient:
    """モックエンジンを使用するDbClientインスタンス."""
    mocker.patch("db_client._client.create_engine", return_value=mock_engine)
    mocker.patch("db_client._client.load_dotenv")
    return DbClient(dsn="postgresql://user:pass@localhost:5432/test")


# 正常系
def test_drop_table_executes_drop_statement(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """DROP TABLE IF EXISTS文がconn.executeで実行される."""
    mock_conn = mocker.MagicMock()
    mock_engine.begin.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.drop_table("ratings")

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "DROP TABLE IF EXISTS ratings" in sql_str


def test_drop_table_uses_transaction(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """トランザクション（engine.begin）を使用する."""
    mock_conn = mocker.MagicMock()
    mock_engine.begin.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.drop_table("ratings")

    mock_engine.begin.assert_called_once()


def test_drop_table_includes_table_name_in_sql(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """指定したテーブル名がSQL文に含まれる."""
    mock_conn = mocker.MagicMock()
    mock_engine.begin.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.drop_table("suitabilities")

    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "suitabilities" in sql_str


# 準正常系
def test_drop_table_raises_on_invalid_table_name(client: DbClient) -> None:
    """無効なテーブル名でValueErrorが発生する."""
    with pytest.raises(ValueError):
        client.drop_table("invalid-table-name!")


def test_drop_table_raises_on_empty_table_name(client: DbClient) -> None:
    """空文字のテーブル名でValueErrorが発生する."""
    with pytest.raises(ValueError):
        client.drop_table("")
