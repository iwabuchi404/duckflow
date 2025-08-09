# レベル1テスト: 単純なPython関数
def calculate_area(width, height):
    """
    長方形の面積を計算する関数
    
    Args:
        width (float): 横幅
        height (float): 縦幅
    
    Returns:
        float: 面積
    """
    return width * height

if __name__ == "__main__":
    # テスト実行
    area = calculate_area(10.0, 5.0)
    print(f"面積: {area}")