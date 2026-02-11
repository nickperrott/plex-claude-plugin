"""SQLite-backed cache for TMDb API results."""

import json
import aiosqlite
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional


class TMDbCache:
    """SQLite cache for TMDb API results with TTL support."""

    def __init__(self, db_path: Path | str, ttl_days: int = 30):
        """Initialize TMDb cache.

        Args:
            db_path: Path to SQLite database file
            ttl_days: Time-to-live in days (default 30 days)
        """
        self.db_path = Path(db_path)
        self.ttl_days = ttl_days
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize database and create tables if needed."""
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS tmdb_cache (
                title TEXT NOT NULL,
                year INTEGER,
                media_type TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (title, year, media_type)
            )
        """)
        await self._conn.commit()

    async def close(self):
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def store(
        self,
        title: str,
        year: Optional[int],
        media_type: str,
        result: Dict[str, Any] | list
    ):
        """Store a TMDb result in cache.

        Args:
            title: Media title (case-insensitive)
            year: Release year (optional)
            media_type: "movie" or "tv"
            result: TMDb API result (dict or list)
        """
        title_lower = title.lower()
        result_json = json.dumps(result)
        created_at = datetime.now().timestamp()

        await self._conn.execute("""
            INSERT OR REPLACE INTO tmdb_cache (title, year, media_type, result, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (title_lower, year, media_type, result_json, created_at))
        await self._conn.commit()

    async def get(
        self,
        title: str,
        year: Optional[int],
        media_type: str
    ) -> Optional[Dict[str, Any] | list]:
        """Retrieve a TMDb result from cache.

        Args:
            title: Media title (case-insensitive)
            year: Release year (optional)
            media_type: "movie" or "tv"

        Returns:
            Cached result or None if not found or expired
        """
        title_lower = title.lower()

        cursor = await self._conn.execute("""
            SELECT result, created_at FROM tmdb_cache
            WHERE title = ? AND year IS ? AND media_type = ?
        """, (title_lower, year, media_type))

        row = await cursor.fetchone()

        if not row:
            return None

        result_json, created_at = row

        # Check TTL
        if self.ttl_days >= 0:
            created_dt = datetime.fromtimestamp(created_at)
            expires_at = created_dt + timedelta(days=self.ttl_days)

            if datetime.now() > expires_at:
                # Expired - remove and return None
                await self._conn.execute("""
                    DELETE FROM tmdb_cache
                    WHERE title = ? AND year IS ? AND media_type = ?
                """, (title_lower, year, media_type))
                await self._conn.commit()
                return None

        return json.loads(result_json)

    async def clear(self):
        """Clear all cache entries."""
        await self._conn.execute("DELETE FROM tmdb_cache")
        await self._conn.commit()

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        cursor = await self._conn.execute("SELECT COUNT(*) FROM tmdb_cache")
        total = (await cursor.fetchone())[0]

        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM tmdb_cache WHERE media_type = 'movie'"
        )
        movie_count = (await cursor.fetchone())[0]

        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM tmdb_cache WHERE media_type = 'tv'"
        )
        tv_count = (await cursor.fetchone())[0]

        return {
            "total_entries": total,
            "movie_count": movie_count,
            "tv_count": tv_count
        }
