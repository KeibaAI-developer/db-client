"""delete_allメソッドの単体テスト."""

from pytest_mock import MockerFixture
from sqlalchemy import Engine

from db_client import DbClient


def mock_client(mocker: MockerFixture) -> tuple[DbClient, Engine]:
    """モックエンジンを使用するDbClientインスタンスとエンジンを返す."""
    mock_engine = mocker.MagicMock(spec=Engine)
    mocker.patch("db_client._client.create_engine", return_value=mock_engine)
    mocker.patch("db_client._client.load_dotenv")
    client = DbClient(dsn="postgresql://user:pass@localhost:5432/test")
    return client, mock_engine


# 正常系
def test_delete_all_executes_delete_without_where(mocker: MockerFixture) -> None:
    """WHERE句なしのDELETE文を実行する."""
    client, mock_engine = mock_client(mocker)
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.delete_all(table_name="ratings")

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args
    sql_str = str(call_args[0][0])
    assert "DELETE FROM ratings" in sql_str
    assert "WHERE" not in sql_str


def test_delete_all_passes_no_params(mocker: MockerFixture) -> None:
    """パラメータなしでexecuteを呼び出す."""
    client, mock_engine = mock_client(mocker)
    mock_conn = mocker.MagicMock()
    enter = mocker.MagicMock(return_value=mock_conn)
    mock_engine.begin.return_value.__enter__ = enter
    mock_engine.begin.return_value.__exit__ = mocker.MagicMock(return_value=False)

    client.delete_all(table_name="ratings")

    call_args = mock_conn.execute.call_args
    assert len(call_args[0]) == 1  # SQLオブジェクトのみ、paramsなし
