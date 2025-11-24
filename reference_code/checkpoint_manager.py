"""
Checkpoint Manager - チェックポイント機能
Step 2: タスク実行中の中間状態保存・復元機能
"""

import json
import pickle
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class Checkpoint:
    """チェックポイントデータ"""
    checkpoint_id: str
    task_id: str
    task_description: str
    step_number: int
    total_steps: int
    progress: float  # 0.0-1.0
    state_data: Dict[str, Any]
    created_at: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "task_description": self.task_description,
            "step_number": self.step_number,
            "total_steps": self.total_steps,
            "progress": self.progress,
            "state_data": self.state_data,
            "created_at": self.created_at.isoformat(),
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """辞書からCheckpointを復元"""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            task_id=data["task_id"],
            task_description=data["task_description"],
            step_number=data["step_number"],
            total_steps=data["total_steps"],
            progress=data["progress"],
            state_data=data["state_data"],
            created_at=datetime.fromisoformat(data["created_at"]),
            context=data.get("context", {})
        )


class CheckpointManager:
    """Step 2: チェックポイント管理クラス"""
    
    def __init__(self, checkpoint_dir: Optional[str] = None):
        """初期化
        
        Args:
            checkpoint_dir: チェックポイント保存ディレクトリ
        """
        if checkpoint_dir:
            self.checkpoint_dir = Path(checkpoint_dir)
        else:
            self.checkpoint_dir = Path.cwd() / ".duckflow_checkpoints"
        
        # ディレクトリを作成
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # メモリ上のチェックポイント
        self.checkpoints: Dict[str, Checkpoint] = {}
        self.max_checkpoints = 10  # 最大保持数
    
    def create_checkpoint(self, task_id: str, task_description: str, 
                         step_number: int, total_steps: int, 
                         state_data: Dict[str, Any],
                         context: Optional[Dict[str, Any]] = None) -> str:
        """チェックポイントを作成
        
        Args:
            task_id: タスクID
            task_description: タスクの説明
            step_number: 現在のステップ番号
            total_steps: 総ステップ数
            state_data: 保存する状態データ
            context: 追加のコンテキスト情報
            
        Returns:
            str: 作成されたチェックポイントID
        """
        import uuid
        
        checkpoint_id = f"cp_{task_id}_{step_number}_{int(time.time())}"
        progress = step_number / total_steps if total_steps > 0 else 0.0
        
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            task_description=task_description,
            step_number=step_number,
            total_steps=total_steps,
            progress=progress,
            state_data=state_data,
            created_at=datetime.now(),
            context=context or {}
        )
        
        # メモリに保存
        self.checkpoints[checkpoint_id] = checkpoint
        
        # ファイルに永続化
        self._save_checkpoint_to_file(checkpoint)
        
        # 古いチェックポイントをクリーンアップ
        self._cleanup_old_checkpoints(task_id)
        
        return checkpoint_id
    
    def restore_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """チェックポイントを復元
        
        Args:
            checkpoint_id: チェックポイントID
            
        Returns:
            Optional[Checkpoint]: 復元されたチェックポイント
        """
        # メモリから取得
        if checkpoint_id in self.checkpoints:
            return self.checkpoints[checkpoint_id]
        
        # ファイルから読み込み
        checkpoint = self._load_checkpoint_from_file(checkpoint_id)
        if checkpoint:
            self.checkpoints[checkpoint_id] = checkpoint
        
        return checkpoint
    
    def get_latest_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """タスクの最新チェックポイントを取得
        
        Args:
            task_id: タスクID
            
        Returns:
            Optional[Checkpoint]: 最新のチェックポイント
        """
        task_checkpoints = [
            cp for cp in self.checkpoints.values() 
            if cp.task_id == task_id
        ]
        
        if not task_checkpoints:
            # ファイルからも探す
            task_checkpoints = self._load_task_checkpoints_from_files(task_id)
        
        if task_checkpoints:
            return max(task_checkpoints, key=lambda cp: cp.created_at)
        
        return None
    
    def list_checkpoints(self, task_id: Optional[str] = None) -> List[Checkpoint]:
        """チェックポイント一覧を取得
        
        Args:
            task_id: 特定のタスクIDでフィルター（オプション）
            
        Returns:
            List[Checkpoint]: チェックポイントのリスト
        """
        checkpoints = list(self.checkpoints.values())
        
        if task_id:
            checkpoints = [cp for cp in checkpoints if cp.task_id == task_id]
        
        return sorted(checkpoints, key=lambda cp: cp.created_at, reverse=True)
    
    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """チェックポイントを削除
        
        Args:
            checkpoint_id: チェックポイントID
            
        Returns:
            bool: 削除に成功した場合True
        """
        # メモリから削除
        if checkpoint_id in self.checkpoints:
            del self.checkpoints[checkpoint_id]
        
        # ファイルから削除
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
            return True
        
        return False
    
    def cleanup_task_checkpoints(self, task_id: str) -> int:
        """タスクのすべてのチェックポイントを削除
        
        Args:
            task_id: タスクID
            
        Returns:
            int: 削除されたチェックポイント数
        """
        deleted_count = 0
        
        # メモリから削除
        to_delete = [
            cp_id for cp_id, cp in self.checkpoints.items() 
            if cp.task_id == task_id
        ]
        
        for cp_id in to_delete:
            if self.delete_checkpoint(cp_id):
                deleted_count += 1
        
        return deleted_count
    
    def _save_checkpoint_to_file(self, checkpoint: Checkpoint) -> None:
        """チェックポイントをファイルに保存"""
        try:
            checkpoint_file = self.checkpoint_dir / f"{checkpoint.checkpoint_id}.json"
            
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"チェックポイント保存エラー: {e}")
    
    def _load_checkpoint_from_file(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """ファイルからチェックポイントを読み込み"""
        try:
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
            
            if not checkpoint_file.exists():
                return None
            
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return Checkpoint.from_dict(data)
                
        except Exception as e:
            print(f"チェックポイント読み込みエラー: {e}")
            return None
    
    def _load_task_checkpoints_from_files(self, task_id: str) -> List[Checkpoint]:
        """タスクのチェックポイントをファイルから読み込み"""
        checkpoints = []
        
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                checkpoint = self._load_checkpoint_from_file(checkpoint_file.stem)
                if checkpoint and checkpoint.task_id == task_id:
                    checkpoints.append(checkpoint)
                    
        except Exception as e:
            print(f"チェックポイントファイル読み込みエラー: {e}")
        
        return checkpoints
    
    def _cleanup_old_checkpoints(self, task_id: str) -> None:
        """古いチェックポイントをクリーンアップ"""
        task_checkpoints = [
            cp for cp in self.checkpoints.values() 
            if cp.task_id == task_id
        ]
        
        if len(task_checkpoints) > self.max_checkpoints:
            # 古いものから削除
            sorted_checkpoints = sorted(task_checkpoints, key=lambda cp: cp.created_at)
            to_delete = sorted_checkpoints[:-self.max_checkpoints]
            
            for checkpoint in to_delete:
                self.delete_checkpoint(checkpoint.checkpoint_id)
    
    def get_summary(self) -> Dict[str, Any]:
        """チェックポイント管理の概要を取得"""
        task_counts = {}
        for checkpoint in self.checkpoints.values():
            task_id = checkpoint.task_id
            task_counts[task_id] = task_counts.get(task_id, 0) + 1
        
        return {
            "total_checkpoints": len(self.checkpoints),
            "task_counts": task_counts,
            "checkpoint_dir": str(self.checkpoint_dir),
            "max_checkpoints": self.max_checkpoints
        }