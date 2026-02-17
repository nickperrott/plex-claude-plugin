# Change Request: Find New Seasons Workflow

**Date**: 2026-02-17
**Type**: New Feature - Agentic Workflow
**Priority**: HIGH

## Overview

Add an intelligent agentic workflow that automatically checks all TV shows in Plex against TMDb to identify new seasons that are available but not yet in the library.

## User Story

> As a Plex user, I want to automatically discover which of my TV shows have new seasons available on TMDb that I don't yet have in my library, so I can keep my collection up to date without manually checking each show.

## Current Workaround

Currently requires:
1. Manually listing all TV shows in Plex
2. For each show, manually checking TMDb for total seasons
3. Comparing Plex seasons vs TMDb seasons
4. Tracking which seasons are missing

This is time-consuming and error-prone for large libraries (100+ shows).

## Proposed Solution

### New High-Level Tool

```python
def find_new_seasons(
    section_id: str = None,
    show_filter: str = None,
    auto_search_torrents: bool = False
) -> Dict:
    """
    Agentic workflow to find TV shows with new seasons available.

    Args:
        section_id: Plex TV library section ID (default: auto-detect)
        show_filter: Optional filter (e.g., "Breaking Bad" to check specific show)
        auto_search_torrents: If True, automatically search for missing seasons

    Workflow:
        1. Get all TV shows from Plex library
        2. For each show, extract seasons currently in library
        3. Search TMDb for show and get total seasons available
        4. Compare and identify missing seasons
        5. Generate report with actionable information
        6. (Optional) Auto-search torrents for missing content

    Returns:
        {
            'total_shows_checked': int,
            'shows_with_new_seasons': [
                {
                    'title': str,
                    'year': int,
                    'plex_rating_key': str,
                    'plex_seasons': [1, 2, 3],
                    'tmdb_id': int,
                    'tmdb_total_seasons': int,
                    'tmdb_status': str,  # 'Returning Series', 'Ended', etc.
                    'missing_seasons': [4, 5],
                    'latest_air_date': str,
                    'next_episode_date': str,  # if available
                    'torrent_searches': [...]  # if auto_search enabled
                }
            ],
            'up_to_date_shows': int,
            'failed_lookups': [...]  # Shows that couldn't be matched
        }
    """
```

## Implementation Details

### Step 1: Enhance Plex Library Tools

Current tools don't return season information. Need to:

```python
# Enhanced library tool
def get_library_inventory(section_id: str) -> List[Dict]:
    """Get complete TV show inventory with season details"""
    shows = []
    for show in plex_library.all():
        seasons = [s.seasonNumber for s in show.seasons() if s.seasonNumber > 0]
        shows.append({
            'title': show.title,
            'year': show.year,
            'rating_key': show.ratingKey,
            'seasons': sorted(seasons),
            'episode_count': sum(s.episodeCount() for s in show.seasons())
        })
    return shows
```

### Step 2: TMDb Matching & Comparison

```python
def match_and_compare(plex_show: Dict) -> Dict:
    """Match Plex show to TMDb and compare seasons"""

    # Search TMDb
    tmdb_results = search_tmdb(
        title=plex_show['title'],
        year=plex_show['year'],
        media_type='tv'
    )

    if not tmdb_results:
        return {'status': 'not_found'}

    tmdb_show = tmdb_results[0]

    # Get season details
    tmdb_seasons = [s['season_number'] for s in tmdb_show['seasons']
                    if s['season_number'] > 0]

    plex_seasons = plex_show['seasons']
    missing = [s for s in tmdb_seasons if s not in plex_seasons]

    return {
        'status': 'matched',
        'tmdb_id': tmdb_show['id'],
        'tmdb_seasons': tmdb_seasons,
        'missing_seasons': missing,
        'has_new_content': len(missing) > 0
    }
```

### Step 3: Intelligent Reporting

Generate user-friendly output:

```
📺 NEW SEASONS AVAILABLE
========================

Found 5 shows with new seasons:

1. Breaking Bad (2008)
   Current: Seasons 1-4 (40 episodes)
   Available: Season 5 (16 episodes)
   Status: Ended
   TMDb ID: 1396

2. Severance (2022)
   Current: Season 1 (9 episodes)
   Available: Season 2 (expected 2026)
   Status: Returning Series
   TMDb ID: 95396

...

📊 SUMMARY
- Total shows checked: 127
- Shows up to date: 122
- Shows with new seasons: 5
- Failed to match: 0
```

### Step 4: Torrent Search & Download Integration

When `auto_search_torrents=True`, automatically search for and download missing seasons:

#### 4.1 Torrent Search Strategy

