"""
プロンプト管理システム

システムプロンプトのバージョン管理、適用、履歴追跡を行います。
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
import hashlib
import shutil


@dataclass
class PromptVersion:
    """プロンプトバージョンの情報"""
    version_id: str
    timestamp: datetime
    prompt_content: Dict[str, str]
    changes: List[str]
    performance_metrics: Optional[Dict[str, float]] = None
    is_active: bool = False
    parent_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptVersion':
        """辞書から復元"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class PromptManager:
    """システムプロンプトのバージョン管理と適用"""
    
    def __init__(self, prompt_dir: str = "codecrafter/prompts/system_prompts"):
        """
        プロンプト管理システムの初期化
        
        Args:
            prompt_dir: プロンプト管理ディレクトリのパス
        """
        self.prompt_dir = Path(prompt_dir)
        self.current_file = self.prompt_dir / "current.yaml"
        self.versions_dir = self.prompt_dir / "versions"
        self.history_file = self.prompt_dir / "history.json"
        
        # ディレクトリ作成
        self.prompt_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir.mkdir(exist_ok=True)
        
        # 履歴初期化
        self.version_history: List[PromptVersion] = []
        self._load_history()
        
        # 現行プロンプトの初期化
        if not self.current_file.exists():
            self._create_default_prompt()
    
    def _create_default_prompt(self) -> None:
        """デフォルトプロンプトを作成"""
        default_prompt = {
            "system_role": "あなたは優秀なAIコーディングエージェントです。",
            "task_understanding": "ユーザーの開発要求を正確に理解し、適切な質問をしてから実装を開始してください。",
            "code_quality": "高品質で保守性の高いコードを生成してください。",
            "error_handling": "エラーが発生した場合は、原因を分析し適切な修正を提案してください。",
            "communication": "作業内容を明確に説明し、必要に応じて確認を取ってください。"
        }
        
        # ファイル保存
        with open(self.current_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_prompt, f, allow_unicode=True, indent=2)
        
        # 初期バージョンとして記録
        version = PromptVersion(
            version_id=self._generate_version_id(default_prompt),
            timestamp=datetime.now(),
            prompt_content=default_prompt,
            changes=["初期プロンプト作成"],
            is_active=True
        )
        self.version_history.append(version)
        self._save_history()
    
    def load_current_prompt(self) -> Dict[str, str]:
        """現行プロンプトの読み込み"""
        try:
            with open(self.current_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            self._create_default_prompt()
            return self.load_current_prompt()
    
    def save_new_version(self, improved_prompt: Dict[str, str], 
                        changes: List[str],
                        performance_metrics: Optional[Dict[str, float]] = None) -> str:
        """
        改善されたプロンプトを新バージョンとして保存
        
        Args:
            improved_prompt: 改善されたプロンプト内容
            changes: 変更内容のリスト
            performance_metrics: 性能指標
            
        Returns:
            新しいバージョンID
        """
        # 現在のアクティブバージョンを取得
        current_version = self.get_active_version()
        parent_version_id = current_version.version_id if current_version else None
        
        # 新バージョン作成
        version_id = self._generate_version_id(improved_prompt)
        new_version = PromptVersion(
            version_id=version_id,
            timestamp=datetime.now(),
            prompt_content=improved_prompt,
            changes=changes,
            performance_metrics=performance_metrics,
            is_active=False,  # まだ適用されていない
            parent_version=parent_version_id
        )
        
        # バージョンファイル保存
        version_file = self.versions_dir / f"{version_id}.yaml"
        with open(version_file, 'w', encoding='utf-8') as f:
            yaml.dump(improved_prompt, f, allow_unicode=True, indent=2)
        
        # 履歴に追加
        self.version_history.append(new_version)
        self._save_history()
        
        return version_id
    
    def apply_version(self, version_id: str) -> bool:
        """
        指定バージョンを現行に適用
        
        Args:
            version_id: 適用するバージョンID
            
        Returns:
            適用成功かどうか
        """
        # バージョン検索
        version = self._find_version(version_id)
        if not version:
            return False
        
        # 現在のアクティブバージョンを無効化
        for v in self.version_history:
            v.is_active = False
        
        # 新バージョンをアクティブに
        version.is_active = True
        
        # 現行ファイルを更新
        with open(self.current_file, 'w', encoding='utf-8') as f:
            yaml.dump(version.prompt_content, f, allow_unicode=True, indent=2)
        
        # 履歴保存
        self._save_history()
        
        return True
    
    def get_version_history(self) -> List[Dict[str, Any]]:
        """バージョン履歴の取得"""
        return [version.to_dict() for version in self.version_history]
    
    def get_active_version(self) -> Optional[PromptVersion]:
        """現在アクティブなバージョンを取得"""
        for version in self.version_history:
            if version.is_active:
                return version
        return None
    
    def compare_versions(self, version_id1: str, version_id2: str) -> Dict[str, Any]:
        """
        2つのバージョンの比較
        
        Args:
            version_id1: 比較元バージョンID
            version_id2: 比較先バージョンID
            
        Returns:
            比較結果
        """
        v1 = self._find_version(version_id1)
        v2 = self._find_version(version_id2)
        
        if not v1 or not v2:
            return {"error": "バージョンが見つかりません"}
        
        # 変更点を比較
        changes = []
        for key in set(v1.prompt_content.keys()) | set(v2.prompt_content.keys()):
            v1_value = v1.prompt_content.get(key, "")
            v2_value = v2.prompt_content.get(key, "")
            
            if v1_value != v2_value:
                changes.append({
                    "field": key,
                    "old_value": v1_value,
                    "new_value": v2_value
                })
        
        return {
            "version_1": {
                "id": v1.version_id,
                "timestamp": v1.timestamp.isoformat()
            },
            "version_2": {
                "id": v2.version_id,
                "timestamp": v2.timestamp.isoformat()
            },
            "changes": changes,
            "performance_comparison": {
                "v1_metrics": v1.performance_metrics or {},
                "v2_metrics": v2.performance_metrics or {}
            }
        }
    
    def rollback_to_version(self, version_id: str) -> bool:
        """指定バージョンにロールバック"""
        version = self._find_version(version_id)
        if not version:
            return False
        
        # バックアップ作成
        backup_path = self.current_file.with_suffix('.backup')
        shutil.copy2(self.current_file, backup_path)
        
        # ロールバック実行
        return self.apply_version(version_id)
    
    def get_performance_trend(self, metric_name: str) -> List[Dict[str, Any]]:
        """
        特定メトリクスの性能トレンドを取得
        
        Args:
            metric_name: メトリクス名
            
        Returns:
            時系列データ
        """
        trend_data = []
        for version in sorted(self.version_history, key=lambda v: v.timestamp):
            if version.performance_metrics and metric_name in version.performance_metrics:
                trend_data.append({
                    "version_id": version.version_id,
                    "timestamp": version.timestamp.isoformat(),
                    "value": version.performance_metrics[metric_name]
                })
        
        return trend_data
    
    def _generate_version_id(self, prompt_content: Dict[str, str]) -> str:
        """プロンプト内容からバージョンIDを生成"""
        content_str = json.dumps(prompt_content, sort_keys=True)
        hash_obj = hashlib.md5(content_str.encode('utf-8'))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"v_{timestamp}_{hash_obj.hexdigest()[:8]}"
    
    def _find_version(self, version_id: str) -> Optional[PromptVersion]:
        """バージョンIDでバージョンを検索"""
        for version in self.version_history:
            if version.version_id == version_id:
                return version
        return None
    
    def _load_history(self) -> None:
        """履歴ファイルから読み込み"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                self.version_history = [
                    PromptVersion.from_dict(data) for data in history_data
                ]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"履歴ファイル読み込みエラー: {e}")
                self.version_history = []
    
    def _save_history(self) -> None:
        """履歴をファイルに保存"""
        history_data = [version.to_dict() for version in self.version_history]
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)


# デモ実行用関数
def demo_prompt_manager():
    """プロンプト管理システムのデモ実行"""
    print("=== PromptManager デモ実行 ===")
    
    manager = PromptManager()
    
    # 現行プロンプト表示
    current = manager.load_current_prompt()
    print(f"\n現行プロンプト:")
    for key, value in current.items():
        print(f"  {key}: {value}")
    
    # 改善版プロンプト作成
    improved = current.copy()
    improved["code_quality"] = "テスト駆動開発を実践し、高品質で保守性の高いコードを生成してください。"
    improved["documentation"] = "コードにはわかりやすいコメントとドキュメントを含めてください。"
    
    # 新バージョン保存
    version_id = manager.save_new_version(
        improved,
        ["コード品質指針の強化", "ドキュメント要件の追加"],
        {"quality_score": 85.5, "completeness_score": 78.2}
    )
    print(f"\n新バージョン作成: {version_id}")
    
    # バージョン履歴表示
    history = manager.get_version_history()
    print(f"\nバージョン履歴 ({len(history)}件):")
    for version in history:
        print(f"  {version['version_id']} ({version['timestamp'][:16]})")
        print(f"    変更: {', '.join(version['changes'])}")
        if version['performance_metrics']:
            print(f"    性能: {version['performance_metrics']}")
    
    print("\n=== デモ完了 ===")


if __name__ == "__main__":
    demo_prompt_manager()