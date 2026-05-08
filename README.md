# db-client

## 概要

PostgreSQLとのデータ入出力を担う汎用ライブラリ。

本ライブラリはDBとの接続管理とDataFrameの入出力のみを担い、テーブル定義には依存しない。
テーブル定義（CREATE TABLE文・カラム型・インデックスなど）は各利用ライブラリ側で管理する。

## 動作要件

- Python 3.12以上

## 依存パッケージ

- `sqlalchemy>=2.0.0`
- `pandas>=2.0.0`
- `psycopg2-binary>=2.9.0`
- `python-dotenv>=1.0.0`

## インストール

```bash
pip install -e /path/to/db-client
```

## セットアップ

`.env` ファイルまたは環境変数に接続情報を設定すると、`dsn` 引数を省略できる。

```bash
# .env ファイル（推奨）
DB_HOST=localhost
DB_PORT=5432
DB_NAME=keibaai
DB_USER=postgres
DB_PASSWORD=postgres
```

`.env.example` を参照。

## 使い方

```python
import logging
from db_client import DbClient
import pandas as pd

# 環境変数（DB_HOST 等）を設定している場合は dsn を省略できる
client = DbClient()

# dsn を直接渡すこともできる（こちらが優先される）
client = DbClient(dsn="postgresql://user:pass@host:5432/dbname")

# logger は省略可（省略時はモジュール名でロガーを生成する）
logger = logging.getLogger(__name__)
client = DbClient(logger=logger)

# upsert: DataFrameをテーブルに保存（主キー重複時は更新）
df = pd.DataFrame({
    "id": ["001", "002"],
    "value": [1.0, 2.0],
})
client.upsert(table_name="my_table", df=df, primary_keys=["id"])

# select: テーブルからDataFrameを取得
all_rows = client.select(table_name="my_table")

# select with conditions
filtered = client.select(
    table_name="my_table",
    where={"id": "001"},
    columns=["id", "value"],
)

# select with IN condition
filtered = client.select(
    table_name="my_table",
    where={"id": ["001", "002"]},
)

# delete: 条件を指定してレコードを削除（等値条件）
client.delete(table_name="my_table", where={"id": "001"})

# delete with IN condition
client.delete(table_name="my_table", where={"id": ["001", "002"]})

# delete with range condition
client.delete(
    table_name="my_table",
    where={"race_code": {"gte": "20220101", "lt": "20230101"}},
)

# delete with combined conditions
client.delete(
    table_name="my_table",
    where={"target": "horse", "race_code": {"gte": "20220101", "lt": "20230101"}},
)

# delete_all: テーブルの全レコードを削除
client.delete_all(table_name="my_table")

# select_max: 指定カラムの最大値を取得
max_code = client.select_max(table_name="my_table", column="race_code")
max_code_filtered = client.select_max(
    table_name="my_table",
    column="race_code",
    where={"target": "horse"},
)

# select_latest_per_group: グループごとの最新行を取得
latest_df = client.select_latest_per_group(
    table_name="my_table",
    group_by="target_id",
    order_by="race_code",
    where={"target": "horse"},
    columns=["target_id", "race_code", "mu_after"],
)

# setup_table: DDLを実行してテーブルとインデックスを作成
ddl = """
CREATE TABLE IF NOT EXISTS my_table (id SERIAL PRIMARY KEY, name VARCHAR(100));
CREATE INDEX IF NOT EXISTS my_table_name ON my_table (name);
"""
client.setup_table(ddl)

# drop_table: テーブルを削除（IF EXISTS）
client.drop_table(table_name="my_table")
```

詳細な使用例は [example/basic_usage.py](example/basic_usage.py) を参照。

## API

### `DbClient(dsn=None, logger=None)`

| 引数 | 型 | 説明 |
|---|---|---|
| `dsn` | `str \| None` | PostgreSQL接続文字列（例: `postgresql://user:pass@host:5432/dbname`）。省略時は `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` 環境変数から構築する |
| `logger` | `logging.Logger \| None` | ロガーインスタンス。`None` の場合はモジュール名でロガーを生成する |

`dsn` も個別環境変数も未設定の場合は `DsnNotConfiguredError` を発生させる。
接続プールを内部で保持し、各メソッド呼び出しで再利用する。

### `setup_table(ddl) -> None`

| 引数 | 型 | 説明 |
|---|---|---|
| `ddl` | `str` | テーブルとインデックスを作成するDDL文字列 |

DDL文字列を実行してテーブルとインデックスを作成する。`IF NOT EXISTS` を用いることで冪等に実行できる。
`;` 区切りで複数のSQL文を含む文字列を渡した場合は各文を個別に実行する。1つのトランザクション内で実行されるため、途中でエラーが発生した場合はロールバックされる。
テーブル定義（DDL文字列）は各利用ライブラリの `params.py` で定数として管理する。

