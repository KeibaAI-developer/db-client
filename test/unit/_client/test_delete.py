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
    mocker.patch("db_client._client.load_dotenv")
    return DbClient(dsn="postgresql://user:pass@localhost:5432/test")


# 正常系
def test_delete_executes_delete_statement(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """whereが指定された場合にDELETE文を実行する."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

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
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

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
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.delete(table_name="ratings", where={"race_code": "202301010101"})

    call_args = mock_conn.execute.call_args
    params = call_args[0][1]
    assert params == {"where_race_code": "202301010101"}


def test_delete_with_in_condition(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """値がリストの場合にIN条件がSQL文に含まれ、paramsが正しく渡される."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.delete(
        table_name="ratings",
        where={"race_code": ["2022010101", "2022010102"]},
    )

    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "IN" in sql_str
    params = call_args[0][1]
    assert params == {"where_race_code_0": "2022010101", "where_race_code_1": "2022010102"}


def test_delete_with_range_condition_gte(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """値がdictでgteを含む場合に>=条件がSQL文に含まれ、paramsが正しく渡される."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.delete(
        table_name="ratings",
        where={"race_code": {"gte": "20220101"}},
    )

    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert ">=" in sql_str
    assert '"race_code"' in sql_str
    params = call_args[0][1]
    assert params == {"where_race_code_gte": "20220101"}


def test_delete_with_range_condition_lt(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """値がdictでltを含む場合に<条件がSQL文に含まれ、paramsが正しく渡される."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.delete(
        table_name="ratings",
        where={"race_code": {"lt": "20230101"}},
    )

    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "< " in sql_str
    assert '"race_code"' in sql_str
    params = call_args[0][1]
    assert params == {"where_race_code_lt": "20230101"}


def test_delete_with_range_and_eq_condition(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """範囲条件と等値条件を組み合わせた場合にAND結合でSQL文に含まれる."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.delete(
        table_name="ratings",
        where={"target": "horse", "race_code": {"gte": "20220101", "lt": "20230101"}},
    )

    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "AND" in sql_str
    assert ">=" in sql_str
    assert "< " in sql_str
    params = call_args[0][1]
    assert params["where_target"] == "horse"
    assert params["where_race_code_gte"] == "20220101"
    assert params["where_race_code_lt"] == "20230101"


# 準正常系
def test_delete_raises_empty_where_error_when_where_is_empty(
    client: DbClient,
) -> None:
    """whereが空の場合にEmptyWhereErrorが発生する."""
    with pytest.raises(EmptyWhereError):
        client.delete(table_name="ratings", where={})


def test_delete_raises_value_error_for_unknown_range_op(
    client: DbClient,
) -> None:
    """範囲条件のキーが不正な場合にValueErrorが発生する."""
    with pytest.raises(ValueError, match="範囲条件のキーが不正です"):
        client.delete(table_name="ratings", where={"race_code": {"eq": "20220101"}})


def test_delete_raises_value_error_for_empty_range_dict(
    client: DbClient,
) -> None:
    """範囲条件のdictが空の場合にValueErrorが発生する."""
    with pytest.raises(ValueError, match="範囲条件のdictが空です"):
        client.delete(table_name="ratings", where={"race_code": {}})
