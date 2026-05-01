"""select_latest_per_groupメソッドの単体テスト."""

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


def _setup_read_sql(
    mocker: MockerFixture, mock_engine: Engine, return_df: pd.DataFrame
) -> MockerFixture:
    """pd.read_sqlのモックをセットアップするヘルパー."""
    mock_conn = mocker.MagicMock()
    mock_engine.connect.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    return mocker.patch("db_client._client.pd.read_sql", return_value=return_df)


# 正常系
def test_select_latest_per_group_returns_dataframe(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """各グループの最新行を含むDataFrameを返す."""
    expected = pd.DataFrame(
        {"target_id": ["A", "B"], "race_code": ["2022020101", "2022010101"]}
    )
    _setup_read_sql(mocker, mock_engine, expected)

    result = client.select_latest_per_group(
        table_name="ratings", group_by="target_id", order_by="race_code"
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2


def test_select_latest_per_group_sql_contains_subquery(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """生成されるSQLに相関サブクエリが含まれる."""
    mock_read_sql = _setup_read_sql(mocker, mock_engine, pd.DataFrame())

    client.select_latest_per_group(
        table_name="ratings", group_by="target_id", order_by="race_code"
    )

    sql_str = str(mock_read_sql.call_args[0][0])
    assert "SELECT MAX" in sql_str
    assert '"race_code"' in sql_str
    assert '"target_id"' in sql_str


def test_select_latest_per_group_with_where_adds_where_clause(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """where条件が指定された場合にWHERE句が含まれる."""
    mock_read_sql = _setup_read_sql(mocker, mock_engine, pd.DataFrame())

    client.select_latest_per_group(
        table_name="ratings",
        group_by="target_id",
        order_by="race_code",
        where={"target": "horse"},
    )

    sql_str = str(mock_read_sql.call_args[0][0])
    assert "WHERE" in sql_str
    assert '"target"' in sql_str


def test_select_latest_per_group_where_applied_to_subquery(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """where条件が相関サブクエリ（t2）にも適用される."""
    mock_read_sql = _setup_read_sql(mocker, mock_engine, pd.DataFrame())

    client.select_latest_per_group(
        table_name="ratings",
        group_by="target_id",
        order_by="race_code",
        where={"target": "horse", "target_id": ["id_a", "id_b"]},
    )

    sql_str = str(mock_read_sql.call_args[0][0])
    # t1側とt2側の両方にwhere条件が含まれる
    assert sql_str.count('"target"') >= 2
    assert sql_str.count("IN") >= 2


def test_select_latest_per_group_with_list_where_generates_in_clause(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """where値がリストの場合にIN句が生成される."""
    mock_read_sql = _setup_read_sql(mocker, mock_engine, pd.DataFrame())

    client.select_latest_per_group(
        table_name="ratings",
        group_by="target_id",
        order_by="race_code",
        where={"target_id": ["id_a", "id_b"]},
    )

    sql_str = str(mock_read_sql.call_args[0][0])
    assert "IN" in sql_str


def test_select_latest_per_group_with_columns_uses_t1_alias(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """columns指定時にt1エイリアス付きのSELECT句が生成される."""
    mock_read_sql = _setup_read_sql(mocker, mock_engine, pd.DataFrame())

    client.select_latest_per_group(
        table_name="ratings",
        group_by="target_id",
        order_by="race_code",
        columns=["target_id", "race_code", "mu_after"],
    )

    sql_str = str(mock_read_sql.call_args[0][0])
    assert 't1."target_id"' in sql_str
    assert 't1."race_code"' in sql_str
    assert 't1."mu_after"' in sql_str


def test_select_latest_per_group_without_columns_uses_t1_asterisk(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """columns未指定時にt1.*が使われる."""
    mock_read_sql = _setup_read_sql(mocker, mock_engine, pd.DataFrame())

    client.select_latest_per_group(
        table_name="ratings", group_by="target_id", order_by="race_code"
    )

    sql_str = str(mock_read_sql.call_args[0][0])
    assert "t1.*" in sql_str


# 準正常系
def test_select_latest_per_group_returns_empty_when_no_data(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """該当レコードがない場合は空DataFrameを返す."""
    _setup_read_sql(mocker, mock_engine, pd.DataFrame())

    result = client.select_latest_per_group(
        table_name="ratings", group_by="target_id", order_by="race_code"
    )

    assert result.empty


def test_select_latest_per_group_raises_on_empty_columns(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """columnsが空リストの場合にValueErrorが発生する."""
    mocker.patch("db_client._client.load_dotenv")

    with pytest.raises(ValueError):
        client.select_latest_per_group(
            table_name="ratings",
            group_by="target_id",
            order_by="race_code",
            columns=[],
        )
