"""
Tests for plugin directory structure and manifest validation.

Validates that the Claude Code plugin has all required files,
proper structure, and valid manifest files.
"""

import json
import pytest
from pathlib import Path


# Plugin root directory
PLUGIN_ROOT = Path(__file__).parent.parent / "plex-plugin"


class TestPluginStructure:
    """Test basic plugin directory structure."""

    def test_plugin_directory_exists(self):
        """Plugin directory should exist."""
        assert PLUGIN_ROOT.exists()
        assert PLUGIN_ROOT.is_dir()

    def test_commands_directory_exists(self):
        """Commands directory should exist."""
        commands_dir = PLUGIN_ROOT / "commands"
        assert commands_dir.exists()
        assert commands_dir.is_dir()

    def test_agents_directory_exists(self):
        """Agents directory should exist."""
        agents_dir = PLUGIN_ROOT / "agents"
        assert agents_dir.exists()
        assert agents_dir.is_dir()

    def test_hooks_directory_exists(self):
        """Hooks directory should exist."""
        hooks_dir = PLUGIN_ROOT / "hooks"
        assert hooks_dir.exists()
        assert hooks_dir.is_dir()


class TestCommandFiles:
    """Test command documentation files."""

    REQUIRED_COMMANDS = [
        "scan",
        "identify",
        "rename",
        "ingest",
        "status",
        "plan",
        "watch",
        "review",
    ]

    def test_all_command_files_exist(self):
        """All 8 command files should exist."""
        commands_dir = PLUGIN_ROOT / "commands"

        for cmd in self.REQUIRED_COMMANDS:
            cmd_file = commands_dir / f"{cmd}.md"
            assert cmd_file.exists(), f"Missing command file: {cmd}.md"

    def test_command_files_not_empty(self):
        """Command files should not be empty."""
        commands_dir = PLUGIN_ROOT / "commands"

        for cmd in self.REQUIRED_COMMANDS:
            cmd_file = commands_dir / f"{cmd}.md"
            content = cmd_file.read_text()
            assert len(content) > 100, f"{cmd}.md is too short"

    def test_command_files_have_headers(self):
        """Command files should have proper markdown headers."""
        commands_dir = PLUGIN_ROOT / "commands"

        for cmd in self.REQUIRED_COMMANDS:
            cmd_file = commands_dir / f"{cmd}.md"
            content = cmd_file.read_text()
            assert content.startswith("#"), f"{cmd}.md missing header"
            assert cmd in content.lower(), f"{cmd}.md doesn't mention command name"

    def test_command_files_have_usage_section(self):
        """Command files should have Usage section."""
        commands_dir = PLUGIN_ROOT / "commands"

        for cmd in self.REQUIRED_COMMANDS:
            cmd_file = commands_dir / f"{cmd}.md"
            content = cmd_file.read_text()
            assert "## Usage" in content or "## usage" in content.lower(), \
                f"{cmd}.md missing Usage section"

    def test_command_files_have_safety_section(self):
        """Command files should document safety classification."""
        commands_dir = PLUGIN_ROOT / "commands"

        for cmd in self.REQUIRED_COMMANDS:
            cmd_file = commands_dir / f"{cmd}.md"
            content = cmd_file.read_text()
            # Should mention safety classification
            has_safety = any(term in content.lower() for term in [
                "safety", "read-only", "write operation", "confirmation"
            ])
            assert has_safety, f"{cmd}.md missing safety documentation"


class TestAgentFiles:
    """Test agent documentation files."""

    REQUIRED_AGENTS = ["library", "media", "ingest", "watcher"]

    def test_all_agent_files_exist(self):
        """All 4 agent files should exist."""
        agents_dir = PLUGIN_ROOT / "agents"

        for agent in self.REQUIRED_AGENTS:
            agent_file = agents_dir / f"{agent}.md"
            assert agent_file.exists(), f"Missing agent file: {agent}.md"

    def test_agent_files_not_empty(self):
        """Agent files should not be empty."""
        agents_dir = PLUGIN_ROOT / "agents"

        for agent in self.REQUIRED_AGENTS:
            agent_file = agents_dir / f"{agent}.md"
            content = agent_file.read_text()
            assert len(content) > 500, f"{agent}.md is too short"

    def test_agent_files_have_role_section(self):
        """Agent files should define role."""
        agents_dir = PLUGIN_ROOT / "agents"

        for agent in self.REQUIRED_AGENTS:
            agent_file = agents_dir / f"{agent}.md"
            content = agent_file.read_text()
            assert "## Role" in content or "role" in content.lower(), \
                f"{agent}.md missing Role section"

    def test_agent_files_have_capabilities_section(self):
        """Agent files should describe capabilities."""
        agents_dir = PLUGIN_ROOT / "agents"

        for agent in self.REQUIRED_AGENTS:
            agent_file = agents_dir / f"{agent}.md"
            content = agent_file.read_text()
            assert "## Capabilities" in content or "capabilit" in content.lower(), \
                f"{agent}.md missing Capabilities section"

    def test_agent_files_reference_tools(self):
        """Agent files should mention MCP tools."""
        agents_dir = PLUGIN_ROOT / "agents"

        for agent in self.REQUIRED_AGENTS:
            agent_file = agents_dir / f"{agent}.md"
            content = agent_file.read_text()
            # Should reference tools or MCP
            has_tool_refs = any(term in content.lower() for term in [
                "tool", "mcp", "function", "operation"
            ])
            assert has_tool_refs, f"{agent}.md doesn't reference tools"


