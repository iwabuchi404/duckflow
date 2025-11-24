# TICKET-ID: DUCKFLOW-V4-004

**TITLE:** Fix Application Lifecycle in Debug Script

## 1. BACKGROUND

Analysis of conversation logs revealed that the root cause of the AI's "memory loss" is the debug script (`debug_dual_loop.py`) re-instantiating the core application logic (`EnhancedCompanionCoreV8` and `AgentState`) on every user input. 

This bug has invalidated previous tests of conversational context and state persistence. Fixing this is critical to enable proper testing and further development.

## 2. OBJECTIVE

Refactor `debug_dual_loop.py` to ensure that the `EnhancedCompanionCoreV8` and its `AgentState` are instantiated only **once** per session, outside the main input loop.

## 3. IMPLEMENTATION PLAN

The implementation AI shall perform the following task.

**File to Modify:** `debug_dual_loop.py`

**Task: Refactor the Main Loop**

1.  Locate the `while True:` loop within the `main` async function.
2.  Move the instantiation of `MockDualLoopSystem` and `EnhancedCompanionCoreV8` to **before** the `while True:` loop begins.
3.  The `while` loop should only contain the logic for receiving user input and calling the `process_user_message` method on the **existing** `core` instance that was created outside the loop.

### Code Example

**BEFORE (Problematic):**
```python
# D:\work\duckflow\debug_dual_loop.py

async def main():
    session_id = f"debug_session_{uuid.uuid4()}"
    # ...
    while True:
        try:
            user_message = input("👤 > ")
            # ...

            # Incorrect: Instances are created on every loop iteration
            dual_loop = MockDualLoopSystem(session_id)
            core = EnhancedCompanionCoreV8(dual_loop)
            
            response = await core.process_user_message(user_message)
            # ...
```

**AFTER (Corrected):**
```python
# D:\work\duckflow\debug_dual_loop.py

async def main():
    session_id = f"debug_session_{uuid.uuid4()}"
    print(f"--- 新しいデバッグセッションを開始: {session_id} ---")

    # Correct: Instances are created once, before the loop.
    dual_loop = MockDualLoopSystem(session_id)
    core = EnhancedCompanionCoreV8(dual_loop)

    while True:
        try:
            user_message = input("👤 > ")
            if user_message.lower() in ["exit", "quit"]:
                break

            # Correct: The existing core instance is reused.
            response = await core.process_user_message(user_message)
            print(f"🤖 < {response}")

        except Exception as e:
            print(f"エラーが発生しました: {e}")
```

## 4. ACCEPTANCE CRITERIA

1.  After running the corrected `debug_dual_loop.py`, the `WARNING - 会話履歴が存在しません` log **must not** appear after the first turn.
2.  The AI must demonstrate it remembers context from previous turns in a multi-turn conversation.
