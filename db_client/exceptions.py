"""例外クラス定義.

このモジュールは、db-clientライブラリで使用される例外クラスを定義する。
"""


class DbClientError(Exception):
    """db-client基底例外.

    db-clientライブラリの全ての例外の基底クラス。
    """

    pass


class EmptyWhereError(DbClientError):
    """where条件が空の場合の例外.

    全件削除の誤操作を防ぐため、deleteメソッドにwhere条件が指定されなかった場合に発生する。
    """

    pass


class DsnNotConfiguredError(DbClientError):
    """接続文字列が未設定の場合の例外.

    dsnおよびDATABASE_URLのどちらも設定されていない場合に発生する。
    """

    pass
