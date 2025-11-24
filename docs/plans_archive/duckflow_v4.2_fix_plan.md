# ドキュメント：v4.2 計画の記憶と連携の強化・実装指示書

## 1. 概要

### 1.1. 目的
本改修の目的は、Duckflowのプランニング能力を向上させ、ファイル操作の安定性を確保することです。具体的には、以下の2点を実装します。
1.  **計画の自動具体化:** `plan_tool.propose` が呼び出された際に、`Plan`の骨子だけでなく、具体的な`Step`リストも自動的に生成・格納するように機能を拡張します。
2.  **ファイル読み込みの安定化:** `structured_file_ops.read_file_chunk` のロジックを、文字化けやエラーに強い堅牢な方式にリファクタリングします。

### 1.2. 主な対象ファイル
- `companion/plan_tool.py`
- `companion/enhanced_core_v8.py`
- `companion/tools/structured_file_ops.py`

---

## 2. 実装ステップ: Part 1 - プランニング能力の拡張

### ステップ 1.1: `PlanTool` へのLLMクライアントの注入

**担当ファイル:** `companion/plan_tool.py`

**タスク:**
`PlanTool` クラスがLLMを呼び出せるように、`__init__` メソッドを修正し、`llm_client` を受け取れるようにしてください。

**修正箇所:**
```python
# companion/plan_tool.py

# LLMClientをインポート
from ..llm.llm_client import LLMClient 
# ... 他インポート

class PlanTool:
    def __init__(self, logs_dir: str = "logs", file_ops: Optional[SimpleFileOps] = None, 
                 llm_client: Optional[LLMClient] = None, # この引数を追加
                 allow_external_paths: bool = False):
        # ... 既存の初期化コード ...
        self.llm_client = llm_client # この行を追加
        # ...
```

**担当ファイル:** `companion/enhanced_core_v8.py`

**タスク:**
`EnhancedCompanionCoreV8` の `__init__` メソッドで `PlanTool` をインスタンス化する際に、`self.llm_client` を渡してください。

**修正箇所:**
```python
# companion/enhanced_core_v8.py

# ... __init__ メソッド内 ...
# ActionPlanTool ではなく PlanTool を使用するように変更
self.plan_tool = PlanTool(llm_client=self.llm_client)
# ...
```

### ステップ 1.2: `plan_tool.propose` メソッドの機能拡張

**担当ファイル:** `companion/plan_tool.py`

**タスク:**
`propose` メソッドを `async` に変更し、プラン提案時にLLMに問い合わせて具体的なステップも自動生成するロジックを追加します。

1.  `propose` メソッドのシグネチャを `async def propose(...)` に変更してください。
2.  メソッド内で、`Plan` オブジェクトを生成した後、`if self.llm_client:` の条件分岐を追加します。
3.  `_generate_steps_for_goal` という新しい非同期ヘルパーメソッドを `PlanTool` 内に作成します。このメソッドは、ユーザーの `goal` を基にLLMに問い合わせ、ステップのリスト（`List[Dict]`）を返します。
4.  `propose` メソッドは、`_generate_steps_for_goal` から受け取ったステップリストをループ処理し、それぞれにユニークな `step_id` を付与しながら `Step` モデルのインスタンスを生成し、`plan.steps` に追加します。
5.  最終的に、ステップ情報が格納された `Plan` オブジェクトを保存します。

**`_generate_steps_for_goal` の実装例:**
```python
# companion/plan_tool.py 内に追加

async def _generate_steps_for_goal(self, goal: str) -> List[Dict[str, Any]]:
    """LLMを使用して目標からステップを生成する"""
    prompt = f"""あなたは優秀なプロジェクトプランナーです。
以下の【目標】を達成するための具体的なステップを、JSON配列形式で提案してください。
各ステップには name (短い名前), description (詳細), depends_on (依存するステップIDのリスト) を含めてください。

【目標】
{goal}

【出力形式】
[
    {
        "name": "ステップ1の名前",
        "description": "ステップ1の詳細な説明",
        "depends_on": []
    },
    {
        "name": "ステップ2の名前",
        "description": "ステップ2の詳細な説明",
        "depends_on": ["step_id_1"]
    }
]
"""
    try:
        response = await self.llm_client.chat(prompt)
        if response and response.content:
            # LLMの応答からJSON部分を抽出してパース
            json_str = self._extract_json_from_response(response.content)
            return json.loads(json_str)
    except Exception as e:
        self.logger.error(f"ステップ生成エラー: {e}")
    return []

def _extract_json_from_response(self, text: str) -> str:
    # LLMの応答からJSONコードブロックを抽出する補助関数
    match = re.search(r"```json
