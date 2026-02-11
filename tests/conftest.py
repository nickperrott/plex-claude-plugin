"""Shared pytest fixtures for Plex Claude Plugin tests."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any


# =============================================================================
# Mock Plex Server Fixtures
# =============================================================================

@pytest.fixture
def mock_plex_server():
    """Mock PlexServer instance with common library sections."""
    server = MagicMock()
    server.friendlyName = "Test Plex Server"
    server.version = "1.40.0.0000-deadbeef"
    server.platform = "Linux"
    server.machineIdentifier = "test-machine-id"

    # Mock library sections
    movies_section = MagicMock()
    movies_section.key = "1"
    movies_section.title = "Movies"
    movies_section.type = "movie"
    movies_section.locations = ["/data/media/Movies"]

    tv_section = MagicMock()
    tv_section.key = "2"
    tv_section.title = "TV Shows"
    tv_section.type = "show"
    tv_section.locations = ["/data/media/TV Shows"]

    server.library.sections.return_value = [movies_section, tv_section]

    # Mock search results
    movie_result = MagicMock()
    movie_result.title = "Inception"
    movie_result.year = 2010
    movie_result.type = "movie"
    movie_result.addedAt = 1609459200

    tv_result = MagicMock()
    tv_result.title = "Breaking Bad"
    tv_result.year = 2008
    tv_result.type = "show"
    tv_result.addedAt = 1609459200

    server.library.search.return_value = [movie_result, tv_result]
    server.library.recentlyAdded.return_value = [movie_result]

    return server


@pytest.fixture
def mock_plex_section():
    """Mock Plex library section."""
    section = MagicMock()
    section.key = "1"
    section.title = "Movies"
    section.type = "movie"
    section.locations = ["/data/media/Movies"]

    # Mock items
    item = MagicMock()
    item.title = "The Matrix"
    item.year = 1999
    item.type = "movie"

    section.all.return_value = [item]
    section.search.return_value = [item]
    section.update = MagicMock()

    return section


# =============================================================================
# Mock TMDb API Fixtures
# =============================================================================

@pytest.fixture
def mock_tmdb_movie_result() -> Dict[str, Any]:
    """Mock TMDb movie search result."""
    return {
        "id": 27205,
        "title": "Inception",
        "release_date": "2010-07-16",
        "popularity": 87.234,
        "overview": "A thief who steals corporate secrets...",
        "media_type": "movie",
        "vote_average": 8.4,
        "original_language": "en"
    }


@pytest.fixture
def mock_tmdb_tv_result() -> Dict[str, Any]:
    """Mock TMDb TV show search result."""
    return {
        "id": 1396,
        "name": "Breaking Bad",
        "first_air_date": "2008-01-20",
        "popularity": 123.456,
        "overview": "A high school chemistry teacher...",
        "media_type": "tv",
        "vote_average": 9.3,
        "original_language": "en"
    }


@pytest.fixture
def mock_tmdb_episode_result() -> Dict[str, Any]:
    """Mock TMDb episode details."""
    return {
        "id": 62085,
        "name": "Pilot",
        "season_number": 1,
        "episode_number": 1,
        "air_date": "2008-01-20",
        "overview": "When an unassuming high school chemistry teacher...",
        "still_path": "/ydlY3iPfeOAvu8gVqrxPoMvzNCn.jpg"
    }


@pytest.fixture
def mock_tmdb_search_response(mock_tmdb_movie_result) -> Dict[str, Any]:
    """Mock TMDb search API response."""
    return {
        "page": 1,
        "total_pages": 1,
        "total_results": 1,
        "results": [mock_tmdb_movie_result]
    }


# =============================================================================
# Guessit Fixtures
# =============================================================================

@pytest.fixture
def mock_guessit_movie() -> Dict[str, Any]:
    """Mock guessit output for a movie filename."""
    return {
        "title": "Inception",
        "year": 2010,
        "screen_size": "1080p",
        "source": "BluRay",
        "video_codec": "x264",
        "type": "movie"
    }


@pytest.fixture
def mock_guessit_tv() -> Dict[str, Any]:
    """Mock guessit output for a TV episode filename."""
    return {
        "title": "Breaking Bad",
        "season": 1,
        "episode": 1,
        "screen_size": "1080p",
        "source": "BluRay",
        "video_codec": "x264",
        "type": "episode"
    }


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory that is cleaned up after the test."""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def temp_media_root(temp_dir):
    """Create a temporary media root directory structure."""
    media_root = temp_dir / "media"
    media_root.mkdir()

    # Create library directories
    movies_dir = media_root / "Movies"
    movies_dir.mkdir()

    tv_dir = media_root / "TV Shows"
    tv_dir.mkdir()

    return media_root