```python
def search_torrents_for_season(show_title: str, season: int, year: int = None) -> List[Dict]:
    """
    Search multiple torrent sources for a specific season.

    Args:
        show_title: TV show name
        season: Season number
        year: Optional release year for disambiguation

    Search Strategy:
        1. Generate search queries:
           - "{show_title} Season {season} complete"
           - "{show_title} S{season:02d} complete"
           - "{show_title} S{season:02d} 1080p"

        2. Search sources (in priority order):
           - MagnetDL (magnetdl.com) - Primary
           - 1337x.to - Secondary
           - RARBG mirrors - Tertiary
           - ThePirateBay mirrors - Fallback

        3. Filter results:
           - Prefer COMPLETE SEASON packs over individual episodes
           - Quality: 1080p > 720p > other
           - Codec: x265 (smaller) or x264 (compatible)
           - Avoid: CAM, TS, screeners
           - Seeders: Minimum 5, prefer 20+

        4. Validate magnet URIs:
           - Must start with "magnet:?xt=urn:btih:"
           - Must contain valid info hash

    Returns:
        [{
            'source': 'magnetdl',
            'title': 'Ted Lasso S03 Complete 1080p',
            'magnet': 'magnet:?xt=urn:btih:...',
            'size': '12.5 GB',
            'seeders': 45,
            'quality': '1080p',
            'is_season_pack': True,
            'score': 95  # Quality score 0-100
        }]
    """
```

#### 4.2 Magnet Extraction

```python
def extract_magnet_from_page(url: str) -> str:
    """
    Extract magnet link from torrent page.

    Implementation approaches:
        1. HTML parsing: BeautifulSoup/lxml to find magnet links
        2. Regex: Search for 'magnet:?xt=' patterns
        3. JavaScript rendering: For sites using dynamic content

    Error handling:
        - Retry with backoff on timeout
        - Try multiple mirrors if primary fails
        - Return None if no valid magnet found
    """
```

#### 4.3 Download Automation

```python
def auto_download_missing_seasons(
    missing_seasons: List[Dict],
    quality_preference: str = '1080p',
    auto_approve: bool = False,
    max_concurrent: int = 3
) -> Dict:
    """
    Automatically search for and download missing seasons.

    Args:
        missing_seasons: List from find_new_seasons() output
        quality_preference: Preferred quality (1080p, 720p, 2160p)
        auto_approve: If False, ask for confirmation before adding
        max_concurrent: Max simultaneous downloads

    Workflow:
        1. For each missing season:
           a. Search torrents with quality filter
           b. Rank results by score (quality + seeders + completeness)
           c. Select top result
           d. If auto_approve=False, present to user for confirmation
           e. Add magnet to Transmission via add_torrent()
           f. Track in download queue

        2. Monitor downloads:
           - Check transmission status periodically
           - Report progress
           - Trigger library scan when complete

    Returns:
        {
            'queued': [{'show': 'Ted Lasso', 'season': 3, 'torrent_id': 123}],
            'failed': [{'show': 'Foundation', 'season': 2, 'reason': 'No torrents found'}],
            'pending_approval': [...]  # If auto_approve=False
        }
    """
```

#### 4.4 Integration with Transmission

```python
# Use existing add_torrent tool
def queue_season_download(magnet: str, show_title: str, season: int):
    """
    Add torrent to Transmission with proper organization.

    Implementation:
        1. Set download directory to organized path:
           /Volumes/MEDIA/transmission/downloads/{show_title}/Season {season:02d}/

        2. Add to Transmission:
           add_torrent(
               magnet_or_url=magnet,
               download_dir=f"/Volumes/MEDIA/transmission/downloads/{sanitize(show_title)}"
           )

        3. Track in ingest queue:
           - Record source magnet, show, season
           - Monitor download completion
           - Auto-ingest when ready
    """
```

#### 4.5 Post-Download Workflow

```python
def on_download_complete(torrent_id: int):
    """
    Handle completed downloads.

    Workflow:
        1. Verify download integrity
        2. Parse filename to confirm season
        3. Move to appropriate Plex directory:
           /Volumes/MEDIA/Tv/{Show Title}/Season {season}/
        4. Trigger Plex library scan for that section
        5. Update ingest history
        6. (Optional) Remove torrent after seeding period
    """
```

## Dependencies

