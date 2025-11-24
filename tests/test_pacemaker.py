import unittest
from unittest.mock import MagicMock
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from companion.modules.pacemaker import DuckPacemaker
from companion.state.agent_state import AgentState, Action, Vitals

class TestDuckPacemaker(unittest.TestCase):
    def setUp(self):
        self.state = AgentState()
        self.pacemaker = DuckPacemaker(self.state)
        
    def test_stagnation_detection_same_action(self):
        """同じアクションとパラメータの繰り返しを検知"""
        action = Action(name="read_file", parameters={"path": "test.txt"}, thought="reading")
        
        # 1回目
        self.pacemaker.update_vitals(action, "content", False)
        self.assertFalse(self.pacemaker._detect_stagnation())
        
        # 2回目
        self.pacemaker.update_vitals(action, "content", False)
        self.assertFalse(self.pacemaker._detect_stagnation())
        
        # 3回目 (検知されるはず)
        self.pacemaker.update_vitals(action, "content", False)
        self.assertTrue(self.pacemaker._detect_stagnation())
        
    def test_stagnation_detection_same_result(self):
        """同じ結果の繰り返しを検知"""
        action1 = Action(name="cmd1", parameters={"p": "1"}, thought="t1")
        action2 = Action(name="cmd2", parameters={"p": "2"}, thought="t2")
        action3 = Action(name="cmd3", parameters={"p": "3"}, thought="t3")
        
        result = "Error: File not found"
        
        self.pacemaker.update_vitals(action1, result, True)
        self.pacemaker.update_vitals(action2, result, True)
        self.pacemaker.update_vitals(action3, result, True)
        
        self.assertTrue(self.pacemaker._detect_stagnation())

    def test_error_cascade_consecutive(self):
        """連続エラー検知"""
        action = Action(name="test", parameters={}, thought="test")
        
        self.pacemaker.update_vitals(action, "error", True)
        self.pacemaker.update_vitals(action, "error", True)
        self.pacemaker.update_vitals(action, "error", True)
        
        self.assertTrue(self.pacemaker._detect_error_cascade())
        
    def test_error_cascade_frequent(self):
        """頻発エラー検知"""
        action = Action(name="test", parameters={}, thought="test")
        
        # 10回中5回エラー
        for i in range(5):
            self.pacemaker.update_vitals(action, "success", False)
        for i in range(5):
            self.pacemaker.update_vitals(action, "error", True)
            
        self.assertTrue(self.pacemaker._detect_error_cascade())

if __name__ == "__main__":
    unittest.main()