class TestHookFiles:
    """Test hook implementation files."""

    def test_safety_hook_exists(self):
        """Safety hook file should exist."""
        hook_file = PLUGIN_ROOT / "hooks" / "safety.py"
        assert hook_file.exists()

    def test_safety_hook_is_valid_python(self):
        """Safety hook should be valid Python."""
        hook_file = PLUGIN_ROOT / "hooks" / "safety.py"
        content = hook_file.read_text()

        # Basic syntax check
        try:
            compile(content, str(hook_file), "exec")
        except SyntaxError as e:
            pytest.fail(f"safety.py has syntax error: {e}")

    def test_safety_hook_has_main_function(self):
        """Safety hook should define safety_hook function."""
        hook_file = PLUGIN_ROOT / "hooks" / "safety.py"
        content = hook_file.read_text()

        assert "def safety_hook(" in content, \
            "safety.py missing safety_hook function"

    def test_safety_hook_has_safety_tiers(self):
        """Safety hook should define SafetyTier enum."""
        hook_file = PLUGIN_ROOT / "hooks" / "safety.py"
        content = hook_file.read_text()

        assert "SafetyTier" in content, \
            "safety.py missing SafetyTier definition"
        assert "READ" in content
        assert "WRITE" in content
        assert "BLOCKED" in content

    def test_safety_hook_has_tool_map(self):
        """Safety hook should have tool classification map."""
        hook_file = PLUGIN_ROOT / "hooks" / "safety.py"
        content = hook_file.read_text()

        assert "TOOL_SAFETY_MAP" in content or "tool_safety" in content.lower(), \
            "safety.py missing tool classification map"


class TestManifestFiles:
    """Test manifest and configuration files."""

    def test_plugin_json_exists(self):
        """plugin.json should exist."""
        manifest = PLUGIN_ROOT / "plugin.json"
        assert manifest.exists()

    def test_plugin_json_is_valid_json(self):
        """plugin.json should be valid JSON."""
        manifest = PLUGIN_ROOT / "plugin.json"
        with open(manifest) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_plugin_json_has_required_fields(self):
        """plugin.json should have all required fields."""
        manifest = PLUGIN_ROOT / "plugin.json"
        with open(manifest) as f:
            data = json.load(f)

        required_fields = [
            "plugin_version",
            "plugin_format",
            "name",
            "display_name",
            "description",
            "author",
            "license",
            "mcp_server",
            "commands",
            "agents",
        ]

        for field in required_fields:
            assert field in data, f"plugin.json missing {field}"

    def test_plugin_json_commands_structure(self):
        """plugin.json commands should have proper structure."""
        manifest = PLUGIN_ROOT / "plugin.json"
        with open(manifest) as f:
            data = json.load(f)

        assert "commands" in data
        assert isinstance(data["commands"], list)
        assert len(data["commands"]) == 8, "Should have 8 commands"

        for cmd in data["commands"]:
            assert "name" in cmd
            assert "description" in cmd
            assert "documentation" in cmd
            assert "safety" in cmd
            assert cmd["safety"] in ["read", "write", "mixed"]

    def test_plugin_json_agents_structure(self):
        """plugin.json agents should have proper structure."""
        manifest = PLUGIN_ROOT / "plugin.json"
        with open(manifest) as f:
            data = json.load(f)

        assert "agents" in data
        assert isinstance(data["agents"], list)
        assert len(data["agents"]) == 4, "Should have 4 agents"

        for agent in data["agents"]:
            assert "name" in agent
            assert "description" in agent
            assert "documentation" in agent

    def test_plugin_json_hooks_structure(self):
        """plugin.json should define safety hook."""
        manifest = PLUGIN_ROOT / "plugin.json"
        with open(manifest) as f:
            data = json.load(f)

        assert "hooks" in data
        assert "safety" in data["hooks"]
        assert "handler" in data["hooks"]["safety"]
        assert "safety.py" in data["hooks"]["safety"]["handler"]

    def test_mcp_json_exists(self):
        """.mcp.json should exist."""
        mcp_config = PLUGIN_ROOT / ".mcp.json"
        assert mcp_config.exists()

    def test_mcp_json_is_valid_json(self):
        """.mcp.json should be valid JSON."""
        mcp_config = PLUGIN_ROOT / ".mcp.json"
        with open(mcp_config) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_mcp_json_has_server_config(self):
        """.mcp.json should have MCP server configuration."""
        mcp_config = PLUGIN_ROOT / ".mcp.json"
        with open(mcp_config) as f:
            data = json.load(f)

        assert "mcpServers" in data
        assert "plex-media-server" in data["mcpServers"]

        server_config = data["mcpServers"]["plex-media-server"]
        assert "command" in server_config
        assert "args" in server_config
        assert "env" in server_config

    def test_mcp_json_env_has_required_vars(self):
        """.mcp.json should define required environment variables."""
        mcp_config = PLUGIN_ROOT / ".mcp.json"
        with open(mcp_config) as f:
            data = json.load(f)

        env = data["mcpServers"]["plex-media-server"]["env"]

        required_vars = [
            "PLEX_URL",
            "PLEX_TOKEN",
            "TMDB_API_KEY",
            "PLEX_MEDIA_ROOT",
        ]

        for var in required_vars:
            assert var in env, f".mcp.json missing {var}"

    def test_skill_md_exists(self):
        """SKILL.md should exist."""
        skill_doc = PLUGIN_ROOT / "SKILL.md"
        assert skill_doc.exists()

    def test_skill_md_not_empty(self):
        """SKILL.md should have substantial content."""
        skill_doc = PLUGIN_ROOT / "SKILL.md"
        content = skill_doc.read_text()
        assert len(content) > 2000, "SKILL.md is too short"

    def test_skill_md_documents_all_commands(self):
        """SKILL.md should document all commands."""
        skill_doc = PLUGIN_ROOT / "SKILL.md"
        content = skill_doc.read_text()

        commands = ["scan", "identify", "rename", "ingest", "status", "plan", "watch", "review"]

        for cmd in commands:
            assert f"/plex:{cmd}" in content, f"SKILL.md missing documentation for /plex:{cmd}"


