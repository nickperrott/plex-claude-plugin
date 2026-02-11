"""Tests for FileManager - file operations with path restrictions and extension whitelist."""

import pytest
from pathlib import Path
from server.files import FileManager, FileOperationError, InvalidExtensionError, PathRestrictionError


class TestFileManagerInitialization:
    """Test FileManager initialization and configuration."""

    def test_initialize_with_valid_paths(self, temp_media_root, temp_ingest_dir):
        """Should initialize FileManager with valid paths."""
        fm = FileManager(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir
        )
        assert fm.media_root == temp_media_root.resolve()
        assert fm.ingest_dir == temp_ingest_dir.resolve()

    def test_initialize_with_string_paths(self, temp_media_root, temp_ingest_dir):
        """Should accept string paths and convert to Path objects."""
        fm = FileManager(
            media_root=str(temp_media_root),
            ingest_dir=str(temp_ingest_dir)
        )
        assert fm.media_root == temp_media_root.resolve()
        assert fm.ingest_dir == temp_ingest_dir.resolve()

    def test_default_allowed_extensions(self, temp_media_root, temp_ingest_dir):
        """Should have default video extensions."""
        fm = FileManager(
            media_root=temp_media_root,
            ingest_dir=temp_ingest_dir
        )
        expected_extensions = {".mkv", ".mp4", ".avi", ".m4v", ".ts", ".wmv", ".mov"}
        assert fm.allowed_extensions == expected_extensions


