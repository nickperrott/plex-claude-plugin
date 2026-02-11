"""Media MCP tools for filename parsing and TMDb matching."""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path

import guessit

from server.matcher import MediaMatcher
from server.tmdb_cache import TMDbCache


# Global matcher instance
_matcher: Optional[MediaMatcher] = None


def get_matcher() -> MediaMatcher:
    """Get or create global MediaMatcher instance."""
    global _matcher

    if _matcher is None:
        tmdb_api_key = os.getenv("TMDB_API_KEY", "")
        media_root = os.getenv("PLEX_MEDIA_ROOT", "/data/media")

        # Initialize cache
        cache_dir = Path.home() / ".cache" / "plex-mcp"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / "tmdb_cache.db"

        cache = TMDbCache(cache_path, ttl_days=30)

        # Note: cache.initialize() must be called async, will be done in main.py
        _matcher = MediaMatcher(
            tmdb_api_key=tmdb_api_key,
            cache=cache,
            media_root=media_root
        )

    return _matcher


async def parse_filename(filename: str) -> Dict[str, Any]:
    """Parse a filename using guessit.

    Args:
        filename: Filename to parse

    Returns:
        Dictionary with success status and parsed metadata or error
    """
    try:
        result = guessit.guessit(filename)
        parsed = dict(result)

        return {
            "success": True,
            "filename": filename,
            "parsed": parsed
        }
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "error": str(e)
        }


async def search_tmdb(
    title: str,
    year: Optional[int] = None,
    media_type: str = "movie"
) -> Dict[str, Any]:
    """Search TMDb for a title.

    Args:
        title: Media title to search
        year: Optional release year
        media_type: "movie" or "tv"

    Returns:
        Dictionary with success status and search results or error
    """
    try:
        matcher = get_matcher()
        results = await matcher.search_tmdb(title, year, media_type)

        response = {
            "success": True,
            "query": {
                "title": title,
                "year": year,
                "media_type": media_type
            },
            "results": results,
            "count": len(results)
        }

        if not results:
            response["message"] = "No results found"

        return response
    except Exception as e:
        return {
            "success": False,
            "query": {
                "title": title,
                "year": year,
                "media_type": media_type
            },
            "error": str(e)
        }


async def preview_rename(filename: str) -> Dict[str, Any]:
    """Preview rename for a media file.

    Args:
        filename: Filename to match and preview

    Returns:
        Dictionary with success status, match info, and Plex path or error
    """
    try:
        matcher = get_matcher()
        result = await matcher.match_media(filename)

        if not result:
            return {
                "success": False,
                "filename": filename,
                "error": "No match found for this file"
            }

        response = {
            "success": True,
            "original_filename": filename,
            "parsed": result["parsed"],
            "tmdb_id": result["tmdb_id"],
            "tmdb_title": result["tmdb_result"].get("title") or result["tmdb_result"].get("name"),
            "confidence": result["confidence"],
            "plex_path": result["plex_path"]
        }

        # Add warning for low confidence
        if result["confidence"] < 0.85:
            response["warning"] = (
                f"Low confidence match ({result['confidence']:.2f}). "
                "Please verify this is correct before proceeding."
            )

        return response
    except Exception as e:
        return {
            "success": False,
            "filename": filename,
            "error": str(e)
        }


async def batch_identify(
    filenames: List[str],
    confidence_threshold: float = 0.85
) -> Dict[str, Any]:
    """Identify multiple media files in batch.

    Args:
        filenames: List of filenames to identify
        confidence_threshold: Minimum confidence threshold (default 0.85)

    Returns:
        Dictionary with success status, batch results, and statistics
    """
    try:
        if not filenames:
            return {
                "success": False,
                "error": "No filenames provided"
            }

        matcher = get_matcher()
        results = await matcher.batch_match(filenames)

        # Process results
        processed_results = []
        matched_count = 0
        failed_count = 0
        low_confidence_count = 0

        for filename, match in zip(filenames, results):
            if match is None:
                processed_results.append({
                    "filename": filename,
                    "matched": False,
                    "error": "No match found"
                })
                failed_count += 1
            else:
                matched_count += 1

                result_item = {
                    "filename": filename,
                    "matched": True,
                    "tmdb_id": match["tmdb_id"],
                    "tmdb_title": match["tmdb_result"].get("title") or match["tmdb_result"].get("name"),
                    "confidence": match["confidence"],
                    "plex_path": match["plex_path"]
                }

                if match["confidence"] < confidence_threshold:
                    result_item["warning"] = "Low confidence match"
                    low_confidence_count += 1

                processed_results.append(result_item)

        return {
            "success": True,
            "total": len(filenames),
            "matched": matched_count,
            "failed": failed_count,
            "low_confidence": low_confidence_count,
            "confidence_threshold": confidence_threshold,
            "results": processed_results
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
