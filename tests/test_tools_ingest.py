"""Tests for Ingest MCP Tools - Integration with FileManager and IngestHistory."""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from server.tools.ingest import (
    IngestTools,
    list_ingest_files,
    ingest_file,
    get_ingest_history,
    check_duplicate
)
from server.history import IngestStatus


class TestIngestToolsInitialization:
    """Test IngestTools initialization."""

    def test_initialize_with_dependencies(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should initialize with FileManager and IngestHistory."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )

        assert tools.file_manager is not None
        assert tools.history is not None

    @pytest.mark.asyncio
    async def test_initialize_history(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should initialize history database."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )

        await tools.initialize()

        assert db_path.exists()

        await tools.close()


class TestListIngestFiles:
    """Test list_ingest_files tool."""

    @pytest.mark.asyncio
    async def test_list_files_in_ingest_directory(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should list all video files in ingest directory."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        # Create test files
        (temp_ingest_dir / "movie1.mkv").write_text("test")
        (temp_ingest_dir / "movie2.mp4").write_text("test")
        (temp_ingest_dir / "invalid.txt").write_text("test")

        result = await tools.list_ingest_files()

        assert result["success"] is True
        assert len(result["files"]) == 2
        assert all(".mkv" in f or ".mp4" in f for f in result["files"])

        await tools.close()

    @pytest.mark.asyncio
    async def test_list_files_with_subdirectories(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should list files recursively in subdirectories."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        # Create nested structure
        subdir = temp_ingest_dir / "movies"
        subdir.mkdir()
        (temp_ingest_dir / "movie1.mkv").write_text("test")
        (subdir / "movie2.mkv").write_text("test")

        result = await tools.list_ingest_files(recursive=True)

        assert result["success"] is True
        assert len(result["files"]) == 2

        await tools.close()

    @pytest.mark.asyncio
    async def test_list_files_empty_directory(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should return empty list for empty directory."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        result = await tools.list_ingest_files()

        assert result["success"] is True
        assert len(result["files"]) == 0

        await tools.close()


class TestIngestFile:
    """Test ingest_file tool."""

    @pytest.mark.asyncio
    async def test_ingest_file_success(self, temp_media_root, temp_ingest_dir, temp_dir, sample_video_file):
        """Should successfully ingest a file."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        dest = temp_media_root / "Movies" / "Inception.2010.mkv"

        result = await tools.ingest_file(
            source_path=str(sample_video_file),
            destination_path=str(dest),
            tmdb_id=27205,
            media_type="movie",
            confidence=0.95,
            operation="move"
        )

        assert result["success"] is True
        assert dest.exists()
        assert not sample_video_file.exists()  # File was moved
        assert "record_id" in result

        await tools.close()

    @pytest.mark.asyncio
    async def test_ingest_file_copy_operation(self, temp_media_root, temp_ingest_dir, temp_dir, sample_video_file):
        """Should copy file when operation is 'copy'."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        dest = temp_media_root / "Movies" / "Inception.2010.mkv"

        result = await tools.ingest_file(
            source_path=str(sample_video_file),
            destination_path=str(dest),
            operation="copy"
        )

        assert result["success"] is True
        assert dest.exists()
        assert sample_video_file.exists()  # Original still exists

        await tools.close()

    @pytest.mark.asyncio
    async def test_ingest_file_invalid_extension(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should reject file with invalid extension."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        invalid_file = temp_ingest_dir / "test.txt"
        invalid_file.write_text("test")
        dest = temp_media_root / "Movies" / "test.txt"

        result = await tools.ingest_file(
            source_path=str(invalid_file),
            destination_path=str(dest)
        )

        assert result["success"] is False
        assert "error" in result

        await tools.close()

    @pytest.mark.asyncio
    async def test_ingest_file_records_history(self, temp_media_root, temp_ingest_dir, temp_dir, sample_video_file):
        """Should record ingest operation in history."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        dest = temp_media_root / "Movies" / "Inception.2010.mkv"

        result = await tools.ingest_file(
            source_path=str(sample_video_file),
            destination_path=str(dest),
            tmdb_id=27205,
            confidence=0.95
        )

        # Verify history record exists
        record_id = result["record_id"]
        record = await tools.history.get_record(record_id)

        assert record is not None
        assert record.tmdb_id == 27205
        assert record.confidence == 0.95
        assert record.status == IngestStatus.SUCCESS

        await tools.close()

    @pytest.mark.asyncio
    async def test_ingest_file_failure_records_history(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should record failed ingest in history."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        nonexistent = temp_ingest_dir / "nonexistent.mkv"
        dest = temp_media_root / "Movies" / "test.mkv"

        result = await tools.ingest_file(
            source_path=str(nonexistent),
            destination_path=str(dest)
        )

        assert result["success"] is False
        assert "record_id" in result

        # Verify history record shows failure
        record = await tools.history.get_record(result["record_id"])
        assert record.status == IngestStatus.FAILED

        await tools.close()


class TestGetIngestHistory:
    """Test get_ingest_history tool."""

    @pytest.mark.asyncio
    async def test_get_all_history(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should retrieve all history records."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        # Add some records
        await tools.history.add_record(
            source_path=temp_ingest_dir / "movie1.mkv",
            destination_path=temp_media_root / "movie1.mkv",
            status=IngestStatus.SUCCESS
        )
        await tools.history.add_record(
            source_path=temp_ingest_dir / "movie2.mkv",
            destination_path=temp_media_root / "movie2.mkv",
            status=IngestStatus.SUCCESS
        )

        result = await tools.get_ingest_history()

        assert result["success"] is True
        assert len(result["records"]) == 2

        await tools.close()

    @pytest.mark.asyncio
    async def test_get_history_filtered_by_status(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should filter history by status."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        # Add records with different statuses
        await tools.history.add_record(
            source_path=temp_ingest_dir / "movie1.mkv",
            destination_path=temp_media_root / "movie1.mkv",
            status=IngestStatus.SUCCESS
        )
        await tools.history.add_record(
            source_path=temp_ingest_dir / "movie2.mkv",
            destination_path=temp_media_root / "movie2.mkv",
            status=IngestStatus.FAILED
        )

        result = await tools.get_ingest_history(status="success")

        assert result["success"] is True
        assert len(result["records"]) == 1
        assert result["records"][0]["status"] == "success"

        await tools.close()

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should limit number of history records returned."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        # Add multiple records
        for i in range(5):
            await tools.history.add_record(
                source_path=temp_ingest_dir / f"movie{i}.mkv",
                destination_path=temp_media_root / f"movie{i}.mkv",
                status=IngestStatus.SUCCESS
            )

        result = await tools.get_ingest_history(limit=3)

        assert result["success"] is True
        assert len(result["records"]) == 3

        await tools.close()


class TestCheckDuplicate:
    """Test check_duplicate tool."""

    @pytest.mark.asyncio
    async def test_check_duplicate_by_tmdb_id(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should check for duplicate by TMDb ID."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        # Add existing record
        await tools.history.add_record(
            source_path=temp_ingest_dir / "movie.mkv",
            destination_path=temp_media_root / "movie.mkv",
            tmdb_id=27205,
            status=IngestStatus.SUCCESS
        )

        result = await tools.check_duplicate(tmdb_id=27205)

        assert result["is_duplicate"] is True
        assert len(result["existing_records"]) == 1

        await tools.close()

    @pytest.mark.asyncio
    async def test_check_duplicate_by_source_path(self, temp_media_root, temp_ingest_dir, temp_dir, sample_video_file):
        """Should check for duplicate by source path."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        # Add existing record
        await tools.history.add_record(
            source_path=sample_video_file,
            destination_path=temp_media_root / "movie.mkv",
            status=IngestStatus.SUCCESS
        )

        result = await tools.check_duplicate(source_path=str(sample_video_file))

        assert result["is_duplicate"] is True

        await tools.close()

    @pytest.mark.asyncio
    async def test_check_no_duplicate(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should return False when no duplicate exists."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        result = await tools.check_duplicate(tmdb_id=99999)

        assert result["is_duplicate"] is False
        assert len(result["existing_records"]) == 0

        await tools.close()


class TestGetStatistics:
    """Test get_statistics tool."""

    @pytest.mark.asyncio
    async def test_get_statistics(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should return ingest statistics."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )
        await tools.initialize()

        # Add various records
        await tools.history.add_record(
            source_path=temp_ingest_dir / "movie1.mkv",
            destination_path=temp_media_root / "movie1.mkv",
            status=IngestStatus.SUCCESS
        )
        await tools.history.add_record(
            source_path=temp_ingest_dir / "movie2.mkv",
            destination_path=temp_media_root / "movie2.mkv",
            status=IngestStatus.FAILED
        )

        result = await tools.get_statistics()

        assert result["success"] is True
        assert result["statistics"]["total"] == 2
        assert result["statistics"]["success"] == 1
        assert result["statistics"]["failed"] == 1

        await tools.close()


class TestMCPToolRegistration:
    """Test MCP tool registration and format."""

    def test_tool_definitions_format(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should provide properly formatted MCP tool definitions."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )

        tool_defs = tools.get_tool_definitions()

        assert isinstance(tool_defs, list)
        assert len(tool_defs) > 0

        # Check first tool has required MCP fields
        first_tool = tool_defs[0]
        assert "name" in first_tool
        assert "description" in first_tool
        assert "inputSchema" in first_tool

    def test_all_tools_registered(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should register all ingest tools."""
        db_path = temp_dir / "test.db"
        tools = IngestTools(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir,
            history_db_path=db_path
        )

        tool_defs = tools.get_tool_definitions()
        tool_names = [t["name"] for t in tool_defs]

        expected_tools = [
            "list_ingest_files",
            "ingest_file",
            "get_ingest_history",
            "check_duplicate",
            "get_ingest_statistics"
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names
