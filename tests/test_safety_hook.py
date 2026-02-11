"""
Tests for the three-tier safety hook.

Tests classification of tools into READ/WRITE/BLOCKED tiers
and verification that blocked operations are denied.
"""

import pytest
import sys
from pathlib import Path

# Add plex-plugin to path for importing
plugin_path = Path(__file__).parent.parent / "plex-plugin"
sys.path.insert(0, str(plugin_path))

from hooks.safety import (
    SafetyTier,
    classify_tool_safety,
    should_allow_operation,
    get_confirmation_message,
    safety_hook,
)


class TestSafetyTierClassification:
    """Test classification of tools into safety tiers."""

    def test_read_only_tools_classified_correctly(self):
        """All read-only tools should be classified as READ tier."""
        read_tools = [
            "list_libraries",
            "get_library_stats",
            "search_library",
            "list_recent",
            "get_server_info",
            "parse_filename",
            "search_tmdb",
            "get_tmdb_metadata",
            "preview_rename",
            "batch_identify",
            "get_ingest_queue",
            "get_queue_item",
            "query_history",
            "get_watcher_status",
            "check_duplicates",
        ]

        for tool in read_tools:
            tier = classify_tool_safety(tool, {})
            assert tier == SafetyTier.READ, f"{tool} should be READ tier"

    def test_write_tools_classified_correctly(self):
        """All write tools should be classified as WRITE tier."""
        write_tools = [
            "scan_library",
            "refresh_metadata",
            "execute_naming_plan",
            "execute_ingest",
            "copy_file",
            "rename_file",
            "move_file",
            "approve_queue_item",
            "reject_queue_item",
            "start_watcher",
            "stop_watcher",
            "restart_watcher",
        ]

        for tool in write_tools:
            tier = classify_tool_safety(tool, {})
            assert tier == SafetyTier.WRITE, f"{tool} should be WRITE tier"

    def test_blocked_tools_classified_correctly(self):
        """All blocked tools should be classified as BLOCKED tier."""
        blocked_tools = [
            "delete_file",
            "delete_directory",
            "delete_library",
            "remove_file",
        ]

        for tool in blocked_tools:
            tier = classify_tool_safety(tool, {})
            assert tier == SafetyTier.BLOCKED, f"{tool} should be BLOCKED tier"

    def test_unknown_tool_defaults_to_write(self):
        """Unknown tools should default to WRITE tier for safety."""
        tier = classify_tool_safety("unknown_nonexistent_tool", {})
        assert tier == SafetyTier.WRITE


class TestAllowOperation:
    """Test should_allow_operation logic."""

    def test_read_operations_allowed(self):
        """READ operations should be allowed."""
        allowed, reason = should_allow_operation(SafetyTier.READ)
        assert allowed is True
        assert reason is None

    def test_write_operations_allowed(self):
        """WRITE operations should be allowed (confirmation handled elsewhere)."""
        allowed, reason = should_allow_operation(SafetyTier.WRITE)
        assert allowed is True
        assert reason is None

    def test_blocked_operations_denied(self):
        """BLOCKED operations should be denied with reason."""
        allowed, reason = should_allow_operation(SafetyTier.BLOCKED)
        assert allowed is False
        assert reason is not None
        assert "blocked" in reason.lower()


class TestConfirmationMessages:
    """Test generation of confirmation messages for WRITE operations."""

    def test_scan_library_message(self):
        """scan_library should have appropriate confirmation message."""
        msg = get_confirmation_message("scan_library", {"library_name": "Movies"})
        assert "Movies" in msg
        assert "scan" in msg.lower()

    def test_scan_all_libraries_message(self):
        """scan_library with no library_name should mention all libraries."""
        msg = get_confirmation_message("scan_library", {"library_name": None})
        assert "all libraries" in msg.lower()

    def test_execute_ingest_message(self):
        """execute_ingest should mention source path."""
        msg = get_confirmation_message(
            "execute_ingest", {"source_path": "/data/ingest/movie.mkv"}
        )
        assert "/data/ingest/movie.mkv" in msg

    def test_start_watcher_message(self):
        """start_watcher should explain automatic processing."""
        msg = get_confirmation_message("start_watcher", {})
        assert "watcher" in msg.lower() or "automatic" in msg.lower()

    def test_unknown_tool_has_generic_message(self):
        """Unknown tools should get generic confirmation message."""
        msg = get_confirmation_message("unknown_tool", {})
        assert len(msg) > 0
        assert "unknown_tool" in msg.lower() or "operation" in msg.lower()


