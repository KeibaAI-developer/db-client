"""deleteメソッドの単体テスト."""

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import Engine

from db_client import DbClient
from db_client.exceptions import EmptyWhereError


@pytest.fixture
def mock_engine(mocker: MockerFixture) -> Engine:
    """モック済みのSQLAlchemyエンジン."""
    return mocker.MagicMock(spec=Engine)


@pytest.fixture
def client(mocker: MockerFixture, mock_engine: Engine) -> DbClient:
    """モックエンジンを使用するDbClientインスタンス."""
    mocker.patch("db_client._client.create_engine", return_value=mock_engine)
    return DbClient(dsn="postgresql://user:pass@localhost:5432/test")


# 正常系
def test_delete_executes_delete_statement(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """whereが指定された場合にDELETE文を実行する."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter  # type: ignore[attr-defined]
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)  # type: ignore[attr-defined]  # noqa: E501

    client.delete(table_name="ratings", where={"race_code": "202301010101"})

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "DELETE FROM ratings" in sql_str
    assert "WHERE" in sql_str
    assert '"race_code"' in sql_str


def test_delete_with_multiple_conditions(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """複数のwhere条件がAND結合でSQL文に含まれる."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter  # type: ignore[attr-defined]
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)  # type: ignore[attr-defined]  # noqa: E501

    client.delete(
        table_name="ratings",
        where={"race_code": "202301010101", "uma_ban": 1},
    )

    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "AND" in sql_str


def test_delete_passes_params_to_execute(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """whereの値がexecuteのparamとして渡される."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter  # type: ignore[attr-defined]
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)  # type: ignore[attr-defined]  # noqa: E501

    client.delete(table_name="ratings", where={"race_code": "202301010101"})

    call_args = mock_conn.execute.call_args
    params = call_args[0][1]
    assert params == {"where_race_code": "202301010101"}


# 準正常系
def test_delete_raises_empty_where_error_when_where_is_empty(
    client: DbClient,
) -> None:
    """whereが空の場合にEmptyWhereErrorが発生する."""
    with pytest.raises(EmptyWhereError):
        client.delete(table_name="ratings", where={})
