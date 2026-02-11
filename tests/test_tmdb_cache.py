"""Tests for TMDb cache with SQLite backend."""

import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path
from server.tmdb_cache import TMDbCache


@pytest.mark.asyncio
class TestTMDbCache:
    """Test TMDb cache functionality."""

    async def test_cache_initialization(self, temp_dir):
        """Test cache creates database and table on init."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        assert db_path.exists()
        await cache.close()

    async def test_store_and_retrieve_movie(self, temp_dir, mock_tmdb_movie_result):
        """Test storing and retrieving a movie result."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        # Store result
        await cache.store(
            title="Inception",
            year=2010,
            media_type="movie",
            result=mock_tmdb_movie_result
        )

        # Retrieve result
        result = await cache.get(title="Inception", year=2010, media_type="movie")

        assert result is not None
        assert result["id"] == 27205
        assert result["title"] == "Inception"
        assert result["media_type"] == "movie"

        await cache.close()

    async def test_store_and_retrieve_tv_show(self, temp_dir, mock_tmdb_tv_result):
        """Test storing and retrieving a TV show result."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        # Store result
        await cache.store(
            title="Breaking Bad",
            year=2008,
            media_type="tv",
            result=mock_tmdb_tv_result
        )

        # Retrieve result
        result = await cache.get(title="Breaking Bad", year=2008, media_type="tv")

        assert result is not None
        assert result["id"] == 1396
        assert result["name"] == "Breaking Bad"
        assert result["media_type"] == "tv"

        await cache.close()

    async def test_cache_miss_returns_none(self, temp_dir):
        """Test cache returns None for non-existent entries."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        result = await cache.get(title="NonExistent", year=2000, media_type="movie")

        assert result is None
        await cache.close()

    async def test_cache_key_collision_handling(self, temp_dir, mock_tmdb_movie_result):
        """Test that cache handles key collisions properly."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        # Store first result
        await cache.store(
            title="The Matrix",
            year=1999,
            media_type="movie",
            result=mock_tmdb_movie_result
        )

        # Store updated result with same key (should replace)
        updated_result = mock_tmdb_movie_result.copy()
        updated_result["popularity"] = 999.999

        await cache.store(
            title="The Matrix",
            year=1999,
            media_type="movie",
            result=updated_result
        )

        # Retrieve should get updated result
        result = await cache.get(title="The Matrix", year=1999, media_type="movie")

        assert result is not None
        assert result["popularity"] == 999.999

        await cache.close()

    async def test_ttl_expiry(self, temp_dir, mock_tmdb_movie_result):
        """Test that expired cache entries are not returned."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path, ttl_days=0)  # Expire immediately for testing
        await cache.initialize()

        # Store result
        await cache.store(
            title="Inception",
            year=2010,
            media_type="movie",
            result=mock_tmdb_movie_result
        )

        # Wait a moment to ensure expiry
        time.sleep(0.1)

        # Should return None due to expiry
        result = await cache.get(title="Inception", year=2010, media_type="movie")

        assert result is None
        await cache.close()

    async def test_ttl_not_expired(self, temp_dir, mock_tmdb_movie_result):
        """Test that non-expired cache entries are returned."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path, ttl_days=30)
        await cache.initialize()

        # Store result
        await cache.store(
            title="Inception",
            year=2010,
            media_type="movie",
            result=mock_tmdb_movie_result
        )

        # Should return result (not expired)
        result = await cache.get(title="Inception", year=2010, media_type="movie")

        assert result is not None
        assert result["id"] == 27205

        await cache.close()

    async def test_year_is_optional(self, temp_dir, mock_tmdb_tv_result):
        """Test cache works with None year."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        # Store without year
        await cache.store(
            title="Breaking Bad",
            year=None,
            media_type="tv",
            result=mock_tmdb_tv_result
        )

        # Retrieve without year
        result = await cache.get(title="Breaking Bad", year=None, media_type="tv")

        assert result is not None
        assert result["id"] == 1396

        await cache.close()

    async def test_clear_cache(self, temp_dir, mock_tmdb_movie_result):
        """Test clearing all cache entries."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        # Store results
        await cache.store("Movie1", 2020, "movie", mock_tmdb_movie_result)
        await cache.store("Movie2", 2021, "movie", mock_tmdb_movie_result)

        # Clear cache
        await cache.clear()

        # Both should be gone
        result1 = await cache.get("Movie1", 2020, "movie")
        result2 = await cache.get("Movie2", 2021, "movie")

        assert result1 is None
        assert result2 is None

        await cache.close()

    async def test_case_insensitive_title_lookup(self, temp_dir, mock_tmdb_movie_result):
        """Test that title lookups are case-insensitive."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        # Store with mixed case
        await cache.store("The Matrix", 1999, "movie", mock_tmdb_movie_result)

        # Retrieve with different case
        result = await cache.get("the matrix", 1999, "movie")

        assert result is not None

        await cache.close()

    async def test_multiple_media_types_same_title_year(self, temp_dir, mock_tmdb_movie_result, mock_tmdb_tv_result):
        """Test storing movie and TV show with same title and year."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        # Store movie
        await cache.store("Test Title", 2020, "movie", mock_tmdb_movie_result)

        # Store TV show with same title/year
        await cache.store("Test Title", 2020, "tv", mock_tmdb_tv_result)

        # Both should be retrievable
        movie_result = await cache.get("Test Title", 2020, "movie")
        tv_result = await cache.get("Test Title", 2020, "tv")

        assert movie_result is not None
        assert tv_result is not None
        assert movie_result["media_type"] == "movie"
        assert tv_result["media_type"] == "tv"

        await cache.close()

    async def test_cache_stats(self, temp_dir, mock_tmdb_movie_result):
        """Test retrieving cache statistics."""
        db_path = temp_dir / "tmdb_cache.db"
        cache = TMDbCache(db_path)
        await cache.initialize()

        # Store some results
        await cache.store("Movie1", 2020, "movie", mock_tmdb_movie_result)
        await cache.store("Movie2", 2021, "movie", mock_tmdb_movie_result)
        await cache.store("Show1", 2022, "tv", mock_tmdb_movie_result)

        stats = await cache.get_stats()

        assert stats["total_entries"] == 3
        assert stats["movie_count"] >= 2
        assert stats["tv_count"] >= 1

        await cache.close()
