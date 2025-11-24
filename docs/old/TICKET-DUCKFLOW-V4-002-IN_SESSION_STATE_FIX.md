# TICKET-ID: DUCKFLOW-V4-002

**TITLE:** In-Session State Corruption During Error Recovery

## 1. BACKGROUND

Analysis of conversation logs revealed a critical issue where the AI loses context within a single session, causing it to enter repetitive loops. The root cause has been identified in the error recovery mechanism within `companion/enhanced_core_v8.py`.

When an internal tool (e.g., `prompt_compiler`) raises an exception, the main `process_message` loop catches it and attempts to recover. However, the current recovery logic inadvertently resets or replaces the `AgentState` object. This wipes the conversation history that was recorded just moments before, leading to the `WARNING - 会話履歴が存在しません` log during the retry attempt. The result is a failure to maintain a coherent conversational flow.

## 2. OBJECTIVE

The goal of this task is to make the in-session state management robust. The `AgentState` instance must remain intact and consistent throughout the entire lifecycle of a single `process_message` call, including all error handling and recovery paths.

## 3. IMPLEMENTATION PLAN

The implementation AI shall perform the following tasks.

### 3.1. Refactor Core Error Handling

**File to Modify:** `companion/enhanced_core_v8.py`

1.  **Locate the Primary `try...except` Block:** In the `process_message` method, identify the exception handler that is responsible for catching errors from tool execution (e.g., calls to `self.user_response_tool` or `self.generate_hierarchical_plan`).
2.  **Analyze the Recovery Logic:** Scrutinize the code within the `except` block. It is highly likely that the logic here is causing the state to be lost.
3.  **Ensure State Persistence:** Modify the `except` block to ensure that any recovery or retry attempts are performed using the **original `self.state` instance**. The state object must not be re-initialized. If recovery involves calling helper functions, pass `self.state` explicitly to ensure the correct context is used.

**Example (Conceptual):**

```python
# --- BEFORE (Conceptual Problem) ---
except Exception as e:
    logger.error(f"An error occurred: {e}")
    # Problem: This recovery call might implicitly use a new, fresh state.
    await self.recover_from_error(user_message) 

# --- AFTER (Conceptual Solution) ---
except Exception as e:
    logger.error(f"An error occurred: {e}")
    # Solution: Explicitly pass the current state to the recovery function.
    await self.recover_from_error(user_message, current_state=self.state)
```

### 3.2. (Secondary) Improve Prompt Compiler Robustness

To prevent the initial error from occurring in the first place, let's add defensive coding.

**File to Modify:** `companion/prompts/prompt_compiler.py`

1.  **Identify the Failure Point:** The log shows the error is `AttributeError: 'str' object has no attribute 'get'`. This indicates a variable was expected to be a dictionary but was a string. Find where a `.get()` call is made.
2.  **Add Type Checking:** Before calling `.get()` on a variable, add a check to ensure it is a dictionary. If it's a string (e.g., an unparsed JSON string), log a detailed warning and either attempt to parse it with `json.loads` in a `try-except` block or return a safe default value. This will prevent the exception that triggers the faulty recovery logic.

## 4. ACCEPTANCE CRITERIA

1.  The system no longer produces the `WARNING - 会話履歴が存在しません` log on a retry attempt within the same turn.
2.  When an internal error occurs, the system recovers gracefully *without* losing the conversation history from the current turn.
3.  A multi-turn conversation can be held successfully without the AI looping back to the initial planning stage.
