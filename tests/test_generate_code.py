#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Code Generation Tool Test

This test script simulates code generation workflow to evaluate code quality.
"""

import asyncio
import os
import sys
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from companion.base.llm_client import default_client, LLMClient
from companion.modules.sub_llm_manager import SubLLMManager
from companion.tools.sub_llm_tools import SubLLMTools


# Test cases with instructions and expected code characteristics
TEST_CASES = [
    # ===== COMPLEX TESTS (3x longer) =====
    {
        "name": "Complex: API Client with Async Context Manager",
        "instruction": """
Create a complete API client class `APIClient` with the following features:

1. Async Context Manager Support:
   - Implement __aenter__ and __aexit__ for async context manager usage
   - Accept base_url and timeout in __init__

2. Request Methods:
   - async get(url: str, params: dict = None) -> Response
   - async post(url: str, data: dict = None) -> Response
   - async put(url: str, data: dict = None) -> Response
   - async delete(url: str) -> Response

3. Response Handling:
   - Create a simple Response dataclass with status_code, headers, and text fields
   - Raise custom APIError exception for HTTP error statuses (4xx, 5xx)

4. Connection Management:
   - Use aiohttp.ClientSession
   - Handle connection errors with try/except
   - Support timeout with asyncio.TimeoutError

5. Retry Logic:
   - Add _retry_request helper that retries up to 3 times with exponential backoff
   - Use time module for sleep in retry delays

Include comprehensive docstrings, type hints, and proper error handling.
        """.strip(),
        "context": """
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
import aiohttp
import asyncio
        """.strip(),
        "expected_elements": [
            "class APIClient", "__init__", "__aenter__", "__aexit__",
            "async def get", "async def post", "async def put", "async def delete",
            "class Response", "@dataclass", "status_code", "headers", "text",
            "class APIError", "raise APIError", "aiohttp.ClientSession",
            "_retry_request", "exponential", "time.sleep", "asyncio.TimeoutError"
        ],
        "language": "python"
    },
    {
        "name": "Complex: Event System with Observer Pattern",
        "instruction": """
Create a complete event system implementing the Observer pattern with the following components:

1. EventManager Class:
   - __init__(self): Initialize empty listeners dictionary
   - subscribe(self, event_type: str, listener: callable): Register listener for event
   - unsubscribe(self, event_type: str, listener: callable): Remove listener
   - emit(self, event_type: str, *args, **kwargs): Call all listeners for event
   - clear(self): Remove all listeners
   - Thread-safe using threading.Lock for concurrent access

2. EventData Class:
   - Create a dataclass with timestamp, event_type, and data fields
   - Use datetime for timestamp
   - Support serialization via to_dict() method

3. Error Handling:
   - Create custom EventError exception class
   - Handle invalid event types in emit() method
   - Log errors to stderr

4. Type Hints:
   - Use Callable for listener type
   - Use TypeVar for generic event data
   - Support multiple argument types

Include proper docstrings, type hints, and thread safety.
        """.strip(),
        "context": """
import threading
from typing import Callable, TypeVar, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime
import sys
        """.strip(),
        "expected_elements": [
            "class EventManager", "__init__", "subscribe", "unsubscribe", "emit", "clear",
            "threading.Lock", "acquire", "release",
            "class EventData", "@dataclass", "timestamp", "event_type", "data",
            "to_dict", "class EventError", "sys.stderr"
        ],
        "language": "python"
    },
    {
        "name": "Complex: Cache System with LRU and Decorator",
        "instruction": """
Create a memory cache system with LRU eviction and decorator support:

1. LRUCache Class:
   - __init__(self, capacity: int): Initialize cache and tracking structures
   - Use OrderedDict from collections to maintain insertion order
   - get(self, key): Retrieve value, move to end (mark as recently used)
   - put(self, key, value): Add or update, evict if capacity exceeded
   - _evict(self): Remove least recently used item
   - clear(self): Empty the cache
   - stats(self) -> dict: Return hits, misses, hit_ratio

2. Cache Decorator:
   - Create cached(ttl_seconds: int = None) function decorator
   - Use functools.wraps to preserve metadata
   - Store function results in LRUCache instance
   - Support TTL (Time To Live) with timestamp checking
   - Thread-safe with threading.RLock

3. CacheEntry Internal Class:
   - Store value, timestamp, and access_count
   - is_expired() method for TTL checking

4. Error Handling:
   - Handle type errors for unhashable keys
   - Raise CacheError for capacity violations

Include comprehensive docstrings and type hints.
        """.strip(),
        "context": """
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Optional, Dict
from time import time
import threading
        """.strip(),
        "expected_elements": [
            "class LRUCache", "__init__", "OrderedDict", "capacity",
            "get", "put", "_evict", "clear", "stats",
            "def cached", "@wraps", "LRUCache", "TTL", "timestamp",
            "class CacheEntry", "value", "is_expired",
            "threading.RLock", "class CacheError"
        ],
        "language": "python"
    },
    {
        "name": "Complex: Configuration System with Validation",
        "instruction": """
