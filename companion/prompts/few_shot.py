"""
Compressed & Categorized Few-shot Examples for Sym-Ops v3.2
"""

# Common Base Examples (Always included)
BASE_EXAMPLES = [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": """\
>> User greeted. Respond simply.
::c1.0 ::s1.0 ::m0.0 ::f1.0
::response @Hello! How can I help you code today?"""}
]

# Task/Edit Specific Examples
TASK_EXAMPLES = [
    {"role": "user", "content": "Add a docstring to main in hello.py"},
    {"role": "assistant", "content": """\
>> Reading hello.py to see the current main() definition.
::c0.9 ::s1.0 ::m0.1 ::f0.9
::read_file @hello.py"""},
    {"role": "assistant", "content": """\
::result ok
1| def main():
2|     print('Hi')"""},
    {"role": "assistant", "content": """\
>> Found main(). Adding docstring.
::c1.0 ::s1.0 ::m0.2 ::f1.0
::edit_file @hello.py
<<<
<<<<<<< SEARCH
def main():
    print('Hi')
=======
def main():
    \"\"\"Entry point.\"\"\"
    print('Hi')
>>>>>>> REPLACE
>>>"""}
]

# Self-Correction Example
CORRECTION_EXAMPLES = [
    {"role": "user", "content": "Update the print message in hello.py"},
    {"role": "assistant", "content": """\
>> Reading file content.
::c0.9 ::s1.0 ::m0.1 ::f0.9
::read_file @hello.py"""},
    {"role": "assistant", "content": """\
::result ok
1| def main():
2|     print('Old Message')"""},
    {"role": "assistant", "content": """\
>> Replacing the old print message.
::c1.0 ::s1.0 ::m0.2 ::f1.0
::edit_file @hello.py
<<<
<<<<<<< SEARCH
    print('Old Message')
=======
    print('New Message')
>>>>>>> REPLACE
>>>"""}
]

# Recovery Examples: edit_file 失敗 or 意図しない結果 → write_file で全書き直し
RECOVERY_EXAMPLES = [
    {"role": "user", "content": "fix_func の引数名を items から values に変える"},
    {"role": "assistant", "content": """\
>> Reading file to get exact content before editing.
::c0.9 ::s1.0 ::m0.1 ::f0.9
::read_file @utils.py"""},
    {"role": "user", "content": """\
::result ok
1| def fix_func(items: list) -> list:
2|     return [x * 2 for x in items]"""},
    {"role": "assistant", "content": """\
>> Renaming parameter items -> values.
::c1.0 ::s1.0 ::m0.2 ::f1.0
::edit_file @utils.py
<<<
<<<<<<< SEARCH
def fix_func(items: list) -> list:
    return [x * 2 for x in items]
=======
def fix_func(values: list) -> list:
    return [x * 2 for x in values]
>>>>>>> REPLACE
>>>"""},
    {"role": "user", "content": """\
::result error
Reason: find_not_matched (Edit 1)
Candidates near the first line of 'find':
  - line 1: "def fix_func(items: list) -> list:"
Detailed Diff with closest candidate (Line 1):
- def fix_func(items: list) -> list:
+ def fix_func(items: list) -> list:"""},
    {"role": "assistant", "content": """\
>> find_not_matched. Re-reading file to check exact content.
::c0.7 ::s1.0 ::m0.2 ::f0.9
::read_file @utils.py"""},
    {"role": "user", "content": """\
::result ok
1| def fix_func(items : list) -> list:
2|     return [x * 2 for x in items]"""},
    {"role": "assistant", "content": """\
>> Extra space before colon. Adjusting SEARCH block to match exact content.
::c0.95 ::s1.0 ::m0.2 ::f1.0
::edit_file @utils.py
<<<
<<<<<<< SEARCH
def fix_func(items : list) -> list:
    return [x * 2 for x in items]
=======
def fix_func(values: list) -> list:
    return [x * 2 for x in values]
>>>>>>> REPLACE
>>>"""},
]

# replace_function recovery example: edit_file fails -> replace_function by symbol name
REPLACE_FUNCTION_EXAMPLES = [
    {"role": "user", "content": """\
::result error
Reason: find_not_matched (Edit 1)
Candidates near the first line of 'find':
  - line 1: "def process_data(data):"
Detailed Diff with closest candidate (Line 1):
- def process_data(data):
+ def process_data(data):"""},
    {"role": "assistant", "content": """\
>> edit_file keeps failing on whitespace mismatch. Using replace_function instead.
>> This replaces the entire function by name, no SEARCH block needed.
::c0.8 ::s1.0 ::m0.2 ::f0.9
::replace_function
<<<
---
path: "utils.py"
name: "process_data"
body: |
  def process_data(data):
      '''Process the input data and return results.'''
      results = []
      for item in data:
          results.append(item.strip().lower())
      return results
---
>>>"""},
]

# Planning Specific Examples
PLANNING_EXAMPLES = [
    {"role": "user", "content": "Build a weather app"},
    {"role": "assistant", "content": """\
>> App request. Proposing modular plan.
::c0.9 ::s1.0 ::m0.1 ::f0.9
::propose_plan
<<<
1. Research API (OpenWeather)
2. Design models
3. Implement client
>>>"""}
]

# Investigation Specific Examples
# CRITICAL: Shows the FULL pattern — investigate → observe → hypothesis
# The "user" role after investigate simulates the tool result returned by the system.
INVESTIGATION_EXAMPLES = [
    {"role": "user", "content": "It crashes with error X"},
    # Turn 1: Enter investigation mode
    {"role": "assistant", "content": """\
>> Unknown crash. Starting investigation.
::c0.8 ::s1.0 ::m0.2 ::f0.8
::investigate @Checking logs for error X"""},
    # Turn 1 result (tool result injected as user message)
    {"role": "user", "content": """\
::result ok
Investigation Mode started. Reason: Checking logs for error X
━━━ NEXT ACTION REQUIRED ━━━
Do NOT call ::response or ::duck_call yet.
Call read_file, grep_files, list_directory, or run_command to observe."""},
    # Turn 2: MUST observe — do NOT call response here
    {"role": "assistant", "content": """\
>> Investigation active. Reading logs to find error X.
::c0.85 ::s1.0 ::m0.3 ::f0.9
::read_file @logs/app.log start=1 end=50"""},
    # Turn 2 result
    {"role": "user", "content": """\
::result ok
1:aa1| [ERROR] NullPointerException at auth.py:42
2:bb2| [TRACE] called from login.py:17"""},
    # Turn 3: Form hypothesis based on evidence
    {"role": "assistant", "content": """\
>> Found error location. auth.py:42 is a null reference.
::c0.9 ::s1.0 ::m0.3 ::f0.9
::submit_hypothesis @NullPointerException at auth.py:42 — user object is None when login is called without session."""},
    # Turn 3 result — system confirms hypothesis and demands next action
    {"role": "user", "content": """\
::result ok
Hypothesis #1 registered: 'NullPointerException at auth.py:42 — user object is None when login is called without session.'.
━━━ NEXT ACTION REQUIRED ━━━
Choose ONE of the following:
  [Not confirmed yet] Verify with: read_file / grep_files / run_command
  [Confirmed]         Close with:  ::finish_investigation @<conclusion>
Do NOT call ::edit_file, ::write_file, or ::response until investigation is closed.
Remaining hypothesis attempts before duck_call: 1"""},
    # Turn 4: Hypothesis is confirmed — close investigation immediately
    {"role": "assistant", "content": """\
>> Evidence is clear: auth.py:42 dereferences user without None check. Root cause confirmed.
::c0.95 ::s1.0 ::m0.3 ::f0.95
::finish_investigation @Root cause: auth.py:42 calls user.id without checking if user is None. Fix: add null guard before login()."""}
]

def get_examples_for_mode(mode: str) -> list:
    """Return a compact set of examples relevant to the current mode."""
    examples = BASE_EXAMPLES.copy()
    if mode == "task" or mode == "task_execution":
        examples.extend(TASK_EXAMPLES)
        # edit_file 失敗時のリカバリーパターンを常に含める
        examples.extend(RECOVERY_EXAMPLES)
        examples.extend(REPLACE_FUNCTION_EXAMPLES)
    elif mode == "planning":
        examples.extend(PLANNING_EXAMPLES)
        examples.extend(REPLACE_FUNCTION_EXAMPLES)
    elif mode == "investigation":
        examples.extend(INVESTIGATION_EXAMPLES)
    else:
        # Mix for generic modes
        examples.extend(TASK_EXAMPLES[:2])
        examples.extend(RECOVERY_EXAMPLES)
        examples.extend(REPLACE_FUNCTION_EXAMPLES)
        examples.extend(PLANNING_EXAMPLES[:1])
    return examples
