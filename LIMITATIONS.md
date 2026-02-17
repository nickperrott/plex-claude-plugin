# Videodrome Plugin - Current Limitations & Design Improvements

**Date**: 2026-02-17
**Version**: 0.1.0

## Overview
This document tracks limitations discovered during real-world usage of the videodrome plugin and proposes design improvements for future iterations.

---

## 1. Plex Library Tools - Incomplete Data

### Current Limitation
The `search_library` and `list_recent` tools return basic show information (title, year) but **do not include season/episode details** in their responses.

### Impact
- Cannot determine which seasons are currently in Plex library
- Impossible to compare Plex inventory against external sources (TMDb) to find missing content
- Limits automation capabilities for library management

### Use Case That Failed
> "List all TV shows and check if new seasons are available that we don't have"

This requires knowing:
- What seasons are in Plex for each show
- How many total seasons exist on TMDb
- Which seasons are missing

### Proposed Solution
Add new tools or enhance existing ones:

```python
# Option 1: Enhanced search with detail level
def search_library(section_id: str, query: str, include_details: bool = False):
    """
    Args:
        include_details: If True, include season/episode counts and IDs
    Returns:
        [{
            'title': 'Show Name',
            'year': 2020,
            'seasons': [1, 2, 3],  # Season numbers present
            'episode_counts': {1: 10, 2: 12, 3: 8},  # Episodes per season
            'rating_key': '12345'
        }]
    """

# Option 2: Dedicated show details tool
def get_show_details(rating_key: str):
    """Get comprehensive details for a specific show"""

# Option 3: Bulk inventory tool
def get_library_inventory(section_id: str):
    """Get complete inventory of all shows with seasons"""
```

---

## 2. TMDb Integration Issues

### Current Limitation
The `search_tmdb` tool encountered technical errors when called by agents.

### Error Observed
```
TMDb Tool Error: The TMDb search tool has a technical issue preventing it from being called
```

### Impact
- Cannot validate if shows/movies exist on TMDb
- Cannot retrieve metadata for matching/verification
- Breaks workflows that depend on TMDb lookups

### Investigation Needed
- Review tool implementation and error handling
- Check API key configuration and validation
- Verify rate limiting and timeout settings
- Test tool directly vs. through agents

### Proposed Solution
1. Add better error messages that expose the actual error
2. Implement retry logic with exponential backoff
3. Add tool health check capability
4. Consider caching TMDb responses

---

## 3. NAS Volume Mount Management

### Current Limitation
The plugin cannot access Plex media directories (e.g., `/Volumes/MEDIA/Tv`) when the NAS volume is not mounted.

### Root Cause
**NOT a permission or sandboxing issue** - the `/Volumes/MEDIA` directory simply doesn't exist when the NAS SMB share is not mounted to the local system.

### Environment Details
- **NAS Server**: 10.9.8.15 (TrueNAS)
- **Share Name**: MEDIA (SMB/CIFS)
- **Expected Mount Point**: `/Volumes/MEDIA`
- **Contains**: Plex library directories (`/Volumes/MEDIA/Tv`, `/Volumes/MEDIA/Movies`)

### Impact
- Cannot access media files when volume is unmounted
- `batch_identify` and file-based operations fail
- Ingest operations cannot verify file paths
- No clear error message indicating mount issue

### Proposed Change Request

Add **automatic NAS volume detection and mounting** to the videodrome plugin:

#### New Tools

```python
def check_media_volume():
    """
    Check if MEDIA volume is mounted.

    Returns:
        {
            'mounted': bool,
            'path': '/Volumes/MEDIA',
            'accessible': bool,
            'nas_ip': '10.9.8.15',
            'share_name': 'MEDIA'
        }
    """

def mount_media_volume(force_remount: bool = False):
    """
    Mount the NAS MEDIA share if not already mounted.

    Args:
        force_remount: Unmount and remount if already mounted

    Implementation:
        mount -t smbfs //guest@10.9.8.15/MEDIA /Volumes/MEDIA
        OR use macOS mount_smbfs
        OR use platform-appropriate SMB mount command

    Returns:
        {
            'success': bool,
            'mounted': bool,
            'path': '/Volumes/MEDIA',
            'message': str
        }
    """

def unmount_media_volume():
    """
    Safely unmount the MEDIA volume.

    Checks:
        - No active file operations
        - Plex not actively accessing files
        - Transmission not downloading to volume
    """
```

#### Enhanced Error Handling

All file-based tools should:
1. Check if `/Volumes/MEDIA` is accessible before operations
2. If not mounted, provide actionable error:
   ```
   Error: MEDIA volume not mounted
   Hint: Run mount_media_volume() to mount //10.9.8.15/MEDIA
   ```
3. Optionally auto-mount if configured

#### Configuration

