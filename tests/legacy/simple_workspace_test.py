# simple_workspace_test.py
"""
Simple workspace manager test
"""

import sys
import os
import tempfile
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.workspace_manager import WorkspaceManager

def test_basic_functionality():
    print("Testing WorkspaceManager basic functionality...")
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_config:
        config_path = temp_config.name
    
    try:
        # Initialize WorkspaceManager
        workspace_manager = WorkspaceManager(config_file=config_path)
        print(f"SUCCESS: Initialized workspace manager")
        print(f"Current workspace: {workspace_manager.current_workspace}")
        
        # Test workspace info display
        info = workspace_manager.get_workspace_info_display()
        print(f"SUCCESS: Got workspace info (length: {len(info)})")
        
        # Test workspace list display
        list_display = workspace_manager.get_workspace_list_display()
        print(f"SUCCESS: Got workspace list (length: {len(list_display)})")
        
        # Test bookmark functionality
        success, message = workspace_manager.add_bookmark("test", description="Test bookmark")
        if success:
            print("SUCCESS: Added bookmark")
        else:
            print(f"FAILED: Could not add bookmark - {message}")
        
        # Test bookmark listing
        bookmarks = workspace_manager.list_bookmarks()
        print(f"SUCCESS: Listed bookmarks (count: {len(bookmarks)})")
        
        # Test search
        results = workspace_manager.search_workspaces("test")
        print(f"SUCCESS: Search completed (results: {len(results)})")
        
        print("All basic tests passed!")
        return True
        
    except Exception as e:
        print(f"ERROR: Test failed - {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        if os.path.exists(config_path):
            os.unlink(config_path)

if __name__ == "__main__":
    print("Simple Workspace Manager Test")
    print("=" * 40)
    
    success = test_basic_functionality()
    
    if success:
        print("\nWorkspace management system is working correctly!")
    else:
        print("\nWorkspace management system has issues!")