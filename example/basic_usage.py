"""db-clientの基本的な使い方の例.

このスクリプトはdb-clientライブラリの基本的な使い方を示す。
実行前に環境変数 DATABASE_URL を設定すること（.env.example を参照）。

使い方:
    export DATABASE_URL=postgresql://user:pass@localhost:5432/keiba
    python example/basic_usage.py
"""

import os

import pandas as pd

from db_client import DbClient


def main() -> None:
    """基本的なCRUD操作のデモ."""
    dsn = os.environ["DATABASE_URL"]
    client = DbClient(dsn=dsn)

    # ---- upsert ----
    # 新規レコードを挿入（主キー重複時は更新）
    df_ratings = pd.DataFrame(
        {
            "race_code": ["202301010101", "202301010102", "202301010103"],
            "uma_ban": [1, 2, 3],
            "target": ["horse", "horse", "horse"],
            "rating": [1500.0, 1520.0, 1480.0],
        }
    )
    client.upsert(
        table_name="ratings",
        df=df_ratings,
        primary_keys=["race_code", "uma_ban", "target"],
    )
    print("upsert完了")

    # ---- select（全件取得）----
    all_ratings = client.select(table_name="ratings")
    print(f"全件取得: {len(all_ratings)}件")
    print(all_ratings)

    # ---- select（条件指定・カラム指定）----
    filtered = client.select(
        table_name="ratings",
        where={"race_code": "202301010101"},
        columns=["race_code", "uma_ban", "rating"],
    )
    print(f"条件指定取得: {len(filtered)}件")
    print(filtered)

    # ---- delete ----
    client.delete(
        table_name="ratings",
        where={"race_code": "202301010103"},
    )
    print("delete完了")

    # 削除後の確認
    remaining = client.select(table_name="ratings")
    print(f"削除後の件数: {len(remaining)}件")


if __name__ == "__main__":
    main()