Add to plugin config:
```python
VIDEODROME_CONFIG = {
    'nas': {
        'ip': '10.9.8.15',
        'share_name': 'MEDIA',
        'mount_point': '/Volumes/MEDIA',
        'auto_mount': True,  # Automatically mount when needed
        'credentials': 'guest',  # or credential manager reference
    }
}
```

#### Platform Considerations

**macOS** (Tested & Working):
```bash
# Use macOS open command - uses current user credentials automatically
open smb://10.9.8.15/MEDIA

# This mounts to /Volumes/MEDIA with current user permissions
# Alternative manual mount (if needed):
# mount_smbfs //10.9.8.15/MEDIA /Volumes/MEDIA
```

**Linux**:
```bash
mount -t cifs //10.9.8.15/MEDIA /mnt/media -o username=$USER
```

**Windows**:
```cmd
net use M: \\10.9.8.15\MEDIA
```

**Note**: Do NOT use `//guest@` prefix - let the system use current user credentials for proper permissions.

### Alternative: API-First Approach

Instead of relying on filesystem access, enhance Plex API tools to provide all needed information without direct file access. This is more portable but may have limitations for:
- Pre-ingest file analysis
- Direct file manipulation
- Verification before Plex indexes

### Recommendation

**Hybrid Approach**:
1. Primary: Use Plex API for all library operations
2. Secondary: Auto-mount volume when file access is needed
3. Graceful fallback: Clear errors when mount fails
4. Config option: Allow disabling auto-mount for API-only mode

---

## 4. Season Comparison Workflow

### Current Gap
No built-in way to compare Plex library against external sources to find missing content.

### Desired Workflow
1. Get all shows from Plex with season details
2. For each show, query TMDb for total available seasons
3. Compare and identify gaps
4. Return actionable list of missing seasons
5. (Future) Auto-search for missing content in torrent sources

### Proposed New Tools

```python
def compare_library_to_tmdb(section_id: str):
    """
    Compare entire Plex library against TMDb to find missing seasons.
    Returns shows with available seasons not in Plex.
    """

def get_missing_seasons(show_rating_key: str):
    """
    Check a specific show for missing seasons.
    Returns list of season numbers available on TMDb but not in Plex.
    """

def suggest_searches(tmdb_id: int, missing_seasons: List[int]):
    """
    Generate torrent search queries for missing content.
    """
```

---

## 5. Batch Operations Performance

### Current Limitation
Checking many shows sequentially with individual API calls is slow.

### Impact
- Large libraries (100+ shows) take significant time to process
- Rate limiting may cause delays or failures
- Poor user experience for bulk operations

### Proposed Solution
1. Implement batch/bulk endpoints where possible
2. Add parallel processing with concurrency limits
3. Cache TMDb results (shows don't change that often)
4. Progress reporting for long operations
5. Background task support for async operations

---

## 6. Data Model & Response Structure

### Current State
Tool responses vary in structure and detail level.

### Proposed Standardization

```python
# Standard show response
{
    'plex': {
        'title': str,
        'year': int,
        'rating_key': str,
        'seasons': [int],  # Season numbers
        'library_section_id': str
    },
    'tmdb': {
        'id': int,
        'name': str,
        'total_seasons': int,
        'status': str,  # 'Ended', 'Returning Series', etc.
        'last_air_date': str
    },
    'analysis': {
        'missing_seasons': [int],
        'up_to_date': bool,
        'needs_attention': bool
    }
}
```

---

## 7. Error Handling & User Feedback

### Current Limitation
Errors are sometimes opaque or generic.

### Improvements Needed
- Structured error responses
- Actionable error messages
- Graceful degradation (partial results on partial failure)
- Better logging for debugging

---

## Priority Ranking

1. **HIGH**: Fix TMDb tool errors - blocking critical workflows
2. **HIGH**: Add season details to Plex library tools - core functionality
3. **HIGH**: Implement NAS volume mount detection/management - prevents cryptic errors
4. **MEDIUM**: Implement comparison/gap analysis tools - enables automation
5. **MEDIUM**: Add batch operation support - performance & UX
6. **LOW**: Standardize response formats - polish & consistency

---

## Next Steps

1. **Investigate TMDb errors** - reproduce and fix
2. **Enhance Plex tools** - add season details to responses
3. **Implement NAS mount management** - add volume detection and auto-mount
4. **Design comparison tool** - spec out the API for library vs TMDb comparison
5. **Create test cases** - for common workflows
6. **User feedback** - validate these priorities with actual usage

### Immediate Actions

**NAS Mount Management**:
- [ ] Add `check_media_volume()` tool
- [ ] Add `mount_media_volume()` tool
- [ ] Add configuration for NAS credentials and mount settings
- [ ] Update existing file-based tools to check mount status first
- [ ] Provide clear error messages when volume is not mounted
- [ ] Document manual mount command: `open smb://10.9.8.15/MEDIA` (macOS)

---

## Notes

- Keep MCP server design principles in mind
- Balance between tool granularity and convenience
- Consider agent vs. direct tool usage patterns
- Document expected vs. actual behavior for each tool
