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

`.env` ファイルまたは環境変数 `DATABASE_URL` に接続文字列を設定すると、`dsn` 引数を省略できる。

```bash
# .env ファイル（推奨）
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

`.env.example` を参照。

## 使い方

```python
import logging
from db_client import DbClient
import pandas as pd

# DATABASE_URL を設定している場合は dsn を省略できる
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

# delete: 条件を指定してレコードを削除
client.delete(table_name="my_table", where={"id": "001"})

# delete_all: テーブルの全レコードを削除
client.delete_all(table_name="my_table")
```

詳細な使用例は [example/basic_usage.py](example/basic_usage.py) を参照。

## API

### `DbClient(dsn=None, logger=None)`

| 引数 | 型 | 説明 |
|---|---|---|
| `dsn` | `str \| None` | PostgreSQL接続文字列（例: `postgresql://user:pass@host:5432/dbname`）。省略時は `DATABASE_URL` 環境変数を使用する |
| `logger` | `logging.Logger \| None` | ロガーインスタンス。`None` の場合はモジュール名でロガーを生成する |

`dsn` と `DATABASE_URL` の両方が未設定の場合は `DbClientError` を発生させる。
接続プールを内部で保持し、各メソッド呼び出しで再利用する。

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
| `where` | `dict[str, Any] \| None` | フィルタ条件。`{カラム名: 値}` 形式（AND結合）。`None` の場合は全件取得 |
| `columns` | `list[str] \| None` | 取得するカラム名のリスト。`None` の場合は全カラムを取得 |

該当レコードが存在しない場合は空のDataFrameを返す。

### `delete(table_name, where) -> None`

| 引数 | 型 | 説明 |
|---|---|---|
| `table_name` | `str` | 対象テーブル名 |
| `where` | `dict[str, Any]` | 削除条件。`{カラム名: 値}` 形式（AND結合） |

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
| `DsnNotConfiguredError` | `dsn` および `DATABASE_URL` のどちらも未設定の場合 |
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
