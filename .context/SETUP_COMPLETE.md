# 🎉 Configuration System Complete!

I've added a complete configuration system to make setup super easy!

## What Was Added

### 1. QUICKSTART.md
Comprehensive 5-minute setup guide with:
- Step-by-step instructions for getting Plex token
- TMDb API key setup
- All configuration options explained
- Troubleshooting tips
- Example configurations

### 2. Interactive Configuration Script
**`configure.py`** - Smart wizard that:
- ✓ Prompts for all settings with examples
- ✓ Validates URLs and paths
- ✓ Tests Plex connection
- ✓ Tests TMDb API
- ✓ Saves to `.env` file
- ✓ Backs up existing config

### 3. Quick Setup Script
**`setup-config.sh`** - One-command setup:
```bash
./setup-config.sh
```

### 4. Plugin Command
**`/plex:configure`** - Run from Claude Code
- Added to plugin.json (9 commands total now)
- Full documentation in commands/configure.md

### 5. Updated README.md
- Quick Start section at the top
- Links to QUICKSTART.md
- Clear 3-step process

## How to Use

### Option 1: Quick Setup (Recommended)

```bash
cd /Users/nick/conductor/workspaces/plex-claude-plugin/montreal-v1
./setup-config.sh
```

### Option 2: Direct Python

```bash
uv run python configure.py
```

### Option 3: From Claude Code

```
/plex:configure
```

## What It Creates

The wizard creates a `.env` file:

```bash
# Plex MCP Server Configuration

# Required Settings
PLEX_URL=http://192.168.1.100:32400
PLEX_TOKEN=abc123...
TMDB_API_KEY=xyz789...
PLEX_MEDIA_ROOT=/Volumes/Media

# Optional Settings
PLEX_INGEST_DIR=/Volumes/Media/Incoming
PLEX_AUTO_INGEST=false
PLEX_CONFIDENCE_THRESHOLD=0.85
PLEX_WATCHER_AUTO_START=false
```

## Next Steps

### 1. Run the Configuration Wizard

```bash
./setup-config.sh
```

### 2. Test the Server

```bash
uv run --env-file .env plex-mcp
```

Should output:
```
INFO - Starting Plex MCP Server...
INFO - Connecting to Plex server at http://...
INFO - Initializing TMDb cache...
INFO - Plex MCP Server started successfully!
```

Press Ctrl+C to stop.

### 3. Add to Claude Desktop

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "plex": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/nick/conductor/workspaces/plex-claude-plugin/montreal-v1",
        "run",
        "--env-file",
        ".env",
        "plex-mcp"
      ]
    }
  }
}
```

**Restart Claude Desktop** to load the server!

### 4. Verify in Claude

In a new conversation:
```
Can you check if the Plex server is connected?
```

Claude should be able to use the plex tools!

## Files Created

```
montreal-v1/
├── QUICKSTART.md              # Comprehensive setup guide
├── configure.py               # Interactive configuration wizard
├── setup-config.sh            # Quick setup script
├── .env                       # Your configuration (created by wizard)
├── .env.backup                # Backup of previous config
├── README.md                  # Updated with Quick Start
└── plex-plugin/
    ├── commands/
    │   └── configure.md       # /plex:configure documentation
    └── plugin.json            # Updated with configure command
```

## Plugin Commands (9 total)

1. `/plex:scan` - Trigger library scans
2. `/plex:identify` - Identify media files
3. `/plex:rename` - Rename files to Plex format
4. `/plex:ingest` - Full ingest pipeline
5. `/plex:status` - Server status
6. `/plex:plan` - Preview naming plans
7. `/plex:watch` - Manage file watcher
8. `/plex:review` - Review queue items
9. **`/plex:configure`** - Interactive setup (NEW!)

## Troubleshooting

### "Missing required environment variables"

Run: `./setup-config.sh` to configure

### "Connection refused"

- Check Plex is running: `http://YOUR_IP:32400/web`
- Try localhost: `http://localhost:32400`
- Check firewall settings

### "Invalid token"

Get fresh token:
1. Plex Web → Play media → Info → View XML
2. Look for `X-Plex-Token=` in URL
3. Copy the token part

### ".env not loading in Claude Desktop"

Make sure `--env-file .env` is in the args array:
```json
"args": [
  "--directory", "/full/path",
  "run",
  "--env-file", ".env",  // ← This line!
  "plex-mcp"
]
```

## Testing Checklist

- [ ] Run `./setup-config.sh` and complete wizard
- [ ] See `.env` file created
- [ ] Run `uv run --env-file .env plex-mcp` successfully
- [ ] Add to Claude Desktop config
- [ ] Restart Claude Desktop
- [ ] Verify Plex tools available in Claude
- [ ] Test with `/plex:status` or similar

---

**You're all set!** 🚀

The configuration wizard will make setup much easier for users. Let me know if you encounter any issues!
