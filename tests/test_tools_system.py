"""Tests for system MCP tools."""

import pytest
from unittest.mock import AsyncMock
from typing import Any, Dict

from server.tools.system import get_server_info


# =============================================================================
# get_server_info Tool Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_server_info_success(mock_async_plex_client):
    """get_server_info should return server information."""
    result = await get_server_info(mock_async_plex_client)

    assert isinstance(result, dict)
    assert result["name"] == "Test Plex Server"
    assert result["version"] == "1.40.0.0000-deadbeef"
    assert result["platform"] == "Linux"

    mock_async_plex_client.get_server_info.assert_called_once()


@pytest.mark.asyncio
async def test_get_server_info_complete_fields(mock_async_plex_client):
    """get_server_info should return all expected fields."""
    mock_async_plex_client.get_server_info = AsyncMock(return_value={
        "name": "Test Plex Server",
        "version": "1.40.0.0000-deadbeef",
        "platform": "Linux",
        "machineIdentifier": "test-machine-id",
        "updatedAt": 1609459200
    })

    result = await get_server_info(mock_async_plex_client)

    assert "name" in result
    assert "version" in result
    assert "platform" in result
    assert "machineIdentifier" in result
    assert result["machineIdentifier"] == "test-machine-id"


@pytest.mark.asyncio
async def test_get_server_info_error_handling(mock_async_plex_client):
    """get_server_info should raise exception on connection error."""
    mock_async_plex_client.get_server_info = AsyncMock(
        side_effect=Exception("Connection failed")
    )

    with pytest.raises(Exception, match="Connection failed"):
        await get_server_info(mock_async_plex_client)


@pytest.mark.asyncio
async def test_get_server_info_unauthorized(mock_async_plex_client):
    """get_server_info should handle unauthorized access."""
    from plexapi.exceptions import Unauthorized

    mock_async_plex_client.get_server_info = AsyncMock(
        side_effect=Unauthorized("Invalid token")
    )

    with pytest.raises(Unauthorized, match="Invalid token"):
        await get_server_info(mock_async_plex_client)


@pytest.mark.asyncio
async def test_get_server_info_timeout(mock_async_plex_client):
    """get_server_info should handle timeout."""
    import asyncio

    mock_async_plex_client.get_server_info = AsyncMock(
        side_effect=asyncio.TimeoutError("Request timeout")
    )

    with pytest.raises(asyncio.TimeoutError):
        await get_server_info(mock_async_plex_client)