Create a comprehensive configuration management system:

1. Config Class:
   - __init__(self, config_path: str = None): Load from file or environment
   - Support multiple formats: JSON, YAML, and .env files
   - _load_from_file(): Read and parse configuration file
   - _load_from_env(): Load from environment variables with prefix
   - get(self, key: str, default: Any = None, required: bool = False) -> Any
   - set(self, key: str, value: Any): Update value
   - save(self, path: str = None): Persist to file (JSON format)

2. Validation:
   - Schema validation using _validate_schema() method
   - Type checking: str, int, float, bool, list, dict
   - Raise ConfigValidationError for invalid types
   - Support nested config validation

3. ConfigError Hierarchy:
   - ConfigError: Base exception
   - ConfigValidationError: Invalid value/type
   - ConfigFileError: File read/write errors

4. Additional Features:
   - reload() method to reload from file
   - get_all() method to return all config as dict
   - has() method to check if key exists
   - Use pathlib.Path for file operations

Include comprehensive error handling, type hints, and docstrings.
        """.strip(),
        "context": """
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union, List
        """.strip(),
        "expected_elements": [
            "class Config", "__init__", "_load_from_file", "_load_from_env",
            "get", "set", "save", "_validate_schema",
            "class ConfigError", "class ConfigValidationError", "class ConfigFileError",
            "reload", "get_all", "has", "pathlib.Path"
        ],
        "language": "python"
    },
    # ===== SIMPLE TESTS =====
    {
        "name": "Simple: Function",
        "instruction": """
Create a function called `calculate_checksum` that takes a data string and returns its SHA256 hash.
Use the hashlib module. Include proper docstring and type hints.
        """.strip(),
        "context": "",
        "expected_elements": ["def calculate_checksum", "hashlib", "sha256", "hexdigest", "-> str"],
        "language": "python"
    },
    {
        "name": "Simple: Class with Methods",
        "instruction": """
Create a class called `TaskManager` with the following:
- __init__(self): Initialize an empty list for tasks
- add_task(self, task): Add a task to the list
- remove_task(self, task): Remove a task from the list
- get_all_tasks(self): Return all tasks as a list

