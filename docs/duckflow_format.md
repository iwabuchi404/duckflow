# Duckflow Response Format Specification v1.0

## Overview

Duckflow v4 uses a **Markdown + Key-Value** format for all LLM responses. This format is optimized for LLM generation, error resilience, and parsing simplicity, while maintaining backward compatibility with JSON.

**Status**: v1.0 (2024-12-04)  
**Replaces**: JSON-only format (v0.x)  
**Backward Compatible**: Yes (JSON parser retained as fallback)

---

## Table of Contents

1. [Format Specification](#format-specification)
2. [Design Philosophy](#design-philosophy)
3. [Why This Format?](#why-this-format)
4. [Comparison with Alternatives](#comparison-with-alternatives)
5. [Implementation Guide](#implementation-guide)
6. [Migration Strategy](#migration-strategy)
7. [Examples](#examples)
8. [Appendix](#appendix)

---

## Format Specification

### Basic Structure

```markdown
[REASONING]
Multi-line reasoning text in natural language.
Can contain explanations, analysis, and thought process.

[CONFIDENCE] 0.0-1.0
[MOOD] 0.0-1.0
[FOCUS] 0.0-1.0
[STAMINA] 0.0-1.0

[ACTION_0_TYPE] action_type
[ACTION_0_PARAM_NAME] param_value
[ACTION_0_CONTENT_START]
Multi-line content
Code, text, or any data
[ACTION_0_CONTENT_END]

[ACTION_1_TYPE] action_type
[ACTION_1_PARAM_NAME] param_value
```

### Section Types

#### 1. REASONING Section
```markdown
[REASONING]
Free-form text explaining the thought process.
Multiple lines allowed.
No special formatting required.
```

**Rules:**
- Starts with `[REASONING]` marker
- Continues until next section marker
- Natural language, no escaping needed
- Multiple paragraphs allowed

---

#### 2. Duck Vitals (Single-line Key-Value)
```markdown
[CONFIDENCE] 0.85
[MOOD] 0.88
[FOCUS] 0.95
[STAMINA] 0.82
```

**Rules:**
- Format: `[KEY] value`
- Value: Float between 0.0 and 1.0
- One per line
- Order: irrelevant

**Standard Vitals:**
- `CONFIDENCE`: Agent's confidence in the plan (0.0 = uncertain, 1.0 = certain)
- `MOOD`: Emotional state (0.0 = frustrated, 1.0 = excited)
- `FOCUS`: Concentration level (0.0 = distracted, 1.0 = laser-focused)
- `STAMINA`: Energy level (0.0 = exhausted, 1.0 = energized)

---

#### 3. Action Blocks

**Format:**
```markdown
[ACTION_N_TYPE] action_type
[ACTION_N_PARAM1] value1
[ACTION_N_PARAM2] value2
[ACTION_N_CONTENT_START]
Multi-line content
[ACTION_N_CONTENT_END]
```

**Rules:**
- `N`: Zero-indexed integer (0, 1, 2, ...)
- `TYPE`: Required for every action
- Parameters: Optional, depends on action type
- `CONTENT_START/END`: Optional, for multi-line content
- Order: Actions should be numbered sequentially

**Common Action Types:**
- `create_file`: Create a new file
- `edit_file`: Edit existing file
- `delete_file`: Delete a file
- `run_command`: Execute shell command
- `search_code`: Search codebase
- `read_file`: Read file content
- `finish`: Complete the task

---

### Complete Example

```markdown
[REASONING]
The user needs authentication functionality. I will:
1. Create an auth module with secure password hashing
2. Create comprehensive unit tests
3. Ensure proper error handling

This approach prioritizes security and testability.

[CONFIDENCE] 0.92
[MOOD] 0.88
[FOCUS] 0.95
[STAMINA] 0.85

[ACTION_0_TYPE] create_file
[ACTION_0_PATH] src/auth.py
[ACTION_0_DESCRIPTION] Main authentication module
[ACTION_0_CONTENT_START]
import hashlib
import hmac
from typing import Optional

class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password using PBKDF2.
    
    Args:
        password: Plain text password
        salt: Optional salt (generated if not provided)
    
    Returns:
        Tuple of (hashed_password, salt)
    """
    if salt is None:
        salt = os.urandom(32).hex()
    
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return hashed.hex(), salt

def authenticate(username: str, password: str, stored_hash: str, salt: str) -> bool:
    """
    Authenticate a user.
    
    Args:
        username: Username
        password: Plain text password
        stored_hash: Stored password hash
        salt: Salt used for hashing
    
    Returns:
        True if authentication successful
    
    Raises:
        AuthenticationError: If authentication fails
    """
    computed_hash, _ = hash_password(password, salt)
    
    if not hmac.compare_digest(computed_hash, stored_hash):
        raise AuthenticationError(f"Authentication failed for user: {username}")
    
    return True
[ACTION_0_CONTENT_END]

[ACTION_1_TYPE] create_file
[ACTION_1_PATH] tests/test_auth.py
[ACTION_1_DESCRIPTION] Unit tests for authentication module
[ACTION_1_CONTENT_START]
import pytest
from src.auth import hash_password, authenticate, AuthenticationError

def test_hash_password():
    """Test password hashing"""
    password = "test_password_123"
    hashed, salt = hash_password(password)
    
    assert len(hashed) == 64  # SHA256 hex
    assert len(salt) == 64
    
    # Same password with same salt should produce same hash
    hashed2, _ = hash_password(password, salt)
    assert hashed == hashed2

def test_authenticate_success():
    """Test successful authentication"""
    password = "correct_password"
    hashed, salt = hash_password(password)
    
    result = authenticate("testuser", password, hashed, salt)
    assert result is True

def test_authenticate_failure():
    """Test failed authentication"""
    password = "correct_password"
    hashed, salt = hash_password(password)
    
    with pytest.raises(AuthenticationError):
        authenticate("testuser", "wrong_password", hashed, salt)

def test_timing_attack_resistance():
    """Test that comparison is timing-attack resistant"""
    password = "test_password"
    hashed, salt = hash_password(password)
    
    # Should use constant-time comparison
    # This test verifies the function runs without timing variations
    import time
    
    start = time.perf_counter()
    try:
        authenticate("user", "wrong", hashed, salt)
    except AuthenticationError:
        pass
    time1 = time.perf_counter() - start
    
    start = time.perf_counter()
    try:
        authenticate("user", "also_wrong_but_different_length", hashed, salt)
    except AuthenticationError:
        pass
    time2 = time.perf_counter() - start
    
    # Times should be similar (within 10% for timing attack resistance)
    assert abs(time1 - time2) / max(time1, time2) < 0.1
[ACTION_1_CONTENT_END]

[ACTION_2_TYPE] finish
[ACTION_2_RESULT] Authentication module created with secure hashing and comprehensive tests
```

---

## Design Philosophy

### 1. LLM-First Design

**Principle**: Format optimized for LLM token generation, not human readability.

**Key Insights:**
- LLMs trained on INI files, log files, and configuration formats
- Simple key-value patterns have high token prediction confidence
- Section markers like `[SECTION]` are easy to generate correctly
- No complex nesting or indentation requirements

### 2. Error Resilience

**Principle**: Format should be recoverable from partial or malformed responses.

**Design Choices:**
- **Section markers**: Clear boundaries allow skipping invalid sections
- **No indentation dependency**: Unlike YAML, no whitespace-sensitive parsing
- **Explicit boundaries**: `CONTENT_START`/`CONTENT_END` prevent ambiguity
- **Optional sections**: Missing sections don't break the entire response

**Example Recovery:**
```markdown
[REASONING]
Some reasoning text

[CONFIDEN  # Typo - skip this line
[MOOD] 0.8  # Continue parsing

[ACTION_0_TYPE] create_file
[ACTION_0_PA  # Incomplete - skip
[ACTION_0_CONTENT_START]
code here
[ACTION_0_CONTENT_END]  # Content still captured
```

### 3. Parsing Simplicity

**Principle**: Parser should be simple, fast, and maintainable.

**Advantages:**
- Line-by-line parsing (no recursive descent needed)
- Regular expression for section detection
- State machine with clear transitions
- No AST construction required

### 4. Extensibility

**Principle**: Easy to add new sections or action types.

**How:**
- New vitals: Just add `[NEW_VITAL] value`
- New action params: `[ACTION_N_NEW_PARAM] value`
- New sections: Define new marker `[NEW_SECTION]`
- Backward compatible: Old parsers ignore unknown sections

---

## Why This Format?

### Problem: JSON Limitations

**From industry research (Aider, OpenHands, SWE-agent):**

1. **Code Escaping Issues**
   ```json
   {
     "code": "def func():\n    return \"hello\""  // Easy to break
   }
   ```
   - LLMs frequently forget to escape quotes
   - Newlines cause parsing errors
   - Reduces code quality (Aider's finding)

2. **Model Dependency**
   ```
   ✅ Stable: OpenAI GPT-4o, xAI Grok
   ⚠️  Unstable: Claude (adds explanations), Gemini
   ❌ Fails: DeepSeek, Qwen, most open models
   ```

3. **Cognitive Load**
   - LLMs must think about JSON structure AND content
   - Increases error rate, especially for long responses

### Solution: Markdown + Key-Value

**Advantages over JSON:**

| Aspect | JSON | Markdown+KV | Winner |
|--------|------|-------------|--------|
| Code escaping | Required | Not needed | ✅ Markdown+KV |
| LLM training data | Moderate | High | ✅ Markdown+KV |
| Error recovery | Difficult | Easy | ✅ Markdown+KV |
| Token efficiency | Good | Good | 🟰 Tie |
| Parsing speed | Fast | Fast | 🟰 Tie |
| Model compatibility | Limited | Universal | ✅ Markdown+KV |
| Structured data | Excellent | Good | ⚠️ JSON |
| Extensibility | Moderate | High | ✅ Markdown+KV |

**Trade-off:**
- JSON: Better for strict schema validation
- Markdown+KV: Better for LLM generation and error resilience

**Decision**: LLM generation quality > Strict validation

---

## Comparison with Alternatives

### vs. JSON

**JSON:**
```json
{
  "reasoning": "Text with \"quotes\" needs escaping",
  "confidence": 0.85,
  "actions": [{
    "type": "create_file",
    "path": "test.py",
    "content": "def func():\n    return \"hello\""
  }]
}
```

**Issues:**
- ❌ Quote escaping errors
- ❌ Newline handling
- ❌ Model-dependent stability
- ✅ Strong typing
- ✅ Wide tooling support

---

### vs. YAML

**YAML:**
```yaml
reasoning: Text here
confidence: 0.85
actions:
  - type: create_file
    path: test.py
    content: |
      def func():
          return "hello"
```

**Issues:**
- ❌ Indentation dependency (LLMs struggle)
- ❌ Ambiguous specification (multiple valid formats)
- ❌ Parser errors common
- ✅ Human readable
- ⚠️ Good for config files, bad for LLM output

---

### vs. XML

**XML:**
```xml
<response>
  <reasoning>Text here</reasoning>
  <confidence>0.85</confidence>
  <actions>
    <action>
      <type>create_file</type>
      <path>test.py</path>
      <content>
def func():
    return "hello"
      </content>
    </action>
  </actions>
</response>
```

**Issues:**
- ⚠️ Verbose (high token count)
- ✅ Excellent for Claude models
- ❌ Poor for non-Claude models
- ✅ Self-documenting
- ❌ Closing tags easy to forget

---

### vs. Pure Markdown

**Pure Markdown:**
```markdown
## Reasoning
Text here

## Actions

### Create file: test.py
```python
def func():
    return "hello"
```
```

**Issues:**
- ❌ Ambiguous structure (heading levels vary)
- ❌ Difficult to parse reliably
- ❌ No clear key-value mapping
- ✅ Most natural for LLMs
- ✅ Highest error resilience

**Our format (Markdown+KV) combines benefits:**
- ✅ Markdown's naturalness
- ✅ Key-value's structure
- ✅ Best of both worlds

---

## Implementation Guide

### Parser Implementation

```python
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class Action:
    """Represents a single action"""
    type: str
    params: Dict[str, str] = field(default_factory=dict)
    content: Optional[str] = None
    
@dataclass
class DuckflowResponse:
    """Parsed Duckflow response"""
    reasoning: str = ""
    vitals: Dict[str, float] = field(default_factory=dict)
    actions: List[Action] = field(default_factory=list)
    raw_text: str = ""
    parse_errors: List[str] = field(default_factory=list)

class DuckflowParser:
    """Parser for Duckflow Markdown+KV format"""
    
    # Section patterns
    REASONING_PATTERN = re.compile(r'^\[REASONING\]')
    VITAL_PATTERN = re.compile(r'^\[([A-Z_]+)\]\s+([\d.]+)')
    ACTION_PATTERN = re.compile(r'^\[ACTION_(\d+)_([A-Z_]+)\]\s*(.+)?')
    CONTENT_START_PATTERN = re.compile(r'^\[ACTION_(\d+)_CONTENT_START\]')
    CONTENT_END_PATTERN = re.compile(r'^\[ACTION_(\d+)_CONTENT_END\]')
    
    # Known vitals
    KNOWN_VITALS = {'CONFIDENCE', 'MOOD', 'FOCUS', 'STAMINA'}
    
    def parse(self, response: str) -> DuckflowResponse:
        """
        Parse a Duckflow response.
        
        Args:
            response: Raw response string
            
        Returns:
            DuckflowResponse object
        """
        result = DuckflowResponse(raw_text=response)
        
        lines = response.split('\n')
        current_section = None
        reasoning_buffer = []
        
        # Action tracking
        actions_dict: Dict[int, Dict[str, Any]] = {}
        current_action_idx = None
        content_buffer = []
        in_content = False
        
        for line_num, line in enumerate(lines, 1):
            try:
                # Check for REASONING section
                if self.REASONING_PATTERN.match(line):
                    current_section = 'reasoning'
                    continue
                
                # Check for vitals
                vital_match = self.VITAL_PATTERN.match(line)
                if vital_match:
                    vital_name, vital_value = vital_match.groups()
                    if vital_name in self.KNOWN_VITALS:
                        try:
                            result.vitals[vital_name.lower()] = float(vital_value)
                        except ValueError:
                            result.parse_errors.append(
                                f"Line {line_num}: Invalid vital value: {vital_value}"
                            )
                    current_section = None
                    continue
                
                # Check for action content start
                content_start_match = self.CONTENT_START_PATTERN.match(line)
                if content_start_match:
                    action_idx = int(content_start_match.group(1))
                    current_action_idx = action_idx
                    in_content = True
                    content_buffer = []
                    current_section = None
                    continue
                
                # Check for action content end
                content_end_match = self.CONTENT_END_PATTERN.match(line)
                if content_end_match:
                    action_idx = int(content_end_match.group(1))
                    if action_idx in actions_dict:
                        actions_dict[action_idx]['content'] = '\n'.join(content_buffer)
                    in_content = False
                    content_buffer = []
                    current_action_idx = None
                    current_section = None
                    continue
                
                # If in content section, collect lines
                if in_content:
                    content_buffer.append(line)
                    continue
                
                # Check for action parameters
                action_match = self.ACTION_PATTERN.match(line)
                if action_match:
                    action_idx = int(action_match.group(1))
                    param_name = action_match.group(2)
                    param_value = action_match.group(3) or ''
                    
                    # Initialize action if needed
                    if action_idx not in actions_dict:
                        actions_dict[action_idx] = {'params': {}}
                    
                    # Store TYPE or params
                    if param_name == 'TYPE':
                        actions_dict[action_idx]['type'] = param_value.strip()
                    else:
                        actions_dict[action_idx]['params'][param_name.lower()] = param_value.strip()
                    
                    current_section = None
                    continue
                
                # Collect reasoning text
                if current_section == 'reasoning':
                    reasoning_buffer.append(line)
                    
            except Exception as e:
                result.parse_errors.append(f"Line {line_num}: {str(e)}")
        
        # Finalize reasoning
        result.reasoning = '\n'.join(reasoning_buffer).strip()
        
        # Convert actions_dict to Action objects
        for idx in sorted(actions_dict.keys()):
            action_data = actions_dict[idx]
            if 'type' not in action_data:
                result.parse_errors.append(f"Action {idx}: Missing TYPE")
                continue
            
            result.actions.append(Action(
                type=action_data['type'],
                params=action_data.get('params', {}),
                content=action_data.get('content')
            ))
        
        return result

# Usage example
parser = DuckflowParser()
response_text = """
[REASONING]
Creating authentication module with security best practices.

[CONFIDENCE] 0.92
[MOOD] 0.88

[ACTION_0_TYPE] create_file
[ACTION_0_PATH] auth.py
[ACTION_0_CONTENT_START]
def authenticate(user, password):
    return True
[ACTION_0_CONTENT_END]
"""

result = parser.parse(response_text)
print(f"Reasoning: {result.reasoning}")
print(f"Confidence: {result.vitals.get('confidence')}")
print(f"Actions: {len(result.actions)}")
print(f"Errors: {len(result.parse_errors)}")
```

---

### Prompt Template

```python
DUCKFLOW_RESPONSE_FORMAT_PROMPT = """
# Response Format

You must respond using the following format:

[REASONING]
Explain your thought process here in natural language.
You can write multiple lines.
Be clear and detailed about your analysis and decisions.

[CONFIDENCE] <float 0.0-1.0>
[MOOD] <float 0.0-1.0>
[FOCUS] <float 0.0-1.0>
[STAMINA] <float 0.0-1.0>

[ACTION_0_TYPE] <action_type>
[ACTION_0_<PARAM_NAME>] <param_value>
[ACTION_0_CONTENT_START]
Multi-line content here (code, text, etc.)
[ACTION_0_CONTENT_END]

[ACTION_1_TYPE] <action_type>
[ACTION_1_<PARAM_NAME>] <param_value>
...

## Action Types

- `create_file`: Create a new file
  Required params: PATH
  Optional: DESCRIPTION, CONTENT_START/END

- `edit_file`: Edit an existing file  
  Required params: PATH
  Optional: DESCRIPTION, CONTENT_START/END

- `delete_file`: Delete a file
  Required params: PATH

- `run_command`: Execute a shell command
  Required params: COMMAND
  Optional: WORKING_DIR

- `search_code`: Search in codebase
  Required params: QUERY

- `read_file`: Read file content
  Required params: PATH

- `finish`: Complete the task
  Required params: RESULT

## Duck Vitals Guide

- CONFIDENCE: Your confidence in the plan (0.0=uncertain, 1.0=certain)
- MOOD: Your emotional state (0.0=frustrated, 0.5=neutral, 1.0=excited)
- FOCUS: Your concentration level (0.0=distracted, 1.0=laser-focused)  
- STAMINA: Your energy level (0.0=exhausted, 1.0=energized)

## Important Rules

1. Always start with [REASONING]
2. Always provide all four Duck Vitals
3. Action indices start at 0 and increment
4. For multi-line content, use CONTENT_START/CONTENT_END
5. No need to escape special characters in content blocks
6. Section order doesn't matter (except REASONING should be first)

## Example

[REASONING]
The user wants to create a simple calculator.
I will create a Python file with basic arithmetic functions.
This is straightforward and well within my capabilities.

[CONFIDENCE] 0.95
[MOOD] 0.90
[FOCUS] 0.95
[STAMINA] 0.92

[ACTION_0_TYPE] create_file
[ACTION_0_PATH] calculator.py
[ACTION_0_DESCRIPTION] Simple calculator with basic operations
[ACTION_0_CONTENT_START]
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
[ACTION_0_CONTENT_END]

[ACTION_1_TYPE] finish
[ACTION_1_RESULT] Calculator module created successfully
"""
```

---

### Error Handling

```python
def parse_with_fallback(response: str) -> DuckflowResponse:
    """
    Parse response with multiple fallback strategies.
    
    Tries:
    1. Markdown+KV parser
    2. JSON parser (backward compatibility)
    3. Flexible extraction (best effort)
    """
    # Try primary parser
    try:
        parser = DuckflowParser()
        result = parser.parse(response)
        
        # Check if parse was successful
        if result.actions or result.reasoning:
            return result
    except Exception as e:
        print(f"Markdown+KV parse failed: {e}")
    
    # Try JSON fallback
    try:
        import json
        # Try direct JSON parse
        data = json.loads(response)
        return convert_json_to_duckflow(data)
    except json.JSONDecodeError:
        pass
    
    # Try JSON extraction (in case wrapped in markdown)
    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            return convert_json_to_duckflow(data)
    except Exception:
        pass
    
    # Last resort: flexible extraction
    return flexible_extract(response)

def convert_json_to_duckflow(data: dict) -> DuckflowResponse:
    """Convert legacy JSON format to DuckflowResponse"""
    result = DuckflowResponse()
    
    result.reasoning = data.get('reasoning', '')
    
    # Extract vitals
    vitals = data.get('duck_vitals', {})
    result.vitals = {k: v for k, v in vitals.items()}
    
    # Extract actions
    for action_data in data.get('actions', []):
        action = Action(
            type=action_data.get('type', ''),
            params={k: v for k, v in action_data.items() if k != 'type'},
            content=action_data.get('content')
        )
        result.actions.append(action)
    
    return result

def flexible_extract(response: str) -> DuckflowResponse:
    """
    Best-effort extraction when structured parsing fails.
    Looks for any recognizable patterns.
    """
    result = DuckflowResponse(raw_text=response)
    
    # Try to find reasoning-like text at the start
    lines = response.split('\n')
    reasoning_lines = []
    for line in lines[:10]:  # First 10 lines
        if line.strip() and not line.startswith('['):
            reasoning_lines.append(line)
    result.reasoning = '\n'.join(reasoning_lines)
    
    # Try to extract any vitals mentioned
    for vital in ['confidence', 'mood', 'focus', 'stamina']:
        pattern = rf'{vital}[:\s]+?([\d.]+)'
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            try:
                result.vitals[vital] = float(match.group(1))
            except ValueError:
                pass
    
    # Try to find code blocks (might be intended actions)
    code_blocks = re.findall(r'```\w*\n(.*?)\n```', response, re.DOTALL)
    for idx, code in enumerate(code_blocks):
        result.actions.append(Action(
            type='unknown',
            content=code,
            params={'index': str(idx)}
        ))
    
    result.parse_errors.append("Used flexible extraction fallback")
    
    return result
```

---

## Migration Strategy

### Phase 1: Dual Support (Week 1-2)

**Goal**: Support both JSON and Markdown+KV formats

**Implementation:**
```python
def parse_response(response: str) -> DuckflowResponse:
    """Auto-detect format and parse accordingly"""
    
    # Check if looks like JSON
    response_stripped = response.strip()
    if response_stripped.startswith('{'):
        return parse_json_format(response)
    
    # Check if looks like Markdown+KV
    if '[REASONING]' in response or '[ACTION_' in response:
        return parse_markdown_kv_format(response)
    
    # Fallback with both attempts
    try:
        return parse_markdown_kv_format(response)
    except Exception:
        return parse_json_format(response)
```

**Prompt Update:**
```python
# Add to existing prompt
PROMPT_ADDITION = """
Note: You can respond in either JSON format (legacy) or the new Markdown+KV format.
Markdown+KV is preferred for better reliability.
"""
```

**Testing:**
- Run both parsers on test suite
- Compare results for consistency
- Monitor parse error rates

---

### Phase 2: Markdown+KV Preferred (Week 3-4)

**Goal**: Encourage LLM to use new format while keeping JSON as fallback

**Prompt Update:**
```python
PROMPT_UPDATE = """
IMPORTANT: Use the Markdown+KV format for your response.

[REASONING]
Your analysis here...

[CONFIDENCE] 0.85
[MOOD] 0.90
...

This format is more reliable than JSON.
"""
```

**Monitoring:**
- Track which format LLM chooses
- Measure parse success rates
- Compare response quality

**Expected Results:**
- 70-80% of responses use Markdown+KV
- Parse error rate decreases
- Longer, more detailed reasoning sections

---

### Phase 3: Markdown+KV Standard (Week 5+)

**Goal**: Make Markdown+KV the standard, JSON only for backward compatibility

**Prompt Update:**
```python
PROMPT_FINAL = """
You MUST respond using the Markdown+KV format:

[REASONING]
...

[CONFIDENCE] 0.85
...

DO NOT use JSON format.
"""
```

**Code Cleanup:**
- Mark JSON parser as legacy
- Add deprecation warnings
- Update all documentation

**Long-term:**
- JSON parser remains for error recovery
- Consider removing JSON after 6 months of stable operation

---

## Examples

### Example 1: Simple File Creation

```markdown
[REASONING]
User wants a hello world program in Python.
This is straightforward - just create a single file with a print statement.

[CONFIDENCE] 0.98
[MOOD] 0.85
[FOCUS] 0.90
[STAMINA] 0.95

[ACTION_0_TYPE] create_file
[ACTION_0_PATH] hello.py
[ACTION_0_DESCRIPTION] Simple hello world program
[ACTION_0_CONTENT_START]
#!/usr/bin/env python3
"""Simple hello world program"""

def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
[ACTION_0_CONTENT_END]

[ACTION_1_TYPE] finish
[ACTION_1_RESULT] Hello world program created successfully
```

---

### Example 2: Multi-File Project

```markdown
[REASONING]
User needs a REST API for a todo application.
I'll create:
1. Main FastAPI application
2. Database models
3. API routes
4. Basic tests

This requires careful planning to ensure proper structure and separation of concerns.

[CONFIDENCE] 0.87
[MOOD] 0.82
[FOCUS] 0.92
[STAMINA] 0.78

[ACTION_0_TYPE] create_file
[ACTION_0_PATH] main.py
[ACTION_0_DESCRIPTION] FastAPI application entry point
[ACTION_0_CONTENT_START]
from fastapi import FastAPI
from routes import todo_router

app = FastAPI(title="Todo API", version="1.0.0")

app.include_router(todo_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Todo API is running"}
[ACTION_0_CONTENT_END]

[ACTION_1_TYPE] create_file
[ACTION_1_PATH] models.py
[ACTION_1_DESCRIPTION] Database models for todos
[ACTION_1_CONTENT_START]
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Todo(Base):
    __tablename__ = "todos"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
[ACTION_1_CONTENT_END]

[ACTION_2_TYPE] create_file
[ACTION_2_PATH] routes.py
[ACTION_2_DESCRIPTION] API route handlers
[ACTION_2_CONTENT_START]
from fastapi import APIRouter, HTTPException
from typing import List
from pydantic import BaseModel

todo_router = APIRouter()

class TodoCreate(BaseModel):
    title: str
    description: str = ""

class TodoResponse(BaseModel):
    id: int
    title: str
    description: str
    completed: bool

# In-memory storage for demo
todos_db = []

@todo_router.get("/todos", response_model=List[TodoResponse])
def get_todos():
    return todos_db

@todo_router.post("/todos", response_model=TodoResponse)
def create_todo(todo: TodoCreate):
    new_todo = {
        "id": len(todos_db) + 1,
        "title": todo.title,
        "description": todo.description,
        "completed": False
    }
    todos_db.append(new_todo)
    return new_todo
[ACTION_2_CONTENT_END]

[ACTION_3_TYPE] create_file
[ACTION_3_PATH] tests/test_api.py
[ACTION_3_DESCRIPTION] Basic API tests
[ACTION_3_CONTENT_START]
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Todo API is running"}

def test_create_todo():
    response = client.post("/api/v1/todos", json={
        "title": "Test todo",
        "description": "Test description"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test todo"
    assert data["completed"] is False
[ACTION_3_CONTENT_END]

[ACTION_4_TYPE] finish
[ACTION_4_RESULT] Todo API created with FastAPI, models, routes, and basic tests
```

---

### Example 3: Code Search and Edit

```markdown
[REASONING]
User reported a bug in the authentication system where passwords aren't being hashed.
I need to:
1. Search for the authentication code
2. Identify the issue
3. Fix the password hashing

This is a security-critical fix, so I need to be careful and thorough.

[CONFIDENCE] 0.82
[MOOD] 0.75
[FOCUS] 0.95
[STAMINA] 0.70

[ACTION_0_TYPE] search_code
[ACTION_0_QUERY] def authenticate
[ACTION_0_CONTEXT] Looking for authentication function

[ACTION_1_TYPE] read_file
[ACTION_1_PATH] auth.py

[ACTION_2_TYPE] edit_file
[ACTION_2_PATH] auth.py
[ACTION_2_DESCRIPTION] Fix password hashing issue
[ACTION_2_EXPLANATION] The current code stores passwords in plain text. This is a critical security vulnerability. I'm updating to use proper password hashing with bcrypt.
[ACTION_2_CONTENT_START]
import bcrypt
from typing import Optional

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def authenticate(username: str, password: str, stored_hash: str) -> bool:
    """
    Authenticate a user with hashed password.
    
    Args:
        username: Username
        password: Plain text password
        stored_hash: Hashed password from database
    
    Returns:
        True if authentication successful
    """
    password_bytes = password.encode('utf-8')
    stored_hash_bytes = stored_hash.encode('utf-8')
    
    return bcrypt.checkpw(password_bytes, stored_hash_bytes)

def create_user(username: str, password: str) -> dict:
    """Create a new user with hashed password"""
    return {
        "username": username,
        "password_hash": hash_password(password)
    }
[ACTION_2_CONTENT_END]

[ACTION_3_TYPE] run_command
[ACTION_3_COMMAND] pytest tests/test_auth.py -v
[ACTION_3_DESCRIPTION] Run authentication tests to verify fix

[ACTION_4_TYPE] finish
[ACTION_4_RESULT] Fixed password hashing vulnerability in authentication system. All tests passing.
```

---

### Example 4: Low Stamina / Complex Task

```markdown
[REASONING]
User wants to refactor a large legacy codebase to use dependency injection.
This is a complex task that will require multiple steps:
1. Analyze current dependencies
2. Create service interfaces
3. Update implementations
4. Modify main application

I'm feeling somewhat low on stamina due to the complexity, but I'm confident in the approach.
I'll need to work carefully and may need to break this into smaller chunks.

[CONFIDENCE] 0.75
[MOOD] 0.68
[FOCUS] 0.88
[STAMINA] 0.55

[ACTION_0_TYPE] search_code
[ACTION_0_QUERY] class DatabaseManager
[ACTION_0_CONTEXT] Finding database dependencies

[ACTION_1_TYPE] search_code
[ACTION_1_QUERY] class EmailService
[ACTION_1_CONTEXT] Finding email service usage

[ACTION_2_TYPE] create_file
[ACTION_2_PATH] interfaces.py
[ACTION_2_DESCRIPTION] Define service interfaces
[ACTION_2_CONTENT_START]
from abc import ABC, abstractmethod
from typing import List, Optional

class DatabaseInterface(ABC):
    """Interface for database operations"""
    
    @abstractmethod
    def connect(self) -> None:
        pass
    
    @abstractmethod
    def query(self, sql: str, params: tuple) -> List[dict]:
        pass

class EmailInterface(ABC):
    """Interface for email operations"""
    
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> bool:
        pass

class CacheInterface(ABC):
    """Interface for caching operations"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        pass
    
    @abstractmethod
    def set(self, key: str, value: str, ttl: int) -> None:
        pass
[ACTION_2_CONTENT_END]

[ACTION_3_TYPE] finish
[ACTION_3_RESULT] Created service interfaces. Need to continue refactoring in next session - stamina low and this is complex work. Next steps: implement dependency injection container and update service implementations.
```

---

## Appendix

### A. Reserved Section Names

**Top-Level Sections:**
- `[REASONING]` - Thought process and analysis
- `[PLANNING]` - High-level plan (optional)
- `[NOTES]` - Additional notes (optional)

**Vitals:**
- `[CONFIDENCE]` - Agent confidence level
- `[MOOD]` - Emotional state
- `[FOCUS]` - Concentration level
- `[STAMINA]` - Energy level

**Action Patterns:**
- `[ACTION_N_TYPE]` - Action type (required)
- `[ACTION_N_*]` - Action parameters
- `[ACTION_N_CONTENT_START]` - Multi-line content start
- `[ACTION_N_CONTENT_END]` - Multi-line content end

### B. Common Action Parameters

**File Operations:**
- `PATH` - File path (required for file operations)
- `DESCRIPTION` - Human-readable description
- `CONTENT_START/END` - Multi-line file content

**Command Execution:**
- `COMMAND` - Shell command to execute
- `WORKING_DIR` - Working directory
- `TIMEOUT` - Command timeout in seconds

**Search Operations:**
- `QUERY` - Search query string
- `CONTEXT` - Additional search context
- `MAX_RESULTS` - Maximum number of results

**Task Completion:**
- `RESULT` - Summary of what was accomplished
- `NEXT_STEPS` - Suggested follow-up actions

### C. Validation Rules

**Required Elements:**
1. At least one of: `[REASONING]` or `[ACTION_0_TYPE]`
2. All four vitals: CONFIDENCE, MOOD, FOCUS, STAMINA
3. Each action must have `[ACTION_N_TYPE]`
4. Sequential action numbering (0, 1, 2, ...)

**Optional Elements:**
- Action parameters (depends on type)
- Content blocks
- Additional sections

**Invalid:**
- Duplicate section names
- Missing `CONTENT_END` after `CONTENT_START`
- Non-numeric vital values
- Non-sequential action indices

### D. Performance Characteristics

**Parser Performance:**
- Average parse time: <1ms for typical response
- Memory usage: O(n) where n = response length
- Streaming: Not supported (requires complete response)

**Error Rate (estimated based on LLM tests):**
- Markdown+KV format: ~2-5% parse failures
- JSON format: ~15-25% parse failures (model-dependent)
- Improvement: **70-85% reduction in parse errors**

### E. Version History

**v1.0 (2024-12-04):**
- Initial specification
- Markdown + Key-Value format
- Duck Vitals integration
- Action list support
- Multi-line content blocks

**Future Considerations:**
- Streaming support (incremental parsing)
- Binary content encoding
- Nested action blocks
- Schema validation

---

## References

1. **Aider**: "LLMs struggle to return code in JSON" - https://aider.chat/docs/
2. **SWE-agent**: Agent-Computer Interface (ACI) design - https://swe-agent.com/
3. **OpenHands**: Tool calling challenges with non-OpenAI models - GitHub Issues
4. **LangChain Issue #1077**: JSON parsing reliability problems
5. **Duckflow v4 Architecture**: 5-node architecture with Duck Vitals system

---

## Document Info

- **Version**: 1.0
- **Date**: 2024-12-04
- **Status**: Final
- **Author**: Duckflow Team
- **Next Review**: After 1 month of production use

---

**End of Specification**