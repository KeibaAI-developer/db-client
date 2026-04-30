"""DbClientクラスの実装.

PostgreSQLとのデータ入出力を行うDbClientクラスを提供する。
"""

import logging
import os
import re
from typing import Any, cast

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text

from db_client.exceptions import DsnNotConfiguredError, EmptyWhereError


class DbClient:
    """PostgreSQLとのデータ入出力を担うクライアント.

    接続プールを内部で保持し、DataFrameの読み書きを提供する。

    Attributes:
        _engine (Engine): SQLAlchemyエンジン（接続プール）
        _logger (logging.Logger): ロガーインスタンス
    """

    def __init__(self, dsn: str | None = None, logger: logging.Logger | None = None) -> None:
        """DbClientを初期化する.

        dsnを省略した場合は ``.env`` ファイルまたは環境変数 ``DATABASE_URL`` から接続文字列を読み込む。
        どちらも設定されていない場合は ``DsnNotConfiguredError`` を発生させる。

        Args:
            dsn (str | None): PostgreSQL接続文字列
                （例: ``postgresql://user:pass@host:5432/dbname``）。
                省略時は環境変数 ``DATABASE_URL`` を使用する
            logger (logging.Logger | None): ロガーインスタンス。
                Noneの場合はモジュール名でロガーを生成する

        Raises:
            DsnNotConfiguredError: dsn および DATABASE_URL のどちらも設定されていない場合
        """
        self._logger = logger or logging.getLogger(__name__)
        load_dotenv()
        resolved_dsn = dsn or os.environ.get("DATABASE_URL")
        if not resolved_dsn:
            msg = "dsn または環境変数 DATABASE_URL を設定してください。"
            self._logger.error(msg)
            raise DsnNotConfiguredError(msg)
        self._engine: Engine = create_engine(resolved_dsn)

    def _validate_table_name(self, table_name: str) -> None:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
            msg = f"無効なテーブル名です: {table_name!r}"
            self._logger.error(msg)
            raise ValueError(msg)

    def upsert(self, table_name: str, df: pd.DataFrame, primary_keys: list[str]) -> None:
        """DataFrameを指定テーブルにupsertする.

        主キーが一致するレコードが既存の場合、非主キーカラムを上書きする。
        dfが空の場合は何もしない。

        Args:
            table_name (str): 対象テーブル名
            df (pd.DataFrame): 保存するDataFrame。カラム名がDBカラム名にマッピングされる
            primary_keys (list[str]): 重複判定に使用する主キーカラム名のリスト

        Raises:
            ValueError: table_nameが無効、primary_keysが空、またはprimary_keysにdf.columnsに
                存在しないキーが含まれる場合
        """
        self._validate_table_name(table_name)

        if not primary_keys:
            msg = "primary_keysが空です。"
            self._logger.error(msg)
            raise ValueError(msg)

        unknown_keys = set(primary_keys) - set(df.columns)
        if unknown_keys:
            msg = f"primary_keysにdf.columnsに存在しないキーが含まれています: {unknown_keys}"
            self._logger.error(msg)
            raise ValueError(msg)

        if df.empty:
            self._logger.debug("upsert: dfが空のため何もしません (table=%s)", table_name)
            return

        columns = list(df.columns)
        non_pk_columns = [col for col in columns if col not in primary_keys]

        col_list = ", ".join(f'"{col}"' for col in columns)
        placeholder_list = ", ".join(f":{col}" for col in columns)
        pk_conflict = ", ".join(f'"{pk}"' for pk in primary_keys)

        if non_pk_columns:
            update_clause = ", ".join(f'"{col}" = EXCLUDED."{col}"' for col in non_pk_columns)
            on_conflict = f"DO UPDATE SET {update_clause}"
        else:
            on_conflict = "DO NOTHING"

        sql = text(
            f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholder_list}) "
            f"ON CONFLICT ({pk_conflict}) {on_conflict}"
        )

        records = cast(list[dict[str, Any]], df.to_dict(orient="records"))
        self._logger.debug("upsert: %d件をupsertします (table=%s)", len(records), table_name)
        with self._engine.begin() as conn:
            conn.execute(sql, records)
        self._logger.info("upsert: %d件をupsertしました (table=%s)", len(records), table_name)

    def select(
        self,
        table_name: str,
        where: dict[str, Any] | None = None,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """指定テーブルからDataFrameを取得する.

        Args:
            table_name (str): 対象テーブル名
            where (dict[str, Any] | None): フィルタ条件。``{カラム名: 値}`` 形式で指定する
                （AND結合）。Noneの場合は全件取得
            columns (list[str] | None): 取得するカラム名のリスト。Noneの場合は全カラムを取得

        Returns:
            pd.DataFrame: 取得したDataFrame。該当レコードが存在しない場合は空のDataFrameを返す

        Raises:
            ValueError: table_nameが無効、またはcolumnsが空リストの場合
        """
        self._validate_table_name(table_name)

        if columns is not None and len(columns) == 0:
            msg = "columnsが空リストです。カラムを指定するか、Noneを指定してください。"
            self._logger.error(msg)
            raise ValueError(msg)

        col_clause = ", ".join(f'"{col}"' for col in columns) if columns is not None else "*"

        query = f"SELECT {col_clause} FROM {table_name}"
        params: dict[str, Any] = {}

        if where:
            conditions = " AND ".join(f'"{key}" = :where_{key}' for key in where)
            query += f" WHERE {conditions}"
            params = {f"where_{key}": val for key, val in where.items()}

        self._logger.debug("select: クエリを実行します (table=%s, where=%s)", table_name, where)
        with self._engine.connect() as conn:
            result = pd.read_sql(text(query), conn, params=params)
        self._logger.info("select: %d件取得しました (table=%s)", len(result), table_name)

        return result

    def delete(self, table_name: str, where: dict[str, Any]) -> None:
        """指定条件のレコードを削除する.

        Args:
            table_name (str): 対象テーブル名
            where (dict[str, Any]): 削除条件。``{カラム名: 値}`` 形式で指定する（AND結合）

        Raises:
            EmptyWhereError: where が空の場合（全件削除の誤操作を防ぐ）
        """
        self._validate_table_name(table_name)

        if not where:
            msg = "where条件が空です。全件削除を防ぐため、必ず条件を指定してください。"
            self._logger.error(msg)
            raise EmptyWhereError(msg)

        conditions = " AND ".join(f'"{key}" = :where_{key}' for key in where)
        params = {f"where_{key}": val for key, val in where.items()}
        sql = text(f"DELETE FROM {table_name} WHERE {conditions}")

        self._logger.debug("delete: レコードを削除します (table=%s, where=%s)", table_name, where)
        with self._engine.begin() as conn:
            conn.execute(sql, params)
        self._logger.info("delete: レコードを削除しました (table=%s, where=%s)", table_name, where)

    def delete_all(self, table_name: str) -> None:
        """指定テーブルの全レコードを削除する.

        全件削除を明示的に行うための専用メソッド。
        誤操作防止のため ``delete`` メソッドとは分離している。

        Args:
            table_name (str): 対象テーブル名
        """
        self._validate_table_name(table_name)

        sql = text(f"DELETE FROM {table_name}")

        self._logger.debug("delete_all: 全レコードを削除します (table=%s)", table_name)
        with self._engine.begin() as conn:
            conn.execute(sql)
        self._logger.info("delete_all: 全レコードを削除しました (table=%s)", table_name)
