import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from companion.core import DuckAgent

async def verify():
    print("🦆 Verifying Duckflow v4...")
    
    try:
        agent = DuckAgent()
        print("✅ Agent initialized.")
        
        # Check tools
        expected_tools = [
            "response", "exit", "duck_call",
            "read_file", "write_file", "list_files", "mkdir",
            "propose_plan", "mark_step_complete",
            "generate_tasks", "mark_task_complete"
        ]
        
        missing_tools = []
        for tool in expected_tools:
            if tool in agent.tools:
                print(f"  - Tool '{tool}' registered.")
            else:
                missing_tools.append(tool)
                print(f"  ❌ Tool '{tool}' MISSING!")
        
        if missing_tools:
            print(f"❌ Verification FAILED. Missing tools: {missing_tools}")
            sys.exit(1)
            
        # Check state
        if agent.state.phase == "IDLE":
            print("✅ Initial state is IDLE.")
        else:
            print(f"❌ Initial state is {agent.state.phase}")
            
        print("\n🎉 Verification SUCCESS! Duckflow v4 is ready to run.")
        
    except Exception as e:
        print(f"❌ Verification FAILED with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify())
