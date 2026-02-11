"""Tests for PlexClient protocol and factory."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from typing import Protocol

from server.client import PlexClient, create_plex_client, PlexAPIClient


# =============================================================================
# Protocol Tests
# =============================================================================


def test_plex_client_is_protocol():
    """PlexClient should be a Protocol class."""
    assert issubclass(PlexClient, Protocol)


def test_plex_client_has_required_methods():
    """PlexClient protocol should define all required async methods."""
    required_methods = [
        "list_libraries",
        "scan_library",
        "search_library",
        "list_recent",
        "get_server_info",
    ]

    for method_name in required_methods:
        assert hasattr(PlexClient, method_name)


# =============================================================================
# Factory Tests
# =============================================================================


@patch("server.client.PlexServer")
def test_create_plex_client_reads_env_vars(mock_plex_server_class, mock_env):
    """Factory should read PLEX_URL and PLEX_TOKEN from environment."""
    mock_server = MagicMock()
    mock_plex_server_class.return_value = mock_server

    client = create_plex_client()

    # Verify PlexServer was instantiated with correct values
    mock_plex_server_class.assert_called_once_with(
        "http://localhost:32400",
        "test-token-12345"
    )

    assert isinstance(client, PlexAPIClient)


@patch("server.client.PlexServer")
def test_create_plex_client_missing_url(mock_plex_server_class, monkeypatch):
    """Factory should raise ValueError if PLEX_URL is missing."""
    monkeypatch.delenv("PLEX_URL", raising=False)
    monkeypatch.setenv("PLEX_TOKEN", "test-token")

    with pytest.raises(ValueError, match="PLEX_URL environment variable is required"):
        create_plex_client()


@patch("server.client.PlexServer")
def test_create_plex_client_missing_token(mock_plex_server_class, monkeypatch):
    """Factory should raise ValueError if PLEX_TOKEN is missing."""
    monkeypatch.setenv("PLEX_URL", "http://localhost:32400")
    monkeypatch.delenv("PLEX_TOKEN", raising=False)

    with pytest.raises(ValueError, match="PLEX_TOKEN environment variable is required"):
        create_plex_client()


# =============================================================================
# PlexAPIClient Implementation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_libraries_async_wrapping(mock_plex_server):
    """list_libraries should wrap synchronous plexapi call with asyncio.to_thread."""
    client = PlexAPIClient(mock_plex_server)

    result = await client.list_libraries()

    assert isinstance(result, list)
    assert len(result) == 2

    # Verify first library
    assert result[0]["key"] == "1"
    assert result[0]["title"] == "Movies"
    assert result[0]["type"] == "movie"
    assert result[0]["locations"] == ["/data/media/Movies"]

    # Verify second library
    assert result[1]["key"] == "2"
    assert result[1]["title"] == "TV Shows"
    assert result[1]["type"] == "show"
    assert result[1]["locations"] == ["/data/media/TV Shows"]


@pytest.mark.asyncio
async def test_scan_library_async_wrapping(mock_plex_server):
    """scan_library should wrap synchronous plexapi call with asyncio.to_thread."""
    client = PlexAPIClient(mock_plex_server)

    # Mock the section lookup and update
    section = MagicMock()
    section.update = MagicMock()
    mock_plex_server.library.section.return_value = section

    result = await client.scan_library("1")

    assert result["status"] == "success"
    assert result["section_id"] == "1"
    mock_plex_server.library.section.assert_called_once_with("1")
    section.update.assert_called_once()


@pytest.mark.asyncio
async def test_search_library_async_wrapping(mock_plex_server):
    """search_library should wrap synchronous plexapi call with asyncio.to_thread."""
    client = PlexAPIClient(mock_plex_server)

    # Mock the section lookup and search
    section = MagicMock()
    movie_result = MagicMock()
    movie_result.title = "Inception"
    movie_result.year = 2010
    movie_result.type = "movie"
    section.search.return_value = [movie_result]
    mock_plex_server.library.section.return_value = section

    result = await client.search_library("1", "Inception")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["title"] == "Inception"
    assert result[0]["year"] == 2010
    assert result[0]["type"] == "movie"

    mock_plex_server.library.section.assert_called_once_with("1")
    section.search.assert_called_once_with("Inception")


@pytest.mark.asyncio
async def test_list_recent_async_wrapping(mock_plex_server):
    """list_recent should wrap synchronous plexapi call with asyncio.to_thread."""
    client = PlexAPIClient(mock_plex_server)

    # Mock the section lookup and recentlyAdded
    section = MagicMock()
    movie_result = MagicMock()
    movie_result.title = "The Matrix"
    movie_result.year = 1999
    movie_result.type = "movie"
    movie_result.addedAt = 1609459200
    section.recentlyAdded.return_value = [movie_result]
    mock_plex_server.library.section.return_value = section

    result = await client.list_recent("1", 10)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["title"] == "The Matrix"
    assert result[0]["year"] == 1999
    assert result[0]["type"] == "movie"
    assert result[0]["addedAt"] == 1609459200

    mock_plex_server.library.section.assert_called_once_with("1")
    section.recentlyAdded.assert_called_once_with(maxresults=10)


@pytest.mark.asyncio
async def test_get_server_info_async_wrapping(mock_plex_server):
    """get_server_info should wrap synchronous plexapi call with asyncio.to_thread."""
    client = PlexAPIClient(mock_plex_server)

    result = await client.get_server_info()

    assert result["name"] == "Test Plex Server"
    assert result["version"] == "1.40.0.0000-deadbeef"
    assert result["platform"] == "Linux"
    assert result["machineIdentifier"] == "test-machine-id"


@pytest.mark.asyncio
async def test_scan_library_section_not_found(mock_plex_server):
    """scan_library should raise error when section not found."""
    client = PlexAPIClient(mock_plex_server)

    from plexapi.exceptions import NotFound
    mock_plex_server.library.section.side_effect = NotFound("Section not found")

    with pytest.raises(NotFound):
        await client.scan_library("999")


@pytest.mark.asyncio
async def test_search_library_section_not_found(mock_plex_server):
    """search_library should raise error when section not found."""
    client = PlexAPIClient(mock_plex_server)

    from plexapi.exceptions import NotFound
    mock_plex_server.library.section.side_effect = NotFound("Section not found")

    with pytest.raises(NotFound):
        await client.search_library("999", "test")


@pytest.mark.asyncio
async def test_list_recent_section_not_found(mock_plex_server):
    """list_recent should raise error when section not found."""
    client = PlexAPIClient(mock_plex_server)

    from plexapi.exceptions import NotFound
    mock_plex_server.library.section.side_effect = NotFound("Section not found")

    with pytest.raises(NotFound):
        await client.list_recent("999", 10)
