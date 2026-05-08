"""setup_tableメソッドの単体テスト."""

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import Engine

from db_client import DbClient

_SINGLE_DDL = "CREATE TABLE IF NOT EXISTS test_table (id SERIAL PRIMARY KEY, name VARCHAR(100))"

_MULTI_DDL = """
CREATE TABLE IF NOT EXISTS test_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS test_table_name ON test_table (name);
"""


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
def test_setup_table_executes_single_ddl(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """単一SQL文のDDLがconn.executeで1回実行される."""
    mock_conn = mocker.MagicMock()
    mock_engine.begin.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.setup_table(_SINGLE_DDL)

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "CREATE TABLE IF NOT EXISTS test_table" in sql_str


def test_setup_table_executes_multi_ddl_as_separate_statements(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """複数SQL文のDDLがそれぞれ個別のconn.executeで実行される."""
    mock_conn = mocker.MagicMock()
    mock_engine.begin.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.setup_table(_MULTI_DDL)

    assert mock_conn.execute.call_count == 2
    all_sql = " ".join(str(call[0][0]) for call in mock_conn.execute.call_args_list)
    assert "CREATE TABLE IF NOT EXISTS test_table" in all_sql
    assert "CREATE INDEX IF NOT EXISTS test_table_name" in all_sql


def test_setup_table_uses_transaction(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """トランザクション（engine.begin）を使用する."""
    mock_conn = mocker.MagicMock()
    mock_engine.begin.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.setup_table(_SINGLE_DDL)

    mock_engine.begin.assert_called_once()


def test_setup_table_multi_ddl_uses_single_transaction(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """複数SQL文のDDLでも1つのトランザクション内で実行される."""
    mock_conn = mocker.MagicMock()
    mock_engine.begin.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.setup_table(_MULTI_DDL)

    mock_engine.begin.assert_called_once()