### `drop_table(table_name) -> None`

| 引数 | 型 | 説明 |
|---|---|---|
| `table_name` | `str` | 削除するテーブル名 |

指定テーブルを削除する（`IF EXISTS`）。テーブルが存在しない場合は何もしない。
無効なテーブル名（記号を含む等）の場合は `ValueError` を発生させる。

### `upsert(table_name, df, primary_keys) -> None`

| 引数 | 型 | 説明 |
|---|---|---|
| `table_name` | `str` | 対象テーブル名 |
| `df` | `pd.DataFrame` | 保存するDataFrame。カラム名がDBカラム名にマッピングされる |
| `primary_keys` | `list[str]` | 重複判定に使用する主キーカラム名のリスト |

主キーが一致するレコードが既存の場合、非主キーカラムを上書きする。`df` が空の場合は何もしない。

### `select(table_name, where=None, columns=None) -> pd.DataFrame`

| 引数 | 型 | 説明 |
|---|---|---|
| `table_name` | `str` | 対象テーブル名 |
| `where` | `dict[str, Any] \| None` | フィルタ条件（AND結合）。`None` の場合は全件取得 |
| `columns` | `list[str] \| None` | 取得するカラム名のリスト。`None` の場合は全カラムを取得 |

`where` の値には以下の3形式を指定できる（AND結合）。

| 形式 | 例 | SQL |
|---|---|---|
| 等値条件 | `{"id": "001"}` | `"id" = '001'` |
| IN条件 | `{"id": ["001", "002"]}` | `"id" IN ('001', '002')` |
| 範囲条件 | `{"code": {"gte": "20220101", "lt": "20230101"}}` | `"code" >= '20220101' AND "code" < '20230101'` |

範囲条件のキーは `gte`（>=）, `lte`（<=）, `gt`（>）, `lt`（<）。

該当レコードが存在しない場合は空のDataFrameを返す。

### `select_max(table_name, column, where=None) -> Any | None`

| 引数 | 型 | 説明 |
|---|---|---|
| `table_name` | `str` | 対象テーブル名 |
| `column` | `str` | 最大値を取得するカラム名 |
| `where` | `dict[str, Any] \| None` | フィルタ条件（`select` の `where` と同じ書式） |

指定カラムの最大値を返す。該当レコードが存在しない場合は `None` を返す。

### `select_latest_per_group(table_name, group_by, order_by, where=None, columns=None) -> pd.DataFrame`

| 引数 | 型 | 説明 |
|---|---|---|
| `table_name` | `str` | 対象テーブル名 |
| `group_by` | `str` | グループ化するカラム名（例: `"target_id"`） |
| `order_by` | `str` | 最大値を基準にするカラム名（例: `"race_code"`） |
| `where` | `dict[str, Any] \| None` | フィルタ条件（`select` の `where` と同じ書式） |
| `columns` | `list[str] \| None` | 取得するカラム名のリスト。`None` の場合は全カラムを取得 |

`group_by` カラムでグループ化し、各グループ内で `order_by` が最大の行をすべて返す。
同一グループ・同一 `order_by` 値の行が複数ある場合（例: 同一レースで調教師が複数頭出走）はすべて返す。

### `delete(table_name, where) -> None`

| 引数 | 型 | 説明 |
|---|---|---|
| `table_name` | `str` | 対象テーブル名 |
| `where` | `dict[str, Any]` | 削除条件（AND結合）。`select` の `where` と同じ書式を受け付ける |

`where` の値には等値条件・IN条件・範囲条件を指定できる（`select` の `where` 参照）。
`where` が空の場合は `EmptyWhereError` を発生させる（全件削除の誤操作を防ぐ）。

### `delete_all(table_name) -> None`

| 引数 | 型 | 説明 |
|---|---|---|
| `table_name` | `str` | 対象テーブル名 |

全件削除を明示的に行うための専用メソッド。`delete` メソッドとは分離している。


## エラーハンドリング

| 例外クラス | 発生条件 |
|---|---|
| `DbClientError` | 全ての例外の基底クラス |
| `DsnNotConfiguredError` | `dsn` も個別環境変数（`DB_HOST` 等）も未設定の場合 |
| `EmptyWhereError` | `delete` に空の `where` を渡した場合（全件削除誤操作防止） |

```python
from db_client.exceptions import DsnNotConfiguredError, EmptyWhereError

try:
    client = DbClient()
except DsnNotConfiguredError as e:
    print(f"接続文字列が未設定です: {e}")

try:
    client.delete(table_name="my_table", where={})
except EmptyWhereError as e:
    print(f"where条件が必要です: {e}")
```