class TestExtensionValidation:
    """Test extension whitelist validation."""

    def test_valid_extension(self, temp_media_root, temp_ingest_dir, valid_video_extensions):
        """Should accept files with valid video extensions."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        for ext in valid_video_extensions:
            test_file = temp_ingest_dir / f"test{ext}"
            assert fm.is_valid_extension(test_file) is True

    def test_invalid_extension(self, temp_media_root, temp_ingest_dir, invalid_extensions):
        """Should reject files with invalid extensions."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        for ext in invalid_extensions:
            test_file = temp_ingest_dir / f"test{ext}"
            assert fm.is_valid_extension(test_file) is False

    def test_case_insensitive_extension(self, temp_media_root, temp_ingest_dir):
        """Should handle extensions case-insensitively."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        assert fm.is_valid_extension(Path("test.MKV")) is True
        assert fm.is_valid_extension(Path("test.Mp4")) is True
        assert fm.is_valid_extension(Path("test.AVI")) is True


class TestPathRestrictions:
    """Test path restriction enforcement."""

    def test_validate_path_in_ingest_dir(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should validate paths within ingest directory."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        assert fm.validate_path(sample_video_file, require_ingest=True) is True

    def test_validate_path_in_media_root(self, temp_media_root, temp_ingest_dir):
        """Should validate paths within media root."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        test_path = temp_media_root / "Movies" / "test.mkv"
        assert fm.validate_path(test_path, require_ingest=False) is True

    def test_reject_path_outside_ingest_dir(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should reject paths outside ingest directory when required."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        outside_file = temp_dir / "outside.mkv"
        outside_file.write_text("test")

        with pytest.raises(PathRestrictionError):
            fm.validate_path(outside_file, require_ingest=True)

    def test_reject_path_outside_media_root(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should reject paths outside media root."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        outside_file = temp_dir / "outside.mkv"
        outside_file.write_text("test")

        with pytest.raises(PathRestrictionError):
            fm.validate_path(outside_file, require_ingest=False)

    def test_reject_path_traversal_attempt(self, temp_media_root, temp_ingest_dir):
        """Should reject path traversal attempts."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        traversal_path = temp_ingest_dir / ".." / ".." / "etc" / "passwd"

        with pytest.raises(PathRestrictionError):
            fm.validate_path(traversal_path, require_ingest=True)


class TestCopyFile:
    """Test file copy operations."""

    def test_copy_file_within_restrictions(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should copy file from ingest to media root."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        dest = temp_media_root / "Movies" / "Inception.2010.mkv"

        result = fm.copy_file(sample_video_file, dest)

        assert result == dest
        assert dest.exists()
        assert dest.read_text() == "fake video content"
        assert sample_video_file.exists()  # Original still exists

    def test_copy_file_invalid_extension(self, temp_media_root, temp_ingest_dir):
        """Should reject copying file with invalid extension."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        invalid_file = temp_ingest_dir / "test.txt"
        invalid_file.write_text("test")
        dest = temp_media_root / "Movies" / "test.txt"

        with pytest.raises(InvalidExtensionError):
            fm.copy_file(invalid_file, dest)

    def test_copy_file_creates_parent_directories(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should create parent directories if they don't exist."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        dest = temp_media_root / "Movies" / "2010" / "Inception" / "movie.mkv"

        result = fm.copy_file(sample_video_file, dest)

        assert result == dest
        assert dest.exists()
        assert dest.parent.exists()

    def test_copy_file_source_not_exists(self, temp_media_root, temp_ingest_dir):
        """Should raise error if source file doesn't exist."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        source = temp_ingest_dir / "nonexistent.mkv"
        dest = temp_media_root / "Movies" / "test.mkv"

        with pytest.raises(FileOperationError):
            fm.copy_file(source, dest)


class TestMoveFile:
    """Test file move operations."""

    def test_move_file_within_restrictions(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should move file from ingest to media root."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        dest = temp_media_root / "Movies" / "Inception.2010.mkv"

        result = fm.move_file(sample_video_file, dest)

        assert result == dest
        assert dest.exists()
        assert not sample_video_file.exists()  # Original removed

    def test_move_file_invalid_extension(self, temp_media_root, temp_ingest_dir):
        """Should reject moving file with invalid extension."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        invalid_file = temp_ingest_dir / "test.txt"
        invalid_file.write_text("test")
        dest = temp_media_root / "Movies" / "test.txt"

        with pytest.raises(InvalidExtensionError):
            fm.move_file(invalid_file, dest)

    def test_move_file_creates_parent_directories(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should create parent directories if they don't exist."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        dest = temp_media_root / "Movies" / "2010" / "Inception" / "movie.mkv"

        result = fm.move_file(sample_video_file, dest)

        assert result == dest
        assert dest.exists()
        assert not sample_video_file.exists()


class TestRenameFile:
    """Test file rename operations."""

    def test_rename_file_in_same_directory(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should rename file in the same directory."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        new_name = "Inception.2010.PROPER.1080p.mkv"

        result = fm.rename_file(sample_video_file, new_name)

        assert result == temp_ingest_dir / new_name
        assert result.exists()
        assert not sample_video_file.exists()

    def test_rename_file_invalid_extension(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should reject renaming to invalid extension."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)

        with pytest.raises(InvalidExtensionError):
            fm.rename_file(sample_video_file, "movie.txt")

    def test_rename_file_path_traversal(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should reject rename attempts with path traversal."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)

        with pytest.raises(FileOperationError):
            fm.rename_file(sample_video_file, "../../../etc/passwd")


class TestDeleteFile:
    """Test file deletion operations."""

    def test_delete_file_in_ingest_dir(self, temp_media_root, temp_ingest_dir, sample_video_file):
        """Should delete file from ingest directory."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)

        result = fm.delete_file(sample_video_file)

        assert result is True
        assert not sample_video_file.exists()

    def test_delete_file_outside_allowed_paths(self, temp_media_root, temp_ingest_dir, temp_dir):
        """Should reject deleting files outside allowed paths."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        outside_file = temp_dir / "outside.mkv"
        outside_file.write_text("test")

        with pytest.raises(PathRestrictionError):
            fm.delete_file(outside_file)

    def test_delete_nonexistent_file(self, temp_media_root, temp_ingest_dir):
        """Should handle deletion of nonexistent file gracefully."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)
        nonexistent = temp_ingest_dir / "nonexistent.mkv"

        with pytest.raises(FileOperationError):
            fm.delete_file(nonexistent)


class TestListFiles:
    """Test file listing operations."""

    def test_list_files_in_ingest_dir(self, temp_media_root, temp_ingest_dir):
        """Should list all valid video files in ingest directory."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)

        # Create test files
        (temp_ingest_dir / "movie1.mkv").write_text("test")
        (temp_ingest_dir / "movie2.mp4").write_text("test")
        (temp_ingest_dir / "invalid.txt").write_text("test")

        files = fm.list_files(temp_ingest_dir)

        assert len(files) == 2
        assert all(f.suffix.lower() in fm.allowed_extensions for f in files)

    def test_list_files_recursive(self, temp_media_root, temp_ingest_dir):
        """Should list files recursively in subdirectories."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)

        # Create nested structure
        subdir = temp_ingest_dir / "subdir"
        subdir.mkdir()
        (temp_ingest_dir / "movie1.mkv").write_text("test")
        (subdir / "movie2.mp4").write_text("test")

        files = fm.list_files(temp_ingest_dir, recursive=True)

        assert len(files) == 2

    def test_list_files_non_recursive(self, temp_media_root, temp_ingest_dir):
        """Should list only files in specified directory when not recursive."""
        fm = FileManager(media_root=temp_media_root, ingest_dir=temp_ingest_dir)

        # Create nested structure
        subdir = temp_ingest_dir / "subdir"
        subdir.mkdir()
        (temp_ingest_dir / "movie1.mkv").write_text("test")
        (subdir / "movie2.mp4").write_text("test")

        files = fm.list_files(temp_ingest_dir, recursive=False)

        assert len(files) == 1
        assert files[0].name == "movie1.mkv"
