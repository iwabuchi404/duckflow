import asyncio
import sys
import os
sys.path.append(os.getcwd())

from companion.state.agent_state import AgentState, Plan
from companion.tools.task_tool import TaskTool
from companion.tools.results import format_symops_response, ToolResult, ToolStatus, serialize_to_text

async def test_generate_tasks_output():
    state = AgentState()
    state.current_plan = Plan(goal="Test generating tasks")
    state.current_plan.add_step("Step 1", "Create a file and run it")
    
    # Mock LLM client just for this test
    class MockLLM:
        async def chat(self, messages, response_model=None):
            return type('Proposal', (), {
                'tasks': [
                    {"title": "Task 1", "description": "Desc 1", "action": {"name": "write_file", "parameters": {"path": "t1.txt", "content": "hello"}}},
                    {"title": "Task 2", "description": "Desc 2"}
                ]
            })
    
    tool = TaskTool(state, MockLLM())
    result = await tool.generate_tasks()
    
    print("Direct Tool Result (List):")
    print(result)
    
    # Simulate core.py formatting
    tool_res = ToolResult(
        status=ToolStatus.OK,
        tool_name="generate_tasks",
        target="task",
        content=result
    )
    formatted = format_symops_response(tool_res)
    
    print("\nFormatted Sym-Ops Response for LLM:")
    print(formatted)
    
    print("\nSerialized for Console:")
    print(serialize_to_text(result))

if __name__ == "__main__":
    asyncio.run(test_generate_tasks_output())
