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
>> Need hash-lines first to perform a safe edit.
::c0.9 ::s1.0 ::m0.1 ::f0.9
::read_file @hello.py"""},
    {"role": "assistant", "content": """\
::result ok
1:a1b| def main():
2:c2d|     print('Hi')"""},
    {"role": "assistant", "content": """\
>> Hash confirmed. Inserting docstring.
>> [CHECK] @path=hello.py, anchors="1:a1b 1:a1b" match exactly.
::c1.0 ::s1.0 ::m0.2 ::f1.0
::edit_file @hello.py
<<<
---
anchors: "1:a1b 1:a1b"
---
def main():
    \"\"\"Entry point.\"\"\"
>>>"""}
]

# Self-Correction Example
CORRECTION_EXAMPLES = [
    {"role": "user", "content": "Update the print message in hello.py"},
    {"role": "assistant", "content": """\
>> Re-reading file to get fresh hashes.
::c0.9 ::s1.0 ::m0.1 ::f0.9
::read_file @hello.py"""},
    {"role": "assistant", "content": """\
::result ok
1:a1b| def main():
2:c2d|     print('Old Message')"""},
    {"role": "assistant", "content": """\
>> [CHECK] Wait, I almost used '2:c2x' but the last read said '2:c2d'.
>> Fixing anchor to 2:c2d and applying edit.
::c1.0 ::s1.0 ::m0.2 ::f1.0
::edit_file @hello.py
<<<
---
anchors: "2:c2d 2:c2d"
---
    print('New Message')
>>>"""}
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
INVESTIGATION_EXAMPLES = [
    {"role": "user", "content": "It crashes with error X"},
    {"role": "assistant", "content": """\
>> Unknown crash. Starting investigation.
::c0.8 ::s1.0 ::m0.2 ::f0.8
::investigate @Checking logs for error X"""},
    {"role": "assistant", "content": """\
>> Found suspicious line in logs. Forming hypothesis.
::c0.9 ::s1.0 ::m0.3 ::f0.9
::submit_hypothesis @Null pointer in auth.py:42"""}
]

def get_examples_for_mode(mode: str) -> list:
    """Return a compact set of examples relevant to the current mode."""
    examples = BASE_EXAMPLES.copy()
    if mode == "task" or mode == "task_execution":
        examples.extend(TASK_EXAMPLES)
    elif mode == "planning":
        examples.extend(PLANNING_EXAMPLES)
    elif mode == "investigation":
        examples.extend(INVESTIGATION_EXAMPLES)
    else:
        # Mix for generic modes
        examples.extend(TASK_EXAMPLES[:2])
        examples.extend(PLANNING_EXAMPLES[:1])
    return examples
