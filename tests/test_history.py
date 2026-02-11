"""Tests for IngestHistory - SQLite audit log for ingest operations."""

import pytest
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from server.history import IngestHistory, IngestStatus, IngestRecord


class TestIngestHistoryInitialization:
    """Test IngestHistory initialization."""

    @pytest.mark.asyncio
    async def test_initialize_creates_database(self, temp_dir):
        """Should create database file and initialize schema."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)

        await history.initialize()

        assert db_path.exists()
        await history.close()

    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, temp_dir):
        """Should create ingest_records table with correct schema."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)

        await history.initialize()

        # Verify table exists by querying it
        records = await history.get_all_records()
        assert isinstance(records, list)
        assert len(records) == 0

        await history.close()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, temp_dir):
        """Should be safe to call initialize multiple times."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)

        await history.initialize()
        await history.initialize()  # Second call should be safe

        assert db_path.exists()
        await history.close()


class TestAddRecord:
    """Test adding ingest records."""

    @pytest.mark.asyncio
    async def test_add_record_with_all_fields(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should add complete ingest record."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        source = temp_ingest_dir / "movie.mkv"
        dest = temp_media_root / "Movies" / "Movie.mkv"

        record_id = await history.add_record(
            source_path=source,
            destination_path=dest,
            tmdb_id=12345,
            media_type="movie",
            confidence=0.95,
            status=IngestStatus.SUCCESS
        )

        assert record_id is not None
        assert isinstance(record_id, int)

        await history.close()

    @pytest.mark.asyncio
    async def test_add_record_minimal_fields(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should add record with only required fields."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        source = temp_ingest_dir / "movie.mkv"
        dest = temp_media_root / "Movies" / "Movie.mkv"

        record_id = await history.add_record(
            source_path=source,
            destination_path=dest,
            status=IngestStatus.PENDING
        )

        assert record_id is not None

        # Verify record
        record = await history.get_record(record_id)
        assert record.source_path == str(source)
        assert record.destination_path == str(dest)
        assert record.status == IngestStatus.PENDING
        assert record.tmdb_id is None
        assert record.confidence is None

        await history.close()

    @pytest.mark.asyncio
    async def test_add_record_with_metadata(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should store additional metadata as JSON."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        source = temp_ingest_dir / "movie.mkv"
        dest = temp_media_root / "Movies" / "Movie.mkv"
        metadata = {
            "title": "Inception",
            "year": 2010,
            "resolution": "1080p"
        }

        record_id = await history.add_record(
            source_path=source,
            destination_path=dest,
            status=IngestStatus.SUCCESS,
            metadata=metadata
        )

        record = await history.get_record(record_id)
        assert record.metadata == metadata

        await history.close()


class TestGetRecord:
    """Test retrieving individual records."""

    @pytest.mark.asyncio
    async def test_get_existing_record(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should retrieve existing record by ID."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        source = temp_ingest_dir / "movie.mkv"
        dest = temp_media_root / "Movies" / "Movie.mkv"

        record_id = await history.add_record(
            source_path=source,
            destination_path=dest,
            tmdb_id=12345,
            media_type="movie",
            confidence=0.95,
            status=IngestStatus.SUCCESS
        )

        record = await history.get_record(record_id)

        assert record is not None
        assert record.id == record_id
        assert record.source_path == str(source)
        assert record.destination_path == str(dest)
        assert record.tmdb_id == 12345
        assert record.media_type == "movie"
        assert record.confidence == 0.95
        assert record.status == IngestStatus.SUCCESS
        assert isinstance(record.timestamp, datetime)

        await history.close()

    @pytest.mark.asyncio
    async def test_get_nonexistent_record(self, temp_dir):
        """Should return None for nonexistent record."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        record = await history.get_record(99999)

        assert record is None

        await history.close()


