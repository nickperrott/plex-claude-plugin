"""IngestHistory - SQLite audit log for ingest operations.

This module provides an audit log for tracking file ingest operations with:
- SQLite database for persistent storage
- Operation tracking (source, destination, TMDb ID, status)
- Query filters (status, TMDb ID, date range, media type)
- Duplicate detection
- Statistics
"""

import json
import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum
from dataclasses import dataclass, asdict


class IngestStatus(str, Enum):
    """Ingest operation status."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class IngestRecord:
    """Represents a single ingest operation record."""
    id: int
    timestamp: datetime
    source_path: str
    destination_path: str
    status: IngestStatus
    tmdb_id: Optional[int] = None
    media_type: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class IngestHistory:
    """Manages SQLite database for ingest operation history.

    Attributes:
        db_path: Path to SQLite database file
    """

    def __init__(self, db_path: Union[str, Path]):
        """Initialize IngestHistory with database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize database and create schema if needed."""
        self._db = await aiosqlite.connect(str(self.db_path))

        # Create table if it doesn't exist
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS ingest_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                source_path TEXT NOT NULL,
                destination_path TEXT NOT NULL,
                status TEXT NOT NULL,
                tmdb_id INTEGER,
                media_type TEXT,
                confidence REAL,
                metadata TEXT,
                error_message TEXT
            )
        """)

        # Create indexes for common queries
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON ingest_records(status)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_tmdb_id
            ON ingest_records(tmdb_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON ingest_records(timestamp)
        """)

        await self._db.commit()

    async def close(self):
        """Close database connection."""
        if self._db:
            await self._db.close()

    async def add_record(
        self,
        source_path: Union[str, Path],
        destination_path: Union[str, Path],
        status: IngestStatus,
        tmdb_id: Optional[int] = None,
        media_type: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> int:
        """Add a new ingest record.

        Args:
            source_path: Source file path
            destination_path: Destination file path
            status: Operation status
            tmdb_id: TMDb ID (optional)
            media_type: Media type (movie/tv) (optional)
            confidence: Match confidence score (optional)
            metadata: Additional metadata (optional)
            error_message: Error message if failed (optional)

        Returns:
            ID of inserted record
        """
        timestamp = datetime.now().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None

        cursor = await self._db.execute("""
            INSERT INTO ingest_records
            (timestamp, source_path, destination_path, status, tmdb_id,
             media_type, confidence, metadata, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp,
            str(source_path),
            str(destination_path),
            status.value,
            tmdb_id,
            media_type,
            confidence,
            metadata_json,
            error_message
        ))

        await self._db.commit()
        return cursor.lastrowid

    async def get_record(self, record_id: int) -> Optional[IngestRecord]:
        """Get a record by ID.

        Args:
            record_id: Record ID

        Returns:
            IngestRecord if found, None otherwise
        """
        cursor = await self._db.execute("""
            SELECT * FROM ingest_records WHERE id = ?
        """, (record_id,))

        row = await cursor.fetchone()
        if not row:
            return None

        return self._row_to_record(row)

    async def update_record(
        self,
        record_id: int,
        status: Optional[IngestStatus] = None,
        tmdb_id: Optional[int] = None,
        confidence: Optional[float] = None,
        error_message: Optional[str] = None
    ):
        """Update an existing record.

        Args:
            record_id: Record ID to update
            status: New status (optional)
            tmdb_id: New TMDb ID (optional)
            confidence: New confidence (optional)
            error_message: New error message (optional)
        """
        updates = []
        values = []

        if status is not None:
            updates.append("status = ?")
            values.append(status.value)

        if tmdb_id is not None:
            updates.append("tmdb_id = ?")
            values.append(tmdb_id)

        if confidence is not None:
            updates.append("confidence = ?")
            values.append(confidence)

        if error_message is not None:
            updates.append("error_message = ?")
            values.append(error_message)

        if not updates:
            return

        values.append(record_id)
        query = f"UPDATE ingest_records SET {', '.join(updates)} WHERE id = ?"

        await self._db.execute(query, values)
        await self._db.commit()

    async def get_all_records(self) -> List[IngestRecord]:
        """Get all records.

        Returns:
            List of all IngestRecords
        """
        cursor = await self._db.execute("""
            SELECT * FROM ingest_records ORDER BY timestamp DESC
        """)

        rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def query_records(
        self,
        status: Optional[IngestStatus] = None,
        tmdb_id: Optional[int] = None,
        media_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[IngestRecord]:
        """Query records with filters.

        Args:
            status: Filter by status
            tmdb_id: Filter by TMDb ID
            media_type: Filter by media type
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of matching IngestRecords
        """
        conditions = []
        values = []

        if status is not None:
            conditions.append("status = ?")
            values.append(status.value)

        if tmdb_id is not None:
            conditions.append("tmdb_id = ?")
            values.append(tmdb_id)

        if media_type is not None:
            conditions.append("media_type = ?")
            values.append(media_type)

        if start_date is not None:
            conditions.append("timestamp >= ?")
            values.append(start_date.isoformat())

        if end_date is not None:
            conditions.append("timestamp <= ?")
            values.append(end_date.isoformat())

        query = "SELECT * FROM ingest_records"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC"

        cursor = await self._db.execute(query, values)
        rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def is_duplicate(
        self,
        tmdb_id: Optional[int] = None,
        source_path: Optional[Union[str, Path]] = None,
        exclude_failed: bool = True
    ) -> bool:
        """Check if a duplicate record exists.

        Args:
            tmdb_id: TMDb ID to check
            source_path: Source path to check
            exclude_failed: Don't count failed ingests as duplicates

        Returns:
            True if duplicate exists
        """
        conditions = []
        values = []

        if tmdb_id is not None:
            conditions.append("tmdb_id = ?")
            values.append(tmdb_id)

        if source_path is not None:
            conditions.append("source_path = ?")
            values.append(str(source_path))

        if exclude_failed:
            conditions.append("status != ?")
            values.append(IngestStatus.FAILED.value)

        if not conditions:
            return False

        query = f"SELECT COUNT(*) FROM ingest_records WHERE {' AND '.join(conditions)}"

        cursor = await self._db.execute(query, values)
        row = await cursor.fetchone()
        return row[0] > 0

    async def get_recent_records(self, limit: int = 10) -> List[IngestRecord]:
        """Get most recent records.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of recent IngestRecords
        """
        cursor = await self._db.execute("""
            SELECT * FROM ingest_records
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        rows = await cursor.fetchall()
        return [self._row_to_record(row) for row in rows]

    async def get_statistics(self) -> Dict[str, int]:
        """Get ingest statistics.

        Returns:
            Dictionary with statistics (total, success, failed, pending)
        """
        cursor = await self._db.execute("""
            SELECT status, COUNT(*) as count
            FROM ingest_records
            GROUP BY status
        """)

        rows = await cursor.fetchall()

        stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "pending": 0
        }

        for row in rows:
            status, count = row
            stats["total"] += count
            if status == IngestStatus.SUCCESS.value:
                stats["success"] = count
            elif status == IngestStatus.FAILED.value:
                stats["failed"] = count
            elif status == IngestStatus.PENDING.value:
                stats["pending"] = count

        return stats

    def _row_to_record(self, row) -> IngestRecord:
        """Convert database row to IngestRecord.

        Args:
            row: Database row tuple

        Returns:
            IngestRecord instance
        """
        metadata = json.loads(row[8]) if row[8] else None

        return IngestRecord(
            id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            source_path=row[2],
            destination_path=row[3],
            status=IngestStatus(row[4]),
            tmdb_id=row[5],
            media_type=row[6],
            confidence=row[7],
            metadata=metadata,
            error_message=row[9]
        )
