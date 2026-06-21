"""Tests for S3-9: API retry with exponential backoff."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from openai import APIError

from companion.base.llm_client import LLMClient, _get_retry_after


def _make_api_error(status_code: int, retry_after: str | None = None) -> APIError:
    """Create a mock APIError with a status code and optional Retry-After header."""
    headers = {}
    if retry_after:
        headers["Retry-After"] = retry_after

    response = MagicMock()
    response.headers = headers
    response.status_code = status_code

    error = APIError(
        message=f"Test error {status_code}",
        request=MagicMock(),
        body=None,
    )
    error.status_code = status_code
    error.response = response
    return error


def _make_client() -> LLMClient:
    """Create a mock LLMClient for testing (no real API key needed)."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
        client = LLMClient.__new__(LLMClient)
        client.provider = "openrouter"
        client.model = "test-model"
        client.base_url = "https://openrouter.ai/api/v1"
        client.api_key = "test-key"
        client.use_mock = False
        client.timeout = 60.0
        client.usage_stats = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cost_estimate": 0.0,
            "retry_count": 0,
            "retry_successes": 0,
        }
        client.client = AsyncMock()
        return client


@pytest.mark.asyncio
async def test_retry_succeeds_on_429():
    """APIError(429) on first call, success on second."""
    client = _make_client()

    success_response = MagicMock()
    success_response.choices = [MagicMock()]
    success_response.choices[0].message.content = "::response\n<<<\nhi\n>>>"
    success_response.usage = None

    error = _make_api_error(429)
    client.client.chat.completions.create = AsyncMock(
        side_effect=[error, success_response]
    )

    # Patch sleep to avoid real delay
    with patch("asyncio.sleep", new_callable=AsyncMock):
        response = await client._call_with_retry(
            model="test", messages=[], temperature=0.7
        )

    assert response is success_response
    assert client.usage_stats["retry_count"] == 1
    assert client.usage_stats["retry_successes"] == 1


@pytest.mark.asyncio
async def test_retry_fails_after_max_retries():
    """APIError(500) on all attempts → exception re-raised."""
    client = _make_client()
    error = _make_api_error(500)
    client.client.chat.completions.create = AsyncMock(side_effect=error)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(APIError):
            await client._call_with_retry(
                model="test", messages=[], temperature=0.7
            )

    assert client.usage_stats["retry_count"] == 3  # max_retries=3


@pytest.mark.asyncio
async def test_retry_succeeds_on_timeout():
    """TimeoutError on first call, success on second."""
    client = _make_client()

    success_response = MagicMock()
    success_response.choices = [MagicMock()]
    success_response.choices[0].message.content = "::response\n<<<\nhi\n>>>"
    success_response.usage = None

    client.client.chat.completions.create = AsyncMock(
        side_effect=[asyncio.TimeoutError(), success_response]
    )

    with patch("asyncio.sleep", new_callable=AsyncMock):
        response = await client._call_with_retry(
            model="test", messages=[], temperature=0.7
        )

    assert response is success_response
    assert client.usage_stats["retry_count"] == 1
    assert client.usage_stats["retry_successes"] == 1


@pytest.mark.asyncio
async def test_non_retryable_error_not_retried():
    """APIError(400) should not be retried (not in retryable codes)."""
    client = _make_client()
    error = _make_api_error(400)
    client.client.chat.completions.create = AsyncMock(side_effect=error)

    with pytest.raises(APIError):
        await client._call_with_retry(
            model="test", messages=[], temperature=0.7
        )

    assert client.usage_stats["retry_count"] == 0


def test_get_retry_after_from_header():
    """_get_retry_after extracts Retry-After header value."""
    error = _make_api_error(429, retry_after="5")
    assert _get_retry_after(error) == 5.0


def test_get_retry_after_none_when_absent():
    """_get_retry_after returns None when header is absent."""
    error = _make_api_error(429)
    assert _get_retry_after(error) is None
