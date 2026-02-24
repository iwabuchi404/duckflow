"""
Few-shot examples モジュール。

LLMがSym-Ops構文を出力形式として学習するための会話ペアを定義する。
"""

FEW_SHOT_EXAMPLES = [
    # パターン1: 短い質問 → response で返答
    {"role": "user", "content": "このプロジェクトは何のツールを使っていますか？"},
    {"role": "assistant", "content": """>> ユーザーがプロジェクトの技術スタックを質問している
>> 短い質問なので response で返答する

::c0.90 ::s1.0 ::m0.10 ::f0.95

::response
<<<
Pythonベースで、Rich (UI)、Pydantic (状態管理)、PyYAML (設定) を使用しています。詳しく調べますか？
>>>"""},

    # パターン2: ファイル編集依頼 → read_file → edit_lines → response
    {"role": "user", "content": "hello.pyのmain関数にコメントを追加して"},
    {"role": "assistant", "content": """>> 編集依頼なので、まずファイルを読んで行番号を確認する

::c0.90 ::s1.0 ::m0.15 ::f0.95

::read_file @hello.py"""},

    {"role": "assistant", "content": """::result ok
::tool read_file
::target hello.py
   def main():
       print('Hello, World!')

    if __name__ == '__main__':
        main()"""},

    {"role": "assistant", "content": """>> 行番号を確認した。
>> Replacing lines 1-1: 'def main():'
>> edit_lines で行1-1を置換する

::c0.95 ::s1.0 ::m0.20 ::f0.95

::edit_lines @hello.py start=1 end=1
<<<
# メイン関数: Hello Worldを出力する
def main():
>>>"""},

    {"role": "assistant", "content": """::result ok
::tool edit_lines
::target hello.py
Edited hello.py."""},

    {"role": "assistant", "content": """>> 編集完了。response で報告する

::c0.95 ::s1.0 ::m0.20 ::f0.95

::response
<<<
`hello.py` の `main` 関数にコメントを追加しました。
>>>"""},
]
