"""upsertメソッドの単体テスト."""

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
def test_upsert_executes_insert_on_conflict(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """DataFrameのレコードをINSERT ON CONFLICTで実行する."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    df = pd.DataFrame({"race_code": ["202301010101"], "uma_ban": [1], "rating": [1500.0]})
    client.upsert(table_name="ratings", df=df, primary_keys=["race_code", "uma_ban"])

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "INSERT INTO ratings" in sql_str
    assert "ON CONFLICT" in sql_str
    assert "DO UPDATE SET" in sql_str


def test_upsert_with_only_primary_keys_uses_do_nothing(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """非主キーカラムがない場合はDO NOTHINGを使う."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    df = pd.DataFrame({"race_code": ["202301010101"], "uma_ban": [1]})
    client.upsert(table_name="ratings", df=df, primary_keys=["race_code", "uma_ban"])

    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "DO NOTHING" in sql_str


def test_upsert_passes_records_to_execute(
    client: DbClient, mock_engine: Engine, mocker: MockerFixture
) -> None:
    """DataFrameのレコードをexecuteに渡す."""
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    df = pd.DataFrame({"race_code": ["202301010101", "202301010102"], "rating": [1500.0, 1600.0]})
    client.upsert(table_name="ratings", df=df, primary_keys=["race_code"])

    call_args = mock_conn.execute.call_args
    records = call_args[0][1]
    assert len(records) == 2
    assert records[0]["race_code"] == "202301010101"
    assert records[1]["race_code"] == "202301010102"


# 準正常系
def test_upsert_does_nothing_when_df_is_empty(client: DbClient, mock_engine: Engine) -> None:
    """dfが空の場合は何もしない."""
    df = pd.DataFrame(columns=["race_code", "rating"])
    client.upsert(table_name="ratings", df=df, primary_keys=["race_code"])

    mock_engine.begin.assert_not_called()
