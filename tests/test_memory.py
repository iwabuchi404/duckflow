import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from companion.modules.memory import MemoryManager
from companion.base.llm_client import LLMClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Mock LLM Client
class MockLLMClient(LLMClient):
    def __init__(self):
        pass
        
    async def chat(self, messages, response_model=None, **kwargs):
        print(f"Mock LLM called with {len(messages)} messages")
        return {"summary": "This is a mock summary of the conversation."}

async def test_memory_manager():
    print("Testing MemoryManager...")
    
    # Initialize with token limit that triggers pruning but not emergency mode
    # Assuming avg 50 chars per message -> 25 tokens
    # 30 messages * 25 = 750 tokens
    # Set max_tokens to 1000 to trigger pruning (845/1000 = 84.5%)
    mock_llm = MockLLMClient()
    memory = MemoryManager(llm_client=mock_llm, max_tokens=1000)  
    
    # Create dummy history
    history = []
    # 10 low importance messages (should be pruned)
    for i in range(10):
        history.append({"role": "assistant", "content": f"System log entry {i}: Routine check completed. No issues found."})
    
    # 10 high importance messages (should be kept)
    for i in range(10):
        history.append({"role": "user", "content": f"Critical instruction {i}: Please execute this task immediately."})
        history.append({"role": "assistant", "content": f"Task {i} completed successfully. Result: Success."})
    
    print(f"Initial history length: {len(history)}")
    initial_tokens = memory._estimate_tokens(history)
    print(f"Initial tokens: {initial_tokens}")
    
    # Check pruning
    if memory.should_prune(history):
        print("Pruning needed (Expected)")
        pruned_history, stats = await memory.prune_history(history)
        
        print(f"Pruned history length: {len(pruned_history)}")
        print(f"Final tokens: {stats['final_tokens']}")
        print(f"Removed messages: {stats['removed_count']}")
        
        # Print first few messages to see what happened
        print("--- Pruned History Start ---")
        for i, msg in enumerate(pruned_history[:5]):
             print(f"Msg {i}: {msg['role']} - {msg['content'][:50]}...")
        print("--- Pruned History End ---")
        
        # Check if summary was inserted
        has_summary = any("要約" in msg["content"] or "summary" in msg["content"] for msg in pruned_history)
        if has_summary:
            print("Summary inserted (Expected)")
        else:
            print("Summary NOT inserted (Unexpected)")
            
        # Check if recent messages are kept
        last_msg = pruned_history[-1]
        if "Task 9" in last_msg["content"]:
            print("Recent message kept (Expected)")
        else:
            print("Recent message lost (Unexpected)")
            
    else:
        print("Pruning NOT needed (Unexpected)")

if __name__ == "__main__":
    asyncio.run(test_memory_manager())