### Required Enhancements
1. ✅ NAS volume mount management (see LIMITATIONS.md #3)
2. 🔧 Fix TMDb tool errors (see LIMITATIONS.md #2)
3. 🔧 Add season details to Plex tools (see LIMITATIONS.md #1)

### New Tools Needed
- `get_library_inventory()` - bulk show/season extraction
- `match_show_to_tmdb()` - intelligent matching with fuzzy search
- `compare_seasons()` - gap analysis
- `find_new_seasons()` - orchestrating workflow

## Performance Considerations

For large libraries:
- **Caching**: Cache TMDb results (shows rarely change)
- **Rate Limiting**: Respect TMDb API limits (40 req/10sec)
- **Parallel Processing**: Check shows concurrently with limits
- **Progress Reporting**: Stream progress for long operations
- **Incremental Updates**: Only check shows updated since last scan

## Configuration

```yaml
videodrome:
  find_new_seasons:
    cache_tmdb_results: true
    cache_ttl_hours: 24
    concurrent_lookups: 5
    rate_limit_per_second: 4
    exclude_patterns:
      - "Season 0"  # Specials
      - ".*\(test\).*"
    min_tmdb_confidence: 0.8  # Matching threshold

    # Torrent search configuration
    auto_search_torrents: false
    auto_download: false  # If true, skip confirmation
    quality_preference: "1080p"  # 2160p, 1080p, 720p
    prefer_x265: true  # Smaller file sizes
    min_seeders: 5
    torrent_sources:
      - name: "magnetdl"
        url: "https://www.magnetdl.com"
        enabled: true
        priority: 1
      - name: "1337x"
        url: "https://1337x.to"
        enabled: true
        priority: 2
      - name: "therarbg"
        url: "https://therarbg.com"
        enabled: false
        priority: 3

    # Download organization
    download_base_dir: "/Volumes/MEDIA/transmission/downloads"
    organize_by_show: true  # Create subdirs per show
    transmission_label: "videodrome-auto"  # Label torrents
```

## Testing Scenarios

### Phase 1: Season Detection
1. **Happy Path**: Library with mix of up-to-date and outdated shows
2. **No Results**: All shows are current
3. **All Need Updates**: Neglected library
4. **Failed Matches**: Shows with unusual names or years
5. **Large Library**: 500+ shows for performance testing
6. **Rate Limiting**: Ensure graceful handling of API limits

### Phase 2: Torrent Search
7. **Popular Show**: Find season pack for mainstream show (high seeders)
8. **Obscure Show**: Search for less popular show (few seeders)
9. **Recent Release**: Find very recent season (< 1 week old)
10. **Multiple Quality Options**: Choose best among 720p/1080p/2160p
11. **No Results**: Handle show with no available torrents
12. **Dead Torrents**: Filter out 0-seeder results

### Phase 3: Download Automation
13. **Single Season Download**: Add one season to Transmission
14. **Batch Download**: Queue 5+ seasons, respect concurrency limits
15. **Download Monitoring**: Track progress, handle completion
16. **Failed Download**: Handle torrent that fails/stalls
17. **Disk Space**: Check available space before queuing
18. **Organization**: Verify files go to correct directories

## User Experience

### CLI Usage
```bash
# Check all shows
claude-code "find new seasons for my TV shows"

# Check specific show
claude-code "check if Breaking Bad has new seasons"

# Auto-search mode
claude-code "find new seasons and search for torrents"
```

### Expected Output
- Progress indicator during scan
- Clear, actionable results
- Links to TMDb for verification
- Option to auto-add to torrent queue

## Success Metrics

- Can process 100 shows in < 2 minutes
- 95%+ accuracy in TMDb matching
- Zero crashes on rate limiting or API errors
- Clear, actionable output format
- User can act on results immediately

## Future Enhancements

1. **Scheduled Scanning**: Weekly auto-check with notifications
2. **Smart Prioritization**: Rank by popularity, air date, user ratings
3. **Auto-Download**: Integrate with torrent automation
4. **Notification System**: Alert when new seasons become available
5. **Multi-Source**: Check other metadata sources (TVDB, IMDb)
6. **Movie Support**: Extend to movie collections/franchises

## Implementation Plan

### Phase 1: Core Season Detection (COMPLETED ✓)
- [x] Fix TMDb tool errors
- [x] Add filesystem-based season detection
- [x] Implement TMDb matching via web search
- [x] Build comparison/gap analysis
- [x] Generate detailed markdown report
- [x] Test with real library (490 shows analyzed)

### Phase 2: Torrent Search Integration (IN PROGRESS)
- [ ] Build `search_torrents_for_season()` function
  - [ ] Implement MagnetDL scraper
  - [ ] Add 1337x scraper as secondary source
  - [ ] Implement magnet link extraction
  - [ ] Add result filtering (quality, seeders, season packs)
  - [ ] Build scoring/ranking algorithm
- [ ] Create torrent search tool for MCP
- [ ] Add error handling and retries
- [ ] Test with various show titles and seasons

### Phase 3: Download Automation (NEXT)
- [ ] Build `auto_download_missing_seasons()` workflow
  - [ ] Integrate with existing `add_torrent()` tool
  - [ ] Implement download directory organization
  - [ ] Add user confirmation prompts (if auto_approve=False)
  - [ ] Track downloads in queue
- [ ] Add download monitoring
  - [ ] Check Transmission status periodically
  - [ ] Report progress to user
  - [ ] Handle failures gracefully
- [ ] Implement post-download workflow
  - [ ] Verify file integrity
  - [ ] Auto-rename/organize files
  - [ ] Trigger Plex library scan
  - [ ] Update ingest history

### Phase 4: Enhancement & Polish
- [ ] Add caching layer for TMDb results
- [ ] Implement parallel torrent searches
- [ ] Add progress reporting for long operations
- [ ] Improve show name matching (fuzzy search)
- [ ] Add quality preference configuration
- [ ] Implement disk space checking before downloads

### Phase 5: Advanced Automation
- [ ] Implement scheduled scanning (weekly/daily)
- [ ] Build notification system (new seasons available)
- [ ] Add RSS feed integration for automated tracking
- [ ] Create dashboard for monitoring downloads
- [ ] Implement smart prioritization (popularity, air dates)

## Session Notes: 2026-02-17

### What We Accomplished Today

1. **✓ Successfully completed Phase 1**:
   - Analyzed 490 TV show directories in `/Volumes/MEDIA/Tv`
   - Detected seasons via filesystem structure
   - Cross-referenced with TMDb via web search
   - Generated comprehensive report (`/tmp/missing_seasons_report.md`)
   - Identified 20+ shows with missing seasons

2. **✓ Key Findings**:
   - HIGH PRIORITY: Only Murders (missing S2-5), Slow Horses (missing S2,4), Ted Lasso (missing S3)
   - Recently completed: Fallout S2, The Night Agent S2-3, Lincoln Lawyer S1,3,4
   - Completed series: Sweet Tooth S2-3, Our Flag Means Death S2

3. **Attempted Phase 2 (Torrent Search)**:
   - Tried to automate torrent search and download
   - Agent identified torrent pages but couldn't extract magnets
   - WebFetch failed with 522 errors (timeout/blocking)
   - Direct curl attempts also failed to extract magnets

### Challenges Encountered

1. **Torrent Site Access**:
   - MagnetDL appears to block automated scraping
   - Need user-agent spoofing or browser emulation
   - May need Selenium/Playwright for JavaScript-rendered pages
   - Alternative: Use torrent APIs or RSS feeds instead

2. **Magnet Link Extraction**:
   - Direct HTML parsing may not work for dynamic sites
   - Need to handle various page structures per site
   - Regex patterns need to be robust

3. **Rate Limiting**:
   - Multiple concurrent requests may trigger blocks
   - Need delays between requests
   - Consider using proxy rotation

### Next Steps for Phase 2 Implementation

1. **Implement Robust Web Scraping**:
   ```python
   # Option 1: Use requests with proper headers
   headers = {
       'User-Agent': 'Mozilla/5.0 ...',
       'Referer': 'https://www.magnetdl.com'
   }

   # Option 2: Use Selenium/Playwright for JS-heavy sites
   from playwright.sync_api import sync_playwright

   # Option 3: Use existing Python torrent libraries
   # - python-libtorrent
   # - torrent-search-python
   # - magnetico
   ```

2. **Alternative Approaches**:
   - Use Prowlarr/Jackett APIs (torrent indexer aggregators)
   - Implement RSS feed watching
   - Use BTN/PTP APIs if user has access
   - Fall back to manual input (user provides magnets)

3. **User Workflow**:
   - Generate search URLs for user to click
   - User copies magnet links
   - Paste into tool for bulk add
   - Semi-automated is better than fully manual

### Lessons Learned

- **Filesystem access is crucial**: Need NAS volume mounted
- **Web scraping is fragile**: Sites change, block bots, use JS
- **Hybrid approach works best**: Automate what we can, assist with rest
- **Report generation succeeded**: Clear, actionable output
- **TMDb web search workaround**: When API fails, web search works

## Related Documents

- `LIMITATIONS.md` - Current plugin limitations
- `README.md` - Plugin overview
- `docs/workflows.md` - Other agentic workflows (to be created)
- `/tmp/missing_seasons_report.md` - Latest analysis output (2026-02-17)

## Notes

This workflow represents the type of high-value automation that makes the videodrome plugin powerful. It combines:
- Data aggregation (Plex library)
- External enrichment (TMDb metadata)
- Intelligent comparison (gap analysis)
- Actionable output (what to download)

This pattern can be applied to other workflows:
- Find missing movie sequels/prequels
- Detect quality upgrades available (1080p → 4K)
- Identify orphaned files not in Plex
- Validate metadata accuracy
