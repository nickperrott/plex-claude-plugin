"""FileManager - File operations with path restrictions and extension whitelist.

This module provides safe file operations for the Plex ingest workflow with:
- Path restriction enforcement (PLEX_MEDIA_ROOT and PLEX_INGEST_DIR)
- Extension whitelist for video files
- Copy, move, rename, and delete operations
"""

import shutil
from pathlib import Path
from typing import Set, List, Union


class FileOperationError(Exception):
    """Base exception for file operation errors."""
    pass


class InvalidExtensionError(FileOperationError):
    """Exception raised when file extension is not in whitelist."""
    pass


class PathRestrictionError(FileOperationError):
    """Exception raised when path is outside allowed boundaries."""
    pass


class FileManager:
    """Manages file operations with security restrictions and validation.

    Attributes:
        media_root: Root directory for Plex media library
        ingest_dir: Directory for incoming files to be ingested
        allowed_extensions: Set of allowed video file extensions
    """

    DEFAULT_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".ts", ".wmv", ".mov"}

    def __init__(
        self,
        media_root: Union[str, Path],
        ingest_dir: Union[str, Path],
        allowed_extensions: Set[str] = None
    ):
        """Initialize FileManager with path restrictions.

        Args:
            media_root: Root directory for Plex media library
            ingest_dir: Directory for incoming files to be ingested
            allowed_extensions: Set of allowed file extensions (default: video extensions)
        """
        self.media_root = Path(media_root).resolve()
        self.ingest_dir = Path(ingest_dir).resolve()
        self.allowed_extensions = allowed_extensions or self.DEFAULT_EXTENSIONS.copy()

        # Ensure extensions are lowercase with leading dot
        self.allowed_extensions = {
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            for ext in self.allowed_extensions
        }

    def is_valid_extension(self, file_path: Union[str, Path]) -> bool:
        """Check if file has a valid extension.

        Args:
            file_path: Path to file to check

        Returns:
            True if extension is valid, False otherwise
        """
        path = Path(file_path)
        return path.suffix.lower() in self.allowed_extensions

    def validate_path(
        self,
        path: Union[str, Path],
        require_ingest: bool = False
    ) -> bool:
        """Validate that path is within allowed boundaries.

        Args:
            path: Path to validate
            require_ingest: If True, path must be within ingest_dir

        Returns:
            True if path is valid

        Raises:
            PathRestrictionError: If path is outside allowed boundaries
        """
        resolved_path = Path(path).resolve()

        if require_ingest:
            # Path must be within ingest_dir
            try:
                resolved_path.relative_to(self.ingest_dir)
            except ValueError:
                raise PathRestrictionError(
                    f"Path {path} is outside ingest directory {self.ingest_dir}"
                )
        else:
            # Path must be within media_root or ingest_dir
            in_media = False
            in_ingest = False

            try:
                resolved_path.relative_to(self.media_root)
                in_media = True
            except ValueError:
                pass

            try:
                resolved_path.relative_to(self.ingest_dir)
                in_ingest = True
            except ValueError:
                pass

            if not (in_media or in_ingest):
                raise PathRestrictionError(
                    f"Path {path} is outside allowed directories"
                )

        return True

    def copy_file(
        self,
        source: Union[str, Path],
        destination: Union[str, Path]
    ) -> Path:
        """Copy file with validation.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            Path to copied file

        Raises:
            InvalidExtensionError: If file extension is not allowed
            PathRestrictionError: If paths are outside allowed boundaries
            FileOperationError: If copy operation fails
        """
        source_path = Path(source)
        dest_path = Path(destination)

        # Validate extension
        if not self.is_valid_extension(source_path):
            raise InvalidExtensionError(
                f"File extension {source_path.suffix} is not allowed"
            )

        # Validate paths
        self.validate_path(source_path, require_ingest=False)
        self.validate_path(dest_path, require_ingest=False)

        # Check source exists
        if not source_path.exists():
            raise FileOperationError(f"Source file {source_path} does not exist")

        try:
            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(source_path, dest_path)

            return dest_path
        except Exception as e:
            raise FileOperationError(f"Failed to copy file: {e}")

    def move_file(
        self,
        source: Union[str, Path],
        destination: Union[str, Path]
    ) -> Path:
        """Move file with validation.

        Args:
            source: Source file path
            destination: Destination file path

        Returns:
            Path to moved file

        Raises:
            InvalidExtensionError: If file extension is not allowed
            PathRestrictionError: If paths are outside allowed boundaries
            FileOperationError: If move operation fails
        """
        source_path = Path(source)
        dest_path = Path(destination)

        # Validate extension
        if not self.is_valid_extension(source_path):
            raise InvalidExtensionError(
                f"File extension {source_path.suffix} is not allowed"
            )

        # Validate paths
        self.validate_path(source_path, require_ingest=False)
        self.validate_path(dest_path, require_ingest=False)

        try:
            # Create parent directories if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(source_path), str(dest_path))

            return dest_path
        except Exception as e:
            raise FileOperationError(f"Failed to move file: {e}")

    def rename_file(
        self,
        source: Union[str, Path],
        new_name: str
    ) -> Path:
        """Rename file in same directory.

        Args:
            source: Source file path
            new_name: New filename (not full path)

        Returns:
            Path to renamed file

        Raises:
            InvalidExtensionError: If new extension is not allowed
            FileOperationError: If rename contains path traversal
        """
        source_path = Path(source)

        # Prevent path traversal
        if '/' in new_name or '\\' in new_name or '..' in new_name:
            raise FileOperationError("New name cannot contain path separators")

        dest_path = source_path.parent / new_name

        # Validate extension of new name
        if not self.is_valid_extension(dest_path):
            raise InvalidExtensionError(
                f"File extension {dest_path.suffix} is not allowed"
            )

        return self.move_file(source_path, dest_path)

    def delete_file(self, file_path: Union[str, Path]) -> bool:
        """Delete file with validation.

        Args:
            file_path: Path to file to delete

        Returns:
            True if file was deleted

        Raises:
            PathRestrictionError: If path is outside allowed boundaries
            FileOperationError: If file doesn't exist or delete fails
        """
        path = Path(file_path)

        # Validate path
        self.validate_path(path, require_ingest=False)

        if not path.exists():
            raise FileOperationError(f"File {path} does not exist")

        try:
            path.unlink()
            return True
        except Exception as e:
            raise FileOperationError(f"Failed to delete file: {e}")

    def list_files(
        self,
        directory: Union[str, Path],
        recursive: bool = False
    ) -> List[Path]:
        """List video files in directory.

        Args:
            directory: Directory to list files from
            recursive: If True, search subdirectories recursively

        Returns:
            List of paths to valid video files
        """
        dir_path = Path(directory)

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        files = []
        for path in dir_path.glob(pattern):
            if path.is_file() and self.is_valid_extension(path):
                files.append(path)

        return sorted(files)
