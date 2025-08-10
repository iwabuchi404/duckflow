#!/usr/bin/env python3
"""
Duckflow á¤ó¨óÈêüİ¤óÈ
4ÎüÉq¢ü­Æ¯ÁãH
"""
import sys
import os

# ×í¸§¯ÈëüÈ’Ñ¹kı 
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# ‡W¨ó³üÇ£ó°-š
os.environ['PYTHONIOENCODING'] = 'utf-8'

if __name__ == "__main__":
    try:
        from codecrafter.main_v2 import main
        
        print("=€ Duckflow v0.3.0-alpha - 4ÎüÉqAI³üÇ£ó°¨ü¸§óÈ")
        print("=¡ Å1Tí¹OL’ãzW_Ÿ(„jAI‹zÑüÈÊü")
        print("= 4ÎüÉÕíü: ãû; ’ Å1ÎÆ ’ ‰hŸL ’ U¡û™š")
        print()
        
        main()
        
    except ImportError as e:
        print(f"L ¤óİüÈ¨éü: {e}")
        print("X¢Â’¤ó¹ÈüëWfO`UD: uv sync")
        sys.exit(1)
    except Exception as e:
        print(f"L wÕ¨éü: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)