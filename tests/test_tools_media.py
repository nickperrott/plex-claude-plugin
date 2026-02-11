"""Tests for Media MCP tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from server.tools.media import (
    parse_filename,
    search_tmdb,
    preview_rename,
    batch_identify
)


@pytest.mark.asyncio
class TestMediaTools:
    """Test Media MCP tool functions."""

    async def test_parse_filename_tool(self, mock_guessit_movie):
        """Test parse_filename tool."""
        with patch("guessit.guessit") as mock_guessit:
            mock_guessit.return_value = mock_guessit_movie

            result = await parse_filename(filename="Inception.2010.1080p.BluRay.x264.mkv")

            assert result["success"] is True
            assert result["parsed"]["title"] == "Inception"
            assert result["parsed"]["year"] == 2010
            assert result["parsed"]["type"] == "movie"

    async def test_parse_filename_tool_tv(self, mock_guessit_tv):
        """Test parse_filename tool with TV episode."""
        with patch("guessit.guessit") as mock_guessit:
            mock_guessit.return_value = mock_guessit_tv

            result = await parse_filename(filename="Breaking.Bad.S01E01.mkv")

            assert result["success"] is True
            assert result["parsed"]["title"] == "Breaking Bad"
            assert result["parsed"]["season"] == 1
            assert result["parsed"]["episode"] == 1
            assert result["parsed"]["type"] == "episode"

    async def test_parse_filename_tool_error(self):
        """Test parse_filename tool error handling."""
        with patch("guessit.guessit") as mock_guessit:
            mock_guessit.side_effect = Exception("Parse error")

            result = await parse_filename(filename="invalid.txt")

            assert result["success"] is False
            assert "error" in result

    async def test_search_tmdb_tool_movie(self, mock_tmdb_movie_result):
        """Test search_tmdb tool for movies."""
        mock_matcher = AsyncMock()
        mock_matcher.search_tmdb.return_value = [mock_tmdb_movie_result]

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await search_tmdb(
                title="Inception",
                year=2010,
                media_type="movie"
            )

            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["results"][0]["id"] == 27205
            assert result["results"][0]["title"] == "Inception"

    async def test_search_tmdb_tool_tv(self, mock_tmdb_tv_result):
        """Test search_tmdb tool for TV shows."""
        mock_matcher = AsyncMock()
        mock_matcher.search_tmdb.return_value = [mock_tmdb_tv_result]

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await search_tmdb(
                title="Breaking Bad",
                year=2008,
                media_type="tv"
            )

            assert result["success"] is True
            assert len(result["results"]) == 1
            assert result["results"][0]["id"] == 1396
            assert result["results"][0]["name"] == "Breaking Bad"

    async def test_search_tmdb_tool_no_results(self):
        """Test search_tmdb tool with no results."""
        mock_matcher = AsyncMock()
        mock_matcher.search_tmdb.return_value = []

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await search_tmdb(
                title="NonExistent Movie",
                year=2000,
                media_type="movie"
            )

            assert result["success"] is True
            assert len(result["results"]) == 0
            assert "message" in result

    async def test_search_tmdb_tool_error(self):
        """Test search_tmdb tool error handling."""
        mock_matcher = AsyncMock()
        mock_matcher.search_tmdb.side_effect = Exception("API error")

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await search_tmdb(
                title="Test",
                media_type="movie"
            )

            assert result["success"] is False
            assert "error" in result

    async def test_preview_rename_tool_movie(self, mock_guessit_movie, mock_tmdb_movie_result):
        """Test preview_rename tool for a movie."""
        mock_matcher = AsyncMock()
        mock_matcher.match_media.return_value = {
            "parsed": mock_guessit_movie,
            "tmdb_id": 27205,
            "tmdb_result": mock_tmdb_movie_result,
            "confidence": 0.95,
            "plex_path": "/data/media/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv"
        }

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await preview_rename(
                filename="Inception.2010.1080p.BluRay.x264.mkv"
            )

            assert result["success"] is True
            assert result["original_filename"] == "Inception.2010.1080p.BluRay.x264.mkv"
            assert result["tmdb_id"] == 27205
            assert result["confidence"] == 0.95
            assert "Inception (2010) {tmdb-27205}" in result["plex_path"]

    async def test_preview_rename_tool_tv(self, mock_guessit_tv, mock_tmdb_tv_result):
        """Test preview_rename tool for a TV episode."""
        mock_matcher = AsyncMock()
        mock_matcher.match_media.return_value = {
            "parsed": mock_guessit_tv,
            "tmdb_id": 1396,
            "tmdb_result": mock_tmdb_tv_result,
            "confidence": 0.92,
            "plex_path": "/data/media/TV Shows/Breaking Bad (2008)/Season 01/Breaking Bad (2008) - s01e01 - Pilot.mkv"
        }

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await preview_rename(
                filename="Breaking.Bad.S01E01.mkv"
            )

            assert result["success"] is True
            assert result["tmdb_id"] == 1396
            assert "Breaking Bad (2008)" in result["plex_path"]
            assert "s01e01" in result["plex_path"]

    async def test_preview_rename_tool_no_match(self):
        """Test preview_rename tool when no match is found."""
        mock_matcher = AsyncMock()
        mock_matcher.match_media.return_value = None

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await preview_rename(
                filename="Unknown.Movie.mkv"
            )

            assert result["success"] is False
            assert "error" in result
            assert "No match found" in result["error"]

    async def test_preview_rename_tool_low_confidence(self, mock_guessit_movie, mock_tmdb_movie_result):
        """Test preview_rename tool with low confidence match."""
        mock_matcher = AsyncMock()
        mock_matcher.match_media.return_value = {
            "parsed": mock_guessit_movie,
            "tmdb_id": 27205,
            "tmdb_result": mock_tmdb_movie_result,
            "confidence": 0.65,
            "plex_path": "/data/media/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv"
        }

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await preview_rename(
                filename="Inception.2010.mkv"
            )

            assert result["success"] is True
            assert result["confidence"] == 0.65
            assert "warning" in result
            assert "low confidence" in result["warning"].lower()

    async def test_batch_identify_tool(self, mock_guessit_movie, mock_tmdb_movie_result):
        """Test batch_identify tool with multiple files."""
        mock_matcher = AsyncMock()
        mock_matcher.batch_match.return_value = [
            {
                "parsed": mock_guessit_movie,
                "tmdb_id": 27205,
                "tmdb_result": mock_tmdb_movie_result,
                "confidence": 0.95,
                "plex_path": "/data/media/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv"
            },
            {
                "parsed": {"title": "The Matrix", "year": 1999, "type": "movie"},
                "tmdb_id": 603,
                "tmdb_result": {"id": 603, "title": "The Matrix"},
                "confidence": 0.93,
                "plex_path": "/data/media/Movies/The Matrix (1999) {tmdb-603}/The Matrix (1999) {tmdb-603}.mkv"
            }
        ]

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await batch_identify(
                filenames=[
                    "Inception.2010.1080p.mkv",
                    "The.Matrix.1999.720p.mkv"
                ]
            )

            assert result["success"] is True
            assert result["total"] == 2
            assert result["matched"] == 2
            assert result["failed"] == 0
            assert len(result["results"]) == 2

    async def test_batch_identify_tool_with_failures(self, mock_guessit_movie, mock_tmdb_movie_result):
        """Test batch_identify tool with some failed matches."""
        mock_matcher = AsyncMock()
        mock_matcher.batch_match.return_value = [
            {
                "parsed": mock_guessit_movie,
                "tmdb_id": 27205,
                "tmdb_result": mock_tmdb_movie_result,
                "confidence": 0.95,
                "plex_path": "/data/media/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv"
            },
            None  # Failed match
        ]

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await batch_identify(
                filenames=[
                    "Inception.2010.mkv",
                    "Unknown.Movie.mkv"
                ]
            )

            assert result["success"] is True
            assert result["total"] == 2
            assert result["matched"] == 1
            assert result["failed"] == 1

    async def test_batch_identify_tool_empty_list(self):
        """Test batch_identify tool with empty filename list."""
        result = await batch_identify(filenames=[])

        assert result["success"] is False
        assert "error" in result

    async def test_batch_identify_tool_confidence_threshold(self, mock_guessit_movie, mock_tmdb_movie_result):
        """Test batch_identify tool with confidence threshold."""
        mock_matcher = AsyncMock()
        mock_matcher.batch_match.return_value = [
            {
                "parsed": mock_guessit_movie,
                "tmdb_id": 27205,
                "tmdb_result": mock_tmdb_movie_result,
                "confidence": 0.95,
                "plex_path": "/data/media/Movies/Inception (2010) {tmdb-27205}/Inception (2010) {tmdb-27205}.mkv"
            },
            {
                "parsed": {"title": "Unknown", "year": 2000, "type": "movie"},
                "tmdb_id": 999,
                "tmdb_result": {"id": 999, "title": "Unknown"},
                "confidence": 0.60,  # Below threshold
                "plex_path": "/data/media/Movies/Unknown (2000) {tmdb-999}/Unknown (2000) {tmdb-999}.mkv"
            }
        ]

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await batch_identify(
                filenames=["Inception.2010.mkv", "Unknown.2000.mkv"],
                confidence_threshold=0.85
            )

            assert result["success"] is True
            assert result["total"] == 2
            # Second result should be flagged as low confidence
            low_confidence_count = sum(
                1 for r in result["results"]
                if r and r.get("confidence", 1.0) < 0.85
            )
            assert low_confidence_count == 1

    async def test_batch_identify_tool_error(self):
        """Test batch_identify tool error handling."""
        mock_matcher = AsyncMock()
        mock_matcher.batch_match.side_effect = Exception("Batch error")

        with patch("server.tools.media.get_matcher", return_value=mock_matcher):
            result = await batch_identify(
                filenames=["test.mkv"]
            )

            assert result["success"] is False
            assert "error" in result