(.*)
```", text, re.DOTALL)
    if match:
        return match.group(1)
    return text
```

---

## 3. 実装ステップ: Part 2 - ファイル読み込みの安定化

### ステップ 2.1: `read_file_chunk` メソッドのリファクタリング

**担当ファイル:** `companion/tools/structured_file_ops.py`

**タスク:**
`read_file_chunk` メソッドを、文字化けに強いロジックに全面的に書き換えます。ファイルをまずバイナリとして読み、その後にデコードを試みることで、エンコーディングエラーとオフセット指定時の問題を解決します。

**新しい `read_file_chunk` の実装:**
```python
# companion/tools/structured_file_ops.py

async def read_file_chunk(self, file_path: str, offset: int = 0, size: int = 8192, **kwargs) -> Dict[str, Any]:
    """ファイルの指定範囲を文字ベースで読み込み（堅牢性向上版）"""
    try:
        self.logger.info(f"ファイルチャンク読み込み開始: {file_path} (offset={offset}, size={size})")
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return {"success": False, "error": f"ファイルが見つかりません: {file_path}"}

        stat = path.stat()
        total_size = stat.st_size

        if offset >= total_size:
            self.logger.warning(f"オフセット({offset})がファイルサイズ({total_size})を超えています。空の内容を返します。")
            content = ""
            actual_read_size = 0
            used_encoding = "N/A"
        else:
            # 1. ファイルをバイナリモードで開いて読み込む
            with open(path, 'rb') as f:
                f.seek(offset)
                binary_chunk = f.read(size)
            
            actual_read_size = len(binary_chunk)

            # 2. デコードを試みる
            content = None
            used_encoding = None
            encodings_to_try = ['utf-8', 'shift_jis', 'euc-jp', 'cp932', 'latin-1']
            for encoding in encodings_to_try:
                try:
                    content = binary_chunk.decode(encoding)
                    used_encoding = encoding
                    self.logger.info(f"エンコーディング {encoding} でデコード成功")
                    break
                except UnicodeDecodeError:
                    continue
            
            # 3. 全てのデコードに失敗した場合のフォールバック
            if content is None:
                content = binary_chunk.hex()
                used_encoding = 'binary'
                self.logger.warning(f"全てのテキストデコードに失敗したため、バイナリ(hex)として扱います: {file_path}")

        is_complete = (offset + actual_read_size) >= total_size
        metadata = {
            "file_path": file_path,
            "total_size_bytes": total_size,
            "offset": offset,
            "requested_size": size,
            "actual_read_size": actual_read_size,
            "is_complete": is_complete,
            "used_encoding": used_encoding,
            "read_time": datetime.now().isoformat()
        }

        return {
            "success": True,
            "file_path": file_path,
            "content": content,
            "metadata": metadata
        }

    except Exception as e:
        self.logger.error(f"ファイルチャンク読み込みエラー: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
```

## 4. レビューの観点
実装完了後、司令塔として私がレビューする際の主要な確認項目は以下の通りです。

1.  `PlanTool` は `llm_client` を受け取り、`propose` メソッドは非同期 (`async`) になっているか。
2.  `propose` メソッドが、LLMを呼び出して`Step`リストを生成し、`Plan`オブジェクトに正しく格納しているか。
3.  `read_file_chunk` が、まずバイナリで読み込み、その後にデコードを試みるロジックに変更されているか。
4.  文字化けや、以前発生した `local variable 'end_pos' referenced before assignment` のようなエラーが解消されているか。