@pytest.fixture
def temp_ingest_dir(temp_dir):
    """Create a temporary ingest directory."""
    ingest_dir = temp_dir / "ingest"
    ingest_dir.mkdir()
    return ingest_dir


@pytest.fixture
def sample_video_file(temp_ingest_dir):
    """Create a sample video file for testing."""
    video_file = temp_ingest_dir / "Inception.2010.1080p.BluRay.x264.mkv"
    video_file.write_text("fake video content")
    return video_file


@pytest.fixture
def sample_tv_file(temp_ingest_dir):
    """Create a sample TV episode file for testing."""
    tv_file = temp_ingest_dir / "Breaking.Bad.S01E01.1080p.BluRay.x264.mkv"
    tv_file.write_text("fake tv episode content")
    return tv_file


# =============================================================================
# SQLite Database Fixtures
# =============================================================================

@pytest.fixture
async def temp_db(temp_dir):
    """Create a temporary SQLite database."""
    db_path = temp_dir / "test.db"
    yield db_path
    # Cleanup happens automatically with temp_dir


# =============================================================================
# Environment Variable Fixtures
# =============================================================================

@pytest.fixture
def mock_env(monkeypatch, temp_media_root, temp_ingest_dir):
    """Set up mock environment variables for testing."""
    env_vars = {
        "PLEX_URL": "http://localhost:32400",
        "PLEX_TOKEN": "test-token-12345",
        "TMDB_API_KEY": "test-tmdb-api-key",
        "PLEX_MEDIA_ROOT": str(temp_media_root),
        "PLEX_INGEST_DIR": str(temp_ingest_dir),
        "PLEX_AUTO_INGEST": "false",
        "PLEX_CONFIDENCE_THRESHOLD": "0.85",
        "PLEX_WATCHER_AUTO_START": "false"
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


# =============================================================================
# Mock Async Client Fixtures
# =============================================================================

@pytest.fixture
def mock_async_plex_client(mock_plex_server):
    """Create a mock async PlexClient for testing."""
    client = AsyncMock()
    client.server = mock_plex_server
    client.list_libraries = AsyncMock(return_value=[
        {
            "key": "1",
            "title": "Movies",
            "type": "movie",
            "locations": ["/data/media/Movies"]
        },
        {
            "key": "2",
            "title": "TV Shows",
            "type": "show",
            "locations": ["/data/media/TV Shows"]
        }
    ])
    client.get_server_info = AsyncMock(return_value={
        "name": "Test Plex Server",
        "version": "1.40.0.0000-deadbeef",
        "platform": "Linux"
    })
    return client


# =============================================================================
# File Extension Fixtures
# =============================================================================

@pytest.fixture
def valid_video_extensions():
    """List of valid video file extensions."""
    return [".mkv", ".mp4", ".avi", ".m4v", ".ts", ".wmv", ".mov"]


@pytest.fixture
def invalid_extensions():
    """List of invalid file extensions."""
    return [".txt", ".jpg", ".png", ".nfo", ".srt", ".exe"]
