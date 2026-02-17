# Change Request: Torrent Search Integration (torrent-search-mcp)

**Date**: 2026-02-17
**Type**: New Feature - Dependency Integration
**Priority**: HIGH

## Overview

Integrate [torrent-search-mcp](https://github.com/philogicae/torrent-search-mcp) as native videodrome tools, enabling automated torrent search to close the gap between `find_new_seasons` gap analysis and `add_torrent` download queuing.

## Motivation

During the "find new seasons" workflow (2026-02-17), we successfully identified 20+ shows with missing seasons but could not automate torrent retrieval:
- Direct web scraping of MagnetDL was blocked (Cloudflare/anti-bot)
- No programmatic magnet link source existed in the plugin
- `torrent-search-mcp` was identified as a native MCP solution

## Security Assessment

**Rating: CAUTION** *(reviewed 2026-02-17)*

| Factor | Risk | Notes |
|--------|------|-------|
| Code malice | LOW | No credential theft or exfiltration found |
| Direct CVEs | LOW | All dependency CVEs (crawl4ai) fixed in current versions |
| Dependency pinning | MEDIUM | Dependencies unpinned — pin versions in our pyproject.toml |
| Maintenance | MEDIUM | Active (last commit Feb 2026), no formal security policy |
| API exposure | MEDIUM | FastAPI mode has no auth — use stdio/MCP transport only, never expose HTTP |

**Mitigations to apply:**
- Use only via stdio MCP transport (never run FastAPI mode)
- Pin `torrent-search-mcp` and `crawl4ai>=0.8.0` in pyproject.toml
- Run in the existing videodrome venv (contained environment)
- No credentials required for ThePirateBay/1337x sources

## Integration Architecture

Integrate as **native videodrome tools** (not a separate MCP server) following existing plugin patterns.

### New Files

```
server/
├── torrent_search.py          # TorrentSearchClient wrapper
└── tools/
    └── torrent_search.py      # @mcp.tool() implementations
tests/
└── test_torrent_search.py     # Unit tests
```

### `server/torrent_search.py` — Client Wrapper

```python
"""TorrentSearchClient wrapping torrent-search-mcp."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TorrentSearchClient:
    """
    Wraps the torrent-search-mcp library for use within videodrome.

    Providers (configured via TORRENT_SEARCH_PROVIDERS env var):
        - thepiratebay
        - nyaa
        - ygg  (requires YGG_USERNAME/YGG_PASSWORD)
    """

    def __init__(self, providers: List[str] = None):
        self.providers = providers or ["thepiratebay", "nyaa"]
        self._is_available = False

    def connect(self) -> bool:
        """Verify torrent-search-mcp is available."""
        try:
            from torrent_search import TorrentSearch  # noqa: F401
            self._is_available = True
            logger.info("TorrentSearchClient ready (providers: %s)", self.providers)
            return True
        except ImportError:
            logger.warning("torrent-search-mcp not installed — torrent search unavailable")
            return False

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for torrents by query string.

        Returns list of results, each with:
            id, title, source, size, seeders, leechers, date
        """
        from torrent_search import TorrentSearch

        loop = asyncio.get_event_loop()
        ts = TorrentSearch()

        results = await loop.run_in_executor(
            None, lambda: ts.search(query, limit=limit)
        )

        return [self._normalise(r) for r in (results or [])]

    async def get_magnet(self, torrent_id: str) -> Optional[str]:
        """
        Resolve a torrent ID to its magnet link.

        Args:
            torrent_id: ID returned by search()

        Returns:
            Magnet URI string, or None if unavailable
        """
        from torrent_search import TorrentSearch

        loop = asyncio.get_event_loop()
        ts = TorrentSearch()

        result = await loop.run_in_executor(
            None, lambda: ts.get_torrent(torrent_id)
        )

        return result.get("magnet") if result else None

    @staticmethod
    def _normalise(raw: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": raw.get("id", ""),
            "title": raw.get("title", ""),
            "source": raw.get("source", ""),
            "size": raw.get("size", ""),
            "seeders": int(raw.get("seeders") or 0),
            "leechers": int(raw.get("leechers") or 0),
            "date": raw.get("date", ""),
            "magnet": raw.get("magnet"),  # may be None — use get_magnet() to resolve
        }

    @staticmethod
    def rank(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort results: season packs first, then by seeder count descending."""
        def score(r):
            title_lower = r["title"].lower()
            pack_bonus = 1000 if any(
                kw in title_lower for kw in ["complete", "season", "s0", "pack"]
            ) else 0
            return pack_bonus + r["seeders"]

        return sorted(results, key=score, reverse=True)
```

### `server/tools/torrent_search.py` — Tool Implementations

```python
"""Torrent search tool functions for videodrome MCP."""

from typing import Any, Dict, List, Optional

from server.torrent_search import TorrentSearchClient


async def search_torrents(
    client: TorrentSearchClient,
    query: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """Search for torrents across configured providers."""
    if not client.is_available:
        return {"error": "Torrent search not available (torrent-search-mcp not installed)"}

    results = await client.search(query, limit=limit)
    ranked = TorrentSearchClient.rank(results)
    return {"results": ranked, "total": len(ranked), "query": query}


async def get_torrent_magnet(
    client: TorrentSearchClient,
    torrent_id: str,
) -> Dict[str, Any]:
    """Resolve a torrent search result ID to its magnet link."""
    if not client.is_available:
        return {"error": "Torrent search not available"}

    magnet = await client.get_magnet(torrent_id)
    if not magnet:
        return {"error": f"Could not retrieve magnet for id={torrent_id}"}
    return {"torrent_id": torrent_id, "magnet": magnet}


async def search_season(
    client: TorrentSearchClient,
    show_title: str,
    season: int,
    quality: str = "1080p",
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Convenience tool: search for a complete season pack.

    Generates optimised queries:
        "{show} Season {N} complete {quality}"
        "{show} S{NN} {quality}"
    and returns ranked results preferring season packs.
    """
    if not client.is_available:
        return {"error": "Torrent search not available"}

    queries = [
        f"{show_title} Season {season} complete {quality}",
        f"{show_title} S{season:02d} {quality}",
    ]

    seen_ids = set()
    all_results = []
    for q in queries:
        results = await client.search(q, limit=limit)
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                all_results.append(r)

    ranked = TorrentSearchClient.rank(all_results)
    return {
        "show": show_title,
        "season": season,
        "quality": quality,
        "results": ranked[:limit],
        "total": len(ranked),
    }
```

### `server/main.py` — Registration additions

```python
from server import torrent_search as torrent_search_module
from server.tools import torrent_search as torrent_search_tools

# In lifespan():
torrent_search_client = torrent_search_module.TorrentSearchClient(
    providers=os.getenv("TORRENT_SEARCH_PROVIDERS", "thepiratebay").split(",")
)
torrent_search_client.connect()  # Gracefully no-ops if library not installed

# New tools:
@mcp.tool()
async def search_torrents(query: str, limit: int = 10) -> dict:
    """Search for torrents by title or keyword across configured providers."""
    return await torrent_search_tools.search_torrents(torrent_search_client, query, limit)

@mcp.tool()
async def get_torrent_magnet(torrent_id: str) -> dict:
    """Get the magnet link for a torrent result ID returned by search_torrents."""
    return await torrent_search_tools.get_torrent_magnet(torrent_search_client, torrent_id)

@mcp.tool()
async def search_season(show_title: str, season: int, quality: str = "1080p") -> dict:
    """Search for a complete season pack for a TV show."""
    return await torrent_search_tools.search_season(torrent_search_client, show_title, season, quality)
```

### `server/safety.py` — Safety classifications

```python
# All torrent search tools are READ tier (no side effects)
"search_torrents":      SafetyTier.READ,
"get_torrent_magnet":   SafetyTier.READ,
"search_season":        SafetyTier.READ,
```

## Dependency Changes

### `pyproject.toml`

```toml
[project]
dependencies = [
    # ... existing deps ...
    "torrent-search-mcp>=1.1.0",  # Torrent search across multiple providers
    "crawl4ai>=0.8.0",            # Required by torrent-search-mcp (pin >= 0.8.0 for CVE fix)
]
```

### Post-install setup

`torrent-search-mcp` requires Playwright/Chromium for scraping. Add to install script:

```bash
# install.sh / setup-install.sh additions
uvx playwright install --with-deps chromium
# or if using venv:
playwright install --with-deps chromium
```

## Configuration

### New Environment Variables

```bash
# Providers to use (comma-separated)
# Options: thepiratebay, nyaa, ygg
TORRENT_SEARCH_PROVIDERS=thepiratebay

# YggTorrent credentials (optional — French torrent site)
YGG_USERNAME=
YGG_PASSWORD=
```

### Add to `manifest.json` user_config section

```json
"TORRENT_SEARCH_PROVIDERS": {
    "type": "string",
    "description": "Comma-separated torrent search providers (thepiratebay, nyaa, ygg)",
    "default": "thepiratebay"
}
```

## End-to-End Workflow

Once implemented, the full automated workflow becomes:

```
find_new_seasons()
    → returns list of {show, missing_seasons}
    → for each missing season:
        search_season(show, season, "1080p")
            → returns ranked results with IDs
        get_torrent_magnet(result["id"])
            → returns magnet URI
        add_torrent(magnet, download_dir)
            → queued in Transmission
    → list_torrents() to monitor progress
    → scan_library() when complete
```

## Implementation Checklist

- [ ] Add `torrent-search-mcp>=1.1.0` to `pyproject.toml`
- [ ] Add playwright install step to `setup-install.sh`
- [ ] Create `server/torrent_search.py` (TorrentSearchClient)
- [ ] Create `server/tools/torrent_search.py` (tool functions)
- [ ] Register 3 new tools in `server/main.py`
- [ ] Add safety classifications in `server/safety.py`
- [ ] Add env vars to `manifest.json`
- [ ] Create `tests/test_torrent_search.py`
- [ ] Update `README.md` with new tool category
- [ ] Test end-to-end: search_season → get_torrent_magnet → add_torrent
- [ ] Pin crawl4ai>=0.8.0 to avoid CVE

## Testing Plan

```python
# tests/test_torrent_search.py

async def test_search_returns_ranked_results():
    """Season packs should rank above individual episodes."""

async def test_search_season_deduplicates():
    """Multi-query search should not return duplicate IDs."""

async def test_graceful_degradation():
    """Tools should return error dict when library not installed."""

async def test_rank_prefers_packs():
    """'Complete Season' in title gets priority over episodes."""
```

## Related Change Requests

- `CHANGE_REQUEST_find_new_seasons.md` — Workflow that uses these tools
- `CHANGE_REQUEST_review_based_discovery.md` — Review-based workflow (also uses torrent search)
- `LIMITATIONS.md` — Original problem statement (Section 2: TMDb errors, Section 3: NAS mount)
