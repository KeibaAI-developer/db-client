"""selectメソッドの単体テスト."""

import pandas as pd
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
def test_select_returns_dataframe(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """レコードが存在する場合にDataFrameを返す."""
    expected = pd.DataFrame({"race_code": ["202301010101"], "rating": [1500.0]})
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__enter__ = enter
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("db_client._client.pd.read_sql", return_value=expected)

    result = client.select(table_name="ratings")

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result["race_code"].iloc[0] == "202301010101"


def test_select_with_where_condition(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """where条件が指定された場合にSQLにWHERE句が含まれる."""
    expected = pd.DataFrame({"race_code": ["202301010101"], "rating": [1500.0]})
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__enter__ = enter
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mock_read_sql = mocker.patch("db_client._client.pd.read_sql", return_value=expected)

    client.select(table_name="ratings", where={"race_code": "202301010101"})

    call_args = mock_read_sql.call_args
    sql_str = str(call_args[0][0])
    assert "WHERE" in sql_str
    assert '"race_code"' in sql_str


def test_select_with_columns(client: DbClient, mock_engine: Engine, mocker: MockerFixture) -> None:
    """columns指定時にSELECT句に指定カラムが含まれる."""
    expected = pd.DataFrame({"race_code": ["202301010101"]})
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__enter__ = enter
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mock_read_sql = mocker.patch("db_client._client.pd.read_sql", return_value=expected)

    client.select(table_name="ratings", columns=["race_code"])

    call_args = mock_read_sql.call_args
    sql_str = str(call_args[0][0])
    assert '"race_code"' in sql_str
    assert "*" not in sql_str


def test_select_without_where_uses_asterisk(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """where未指定時にSELECT *を使う."""
    expected = pd.DataFrame()
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__enter__ = enter
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mock_read_sql = mocker.patch("db_client._client.pd.read_sql", return_value=expected)

    client.select(table_name="ratings")

    call_args = mock_read_sql.call_args
    sql_str = str(call_args[0][0])
    assert "SELECT *" in sql_str
    assert "WHERE" not in sql_str


def test_select_with_list_where_generates_in_clause(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """whereの値がリストの場合にIN句が生成される."""
    expected = pd.DataFrame({"target_id": ["a", "b"]})
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__enter__ = enter
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mock_read_sql = mocker.patch("db_client._client.pd.read_sql", return_value=expected)

    client.select(table_name="ratings", where={"target_id": ["a", "b"]})

    call_args = mock_read_sql.call_args
    sql_str = str(call_args[0][0])
    assert "IN" in sql_str
    assert '"target_id"' in sql_str


def test_select_with_list_where_passes_all_values_as_params(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """whereのリスト値が個別パラメータとしてSQLに渡される."""
    expected = pd.DataFrame()
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__enter__ = enter
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mock_read_sql = mocker.patch("db_client._client.pd.read_sql", return_value=expected)

    client.select(table_name="ratings", where={"target_id": ["horse_a", "horse_b", "horse_c"]})

    call_args = mock_read_sql.call_args
    params = call_args[1]["params"]
    assert params["where_target_id_0"] == "horse_a"
    assert params["where_target_id_1"] == "horse_b"
    assert params["where_target_id_2"] == "horse_c"


def test_select_with_mixed_where_combines_eq_and_in(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """whereにスカラーとリストが混在する場合、等値条件とIN条件がAND結合される."""
    expected = pd.DataFrame()
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__enter__ = enter
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mock_read_sql = mocker.patch("db_client._client.pd.read_sql", return_value=expected)

    client.select(
        table_name="ratings",
        where={"target": "horse", "target_id": ["id_a", "id_b"]},
    )

    call_args = mock_read_sql.call_args
    sql_str = str(call_args[0][0])
    assert "IN" in sql_str
    assert '"target"' in sql_str
    assert '"target_id"' in sql_str


def test_select_with_empty_list_raises_value_error(client: DbClient) -> None:
    """whereの値が空リストの場合にValueErrorが発生する."""
    with pytest.raises(ValueError, match="リストが空"):
        client.select(table_name="ratings", where={"target_id": []})


# 準正常系
def test_select_returns_empty_dataframe_when_no_records(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """該当レコードが存在しない場合は空のDataFrameを返す."""
    empty_df = pd.DataFrame()
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__enter__ = enter
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    mocker.patch("db_client._client.pd.read_sql", return_value=empty_df)

    result = client.select(table_name="ratings", where={"race_code": "nonexistent"})

    assert isinstance(result, pd.DataFrame)
    assert result.empty