class TestSafetyHook:
    """Test the main safety_hook function."""

    def test_read_tool_hook_result(self):
        """READ tools should return appropriate hook result."""
        result = safety_hook("list_libraries", {})

        assert result["tier"] == "read"
        assert result["allowed"] is True
        assert result["requires_confirmation"] is False
        assert result["confirmation_message"] is None
        assert result["reason"] is None

    def test_write_tool_hook_result(self):
        """WRITE tools should return appropriate hook result."""
        result = safety_hook("scan_library", {"library_name": "Movies"})

        assert result["tier"] == "write"
        assert result["allowed"] is True
        assert result["requires_confirmation"] is True
        assert result["confirmation_message"] is not None
        assert "Movies" in result["confirmation_message"]
        assert result["reason"] is None

    def test_blocked_tool_hook_result(self):
        """BLOCKED tools should return appropriate hook result."""
        result = safety_hook("delete_file", {"path": "/some/file.mkv"})

        assert result["tier"] == "blocked"
        assert result["allowed"] is False
        assert result["requires_confirmation"] is False
        assert result["reason"] is not None
        assert "blocked" in result["reason"].lower()


class TestRealWorldScenarios:
    """Test realistic usage scenarios."""

    def test_ingest_workflow(self):
        """Test a complete ingest workflow."""
        # Step 1: Identify (READ)
        result = safety_hook("batch_identify", {"directory": "/data/ingest"})
        assert result["tier"] == "read"
        assert result["requires_confirmation"] is False

        # Step 2: Preview (READ)
        result = safety_hook("preview_rename", {"source": "/data/ingest/movie.mkv"})
        assert result["tier"] == "read"
        assert result["requires_confirmation"] is False

        # Step 3: Execute (WRITE)
        result = safety_hook("execute_ingest", {"source": "/data/ingest/movie.mkv"})
        assert result["tier"] == "write"
        assert result["requires_confirmation"] is True

        # Step 4: Scan library (WRITE)
        result = safety_hook("scan_library", {"library_name": "Movies"})
        assert result["tier"] == "write"
        assert result["requires_confirmation"] is True

    def test_status_check_workflow(self):
        """Test status checking workflow (all READ)."""
        operations = [
            ("get_server_info", {}),
            ("list_libraries", {}),
            ("get_watcher_status", {}),
            ("query_history", {"limit": 10}),
        ]

        for tool, args in operations:
            result = safety_hook(tool, args)
            assert result["tier"] == "read"
            assert result["requires_confirmation"] is False

    def test_destructive_operations_blocked(self):
        """Test that all destructive operations are blocked."""
        destructive_ops = [
            ("delete_file", {"path": "/Movies/movie.mkv"}),
            ("delete_library", {"name": "Movies"}),
            ("delete_directory", {"path": "/Movies"}),
            ("remove_file", {"path": "/Movies/movie.mkv"}),
        ]

        for tool, args in destructive_ops:
            result = safety_hook(tool, args)
            assert result["tier"] == "blocked"
            assert result["allowed"] is False
            assert result["reason"] is not None

    def test_watcher_control_workflow(self):
        """Test watcher start/stop requires confirmation."""
        # Check status (READ)
        result = safety_hook("get_watcher_status", {})
        assert result["requires_confirmation"] is False

        # Start watcher (WRITE)
        result = safety_hook("start_watcher", {})
        assert result["requires_confirmation"] is True

        # Stop watcher (WRITE)
        result = safety_hook("stop_watcher", {})
        assert result["requires_confirmation"] is True


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_args(self):
        """Safety hook should work with empty args."""
        result = safety_hook("list_libraries", {})
        assert result["allowed"] is True

    def test_none_args(self):
        """Safety hook should handle None values in args."""
        result = safety_hook("scan_library", {"library_name": None})
        assert result["allowed"] is True
        assert result["requires_confirmation"] is True

    def test_extra_args_ignored(self):
        """Extra unexpected args should be ignored."""
        result = safety_hook(
            "list_libraries",
            {"unexpected_arg": "value", "another": 123}
        )
        assert result["tier"] == "read"

    def test_missing_expected_args(self):
        """Missing args should not break safety classification."""
        result = safety_hook("execute_ingest", {})
        assert result["tier"] == "write"
        assert result["requires_confirmation"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
