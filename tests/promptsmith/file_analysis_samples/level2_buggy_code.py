# レベル2テスト: バグを含むコード（意図的）
import json
from typing import List

def process_user_data(users_json: str) -> List[str]:
    """
    ユーザーデータを処理してメール一覧を返す
    注意: このコードには複数のバグが含まれています
    """
    # バグ1: JSONデコードエラーハンドリングなし
    users = json.loads(users_json)
    
    email_list = []
    
    # バグ2: usersがListでない場合の処理なし
    for user in users:
        # バグ3: 'email'キーが存在しない場合の処理なし
        email = user['email']
        
        # バグ4: emailの妥当性チェックなし
        email_list.append(email)
        
        # バグ5: ログに個人情報を出力
        print(f"Processing user: {user['name']} - {email}")
    
    return email_list

def calculate_discount(price: float, discount_rate: float) -> float:
    """
    割引後の価格を計算
    注意: このコードにも問題があります
    """
    # バグ6: ゼロ除算チェックなし
    discount_amount = price * discount_rate / 100
    
    # バグ7: 負の値チェックなし
    final_price = price - discount_amount
    
    # バグ8: 浮動小数点の精度問題を考慮していない
    return final_price

class UserManager:
    """ユーザー管理クラス（バグあり）"""
    
    def __init__(self):
        # バグ9: 不適切なデフォルト引数（mutable default argument）
        self.users = []
        self._current_id = 0
    
    def add_user(self, name: str, email: str, roles=[]):
        """ユーザーを追加（問題のあるデフォルト引数）"""
        # バグ10: IDの重複チェックなし
        user_id = self._current_id
        self._current_id += 1
        
        # バグ11: rolesがmutable default argumentのため、
        # 同じリストオブジェクトが再利用される
        user = {
            'id': user_id,
            'name': name,
            'email': email,
            'roles': roles
        }
        
        self.users.append(user)
        return user_id
    
    def get_user_by_email(self, email: str):
        """メールアドレスでユーザーを検索"""
        # バグ12: 大文字小文字を区別してしまう
        for user in self.users:
            if user['email'] == email:
                return user
        
        # バグ13: 見つからない場合の処理が不明確
        return None
    
    def delete_user(self, user_id: int):
        """ユーザーを削除"""
        # バグ14: 非効率な削除処理（O(n)時間）
        for i, user in enumerate(self.users):
            if user['id'] == user_id:
                del self.users[i]
                return True
        
        # バグ15: 削除失敗時の例外を投げない
        return False

# バグ16: 実行時エラーを引き起こすテストコード
if __name__ == "__main__":
    # 壊れたJSONデータでテスト
    broken_json = '{"users": [{"name": "John", "email": "john@example.com"}]'  # 閉じ括弧なし
    
    try:
        emails = process_user_data(broken_json)
        print(f"Emails: {emails}")
    except Exception as e:
        print(f"Error occurred: {e}")
    
    # 負の割引率でテスト
    price = calculate_discount(100.0, -10.0)  # 負の割引率
    print(f"Price after discount: {price}")
    
    # UserManagerのバグを実証
    manager = UserManager()
    
    # 同じデフォルト引数の問題を実証
    user1_id = manager.add_user("Alice", "alice@example.com")
    user2_id = manager.add_user("Bob", "bob@example.com")
    
    # 最初のユーザーにロールを追加
    user1 = manager.get_user_by_email("alice@example.com")
    user1['roles'].append("admin")
    
    # 2番目のユーザーも同じroles参照を持つ問題
    user2 = manager.get_user_by_email("bob@example.com")
    print(f"User2 roles (should be empty but isn't): {user2['roles']}")