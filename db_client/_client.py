"""DbClientクラスの実装.

PostgreSQLとのデータ入出力を行うDbClientクラスを提供する。
"""

import logging
import os
import re
from typing import Any, cast
from urllib.parse import quote_plus

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text

from db_client.exceptions import DsnNotConfiguredError, EmptyWhereError

_RANGE_OPS: dict[str, str] = {"gte": ">=", "lte": "<=", "gt": ">", "lt": "<"}


class DbClient:
    """PostgreSQLとのデータ入出力を担うクライアント.

    接続プールを内部で保持し、DataFrameの読み書きを提供する。

    Attributes:
        _engine (Engine): SQLAlchemyエンジン（接続プール）
        _logger (logging.Logger): ロガーインスタンス
    """

    def __init__(self, dsn: str | None = None, logger: logging.Logger | None = None) -> None:
        """DbClientを初期化する.

        dsnを省略した場合は ``.env`` ファイルまたは環境変数
        ``DB_HOST`` / ``DB_PORT`` / ``DB_NAME`` / ``DB_USER`` / ``DB_PASSWORD``
        から接続文字列を構築する。解決できない場合は ``DsnNotConfiguredError`` を発生させる。

        Args:
            dsn (str | None): PostgreSQL接続文字列
                （例: ``postgresql://user:pass@host:5432/dbname``）。
                省略時は環境変数から構築する
            logger (logging.Logger | None): ロガーインスタンス。
                Noneの場合はモジュール名でロガーを生成する

        Raises:
            DsnNotConfiguredError: dsnが未指定かつ必要な環境変数が不足している場合
        """
        self._logger = logger or logging.getLogger(__name__)
        load_dotenv()
        resolved_dsn = dsn or self._build_dsn_from_env()
        if not resolved_dsn:
            msg = "dsn または DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD を設定してください。"
            self._logger.error(msg)
            raise DsnNotConfiguredError(msg)
        self._engine: Engine = create_engine(resolved_dsn)

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
        self._logger.debug("upsert: %d件をupsertしました (table=%s)", len(records), table_name)

    def select(
        self,
        table_name: str,
        where: dict[str, Any] | None = None,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """指定テーブルからDataFrameを取得する.

        Args:
            table_name (str): 対象テーブル名
            where (dict[str, Any] | None): フィルタ条件（AND結合）。Noneの場合は全件取得。
                値がリストの場合はIN条件（``{カラム名: [値1, 値2, ...]}``）、
                それ以外は等値条件（``{カラム名: 値}``）として扱う
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

        where_sql, params = self._build_where_clause(where)
        query = f"SELECT {col_clause} FROM {table_name}"
        if where_sql:
            query += f" WHERE {where_sql}"

        self._logger.debug("select: クエリを実行します (table=%s, where=%s)", table_name, where)
        with self._engine.connect() as conn:
            result = pd.read_sql(text(query), conn, params=params)
        self._logger.debug("select: %d件取得しました (table=%s)", len(result), table_name)

        return result

    def select_max(
        self,
        table_name: str,
        column: str,
        where: dict[str, Any] | None = None,
    ) -> Any:
        """指定カラムの最大値を返す.

        データが存在しない場合はNoneを返す。

        Args:
            table_name (str): 対象テーブル名
            column (str): 最大値を取得するカラム名
            where (dict[str, Any] | None): フィルタ条件（selectと同じ書式）

        Returns:
            Any: 指定カラムの最大値。該当レコードが存在しない場合はNone

        Raises:
            ValueError: table_nameが無効な場合
        """
        self._validate_table_name(table_name)
        self._validate_column_name(column)

        where_sql, params = self._build_where_clause(where)
        query = f'SELECT MAX("{column}") AS max_val FROM {table_name}'
        if where_sql:
            query += f" WHERE {where_sql}"

        self._logger.debug(
            "select_max: クエリを実行します (table=%s, column=%s, where=%s)",
            table_name,
            column,
            where,
        )
        with self._engine.connect() as conn:
            result = pd.read_sql(text(query), conn, params=params)
        max_val = result["max_val"].iloc[0]
        self._logger.debug(
            "select_max: 最大値=%s (table=%s, column=%s)", max_val, table_name, column
        )
        return None if pd.isna(max_val) else max_val

    def select_latest_per_group(
        self,
        table_name: str,
        group_by: str,
        order_by: str,
        where: dict[str, Any] | None = None,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """各グループの最大order_byカラム値を持つ行をすべて取得する.

        group_byカラムでグループ化し、各グループ内でorder_byが最大の行を
        すべて返す。同一グループ・同一order_by値の行が複数ある場合
        （例: 同一レースで調教師の複数頭出走）はすべて返す。

        Args:
            table_name (str): 対象テーブル名
            group_by (str): グループ化するカラム名（例: ``"target_id"``）
            order_by (str): 最大値を基準にするカラム名（例: ``"race_code"``）
            where (dict[str, Any] | None): フィルタ条件（selectと同じ書式）
            columns (list[str] | None): 取得するカラム名のリスト。Noneの場合は全カラムを取得

        Returns:
            pd.DataFrame: 各グループの最大order_by値を持つ全行のDataFrame

        Raises:
            ValueError: table_nameが無効、またはcolumnsが空リストの場合
        """
        self._validate_table_name(table_name)

        if columns is not None and len(columns) == 0:
            msg = "columnsが空リストです。カラムを指定するか、Noneを指定してください。"
            self._logger.error(msg)
            raise ValueError(msg)

        col_clause = ", ".join(f't1."{col}"' for col in columns) if columns is not None else "t1.*"
        where_sql, params = self._build_where_clause(where, alias="t1")
        sub_where_sql, _ = self._build_where_clause(where, alias="t2")
        where_part = f"WHERE {where_sql}" if where_sql else ""
        and_or_where = "AND" if where_sql else "WHERE"

        sub_and = f" AND {sub_where_sql}" if sub_where_sql else ""
        sub_query = (
            f'SELECT MAX(t2."{order_by}") FROM {table_name} t2'
            f' WHERE t2."{group_by}" = t1."{group_by}"'
            f"{sub_and}"
        )
        query = (
            f"SELECT {col_clause} FROM {table_name} t1"
            f" {where_part}"
            f' {and_or_where} t1."{order_by}" = ({sub_query})'
        )

        self._logger.debug(
            "select_latest_per_group: クエリを実行します (table=%s, group_by=%s, order_by=%s)",
            table_name,
            group_by,
            order_by,
        )
        with self._engine.connect() as conn:
            result = pd.read_sql(text(query), conn, params=params)
        self._logger.debug(
            "select_latest_per_group: %d件取得しました (table=%s)", len(result), table_name
        )
        return result

    def delete(self, table_name: str, where: dict[str, Any]) -> None:
        """指定条件のレコードを削除する.

        Args:
            table_name (str): 対象テーブル名
            where (dict[str, Any]): 削除条件（AND結合）。selectと同じ書式を受け付ける。
                値がリストの場合はIN条件（``{カラム名: [値1, 値2, ...]}``）、
                値がdictの場合は範囲条件（``{カラム名: {"gte": 値, "lte": 値, "gt": 値, "lt": 値}}``）、
                それ以外は等値条件（``{カラム名: 値}``）として扱う

        Raises:
            EmptyWhereError: where が空の場合（全件削除の誤操作を防ぐ）
        """
        self._validate_table_name(table_name)

        if not where:
            msg = "where条件が空です。全件削除を防ぐため、必ず条件を指定してください。"
            self._logger.error(msg)
            raise EmptyWhereError(msg)

        where_sql, params = self._build_where_clause(where)
        sql = text(f"DELETE FROM {table_name} WHERE {where_sql}")

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

    @staticmethod
    def _build_dsn_from_env() -> str | None:
        """環境変数の個別設定からDSNを構築する."""
        host = os.environ.get("DB_HOST")
        name = os.environ.get("DB_NAME")
        user = os.environ.get("DB_USER")
        password = os.environ.get("DB_PASSWORD")
        if not all([host, name, user, password]):
            return None
        assert user is not None and password is not None
        port = os.environ.get("DB_PORT", "5432")
        return f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{name}"

    def _validate_table_name(self, table_name: str) -> None:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
            msg = f"無効なテーブル名です: {table_name!r}"
            self._logger.error(msg)
            raise ValueError(msg)

    def _validate_column_name(self, column: str) -> None:
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", column):
            msg = f"無効なカラム名です: {column!r}"
            self._logger.error(msg)
            raise ValueError(msg)

    def _build_where_clause(
        self,
        where: dict[str, Any] | None,
        alias: str = "",
    ) -> tuple[str, dict[str, Any]]:
        """WHERE句の文字列とバインドパラメータを構築する.

        Args:
            where (dict[str, Any] | None): フィルタ条件
            alias (str): テーブルエイリアス。空文字列の場合はエイリアスなし

        Returns:
            str: WHERE句の文字列（"WHERE"キーワードは含まない）
            dict[str, Any]: バインドパラメータ

        Raises:
            ValueError: whereの値に空リストが含まれる場合、または範囲条件のキーが不正な場合
        """
        if not where:
            return "", {}

        prefix = f"{alias}." if alias else ""
        parts: list[str] = []
        params: dict[str, Any] = {}

        for key, val in where.items():
            if isinstance(val, list):
                if len(val) == 0:
                    msg = f"where条件のリストが空です: キー '{key}'"
                    self._logger.error(msg)
                    raise ValueError(msg)
                placeholders = ", ".join(f":where_{key}_{i}" for i in range(len(val)))
                parts.append(f'{prefix}"{key}" IN ({placeholders})')
                for i, v in enumerate(val):
                    params[f"where_{key}_{i}"] = v
            elif isinstance(val, dict):
                if not val:
                    msg = f"範囲条件のdictが空です: キー '{key}'"
                    self._logger.error(msg)
                    raise ValueError(msg)
                unknown = set(val.keys()) - set(_RANGE_OPS.keys())
                if unknown:
                    msg = (
                        f"範囲条件のキーが不正です: {unknown}（使用可能: {set(_RANGE_OPS.keys())}）"
                    )
                    self._logger.error(msg)
                    raise ValueError(msg)
                for op_key, op_sql in _RANGE_OPS.items():
                    if op_key in val:
                        param_key = f"where_{key}_{op_key}"
                        parts.append(f'{prefix}"{key}" {op_sql} :{param_key}')
                        params[param_key] = val[op_key]
            else:
                parts.append(f'{prefix}"{key}" = :where_{key}')
                params[f"where_{key}"] = val

        return " AND ".join(parts), params
