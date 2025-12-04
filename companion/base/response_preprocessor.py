import re
import logging
from typing import Callable, List

logger = logging.getLogger(__name__)


class ResponsePreprocessor:
    """
    LLM応答の前処理を行うクラス。
    複数の前処理ステップを順次適用できる。
    """
    
    def __init__(self):
        self.processors: List[Callable[[str], str]] = []
        self._register_default_processors()
    
    def _register_default_processors(self):
        """デフォルトの前処理を登録"""
        self.register(self.extract_json_from_special_tokens)
        self.register(self.remove_markdown_code_blocks)
        self.register(self.extract_json_object)  # NEW: JSONオブジェクトだけを抽出
        self.register(self.strip_whitespace)
    
    def register(self, processor: Callable[[str], str]):
        """
        前処理関数を登録する。
        
        Args:
            processor: str を受け取り str を返す関数
        """
        self.processors.append(processor)
        logger.debug(f"Registered preprocessor: {processor.__name__}")
    
    def unregister(self, processor: Callable[[str], str]):
        """
        前処理関数を登録解除する。
        
        Args:
            processor: 登録解除する関数
        """
        if processor in self.processors:
            self.processors.remove(processor)
            logger.debug(f"Unregistered preprocessor: {processor.__name__}")
    
    def clear(self):
        """すべての前処理を解除"""
        self.processors.clear()
        logger.debug("Cleared all preprocessors")
    
    def process(self, content: str) -> str:
        """
        登録された前処理を順次適用する。
        
        Args:
            content: LLMからの生の応答
            
        Returns:
            前処理後の応答
        """
        original_content = content
        
        for processor in self.processors:
            try:
                content = processor(content)
            except Exception as e:
                logger.warning(f"Preprocessor {processor.__name__} failed: {e}")
                # エラーが発生しても処理を続行
        
        if content != original_content:
            logger.debug(f"Response preprocessed: {len(original_content)} -> {len(content)} chars")
        
        return content
    
    # ========================================
    # 前処理関数（静的メソッド）
    # ========================================
    
    @staticmethod
    def extract_json_from_special_tokens(content: str) -> str:
        """
        特殊トークン形式（<|message|>{...}<|call|>など）からJSONを抽出する。
        
        一部のモデル（gpt-oss-120bなど）が独自のツール呼び出しフォーマットを
        使用する場合に対応。
        """
        content = content.strip()
        
        # <|message|>と<|call|>または<|end|>の間のJSONを抽出
        match = re.search(r'<\|message\|>(\{.*?\})(?:<\||$)', content, re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            logger.debug("Extracted JSON from special token format (<|message|>...)")
            return extracted
        
        # <|start|>から始まる場合、全体をスキップして次の処理に任せる
        if content.startswith('<|start|>'):
            logger.debug("Detected special token format but couldn't extract JSON")
        
        return content
    
    @staticmethod
    def remove_markdown_code_blocks(content: str) -> str:
        """
        マークダウンコードブロックを除去する。
        
        パターン:
        - ```json\n...\n```
        - ```\n...\n```
        
        複数のマークダウンブロックがある場合、最も外側を優先的に除去する。
        """
        content = content.strip()
        
        # パターン1: 最も外側の ```...``` を除去（言語指定なし）
        # 例: ```\n説明文\n```typescript\ncode\n```\n{"json": "here"}\n```
        match = re.match(r'^```\s*\n(.*)\n```\s*$', content, re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            logger.debug("Removed outermost markdown code block wrapper (no language)")
            return extracted
        
        # パターン2: 最も外側の ```json...``` を除去
        match = re.match(r'^```(?:json|JSON)\s*\n(.*)\n```\s*$', content, re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            logger.debug("Removed outermost markdown code block wrapper (json)")
            return extracted
        
        # パターン3: 前後にテキストがある場合、最後の ```json...``` を抽出
        # 例: "説明文\n\n```json\n{...}\n```"
        # 最後に出現するJSONブロックを優先（LLMは通常、最後にJSONを置く）
        matches = list(re.finditer(r'```(?:json|JSON)?\s*\n(.*?)\n```', content, re.DOTALL))
        if matches:
            # 最後のマッチを使用
            last_match = matches[-1]
            extracted = last_match.group(1).strip()
            logger.debug(f"Extracted last JSON from markdown code block (found {len(matches)} blocks)")
            return extracted
        
        return content
    
    @staticmethod
    def extract_json_object(content: str) -> str:
        """
        テキスト内からJSONオブジェクトを抽出する。
        
        LLMが説明文を追加してからJSONを返す場合に対応。
        例: "Here is my response:\n\n{...}" -> "{...}"
        
        括弧のバランスを追跡して、完全なJSONオブジェクトを抽出する。
        """
        content = content.strip()
        
        # すでにJSONで始まっている場合はそのまま返す
        if content.startswith('{') or content.startswith('['):
            return content
        
        # { または [ を探す
        start_brace = content.find('{')
        start_bracket = content.find('[')
        
        # どちらが先に現れるかを判定
        if start_brace == -1 and start_bracket == -1:
            # JSONが見つからない
            return content
        
        # 最初に現れる方を選択
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            start_pos = start_brace
            open_char = '{'
            close_char = '}'
        else:
            start_pos = start_bracket
            open_char = '['
            close_char = ']'
        
        # 括弧のバランスを追跡して終了位置を見つける
        depth = 0
        in_string = False
        escape_next = False
        
        for i in range(start_pos, len(content)):
            char = content[i]
            
            # エスケープ処理
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            # 文字列内かどうかを追跡
            if char == '"':
                in_string = not in_string
                continue
            
            # 文字列内では括弧をカウントしない
            if in_string:
                continue
            
            # 括弧のカウント
            if char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                
                # 完全なJSONオブジェクトが見つかった
                if depth == 0:
                    extracted = content[start_pos:i+1].strip()
                    if start_pos > 0:
                        logger.debug(f"Extracted JSON object from text (removed {start_pos} chars prefix)")
                    return extracted
        
        # 完全なJSONが見つからなかった場合は元のコンテンツを返す
        logger.warning("Could not find complete JSON object with balanced brackets")
        return content
    
    @staticmethod
    def strip_whitespace(content: str) -> str:
        """前後の空白を除去"""
        return content.strip()
    
    @staticmethod
    def remove_bom(content: str) -> str:
        """UTF-8 BOM（Byte Order Mark）を除去"""
        if content.startswith('\ufeff'):
            logger.debug("Removed UTF-8 BOM")
            return content[1:]
        return content
    
    @staticmethod
    def normalize_newlines(content: str) -> str:
        """改行コードを統一（CRLF -> LF）"""
        if '\r\n' in content:
            logger.debug("Normalized CRLF to LF")
            return content.replace('\r\n', '\n')
        return content


# グローバルインスタンス
default_preprocessor = ResponsePreprocessor()

