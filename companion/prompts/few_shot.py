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

    # パターン2: ファイル編集依頼 → read_file → edit_file → response
    {"role": "user", "content": "hello.pyのmain関数にコメントを追加して"},
    {"role": "assistant", "content": """>> 編集依頼なので、まずファイルを読んでハッシュを確認する

::c0.90 ::s1.0 ::m0.15 ::f0.95

::read_file @hello.py"""},

    {"role": "assistant", "content": """::result ok
::tool read_file
::target hello.py
1:a1b| def main():
2:c2d|     print('Hello, World!')
3:e3f| 
4:g4h| if __name__ == '__main__':
5:i5j|     main()"""},

    {"role": "assistant", "content": """>> ハッシュを確認した。
>> 置換対象は 1:a1b 1:a1b の行。
>> edit_file で YAML フロントマター形式でコメントを付与する

::c0.95 ::s1.0 ::m0.20 ::f0.95

::edit_file @hello.py
<<<
---
anchors: "1:a1b 1:a1b"
---
# メイン関数: Hello Worldを出力する
def main():
>>>"""},

    {"role": "assistant", "content": """::result ok
::tool edit_file
::target hello.py
Successfully edited hello.py."""},

    {"role": "assistant", "content": """>> 編集完了。response で報告する

::c0.95 ::s1.0 ::m0.20 ::f0.95

::response
<<<
`hello.py` の `main` 関数にコメントを追加しました。
>>>"""},
]