Include proper docstrings and type hints.
        """.strip(),
        "context": "",
        "expected_elements": ["class TaskManager", "__init__", "add_task", "remove_task", "get_all_tasks"],
        "language": "python"
    }
]


def evaluate_code_quality(generated_code: str, test_case: dict) -> dict:
    """
    Evaluate the quality of generated code.

    Returns:
        Dictionary with quality metrics
    """
    result = {
        "has_expected_elements": True,
        "missing_elements": [],
        "syntax_errors": [],
        "formatting_issues": [],
        "completeness": 0.0,
        "code_length": len(generated_code),
        "line_count": len(generated_code.splitlines())
    }

    # Check for expected elements
    for element in test_case["expected_elements"]:
        if element not in generated_code:
            result["missing_elements"].append(element)
            result["has_expected_elements"] = False

    # Check for basic syntax issues (heuristic)
    if "```" in generated_code:
        result["formatting_issues"].append("Contains markdown code blocks - should be raw code")

    # Check for placeholder text
    placeholders = ["...", "TODO", "PASS", "Your code here", "# Your implementation"]
    for placeholder in placeholders:
        if placeholder in generated_code and placeholder not in test_case["instruction"]:
            result["formatting_issues"].append(f"Contains placeholder: {placeholder}")

    # Check for incomplete implementations
    incomplete_patterns = ["pass  # TODO", "raise NotImplementedError", "return None  # TODO"]
    for pattern in incomplete_patterns:
        if pattern in generated_code:
            result["formatting_issues"].append(f"Contains incomplete implementation: {pattern}")

    # Calculate completeness score
    if test_case["expected_elements"]:
        found = len(test_case["expected_elements"]) - len(result["missing_elements"])
        result["completeness"] = found / len(test_case["expected_elements"])

    return result


def print_test_header(test_name: str):
    """Print formatted test header."""
    print("\n" + "=" * 80)
    print(f"  🧪 Test: {test_name}")
    print("=" * 80)


def print_test_result(test_name: str, instruction: str, context: str, generated_code: str, quality: dict):
    """Print formatted test result."""
    print_test_header(test_name)

    print("\n📝 Instruction:")
    print(instruction)
    print()

    if context:
        print("📚 Context:")
        print(context)
        print()

    print("✨ Generated Code:")
    print("-" * 80)
    print(generated_code)
    print("-" * 80)
    print()

    print("📊 Quality Evaluation:")
    print(f"  - Code Length: {quality['code_length']} chars ({quality['line_count']} lines)")
    print(f"  - Expected Elements Found: {quality['has_expected_elements']}")

    if quality["missing_elements"]:
        print(f"  - Missing Elements ({len(quality['missing_elements'])}): {', '.join(quality['missing_elements'][:5])}")
        if len(quality['missing_elements']) > 5:
            print(f"    ... and {len(quality['missing_elements']) - 5} more")

    if quality["formatting_issues"]:
        print(f"  - Formatting Issues ({len(quality['formatting_issues'])}):")
        for issue in quality['formatting_issues']:
            print(f"    • {issue}")

    if quality["syntax_errors"]:
        print(f"  - Syntax Errors: {', '.join(quality['syntax_errors'])}")

    print(f"  - Completeness Score: {quality['completeness']:.2%}")


async def run_code_generation_tests(llm_client: LLMClient):
    """
    Run code generation tests.

    Args:
        llm_client: LLM client to use for generation
    """
    manager = SubLLMManager(llm_client)
    tools = SubLLMTools(manager)

    results = []

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{'#' * 80}")
        print(f"# Test Case {i}/{len(TEST_CASES)}: {test_case['name']}")
        print(f"{'#' * 80}")

        try:
            # Generate code
            print(f"\n⏳ Generating code...")
            generated_code = await manager.generate_code(
                instruction=test_case["instruction"],
                context=test_case["context"]
            )

            # Check for errors
            if generated_code.startswith("Error:"):
                print(f"\n❌ Generation Error: {generated_code}")
                results.append({
                    "name": test_case["name"],
                    "status": "error",
                    "error": generated_code
                })
                continue

            # Evaluate quality
            quality = evaluate_code_quality(generated_code, test_case)

            # Print detailed results
            print_test_result(
                test_case["name"],
                test_case["instruction"],
                test_case["context"],
                generated_code,
                quality
            )

            results.append({
                "name": test_case["name"],
                "status": "success",
                "quality": quality
            })

        except Exception as e:
            print(f"\n❌ Test Execution Error: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "name": test_case["name"],
                "status": "execution_error",
                "error": str(e)
            })

    # Print summary
    print("\n" + "=" * 80)
    print("  📋 Test Summary")
    print("=" * 80)

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    exec_error_count = sum(1 for r in results if r["status"] == "execution_error")

    print(f"  - Total Tests: {len(results)}")
    print(f"  - Successful: {success_count}")
    print(f"  - Generation Errors: {error_count}")
    print(f"  - Execution Errors: {exec_error_count}")

    # Quality summary
    if success_count > 0:
        avg_completeness = sum(
            r["quality"]["completeness"] for r in results if r["status"] == "success"
        ) / success_count

        print(f"\n  📊 Quality Metrics:")
        print(f"  - Average Completeness: {avg_completeness:.2%}")

        # Check for formatting issues across all tests
        all_formatting_issues = []
        for r in results:
            if r["status"] == "success":
                all_formatting_issues.extend(r["quality"].get("formatting_issues", []))

        if all_formatting_issues:
            print(f"\n  ⚠️  Common Formatting Issues:")
            unique_issues = set(all_formatting_issues)
            for issue in unique_issues:
                count = all_formatting_issues.count(issue)
                print(f"    - {issue} (appeared {count} times)")

        # Code length analysis
        total_chars = sum(r["quality"].get("code_length", 0) for r in results if r["status"] == "success")
        total_lines = sum(r["quality"].get("line_count", 0) for r in results if r["status"] == "success")
        avg_chars = total_chars / success_count
        avg_lines = total_lines / success_count

        print(f"\n  📏 Code Size Analysis:")
        print(f"  - Total Generated: {total_chars} chars, {total_lines} lines")
        print(f"  - Average per Test: {avg_chars:.0f} chars, {avg_lines:.0f} lines")


async def main():
    """Main test execution."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                                ║
    ║     🦆 Duckflow Code Generation Tool - Complex Test            ║
    ║                                                                ║
    ╚══════════════════════════════════════════════════════════════╝

    This test will evaluate the code generation quality of Sub-LLM.
    For each test case, you'll see:
      1. The instruction given to the Sub-LLM
      2. Any context provided
      3. The generated code
      4. An automated quality evaluation

    Tests will run automatically with 4 complex and 2 simple cases.
    """)

    # Test connection
    print("\n🔌 Testing LLM connection...")
    try:
        connection_ok = await default_client.test_connection()
        if not connection_ok:
            print("❌ LLM connection failed. Please check your API configuration.")
            return
        print("✅ LLM connection successful")
    except Exception as e:
        print(f"❌ LLM connection error: {e}")
        return

    # Run tests
    await run_code_generation_tests(default_client)

    print("\n✅ All tests completed.")


if __name__ == "__main__":
    asyncio.run(main())
