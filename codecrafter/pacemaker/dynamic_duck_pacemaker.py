"""
Dynamic Duck Pacemaker - 動的制御機能を持つDuck Pacemaker
AIエージェントの動的ペース制御システム
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
from pathlib import Path

from .adaptive_loop_calculator import AdaptiveLoopCalculator, ContextComplexityAnalyzer, UserUrgencyEstimator
from ..services.task_classifier import TaskProfileType
from ..state.agent_state import AgentState, Vitals
from ..ui.rich_ui import rich_ui


@dataclass
class PerformanceRecord:
    """パフォーマンス記録"""
    task_profile: TaskProfileType
    loops_used: int
    max_loops_set: int
    success: bool
    execution_time: float
    vitals_start: Dict[str, float]
    vitals_end: Dict[str, float]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "task_profile": self.task_profile.value,
            "loops_used": self.loops_used,
            "max_loops_set": self.max_loops_set,
            "success": self.success,
            "execution_time": self.execution_time,
            "efficiency": self.loops_used / self.max_loops_set if self.max_loops_set > 0 else 0,
            "vitals_start": self.vitals_start,
            "vitals_end": self.vitals_end,
            "timestamp": self.timestamp.isoformat()
        }


class PerformanceTracker:
    """パフォーマンス追跡と学習機能"""
    
    def __init__(self, data_file: Optional[str] = None):
        self.data_file = Path(data_file) if data_file else Path("logs/duck_pacemaker_performance.jsonl")
        self.session_records: List[PerformanceRecord] = []
        self.success_patterns: Dict[str, Dict[str, Any]] = {}
        
        # データファイルのディレクトリを作成
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 既存データを読み込み
        self._load_historical_data()
    
    def record_session_start(
        self,
        task_profile: TaskProfileType,
        max_loops_set: int,
        vitals: Vitals
    ) -> str:
        """セッション開始を記録"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        # セッション開始情報を一時保存
        setattr(self, f"_temp_{session_id}", {
            "task_profile": task_profile,
            "max_loops_set": max_loops_set,
            "vitals_start": {
                "mood": vitals.mood,
                "focus": vitals.focus,
                "stamina": vitals.stamina
            },
            "start_time": datetime.now()
        })
        
        return session_id
    
    def record_session_end(
        self,
        session_id: str,
        loops_used: int,
        success: bool,
        vitals: Vitals
    ):
        """セッション終了を記録"""
        temp_key = f"_temp_{session_id}"
        if not hasattr(self, temp_key):
            rich_ui.print_warning(f"セッション開始データが見つかりません: {session_id}")
            return
        
        start_data = getattr(self, temp_key)
        execution_time = (datetime.now() - start_data["start_time"]).total_seconds()
        
        # パフォーマンス記録を作成
        record = PerformanceRecord(
            task_profile=start_data["task_profile"],
            loops_used=loops_used,
            max_loops_set=start_data["max_loops_set"],
            success=success,
            execution_time=execution_time,
            vitals_start=start_data["vitals_start"],
            vitals_end={
                "mood": vitals.mood,
                "focus": vitals.focus,
                "stamina": vitals.stamina
            },
            timestamp=datetime.now()
        )
        
        # 記録を保存
        self.session_records.append(record)
        self._save_record(record)
        
        # 成功パターンを更新
        self._update_success_patterns(record)
        
        # 一時データを削除
        delattr(self, temp_key)
        
        rich_ui.print_message(
            f"[PERFORMANCE] セッション記録完了: {record.task_profile.value} "
            f"({loops_used}/{start_data['max_loops_set']}ループ, "
            f"{'成功' if success else '失敗'})",
            "info"
        )
    
    def get_optimal_loops(self, task_profile: TaskProfileType) -> Optional[int]:
        """過去のデータから最適なループ数を推定"""
        relevant_records = [
            r for r in self.session_records
            if r.task_profile == task_profile and r.success
        ]
        
        if not relevant_records:
            return None
        
        # 成功セッションの統計
        loops_used = [r.loops_used for r in relevant_records]
        avg_loops = sum(loops_used) / len(loops_used)
        
        # 安全マージンを追加（20%）
        optimal_loops = int(avg_loops * 1.2)
        
        return max(optimal_loops, 2)  # 最小2回は確保
    
    def get_success_rate(self, task_profile: TaskProfileType) -> float:
        """タスクプロファイル別の成功率を取得"""
        relevant_records = [
            r for r in self.session_records
            if r.task_profile == task_profile
        ]
        
        if not relevant_records:
            return 0.8  # デフォルト成功率
        
        success_count = sum(1 for r in relevant_records if r.success)
        return success_count / len(relevant_records)
    
    def _load_historical_data(self):
        """過去のデータを読み込み"""
        if not self.data_file.exists():
            return
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        # 簡易的な統計情報として保存
                        task_profile = data.get("task_profile", "unknown")
                        if task_profile not in self.success_patterns:
                            self.success_patterns[task_profile] = {
                                "total_sessions": 0,
                                "successful_sessions": 0,
                                "avg_loops": 0,
                                "avg_efficiency": 0
                            }
        except Exception as e:
            rich_ui.print_warning(f"過去データの読み込みエラー: {e}")
    
    def _save_record(self, record: PerformanceRecord):
        """記録をファイルに保存"""
        try:
            with open(self.data_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            rich_ui.print_warning(f"パフォーマンス記録の保存エラー: {e}")
    
    def _update_success_patterns(self, record: PerformanceRecord):
        """成功パターンを更新"""
        task_key = record.task_profile.value
        
        if task_key not in self.success_patterns:
            self.success_patterns[task_key] = {
                "total_sessions": 0,
                "successful_sessions": 0,
                "avg_loops": 0,
                "avg_efficiency": 0
            }
        
        pattern = self.success_patterns[task_key]
        pattern["total_sessions"] += 1
        
        if record.success:
            pattern["successful_sessions"] += 1
        
        # 移動平均で更新
        alpha = 0.1  # 学習率
        pattern["avg_loops"] = (1 - alpha) * pattern["avg_loops"] + alpha * record.loops_used
        
        efficiency = record.loops_used / record.max_loops_set if record.max_loops_set > 0 else 0
        pattern["avg_efficiency"] = (1 - alpha) * pattern["avg_efficiency"] + alpha * efficiency


class DynamicDuckPacemaker:
    """動的制御機能を持つDuck Pacemaker"""
    
    def __init__(self):
        self.loop_calculator = AdaptiveLoopCalculator()
        self.performance_tracker = PerformanceTracker()
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
        
        # 設定
        self.learning_enabled = True
        self.adaptation_rate = 0.1
        
        rich_ui.print_message("[DUCK_PACEMAKER] 動的制御システム初期化完了", "info")
    
    def start_session(
        self,
        state: AgentState,
        task_profile: TaskProfileType
    ) -> Dict[str, Any]:
        """セッション開始と動的制限設定"""
        
        # コンテキスト分析
        context_complexity = ContextComplexityAnalyzer.analyze_complexity(state)
        user_urgency = UserUrgencyEstimator.estimate_urgency(state)
        
        # 過去の成功率を取得
        success_rate = self.performance_tracker.get_success_rate(task_profile)
        
        # 動的制限を計算
        calculation_result = self.loop_calculator.calculate_max_loops(
            task_profile=task_profile,
            vitals=state.vitals,
            user_urgency=user_urgency,
            context_complexity=context_complexity,
            success_rate=success_rate
        )
        
        # 状態を更新
        new_max_loops = calculation_result["max_loops"]
        state.graph_state.max_loops = new_max_loops
        
        # セッション追跡開始
        if self.learning_enabled:
            self.current_session_id = self.performance_tracker.record_session_start(
                task_profile=task_profile,
                max_loops_set=new_max_loops,
                vitals=state.vitals
            )
        
        self.session_start_time = datetime.now()
        
        # 結果をログ出力
        rich_ui.print_message(
            f"[DUCK_PACEMAKER] 動的制限設定完了:\n"
            f"  タスク: {task_profile.value}\n"
            f"  最大ループ: {new_max_loops}回 (ティア: {calculation_result['tier']})\n"
            f"  複雑度: {context_complexity:.2f}, 緊急度: {user_urgency:.2f}\n"
            f"  成功率: {success_rate:.2f}",
            "info"
        )
        
        return {
            "max_loops": new_max_loops,
            "calculation_result": calculation_result,
            "context_complexity": context_complexity,
            "user_urgency": user_urgency,
            "success_rate": success_rate
        }
    
    def end_session(
        self,
        state: AgentState,
        success: bool
    ):
        """セッション終了処理"""
        if not self.current_session_id or not self.learning_enabled:
            return
        
        # 実際に使用されたループ数を取得
        loops_used = state.graph_state.loop_count
        
        # パフォーマンス記録
        self.performance_tracker.record_session_end(
            session_id=self.current_session_id,
            loops_used=loops_used,
            success=success,
            vitals=state.vitals
        )
        
        # セッション情報をリセット
        self.current_session_id = None
        self.session_start_time = None
    
    def update_during_execution(
        self,
        state: AgentState,
        current_loop: int
    ) -> Dict[str, Any]:
        """実行中の動的更新"""
        
        # 現在の進捗率
        progress_rate = current_loop / state.graph_state.max_loops
        
        # バイタル状態の悪化チェック
        intervention = state.needs_duck_intervention()
        
        result = {
            "intervention_required": intervention["required"],
            "progress_rate": progress_rate,
            "vitals_status": state.vitals.get_health_status(),
            "recommendation": None
        }
        
        # 早期完了の推奨
        if (progress_rate > 0.5 and 
            state.vitals.stamina > 0.8 and 
            state.vitals.focus > 0.8):
            result["recommendation"] = "EARLY_COMPLETION_POSSIBLE"
        
        # 制限延長の推奨
        elif (progress_rate > 0.8 and 
              state.vitals.stamina > 0.5 and 
              not intervention["required"]):
            result["recommendation"] = "EXTENSION_POSSIBLE"
        
        return result
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """パフォーマンス要約を取得"""
        patterns = self.performance_tracker.success_patterns
        
        summary = {
            "total_task_types": len(patterns),
            "task_performance": {},
            "overall_stats": {
                "total_sessions": sum(p["total_sessions"] for p in patterns.values()),
                "overall_success_rate": 0.0,
                "avg_efficiency": 0.0
            }
        }
        
        if patterns:
            total_sessions = summary["overall_stats"]["total_sessions"]
            total_successful = sum(p["successful_sessions"] for p in patterns.values())
            
            if total_sessions > 0:
                summary["overall_stats"]["overall_success_rate"] = total_successful / total_sessions
                summary["overall_stats"]["avg_efficiency"] = sum(
                    p["avg_efficiency"] for p in patterns.values()
                ) / len(patterns)
            
            # タスク別詳細
            for task_type, pattern in patterns.items():
                if pattern["total_sessions"] > 0:
                    summary["task_performance"][task_type] = {
                        "success_rate": pattern["successful_sessions"] / pattern["total_sessions"],
                        "avg_loops": pattern["avg_loops"],
                        "avg_efficiency": pattern["avg_efficiency"],
                        "total_sessions": pattern["total_sessions"]
                    }
        
        return summary