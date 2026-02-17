#!/usr/bin/env bash
# SessionStart hook: outputs Videodrome context for Claude's session.

echo "Videodrome Plugin Active"
echo "========================"
echo ""
echo "Available tool categories:"
echo "  - Library management (list_libraries, scan_library, search_library)"
echo "  - Media identification (parse_filename, search_tmdb, preview_rename)"
echo "  - File ingest (list_ingest_files, ingest_file, get_ingest_history)"
echo "  - Watcher automation (get_watcher_status, start/stop_watcher)"
echo "  - Transmission torrents (add_torrent, list_torrents, get_torrent_status)"
echo ""
echo "Safety rules:"
echo "  - Read-only tools run without confirmation"
echo "  - Write operations require user confirmation"
echo ""

# Show Plex connection status
PLEX_URL="${VIDEODROME_PLEX_URL:-not configured}"
echo "Plex URL: ${PLEX_URL}"

# Show ingest directory status
INGEST_DIR="${VIDEODROME_INGEST_DIR:-not configured}"
if [ -n "$INGEST_DIR" ] && [ "$INGEST_DIR" != "not configured" ]; then
    echo "Ingest Directory: ${INGEST_DIR}"
fi
