# レベル2テスト: パフォーマンス問題を含むコード
import time
from typing import List, Dict

def inefficient_search(data: List[int], target: int) -> int:
    """
    非効率な線形検索の実装
    問題: ソートされたデータでも線形検索を使用
    """
    comparisons = 0
    for i, value in enumerate(data):
        comparisons += 1
        if value == target:
            print(f"Found after {comparisons} comparisons")
            return i
        # 不要な処理: すでに目標値を超えてもチェックを続行
        if value > target:
            continue  # binary search なら早期終了できる
    return -1

def slow_string_concatenation(strings: List[str]) -> str:
    """
    非効率な文字列結合
    問題: ループ内での文字列結合によりO(n²)時間計算量
    """
    result = ""
    for s in strings:
        # 每次连接都创建新字符串对象
        result += s + " "
        # 不必要的睡眠（デバッグ用？）
        time.sleep(0.001)  # 実際の処理では不要
    
    return result.strip()

class InefficiientDatabase:
    """非効率なデータベース操作のシミュレーション"""
    
    def __init__(self):
        # 問題: インデックスなしの大きなデータ構造
        self.users = []
        self.cache = {}  # キャッシュが適切に使用されていない
    
    def add_user(self, user: Dict):
        """ユーザー追加（重複チェックが非効率）"""
        # 問題: 每次添加都做全表扫描检查重复
        for existing_user in self.users:
            if existing_user['id'] == user['id']:
                raise ValueError("User already exists")
        
        self.users.append(user)
        # キャッシュを全クリア（過度）
        self.cache.clear()
    
    def find_users_by_name(self, name: str) -> List[Dict]:
        """名前でユーザー検索（非効率な実装）"""
        results = []
        
        # 問題: 毎回全データをスキャン
        for user in self.users:
            # 大文字小文字変換を毎回実行
            if user['name'].lower() == name.lower():
                # 深いコピーが不要なのに実行
                import copy
                results.append(copy.deepcopy(user))
        
        return results
    
    def get_user_statistics(self) -> Dict:
        """統計情報取得（重い処理）"""
        stats = {
            'total_users': len(self.users),
            'active_users': 0,
            'by_department': {},
            'average_age': 0
        }
        
        # 問題: 3回の反復でデータを処理（1回で済む）
        for user in self.users:
            if user.get('active', False):
                stats['active_users'] += 1
        
        for user in self.users:
            dept = user.get('department', 'Unknown')
            if dept in stats['by_department']:
                stats['by_department'][dept] += 1
            else:
                stats['by_department'][dept] = 1
        
        total_age = 0
        age_count = 0
        for user in self.users:
            if 'age' in user:
                total_age += user['age']
                age_count += 1
        
        if age_count > 0:
            stats['average_age'] = total_age / age_count
        
        return stats

def memory_leak_simulation(n: int):
    """
    メモリリークをシミュレーション
    問題: 大きなデータ構造を保持し続ける
    """
    # 全てのデータを保持する巨大なリスト
    all_data = []
    
    for i in range(n):
        # 不要に大きなデータ構造を作成
        large_dict = {
            'id': i,
            'data': [j for j in range(1000)],  # 1000要素のリスト
            'text': 'x' * 1000,  # 1000文字の文字列
            'nested': {
                'level1': {
                    'level2': {
                        'level3': [k for k in range(100)]
                    }
                }
            }
        }
        all_data.append(large_dict)
    
    # 処理完了後もデータを保持
    return len(all_data)  # 実際には全データが返されることが多い

def quadratic_algorithm(data: List[int]) -> List[List[int]]:
    """
    O(n²)アルゴリズムの例
    問題: より効率的な解法が存在する
    """
    pairs = []
    
    # ネストした二重ループ
    for i in range(len(data)):
        for j in range(len(data)):
            # 不要な重複チェック
            if i != j:
                # 每次都创建新元组
                pair = (data[i], data[j])
                
                # 非効率な重複チェック
                duplicate = False
                for existing_pair in pairs:
                    if (existing_pair[0] == pair[1] and 
                        existing_pair[1] == pair[0]):
                        duplicate = True
                        break
                
                if not duplicate:
                    pairs.append(pair)
    
    return pairs

# 使用例とパフォーマンステスト
if __name__ == "__main__":
    print("Performance issues demonstration:")
    
    # 非効率な検索テスト
    sorted_data = list(range(1000))
    start_time = time.time()
    result = inefficient_search(sorted_data, 500)
    end_time = time.time()
    print(f"Linear search took: {end_time - start_time:.4f}s")
    
    # 文字列結合テスト
    strings = ["hello"] * 100
    start_time = time.time()
    concatenated = slow_string_concatenation(strings)
    end_time = time.time()
    print(f"String concatenation took: {end_time - start_time:.4f}s")
    
    # データベース操作テスト
    db = InefficiientDatabase()
    for i in range(100):
        db.add_user({'id': i, 'name': f'User{i}', 'department': f'Dept{i%5}'})
    
    start_time = time.time()
    users = db.find_users_by_name("User50")
    end_time = time.time()
    print(f"Database search took: {end_time - start_time:.4f}s")
    
    # メモリ使用量テスト（小規模）
    memory_result = memory_leak_simulation(10)
    print(f"Memory test completed with {memory_result} items")