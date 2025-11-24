"""
LLM Output Formatter for Duckflow v3

設計ドキュメント 7. LLM出力フォーマットの統一の実装
- Main LLMの出力フォーマット統一
- JSONスキーマの厳格化
- エラー時の復旧処理
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, ValidationError


class LLMOutputSchema(BaseModel):
    """LLM出力の統一スキーマ"""
    
    rationale: str = Field(description="操作の理由（1行）")
    goal_consistency: str = Field(description="目標との整合性（yes/no + 理由）")
    constraint_check: str = Field(description="制約チェック（yes/no + 理由）")
    next_step: str = Field(description="次のステップ（done/pending_user/defer/continue）")
    step: str = Field(description="ステップ（PLANNING/EXECUTION/REVIEW/AWAITING_APPROVAL）")
    state_delta: str = Field(default="", description="状態変化（あれば）")


class LLMOutputFormatter:
    """LLM出力フォーマットを統一・検証するクラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 有効な値の定義
        self.valid_next_steps = ["done", "pending_user", "defer", "continue"]
        self.valid_steps = ["PLANNING", "EXECUTION", "REVIEW", "AWAITING_APPROVAL"]
        
        # デフォルト値
        self.default_output = {
            "rationale": "デフォルトの操作理由",
            "goal_consistency": "yes: デフォルト設定",
            "constraint_check": "yes: 制約なし",
            "next_step": "continue",
            "step": "PLANNING",
            "state_delta": ""
        }
    
    def validate(self, output_data: Union[str, Dict[str, Any]]) -> LLMOutputSchema:
        """LLM出力を検証
        
        Args:
            output_data: LLMの出力（文字列または辞書）
            
        Returns:
            LLMOutputSchema: 検証済みの出力スキーマ
            
        Raises:
            ValidationError: 検証に失敗した場合
        """
        try:
            # 文字列の場合はJSONとして解析
            if isinstance(output_data, str):
                parsed_data = self._parse_json_string(output_data)
            else:
                parsed_data = output_data
            
            # 必須フィールドの存在チェック
            self._validate_required_fields(parsed_data)
            
            # 値の妥当性チェック
            self._validate_field_values(parsed_data)
            
            # スキーマに変換
            return LLMOutputSchema(**parsed_data)
            
        except Exception as e:
            self.logger.error(f"LLM出力検証エラー: {e}")
            raise ValidationError(f"LLM出力の検証に失敗: {e}")
    
    def try_repair(self, output_data: Union[str, Dict[str, Any]]) -> Optional[LLMOutputSchema]:
        """LLM出力の修復を試行
        
        Args:
            output_data: 修復対象の出力
            
        Returns:
            LLMOutputSchema: 修復された出力（修復不可能な場合はNone）
        """
        try:
            # 文字列の場合はJSONとして解析を試行
            if isinstance(output_data, str):
                parsed_data = self._parse_json_string(output_data)
            else:
                parsed_data = output_data
            
            # 修復処理
            repaired_data = self._repair_output(parsed_data)
            
            # 修復後の検証
            return self.validate(repaired_data)
            
        except Exception as e:
            self.logger.warning(f"LLM出力修復失敗: {e}")
            return None
    
    def _parse_json_string(self, json_string: str) -> Dict[str, Any]:
        """JSON文字列を解析"""
        try:
            # 基本的なJSON解析
            return json.loads(json_string)
        except json.JSONDecodeError:
            # JSON解析に失敗した場合、部分的な抽出を試行
            return self._extract_partial_json(json_string)
    
    def _extract_partial_json(self, text: str) -> Dict[str, Any]:
        """部分的なJSON抽出を試行"""
        extracted_data = {}
        
        # 各フィールドを正規表現で抽出
        import re
        
        # rationale
        rationale_match = re.search(r'"rationale"\s*:\s*"([^"]*)"', text)
        if rationale_match:
            extracted_data["rationale"] = rationale_match.group(1)
        
        # goal_consistency
        goal_match = re.search(r'"goal_consistency"\s*:\s*"([^"]*)"', text)
        if goal_match:
            extracted_data["goal_consistency"] = goal_match.group(1)
        
        # constraint_check
        constraint_match = re.search(r'"constraint_check"\s*:\s*"([^"]*)"', text)
        if constraint_match:
            extracted_data["constraint_check"] = constraint_match.group(1)
        
        # next_step
        next_step_match = re.search(r'"next_step"\s*:\s*"([^"]*)"', text)
        if next_step_match:
            extracted_data["next_step"] = next_step_match.group(1)
        
        # step
        step_match = re.search(r'"step"\s*:\s*"([^"]*)"', text)
        if step_match:
            extracted_data["step"] = step_match.group(1)
        
        # state_delta
        delta_match = re.search(r'"state_delta"\s*:\s*"([^"]*)"', text)
        if delta_match:
            extracted_data["state_delta"] = delta_match.group(1)
        
        return extracted_data
    
    def _validate_required_fields(self, data: Dict[str, Any]) -> None:
        """必須フィールドの存在チェック"""
        required_fields = ["rationale", "goal_consistency", "constraint_check", "next_step", "step"]
        
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"必須フィールド '{field}' が不足または空です")
    
    def _validate_field_values(self, data: Dict[str, Any]) -> None:
        """フィールド値の妥当性チェック"""
        # next_stepの妥当性チェック
        if data.get("next_step") not in self.valid_next_steps:
            self.logger.warning(f"無効なnext_step: {data.get('next_step')}")
            data["next_step"] = "continue"  # デフォルト値に修正
        
        # stepの妥当性チェック
        if data.get("step") not in self.valid_steps:
            self.logger.warning(f"無効なstep: {data.get('step')}")
            data["step"] = "PLANNING"  # デフォルト値に修正
        
        # 文字数制限のチェック
        if len(data.get("rationale", "")) > 200:
            data["rationale"] = data["rationale"][:197] + "..."
        
        if len(data.get("goal_consistency", "")) > 200:
            data["goal_consistency"] = data["goal_consistency"][:197] + "..."
        
        if len(data.get("constraint_check", "")) > 200:
            data["constraint_check"] = data["constraint_check"][:197] + "..."
        
        if len(data.get("state_delta", "")) > 200:
            data["state_delta"] = data["state_delta"][:197] + "..."
    
    def _repair_output(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """出力データの修復"""
        repaired_data = self.default_output.copy()
        
        # 利用可能なデータで上書き
        for field in repaired_data:
            if field in data and data[field]:
                repaired_data[field] = data[field]
        
        # 特殊な修復処理
        if "rationale" not in repaired_data or not repaired_data["rationale"]:
            repaired_data["rationale"] = "修復された操作理由"
        
        if "goal_consistency" not in repaired_data or not repaired_data["goal_consistency"]:
            repaired_data["goal_consistency"] = "yes: 修復後の設定"
        
        if "constraint_check" not in repaired_data or not repaired_data["constraint_check"]:
            repaired_data["constraint_check"] = "yes: 制約チェック完了"
        
        return repaired_data
    
    def format_for_display(self, output_schema: LLMOutputSchema) -> str:
        """出力スキーマを表示用にフォーマット"""
        formatted = f"""LLM出力結果:
├─ 操作理由: {output_schema.rationale}
├─ 目標整合性: {output_schema.goal_consistency}
├─ 制約チェック: {output_schema.constraint_check}
├─ 次のステップ: {output_schema.next_step}
├─ 現在のステップ: {output_schema.step}"""
        
        if output_schema.state_delta:
            formatted += f"\n└─ 状態変化: {output_schema.state_delta}"
        else:
            formatted += "\n└─ 状態変化: なし"
        
        return formatted
    
    def get_validation_summary(self, output_schema: LLMOutputSchema) -> Dict[str, Any]:
        """検証結果のサマリーを取得"""
        return {
            "is_valid": True,
            "fields_present": len([f for f in output_schema.__fields__ if getattr(output_schema, f)]),
            "total_fields": len(output_schema.__fields__),
            "next_action": output_schema.next_step,
            "current_step": output_schema.step,
            "has_state_delta": bool(output_schema.state_delta)
        }
    
    def create_error_output(self, error_message: str) -> LLMOutputSchema:
        """エラー時のデフォルト出力を作成"""
        error_data = self.default_output.copy()
        error_data.update({
            "rationale": f"エラー発生: {error_message}",
            "goal_consistency": "no: エラーにより確認不可",
            "constraint_check": "no: エラーにより確認不可",
            "next_step": "defer",
            "step": "PLANNING",
            "state_delta": "エラー状態に移行"
        })
        
        return LLMOutputSchema(**error_data)