class TestManifestConsistency:
    """Test consistency between different manifest files."""

    def test_command_files_match_plugin_json(self):
        """Command files should match commands in plugin.json."""
        manifest = PLUGIN_ROOT / "plugin.json"
        with open(manifest) as f:
            data = json.load(f)

        commands_dir = PLUGIN_ROOT / "commands"

        for cmd in data["commands"]:
            cmd_name = cmd["name"]
            doc_path = cmd["documentation"]

            # Check file exists
            full_path = PLUGIN_ROOT / doc_path
            assert full_path.exists(), \
                f"plugin.json references missing file: {doc_path}"

            # Check file is in commands directory
            assert full_path.parent == commands_dir

    def test_agent_files_match_plugin_json(self):
        """Agent files should match agents in plugin.json."""
        manifest = PLUGIN_ROOT / "plugin.json"
        with open(manifest) as f:
            data = json.load(f)

        agents_dir = PLUGIN_ROOT / "agents"

        for agent in data["agents"]:
            agent_name = agent["name"]
            doc_path = agent["documentation"]

            # Check file exists
            full_path = PLUGIN_ROOT / doc_path
            assert full_path.exists(), \
                f"plugin.json references missing file: {doc_path}"

            # Check file is in agents directory
            assert full_path.parent == agents_dir

    def test_mcp_server_name_matches(self):
        """MCP server name should match between plugin.json and .mcp.json."""
        plugin_manifest = PLUGIN_ROOT / "plugin.json"
        with open(plugin_manifest) as f:
            plugin_data = json.load(f)

        mcp_config = PLUGIN_ROOT / ".mcp.json"
        with open(mcp_config) as f:
            mcp_data = json.load(f)

        plugin_server_name = plugin_data["mcp_server"]
        assert plugin_server_name in mcp_data["mcpServers"], \
            "MCP server name mismatch between plugin.json and .mcp.json"


class TestProjectRootManifest:
    """Test the project root manifest.json file."""

    def test_root_manifest_exists(self):
        """Root manifest.json should exist."""
        root_manifest = Path(__file__).parent.parent / "manifest.json"
        assert root_manifest.exists()

    def test_root_manifest_is_valid_json(self):
        """Root manifest.json should be valid JSON."""
        root_manifest = Path(__file__).parent.parent / "manifest.json"
        with open(root_manifest) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_root_manifest_has_server_config(self):
        """Root manifest should have server configuration."""
        root_manifest = Path(__file__).parent.parent / "manifest.json"
        with open(root_manifest) as f:
            data = json.load(f)

        required_fields = [
            "manifest_version",
            "name",
            "display_name",
            "description",
            "version",
            "author",
            "server",
        ]

        for field in required_fields:
            assert field in data, f"manifest.json missing {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
