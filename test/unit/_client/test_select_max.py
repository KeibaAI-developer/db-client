"""select_maxメソッドの単体テスト."""

from typing import Any

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


def _setup_read_sql(mocker: MockerFixture, mock_engine: Engine, return_df: pd.DataFrame) -> Any:
    """pd.read_sqlのモックをセットアップするヘルパー."""
    mock_conn = mocker.MagicMock()
    mock_engine.connect.return_value.__enter__ = mocker.MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = mocker.MagicMock(return_value=False)
    return mocker.patch("db_client._client.pd.read_sql", return_value=return_df)


# 正常系
def test_select_max_returns_max_value(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """最大値が存在する場合にその値を返す."""
    _setup_read_sql(mocker, mock_engine, pd.DataFrame({"max_val": ["2022123112120112"]}))

    result = client.select_max(table_name="ratings", column="race_code")

    assert result == "2022123112120112"


def test_select_max_returns_none_when_no_records(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """レコードが存在しない場合（MAX結果がNULL）にNoneを返す."""
    _setup_read_sql(mocker, mock_engine, pd.DataFrame({"max_val": [None]}))

    result = client.select_max(table_name="ratings", column="race_code")

    assert result is None


def test_select_max_sql_contains_max_function(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """生成されるSQLにMAX関数と指定カラムが含まれる."""
    mock_read_sql = _setup_read_sql(
        mocker, mock_engine, pd.DataFrame({"max_val": ["2022010101010101"]})
    )

    client.select_max(table_name="ratings", column="race_code")

    sql_str = str(mock_read_sql.call_args[0][0])
    assert 'MAX("race_code")' in sql_str
    assert "FROM ratings" in sql_str


def test_select_max_with_where_adds_where_clause(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """where条件が指定された場合にWHERE句が含まれる."""
    mock_read_sql = _setup_read_sql(
        mocker, mock_engine, pd.DataFrame({"max_val": ["2022010101010101"]})
    )

    client.select_max(table_name="ratings", column="race_code", where={"target": "horse"})

    sql_str = str(mock_read_sql.call_args[0][0])
    assert "WHERE" in sql_str
    assert '"target"' in sql_str


def test_select_max_without_where_has_no_where_clause(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """where未指定時にWHERE句が含まれない."""
    mock_read_sql = _setup_read_sql(
        mocker, mock_engine, pd.DataFrame({"max_val": ["2022010101010101"]})
    )

    client.select_max(table_name="ratings", column="race_code")

    sql_str = str(mock_read_sql.call_args[0][0])
    assert "WHERE" not in sql_str


def test_select_max_passes_where_params(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """whereのバインドパラメータがread_sqlに渡される."""
    mock_read_sql = _setup_read_sql(
        mocker, mock_engine, pd.DataFrame({"max_val": ["2022010101010101"]})
    )

    client.select_max(table_name="ratings", column="race_code", where={"target": "horse"})

    call_params = mock_read_sql.call_args[1].get("params") or mock_read_sql.call_args[0][2]
    assert call_params.get("where_target") == "horse"


# 準正常系
def test_select_max_raises_on_invalid_table_name(client: DbClient, mocker: MockerFixture) -> None:
    """無効なテーブル名を指定した場合にValueErrorを発生させる."""
    with pytest.raises(ValueError, match="無効なテーブル名"):
        client.select_max(table_name="invalid-table!", column="race_code")


def test_select_max_raises_on_invalid_column_name(client: DbClient, mocker: MockerFixture) -> None:
    """無効なカラム名を指定した場合にValueErrorを発生させる."""
    with pytest.raises(ValueError, match="無効なカラム名"):
        client.select_max(table_name="ratings", column='invalid"; DROP TABLE ratings; --')