class TestUpdateRecord:
    """Test updating existing records."""

    @pytest.mark.asyncio
    async def test_update_record_status(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should update record status."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        source = temp_ingest_dir / "movie.mkv"
        dest = temp_media_root / "Movies" / "Movie.mkv"

        record_id = await history.add_record(
            source_path=source,
            destination_path=dest,
            status=IngestStatus.PENDING
        )

        await history.update_record(record_id, status=IngestStatus.SUCCESS)

        record = await history.get_record(record_id)
        assert record.status == IngestStatus.SUCCESS

        await history.close()

    @pytest.mark.asyncio
    async def test_update_record_multiple_fields(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should update multiple fields at once."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        source = temp_ingest_dir / "movie.mkv"
        dest = temp_media_root / "Movies" / "Movie.mkv"

        record_id = await history.add_record(
            source_path=source,
            destination_path=dest,
            status=IngestStatus.PENDING
        )

        await history.update_record(
            record_id,
            status=IngestStatus.SUCCESS,
            tmdb_id=12345,
            confidence=0.92
        )

        record = await history.get_record(record_id)
        assert record.status == IngestStatus.SUCCESS
        assert record.tmdb_id == 12345
        assert record.confidence == 0.92

        await history.close()


class TestQueryRecords:
    """Test querying records with filters."""

    @pytest.mark.asyncio
    async def test_get_all_records(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should retrieve all records."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        # Add multiple records
        for i in range(3):
            await history.add_record(
                source_path=temp_ingest_dir / f"movie{i}.mkv",
                destination_path=temp_media_root / f"movie{i}.mkv",
                status=IngestStatus.SUCCESS
            )

        records = await history.get_all_records()

        assert len(records) == 3

        await history.close()

    @pytest.mark.asyncio
    async def test_query_by_status(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should filter records by status."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        # Add records with different statuses
        await history.add_record(
            source_path=temp_ingest_dir / "movie1.mkv",
            destination_path=temp_media_root / "movie1.mkv",
            status=IngestStatus.SUCCESS
        )
        await history.add_record(
            source_path=temp_ingest_dir / "movie2.mkv",
            destination_path=temp_media_root / "movie2.mkv",
            status=IngestStatus.FAILED
        )
        await history.add_record(
            source_path=temp_ingest_dir / "movie3.mkv",
            destination_path=temp_media_root / "movie3.mkv",
            status=IngestStatus.SUCCESS
        )

        success_records = await history.query_records(status=IngestStatus.SUCCESS)

        assert len(success_records) == 2
        assert all(r.status == IngestStatus.SUCCESS for r in success_records)

        await history.close()

    @pytest.mark.asyncio
    async def test_query_by_tmdb_id(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should filter records by TMDb ID."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        # Add records with different TMDb IDs
        await history.add_record(
            source_path=temp_ingest_dir / "movie1.mkv",
            destination_path=temp_media_root / "movie1.mkv",
            tmdb_id=12345,
            status=IngestStatus.SUCCESS
        )
        await history.add_record(
            source_path=temp_ingest_dir / "movie2.mkv",
            destination_path=temp_media_root / "movie2.mkv",
            tmdb_id=67890,
            status=IngestStatus.SUCCESS
        )

        records = await history.query_records(tmdb_id=12345)

        assert len(records) == 1
        assert records[0].tmdb_id == 12345

        await history.close()

    @pytest.mark.asyncio
    async def test_query_by_date_range(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should filter records by date range."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        # Add record
        record_id = await history.add_record(
            source_path=temp_ingest_dir / "movie.mkv",
            destination_path=temp_media_root / "movie.mkv",
            status=IngestStatus.SUCCESS
        )

        # Query with date range
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        records = await history.query_records(
            start_date=yesterday,
            end_date=tomorrow
        )

        assert len(records) == 1
        assert records[0].id == record_id

        await history.close()

    @pytest.mark.asyncio
    async def test_query_by_media_type(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should filter records by media type."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        await history.add_record(
            source_path=temp_ingest_dir / "movie.mkv",
            destination_path=temp_media_root / "movie.mkv",
            media_type="movie",
            status=IngestStatus.SUCCESS
        )
        await history.add_record(
            source_path=temp_ingest_dir / "episode.mkv",
            destination_path=temp_media_root / "episode.mkv",
            media_type="tv",
            status=IngestStatus.SUCCESS
        )

        movie_records = await history.query_records(media_type="movie")

        assert len(movie_records) == 1
        assert movie_records[0].media_type == "movie"

        await history.close()


class TestDuplicateDetection:
    """Test duplicate detection functionality."""

    @pytest.mark.asyncio
    async def test_find_duplicate_by_tmdb_id(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should detect duplicates by TMDb ID."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        # Add record with TMDb ID
        await history.add_record(
            source_path=temp_ingest_dir / "movie1.mkv",
            destination_path=temp_media_root / "movie1.mkv",
            tmdb_id=12345,
            status=IngestStatus.SUCCESS
        )

        # Check for duplicate
        is_duplicate = await history.is_duplicate(tmdb_id=12345)

        assert is_duplicate is True

        await history.close()

    @pytest.mark.asyncio
    async def test_find_duplicate_by_source_path(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should detect duplicates by source path."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        source = temp_ingest_dir / "movie.mkv"

        # Add record
        await history.add_record(
            source_path=source,
            destination_path=temp_media_root / "movie.mkv",
            status=IngestStatus.SUCCESS
        )

        # Check for duplicate
        is_duplicate = await history.is_duplicate(source_path=source)

        assert is_duplicate is True

        await history.close()

    @pytest.mark.asyncio
    async def test_no_duplicate_found(self, temp_dir):
        """Should return False when no duplicate exists."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        is_duplicate = await history.is_duplicate(tmdb_id=99999)

        assert is_duplicate is False

        await history.close()

    @pytest.mark.asyncio
    async def test_ignore_failed_status_in_duplicate_check(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should not count failed ingests as duplicates."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        # Add failed record
        await history.add_record(
            source_path=temp_ingest_dir / "movie.mkv",
            destination_path=temp_media_root / "movie.mkv",
            tmdb_id=12345,
            status=IngestStatus.FAILED
        )

        # Check for duplicate - should be False since the record is FAILED
        is_duplicate = await history.is_duplicate(tmdb_id=12345, exclude_failed=True)

        assert is_duplicate is False

        await history.close()


class TestGetRecentRecords:
    """Test retrieving recent records."""

    @pytest.mark.asyncio
    async def test_get_recent_records_with_limit(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should retrieve most recent records up to limit."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        # Add multiple records
        for i in range(5):
            await history.add_record(
                source_path=temp_ingest_dir / f"movie{i}.mkv",
                destination_path=temp_media_root / f"movie{i}.mkv",
                status=IngestStatus.SUCCESS
            )

        recent = await history.get_recent_records(limit=3)

        assert len(recent) == 3
        # Should be in reverse chronological order
        assert recent[0].id > recent[1].id > recent[2].id

        await history.close()


class TestStatistics:
    """Test ingest statistics."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, temp_dir, temp_ingest_dir, temp_media_root):
        """Should calculate statistics for ingest operations."""
        db_path = temp_dir / "ingest_history.db"
        history = IngestHistory(db_path)
        await history.initialize()

        # Add various records
        await history.add_record(
            source_path=temp_ingest_dir / "movie1.mkv",
            destination_path=temp_media_root / "movie1.mkv",
            status=IngestStatus.SUCCESS
        )
        await history.add_record(
            source_path=temp_ingest_dir / "movie2.mkv",
            destination_path=temp_media_root / "movie2.mkv",
            status=IngestStatus.SUCCESS
        )
        await history.add_record(
            source_path=temp_ingest_dir / "movie3.mkv",
            destination_path=temp_media_root / "movie3.mkv",
            status=IngestStatus.FAILED
        )

        stats = await history.get_statistics()

        assert stats["total"] == 3
        assert stats["success"] == 2
        assert stats["failed"] == 1
        assert stats["pending"] == 0

        await history.close()
