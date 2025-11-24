#!/usr/bin/env python3
"""
Duckflow対話品質テスト スクリプト
"""
import sys
import json
import time
from datetime import datetime
from typing import List, Dict, Any
sys.path.append('.')

from codecrafter.main_v2 import DuckflowAgentV2
from codecrafter.base.config import config_manager
from codecrafter.state.agent_state import AgentState

class DialogueQualityTester:
    """対話品質テストクラス"""
    
    def __init__(self):
        """テスターを初期化"""
        self.config = config_manager.load_config()
        self.test_results = []
        self.start_time = datetime.now()
        
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """包括的な対話品質テストを実行"""
        print("=== Duckflow対話品質テスト開始 ===")
        print(f"開始時刻: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"LLMプロバイダー: {self.config.llm.provider}")
        print()
        
        # テストケース定義
        test_cases = [
            {
                'id': 1,
                'category': '基本対話',
                'description': 'シンプルな質問応答テスト',
                'input': 'こんにちは、あなたは何ができますか？',
                'expected_features': ['greeting', 'capabilities_explanation']
            },
            {
                'id': 2, 
                'category': 'ファイル確認要求',
                'description': 'RoutingEngine決定論的ルーティングテスト',
                'input': 'CLAUDE.mdの内容を確認してください',
                'expected_features': ['file_read_request', 'routing_engine_trigger']
            },
            {
                'id': 3,
                'category': '日本語ファイル名',
                'description': '日本語ファイル名処理テスト',
                'input': 'プログレス・レポート.mdというファイルがあるか確認してください',
                'expected_features': ['japanese_filename_support', 'file_existence_check']
            },
            {
                'id': 4,
                'category': 'プロジェクト分析',
                'description': 'RAG統合プロジェクト理解テスト',
                'input': 'このプロジェクトの主要な機能とアーキテクチャを分析してください',
                'expected_features': ['rag_integration', 'project_analysis', 'architecture_understanding']
            },
            {
                'id': 5,
                'category': '複雑指示',
                'description': 'LangGraph複数ステップ処理テスト', 
                'input': 'codecrafterディレクトリの構造を確認して、重要なPythonファイルを特定し、それらの役割を説明してください',
                'expected_features': ['multi_step_processing', 'directory_analysis', 'code_understanding']
            }
        ]
        
        # 各テストケースを実行
        for i, test_case in enumerate(test_cases, 1):
            print(f"🧪 テスト {i}/{len(test_cases)}: {test_case['category']}")
            print(f"   {test_case['description']}")
            print(f"   入力: {test_case['input']}")
            
            result = self.execute_single_test(test_case)
            self.test_results.append(result)
            
            print(f"   結果: {'✅ 成功' if result['success'] else '❌ 失敗'}")
            if not result['success']:
                print(f"   エラー: {result.get('error', '不明なエラー')}")
            print()
            
            # テスト間の間隔
            time.sleep(2)
        
        # 結果集計
        summary = self.generate_summary()
        self.save_results(summary)
        
        return summary
    
    def execute_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """単一テストケースを実行"""
        test_result = {
            'test_id': test_case['id'],
            'category': test_case['category'],
            'input': test_case['input'],
            'start_time': datetime.now(),
            'success': False,
            'response': None,
            'error': None,
            'execution_time': 0,
            'routing_decision': None,
            'features_detected': []
        }
        
        try:
            # 新しいエージェントセッションを開始
            agent = DuckflowAgentV2()
            
            # テスト実行
            start_time = time.time()
            
            # エージェントにメッセージを送信（LangGraph経由）
            agent._handle_orchestrated_conversation(test_case['input'])
            
            # 最新のAI応答を取得
            recent_messages = agent.state.get_recent_messages(1)
            if recent_messages and recent_messages[-1].role == 'assistant':
                response = recent_messages[-1].content
            else:
                response = "応答なし"
            
            end_time = time.time()
            test_result['execution_time'] = end_time - start_time
            test_result['response'] = response
            test_result['success'] = True
            
            # エージェント状態から詳細情報を取得
            if hasattr(agent, 'state'):
                # RoutingEngineの決定を確認
                if hasattr(agent.orchestrator, 'routing_engine'):
                    try:
                        routing_decision = agent.orchestrator.routing_engine.analyze_user_intent(
                            test_case['input'], []
                        )
                        test_result['routing_decision'] = {
                            'needs_file_read': routing_decision.needs_file_read,
                            'needs_file_list': routing_decision.needs_file_list,
                            'target_files': routing_decision.target_files,
                            'confidence': routing_decision.confidence,
                            'routing_reason': routing_decision.routing_reason
                        }
                    except Exception as e:
                        test_result['routing_decision'] = f"RoutingEngine error: {e}"
                
                # 実行されたツール履歴
                if hasattr(agent.state, 'tool_executions'):
                    test_result['tools_executed'] = [
                        {
                            'tool_name': tool.tool_name,
                            'success': not bool(tool.error)
                        }
                        for tool in agent.state.tool_executions[-5:]  # 最新5件
                    ]
            
            # 期待される機能の検出
            test_result['features_detected'] = self.detect_features(
                test_case['input'], 
                response, 
                test_result.get('routing_decision'),
                test_case.get('expected_features', [])
            )
            
        except Exception as e:
            test_result['error'] = str(e)
            test_result['success'] = False
        
        test_result['end_time'] = datetime.now()
        return test_result
    
    def detect_features(self, input_text: str, response: str, routing_decision: Any, expected: List[str]) -> List[str]:
        """応答から機能の動作を検出"""
        detected = []
        
        # 基本的な応答チェック
        if response and len(response.strip()) > 0:
            detected.append('response_generated')
        
        # ファイル操作検出
        if 'FILE_OPERATION:READ' in response:
            detected.append('file_read_operation')
        elif 'FILE_OPERATION:' in response:
            detected.append('file_operation')
        
        # RoutingEngine機能検出
        if routing_decision and isinstance(routing_decision, dict):
            if routing_decision.get('needs_file_read'):
                detected.append('routing_engine_file_detection')
            if routing_decision.get('confidence', 0) > 0.8:
                detected.append('high_confidence_routing')
        
        # 日本語処理検出
        if any(char in input_text for char in 'あいうえおかきくけこ'):
            detected.append('japanese_processing')
        
        # プロジェクト理解検出
        if any(keyword in response.lower() for keyword in ['architecture', 'structure', 'module', 'component']):
            detected.append('project_understanding')
        
        return detected
    
    def generate_summary(self) -> Dict[str, Any]:
        """テスト結果の要約を生成"""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result['success'])
        
        summary = {
            'test_session': {
                'start_time': self.start_time,
                'end_time': datetime.now(),
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'success_rate': successful_tests / total_tests if total_tests > 0 else 0,
                'llm_provider': self.config.llm.provider
            },
            'category_results': {},
            'feature_analysis': {},
            'performance_metrics': {
                'average_response_time': sum(r['execution_time'] for r in self.test_results) / total_tests,
                'fastest_response': min(r['execution_time'] for r in self.test_results),
                'slowest_response': max(r['execution_time'] for r in self.test_results)
            },
            'detailed_results': self.test_results
        }
        
        # カテゴリ別結果
        for result in self.test_results:
            category = result['category']
            if category not in summary['category_results']:
                summary['category_results'][category] = {'total': 0, 'successful': 0}
            
            summary['category_results'][category]['total'] += 1
            if result['success']:
                summary['category_results'][category]['successful'] += 1
        
        # 機能検出分析
        all_features = []
        for result in self.test_results:
            all_features.extend(result.get('features_detected', []))
        
        from collections import Counter
        feature_counts = Counter(all_features)
        summary['feature_analysis'] = dict(feature_counts)
        
        return summary
    
    def save_results(self, summary: Dict[str, Any]):
        """結果をファイルに保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'logs/dialogue_quality_test_{timestamp}.json'
        
        try:
            import os
            os.makedirs('logs', exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"📊 テスト結果を保存: {filename}")
        except Exception as e:
            print(f"⚠️ 結果保存失敗: {e}")

def main():
    """メイン実行関数"""
    tester = DialogueQualityTester()
    summary = tester.run_comprehensive_test()
    
    # 結果表示
    print("=== テスト結果サマリー ===")
    session = summary['test_session']
    print(f"実行時間: {session['end_time'] - session['start_time']}")
    print(f"成功率: {session['successful_tests']}/{session['total_tests']} ({session['success_rate']:.1%})")
    print(f"平均応答時間: {summary['performance_metrics']['average_response_time']:.2f}秒")
    print()
    
    print("カテゴリ別結果:")
    for category, results in summary['category_results'].items():
        success_rate = results['successful'] / results['total']
        print(f"  {category}: {results['successful']}/{results['total']} ({success_rate:.1%})")
    print()
    
    print("検出された機能:")
    for feature, count in summary['feature_analysis'].items():
        print(f"  {feature}: {count}回検出")
    
    return summary

if __name__ == "__main__":
    main()