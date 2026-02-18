"""Tests for discovery tools (find_new_seasons, discover_top_rated_content)."""

import asyncio
import json
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.tools.discovery import (
    find_new_seasons,
    discover_top_rated_content,
    _parse_star_rating_from_html,
    _parse_guardian_jsonld,
    _fetch_newspaper_reviews,
    _fetch_guardian_review,
    _fetch_telegraph_review,
    _find_guardian_review_url_via_rss,
    _fetch_url_with_browser,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_plex_client():
    client = MagicMock()
    client.list_libraries = AsyncMock(return_value=[
        {"key": "2", "title": "TV Shows", "type": "show", "locations": ["/data/tv"]},
    ])
    client.get_library_inventory = AsyncMock(return_value=[
        {"title": "Breaking Bad", "year": 2008, "rating_key": "101", "seasons": [1, 2, 3, 4], "episode_count": 40},
        {"title": "Severance", "year": 2022, "rating_key": "202", "seasons": [1], "episode_count": 9},
    ])
    client.search_library = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_matcher():
    matcher = MagicMock()

    async def fake_search_tmdb(title, year=None, media_type="movie", **kwargs):
        if title == "Breaking Bad":
            return [{
                "id": 1396,
                "name": "Breaking Bad",
                "status": "Ended",
                "seasons": [
                    {"season_number": 1}, {"season_number": 2},
                    {"season_number": 3}, {"season_number": 4}, {"season_number": 5},
                ],
                "last_air_date": "2013-09-29",
                "next_episode_to_air": None,
                "media_type": "tv",
            }]
        if title == "Severance":
            return [{
                "id": 95396,
                "name": "Severance",
                "status": "Returning Series",
                "seasons": [
                    {"season_number": 1}, {"season_number": 2},
                ],
                "last_air_date": "2025-01-01",
                "next_episode_to_air": None,
                "media_type": "tv",
            }]
        return []

    matcher.search_tmdb = fake_search_tmdb
    return matcher


# =============================================================================
# find_new_seasons tests
# =============================================================================


@pytest.mark.asyncio
async def test_find_new_seasons_identifies_missing(mock_plex_client, mock_matcher):
    """find_new_seasons should correctly identify seasons missing from Plex."""
    result = await find_new_seasons(mock_plex_client, mock_matcher, section_id="2")

    assert result["total_shows_checked"] == 2
    shows = {s["title"]: s for s in result["shows_with_new_seasons"]}

    # Breaking Bad: has 1-4 in Plex, TMDb has 1-5 → season 5 missing
    assert "Breaking Bad" in shows
    assert shows["Breaking Bad"]["missing_seasons"] == [5]

    # Severance: has season 1 in Plex, TMDb has 1-2 → season 2 missing
    assert "Severance" in shows
    assert shows["Severance"]["missing_seasons"] == [2]


@pytest.mark.asyncio
async def test_find_new_seasons_up_to_date_show(mock_plex_client, mock_matcher):
    """find_new_seasons should count shows that are fully up to date."""
    # Modify inventory so Breaking Bad has all 5 seasons
    mock_plex_client.get_library_inventory = AsyncMock(return_value=[
        {"title": "Breaking Bad", "year": 2008, "rating_key": "101",
         "seasons": [1, 2, 3, 4, 5], "episode_count": 62},
    ])

    result = await find_new_seasons(mock_plex_client, mock_matcher, section_id="2")

    assert result["up_to_date_shows"] == 1
    assert result["shows_with_new_seasons_count"] == 0


@pytest.mark.asyncio
async def test_find_new_seasons_auto_detects_section(mock_plex_client, mock_matcher):
    """find_new_seasons should auto-detect the TV section when section_id is None."""
    result = await find_new_seasons(mock_plex_client, mock_matcher, section_id=None)

    # Should have called list_libraries and used section "2"
    mock_plex_client.list_libraries.assert_called_once()
    assert result["section_id"] == "2"


@pytest.mark.asyncio
async def test_find_new_seasons_no_tv_section(mock_plex_client, mock_matcher):
    """find_new_seasons should return error when no TV section found."""
    mock_plex_client.list_libraries = AsyncMock(return_value=[
        {"key": "1", "title": "Movies", "type": "movie"},
    ])

    result = await find_new_seasons(mock_plex_client, mock_matcher, section_id=None)

    assert "error" in result


@pytest.mark.asyncio
async def test_find_new_seasons_show_filter(mock_plex_client, mock_matcher):
    """find_new_seasons with show_filter should only check matching shows."""
    result = await find_new_seasons(
        mock_plex_client, mock_matcher, section_id="2", show_filter="Breaking"
    )

    assert result["total_shows_checked"] == 1
    assert result["shows_with_new_seasons"][0]["title"] == "Breaking Bad"


@pytest.mark.asyncio
async def test_find_new_seasons_failed_lookup(mock_plex_client, mock_matcher):
    """find_new_seasons should record failed lookups without crashing."""
    async def failing_search(title, year=None, media_type="movie", **kwargs):
        raise RuntimeError("API error")

    mock_matcher.search_tmdb = failing_search

    result = await find_new_seasons(mock_plex_client, mock_matcher, section_id="2")

    assert len(result["failed_lookups"]) == 2
    assert result["shows_with_new_seasons_count"] == 0


@pytest.mark.asyncio
async def test_find_new_seasons_with_torrent_search(mock_plex_client, mock_matcher):
    """find_new_seasons with auto_search_torrents should include torrent_searches."""
    mock_torrent_client = MagicMock()
    mock_torrent_client.is_available = True
    mock_torrent_client.search = AsyncMock(return_value=[
        {"id": "t1", "title": "Breaking Bad S05 Complete", "seeders": 100,
         "leechers": 5, "source": "tpb", "size": "10 GB", "date": "2024", "magnet": None}
    ])

    result = await find_new_seasons(
        mock_plex_client, mock_matcher,
        section_id="2",
        show_filter="Breaking Bad",
        auto_search_torrents=True,
        torrent_client=mock_torrent_client,
    )

    bb = next(s for s in result["shows_with_new_seasons"] if s["title"] == "Breaking Bad")
    assert "torrent_searches" in bb
    assert bb["torrent_searches"][0]["season"] == 5


@pytest.mark.asyncio
async def test_find_new_seasons_fetches_tmdb_tv_details_when_search_lacks_seasons(
    mock_plex_client, mock_matcher
):
    """find_new_seasons should fetch TMDb TV details when search payload omits season metadata."""
    mock_plex_client.get_library_inventory = AsyncMock(return_value=[
        {"title": "Breaking Bad", "year": 2008, "rating_key": "101", "seasons": [1, 2, 3, 4], "episode_count": 40},
    ])

    async def search_without_seasons(title, year=None, media_type="movie", **kwargs):
        return [{
            "id": 1396,
            "name": "Breaking Bad",
            "media_type": "tv",
        }]

    mock_matcher.search_tmdb = search_without_seasons

    mock_tv = MagicMock()
    mock_tv.info = MagicMock(return_value={
        "id": 1396,
        "name": "Breaking Bad",
        "status": "Ended",
        "seasons": [
            {"season_number": 0},
            {"season_number": 1},
            {"season_number": 2},
            {"season_number": 3},
            {"season_number": 4},
            {"season_number": 5},
        ],
        "last_air_date": "2013-09-29",
        "next_episode_to_air": None,
    })

    with patch("tmdbsimple.TV", return_value=mock_tv):
        result = await find_new_seasons(mock_plex_client, mock_matcher, section_id="2")

    shows = {s["title"]: s for s in result["shows_with_new_seasons"]}
    assert shows["Breaking Bad"]["missing_seasons"] == [5]
    mock_tv.info.assert_called_once()


# =============================================================================
# discover_top_rated_content tests
# =============================================================================


@pytest.mark.asyncio
async def test_discover_returns_dict_structure(mock_plex_client, mock_matcher):
    """discover_top_rated_content should return expected top-level keys."""
    mock_trending = MagicMock()
    mock_trending.info = MagicMock(return_value={
        "results": [
            {
                "id": 1234, "title": "Great Movie", "vote_average": 8.5,
                "vote_count": 500, "popularity": 80.0, "genre_ids": [],
                "release_date": "2024-06-01", "overview": "A great film."
            }
        ]
    })

    mock_top = MagicMock()
    mock_top.top_rated = MagicMock(return_value={"results": []})

    mock_genres = MagicMock()
    mock_genres.movie_list = MagicMock(return_value={"genres": []})
    mock_genres.tv_list = MagicMock(return_value={"genres": []})

    with patch("tmdbsimple.Trending", return_value=mock_trending), \
         patch("tmdbsimple.Movies", return_value=mock_top), \
         patch("tmdbsimple.TV", return_value=mock_top), \
         patch("tmdbsimple.Genres", return_value=mock_genres):
        result = await discover_top_rated_content(
            mock_plex_client, mock_matcher,
            content_type="movie", min_rating=7.0, max_results=10
        )

    assert "recommendations" in result
    assert "total_found" in result
    assert "filtered_out" in result
    assert "already_in_library" in result


@pytest.mark.asyncio
async def test_discover_filters_by_min_rating(mock_plex_client, mock_matcher):
    """discover_top_rated_content should exclude items below min_rating."""
    mock_trending = MagicMock()
    mock_trending.info = MagicMock(return_value={
        "results": [
            {"id": 1, "title": "Great Film", "vote_average": 9.0, "vote_count": 200,
             "popularity": 50.0, "genre_ids": [], "release_date": "2024-01-01", "overview": ""},
            {"id": 2, "title": "Mediocre Film", "vote_average": 5.0, "vote_count": 200,
             "popularity": 10.0, "genre_ids": [], "release_date": "2024-01-01", "overview": ""},
        ]
    })
    mock_top = MagicMock()
    mock_top.top_rated = MagicMock(return_value={"results": []})
    mock_genres = MagicMock()
    mock_genres.movie_list = MagicMock(return_value={"genres": []})
    mock_genres.tv_list = MagicMock(return_value={"genres": []})

    with patch("tmdbsimple.Trending", return_value=mock_trending), \
         patch("tmdbsimple.Movies", return_value=mock_top), \
         patch("tmdbsimple.Genres", return_value=mock_genres):
        result = await discover_top_rated_content(
            mock_plex_client, mock_matcher,
            content_type="movie", min_rating=7.5
        )

    titles = [r["title"] for r in result["recommendations"]]
    assert "Great Film" in titles
    assert "Mediocre Film" not in titles


@pytest.mark.asyncio
async def test_discover_year_range_supports_open_ended_start(mock_plex_client, mock_matcher):
    """discover_top_rated_content should apply start-only year range filters."""
    mock_trending = MagicMock()
    mock_trending.info = MagicMock(return_value={
        "results": [
            {"id": 1, "title": "Older Film", "vote_average": 8.0, "vote_count": 200,
             "popularity": 10.0, "genre_ids": [], "release_date": "2020-01-01", "overview": ""},
            {"id": 2, "title": "Newer Film", "vote_average": 8.2, "vote_count": 200,
             "popularity": 20.0, "genre_ids": [], "release_date": "2024-01-01", "overview": ""},
        ]
    })
    mock_top = MagicMock()
    mock_top.top_rated = MagicMock(return_value={"results": []})
    mock_genres = MagicMock()
    mock_genres.movie_list = MagicMock(return_value={"genres": []})
    mock_genres.tv_list = MagicMock(return_value={"genres": []})

    with patch("tmdbsimple.Trending", return_value=mock_trending), \
         patch("tmdbsimple.Movies", return_value=mock_top), \
         patch("tmdbsimple.Genres", return_value=mock_genres):
        result = await discover_top_rated_content(
            mock_plex_client, mock_matcher,
            content_type="movie",
            min_rating=7.0,
            year_range=(2023, None),
        )

    titles = [r["title"] for r in result["recommendations"]]
    assert "Newer Film" in titles
    assert "Older Film" not in titles


# =============================================================================
# _parse_star_rating_from_html unit tests
# =============================================================================


def test_parse_star_rating_data_attribute():
    """_parse_star_rating_from_html should extract data-rating attribute."""
    html = '<div data-rating="4">Some review content</div>'
    score = _parse_star_rating_from_html(html)
    assert score == 8.0  # 4/5 * 10


def test_parse_star_rating_fraction():
    """_parse_star_rating_from_html should parse '4/5' fraction."""
    html = "<p>We give this film 4/5 stars.</p>"
    score = _parse_star_rating_from_html(html)
    assert score == 8.0


def test_parse_star_rating_unicode_stars():
    """_parse_star_rating_from_html should count filled ★ characters."""
    html = "<p>Rating: ★★★☆☆ for this movie.</p>"
    score = _parse_star_rating_from_html(html)
    # Longest run of ★ is 3 → 3/5 * 10 = 6.0
    assert score == 6.0


def test_parse_star_rating_css_class():
    """_parse_star_rating_from_html should parse stars-N CSS class."""
    html = '<span class="stars-3">Review</span>'
    score = _parse_star_rating_from_html(html)
    assert score == 6.0  # 3/5 * 10


def test_parse_star_rating_no_match():
    """_parse_star_rating_from_html should return None when no rating found."""
    html = "<p>This is a review with no numerical rating.</p>"
    score = _parse_star_rating_from_html(html)
    assert score is None


def test_parse_star_rating_data_attribute_caps_at_10():
    """_parse_star_rating_from_html should not exceed 10.0."""
    html = '<div data-rating="5">Perfect</div>'
    score = _parse_star_rating_from_html(html)
    assert score == 10.0


# =============================================================================
# _fetch_newspaper_reviews tests
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_newspaper_reviews_both_sources():
    """_fetch_newspaper_reviews should merge guardian and telegraph scores."""
    loop = asyncio.get_event_loop()

    guardian_data = {"score": 8.0, "url": "https://www.theguardian.com/film/2023/review", "headline": "Excellent film", "source": "guardian"}
    telegraph_data = {"score": 7.0, "url": "https://archive.ph/example", "source": "telegraph"}

    with patch("server.tools.discovery._fetch_guardian_review", return_value=guardian_data), \
         patch("server.tools.discovery._fetch_telegraph_review", return_value=telegraph_data):
        result = await _fetch_newspaper_reviews("Oppenheimer", 2023, loop)

    assert result["guardian"] == 8.0
    assert result["guardian_url"] == "https://www.theguardian.com/film/2023/review"
    assert result["guardian_headline"] == "Excellent film"
    assert result["telegraph"] == 7.0


@pytest.mark.asyncio
async def test_fetch_newspaper_reviews_guardian_only():
    """_fetch_newspaper_reviews should work when only guardian returns a score."""
    loop = asyncio.get_event_loop()

    guardian_data = {"score": 9.0, "url": "https://www.theguardian.com/film/2023/review", "headline": "Masterpiece", "source": "guardian"}

    with patch("server.tools.discovery._fetch_guardian_review", return_value=guardian_data), \
         patch("server.tools.discovery._fetch_telegraph_review", return_value=None):
        result = await _fetch_newspaper_reviews("Barbie", 2023, loop)

    assert "guardian" in result
    assert "telegraph" not in result


@pytest.mark.asyncio
async def test_fetch_newspaper_reviews_both_fail_returns_empty():
    """_fetch_newspaper_reviews should return empty dict when both sources fail."""
    loop = asyncio.get_event_loop()

    with patch("server.tools.discovery._fetch_guardian_review", return_value=None), \
         patch("server.tools.discovery._fetch_telegraph_review", return_value=None):
        result = await _fetch_newspaper_reviews("Unknown Film", 2023, loop)

    assert result == {}


# ---------------------------------------------------------------------------
# _parse_guardian_jsonld unit tests
# ---------------------------------------------------------------------------


def test_parse_guardian_jsonld_extracts_review_rating():
    """_parse_guardian_jsonld should extract rating from JSON-LD Review object."""
    jsonld = json.dumps({"@type": "Review", "reviewRating": {"ratingValue": "4", "bestRating": "5"}})
    html = f'<script type="application/ld+json">{jsonld}</script>'
    score = _parse_guardian_jsonld(html)
    assert score == 8.0  # 4/5 * 10


def test_parse_guardian_jsonld_handles_array():
    """_parse_guardian_jsonld should handle a JSON-LD array."""
    jsonld = json.dumps([
        {"@type": "WebPage"},
        {"@type": "Review", "reviewRating": {"ratingValue": "3", "bestRating": "5"}},
    ])
    html = f'<script type="application/ld+json">{jsonld}</script>'
    score = _parse_guardian_jsonld(html)
    assert score == 6.0


def test_parse_guardian_jsonld_returns_none_when_no_review():
    """_parse_guardian_jsonld should return None when no Review type found."""
    jsonld = json.dumps({"@type": "WebPage", "name": "Guardian"})
    html = f'<script type="application/ld+json">{jsonld}</script>'
    score = _parse_guardian_jsonld(html)
    assert score is None


def test_parse_guardian_jsonld_caps_at_10():
    """_parse_guardian_jsonld should not exceed 10.0."""
    jsonld = json.dumps({"@type": "Review", "reviewRating": {"ratingValue": "5", "bestRating": "5"}})
    html = f'<script type="application/ld+json">{jsonld}</script>'
    score = _parse_guardian_jsonld(html)
    assert score == 10.0


# ---------------------------------------------------------------------------
# _fetch_guardian_review scraping tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_guardian_review_extracts_jsonld_score_via_rss():
    """_fetch_guardian_review should use RSS URL and extract score from JSON-LD."""
    loop = asyncio.get_event_loop()

    padding = "<!-- " + "x" * 480 + " -->"
    jsonld = json.dumps({"@type": "Review", "reviewRating": {"ratingValue": "4", "bestRating": "5"}})
    review_html = (
        "<html><head>"
        "<title>Barbie review</title>"
        "</head><body>"
        f'<script type="application/ld+json">{jsonld}</script>'
        + padding
        + "</body></html>"
    )

    rss_url = "https://www.theguardian.com/film/2023/jul/21/barbie-review-greta-gerwig"

    with patch("server.tools.discovery._find_guardian_review_url_via_rss",
               new=AsyncMock(return_value=rss_url)), \
         patch("server.tools.discovery._fetch_url_with_browser",
               new=AsyncMock(return_value=review_html)):
        result = await _fetch_guardian_review("Barbie", 2023, loop)

    assert result is not None
    assert result["score"] == 8.0  # 4/5 * 10
    assert result["source"] == "guardian"
    assert "barbie-review" in result["url"]


@pytest.mark.asyncio
async def test_fetch_guardian_review_falls_back_to_search_when_rss_misses():
    """_fetch_guardian_review should scrape search page when RSS has no match."""
    loop = asyncio.get_event_loop()

    padding = "<!-- " + "x" * 480 + " -->"
    search_html = (
        "<html><head><title>Guardian film search</title></head><body>"
        '<a href="https://www.theguardian.com/film/2020/jan/10/old-film-review">'
        "Old Film review</a>"
        + padding
        + "</body></html>"
    )
    jsonld = json.dumps({"@type": "Review", "reviewRating": {"ratingValue": "3", "bestRating": "5"}})
    review_html = (
        "<html><head><title>Old Film review</title></head><body>"
        f'<script type="application/ld+json">{jsonld}</script>'
        + padding
        + "</body></html>"
    )

    browser_calls = [search_html, review_html]

    with patch("server.tools.discovery._find_guardian_review_url_via_rss",
               new=AsyncMock(return_value=None)), \
         patch("server.tools.discovery._fetch_url_with_browser",
               new=AsyncMock(side_effect=browser_calls)):
        result = await _fetch_guardian_review("Old Film", 2020, loop)

    assert result is not None
    assert result["score"] == 6.0  # 3/5 * 10
    assert result["source"] == "guardian"


@pytest.mark.asyncio
async def test_fetch_guardian_review_returns_none_when_search_blocked():
    """_fetch_guardian_review should return None cleanly when search page is blocked."""
    loop = asyncio.get_event_loop()

    with patch("server.tools.discovery._find_guardian_review_url_via_rss",
               new=AsyncMock(return_value=None)), \
         patch("server.tools.discovery._fetch_url_with_browser",
               new=AsyncMock(return_value=None)):
        result = await _fetch_guardian_review("ZXY Unknown Film 9999", None, loop)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_guardian_review_falls_back_to_search_when_rss_article_unparseable():
    """_fetch_guardian_review should fall back to search if RSS article has no parseable rating."""
    loop = asyncio.get_event_loop()

    padding = "<!-- " + "x" * 480 + " -->"
    rss_url = "https://www.theguardian.com/film/2024/jan/10/some-film-review"
    rss_review_html = (
        "<html><head><title>Some Film review</title></head><body>"
        "<p>No rating in this page</p>"
        + padding
        + "</body></html>"
    )
    search_html = (
        "<html><head><title>Guardian film search</title></head><body>"
        '<a href="https://www.theguardian.com/film/2024/jan/11/some-film-review-better-match">'
        "Some Film review</a>"
        + padding
        + "</body></html>"
    )
    jsonld = json.dumps({"@type": "Review", "reviewRating": {"ratingValue": "5", "bestRating": "5"}})
    review_html = (
        "<html><head><title>Some Film review</title></head><body>"
        f'<script type="application/ld+json">{jsonld}</script>'
        + padding
        + "</body></html>"
    )

    browser_calls = [rss_review_html, search_html, review_html]

    with patch("server.tools.discovery._find_guardian_review_url_via_rss",
               new=AsyncMock(return_value=rss_url)), \
         patch("server.tools.discovery._fetch_url_with_browser",
               new=AsyncMock(side_effect=browser_calls)):
        result = await _fetch_guardian_review("Some Film", 2024, loop)

    assert result is not None
    assert result["score"] == 10.0
    assert "better-match" in result["url"]


# =============================================================================
# discover_top_rated_content with include_newspaper_reviews=False
# =============================================================================


@pytest.mark.asyncio
async def test_discover_newspaper_reviews_disabled(mock_plex_client, mock_matcher):
    """discover_top_rated_content with include_newspaper_reviews=False should not call newspaper functions."""
    mock_trending = MagicMock()
    mock_trending.info = MagicMock(return_value={
        "results": [
            {"id": 99, "title": "Test Film", "vote_average": 8.0, "vote_count": 200,
             "popularity": 60.0, "genre_ids": [], "release_date": "2024-01-01", "overview": ""},
        ]
    })
    mock_top = MagicMock()
    mock_top.top_rated = MagicMock(return_value={"results": []})
    mock_genres = MagicMock()
    mock_genres.movie_list = MagicMock(return_value={"genres": []})
    mock_genres.tv_list = MagicMock(return_value={"genres": []})

    with patch("tmdbsimple.Trending", return_value=mock_trending), \
         patch("tmdbsimple.Movies", return_value=mock_top), \
         patch("tmdbsimple.Genres", return_value=mock_genres), \
         patch("server.tools.discovery._fetch_newspaper_reviews") as mock_np:
        result = await discover_top_rated_content(
            mock_plex_client, mock_matcher,
            content_type="movie", min_rating=7.0,
            include_newspaper_reviews=False,
        )

    mock_np.assert_not_called()
    assert "recommendations" in result


# =============================================================================
# _find_guardian_review_url_via_rss unit tests
# =============================================================================


@pytest.mark.asyncio
async def test_find_guardian_review_url_via_rss_matches_title():
    """_find_guardian_review_url_via_rss should return the link for a matching review item."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Film | The Guardian</title>
    <item>
      <title>Dune: Part Two review – spectacular science fiction epic</title>
      <link>https://www.theguardian.com/film/2024/feb/27/dune-part-two-review</link>
    </item>
    <item>
      <title>Poor Things review – Emma Stone dazzles</title>
      <link>https://www.theguardian.com/film/2024/jan/12/poor-things-review</link>
    </item>
  </channel>
</rss>"""

    def fake_urlopen(req, timeout=None):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = rss_xml.encode()
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        url = await _find_guardian_review_url_via_rss("Dune: Part Two")

    assert url == "https://www.theguardian.com/film/2024/feb/27/dune-part-two-review"


@pytest.mark.asyncio
async def test_find_guardian_review_url_via_rss_returns_none_when_no_match():
    """_find_guardian_review_url_via_rss should return None when title not in feed."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Poor Things review – Emma Stone dazzles</title>
      <link>https://www.theguardian.com/film/2024/jan/12/poor-things-review</link>
    </item>
  </channel>
</rss>"""

    def fake_urlopen(req, timeout=None):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = rss_xml.encode()
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        url = await _find_guardian_review_url_via_rss("Oppenheimer")

    assert url is None


@pytest.mark.asyncio
async def test_find_guardian_review_url_via_rss_returns_none_on_network_error():
    """_find_guardian_review_url_via_rss should return None on network failure."""
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        url = await _find_guardian_review_url_via_rss("Any Film")

    assert url is None


@pytest.mark.asyncio
async def test_find_guardian_review_url_via_rss_avoids_partial_title_matches():
    """_find_guardian_review_url_via_rss should not match substrings inside other titles."""
    rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>There Will Be Blood review – still a masterpiece</title>
      <link>https://www.theguardian.com/film/2024/mar/01/there-will-be-blood-review</link>
    </item>
    <item>
      <title>Hereditary review – Ari Aster chills</title>
      <link>https://www.theguardian.com/film/2024/mar/02/hereditary-review</link>
    </item>
  </channel>
</rss>"""

    def fake_urlopen(req, timeout=None):
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = rss_xml.encode()
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        url = await _find_guardian_review_url_via_rss("Her")

    assert url is None


# =============================================================================
# Telegraph — no archive.ph fallback
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_telegraph_returns_none_cleanly_when_paywalled():
    """_fetch_telegraph_review should return None cleanly (no archive.ph) when blocked."""
    loop = asyncio.get_event_loop()

    with patch("server.tools.discovery._fetch_url_with_browser",
               new=AsyncMock(return_value=None)):
        result = await _fetch_telegraph_review("Inception", 2010, loop)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_telegraph_no_archive_ph_calls():
    """_fetch_telegraph_review must not make any archive.ph requests."""
    loop = asyncio.get_event_loop()

    browser_urls_called = []

    async def track_browser_calls(url):
        browser_urls_called.append(url)
        return None

    from server.tools.discovery import _fetch_telegraph_review

    with patch("server.tools.discovery._fetch_url_with_browser",
               side_effect=track_browser_calls):
        await _fetch_telegraph_review("Some Film", 2023, loop)

    assert not any("archive.ph" in u for u in browser_urls_called), (
        f"archive.ph was called unexpectedly: {browser_urls_called}"
    )


# =============================================================================
# _fetch_url_with_browser tiered scraper tests
# =============================================================================


@pytest.mark.asyncio
async def test_fetch_url_with_browser_uses_curl_cffi_fast_path():
    """_fetch_url_with_browser should return content from curl-cffi on 200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html><body>content</body></html>"

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    curl_cffi_module = types.ModuleType("curl_cffi")
    curl_requests_module = types.ModuleType("curl_cffi.requests")
    curl_requests_module.AsyncSession = MagicMock(return_value=mock_session)
    curl_cffi_module.requests = curl_requests_module

    with patch.dict(
        sys.modules,
        {"curl_cffi": curl_cffi_module, "curl_cffi.requests": curl_requests_module},
    ):
        result = await _fetch_url_with_browser("https://example.com")

    assert result == "<html><body>content</body></html>"


@pytest.mark.asyncio
async def test_fetch_url_with_browser_escalates_to_crawl4ai_on_non_200():
    """_fetch_url_with_browser should fall through to crawl4ai when curl-cffi gets a non-200."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_crawl_result = MagicMock()
    mock_crawl_result.success = True
    mock_crawl_result.html = "<html>crawl4ai result</html>"

    mock_crawler = MagicMock()
    mock_crawler.arun = AsyncMock(return_value=mock_crawl_result)
    mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
    mock_crawler.__aexit__ = AsyncMock(return_value=False)

    curl_cffi_module = types.ModuleType("curl_cffi")
    curl_requests_module = types.ModuleType("curl_cffi.requests")
    curl_requests_module.AsyncSession = MagicMock(return_value=mock_session)
    curl_cffi_module.requests = curl_requests_module

    crawl4ai_module = types.ModuleType("crawl4ai")
    crawl4ai_module.AsyncWebCrawler = MagicMock(return_value=mock_crawler)
    crawl4ai_module.BrowserConfig = MagicMock(return_value=MagicMock())

    class ImportErrorUndetectedAdapter:
        def __init__(self):
            raise ImportError("Patchright unavailable")

    browser_adapter_module = types.ModuleType("crawl4ai.browser_adapter")
    browser_adapter_module.UndetectedAdapter = ImportErrorUndetectedAdapter

    strategy_module = types.ModuleType("crawl4ai.async_crawler_strategy")
    strategy_module.AsyncPlaywrightCrawlerStrategy = MagicMock(return_value=MagicMock())

    with patch.dict(
        sys.modules,
        {
            "curl_cffi": curl_cffi_module,
            "curl_cffi.requests": curl_requests_module,
            "crawl4ai": crawl4ai_module,
            "crawl4ai.browser_adapter": browser_adapter_module,
            "crawl4ai.async_crawler_strategy": strategy_module,
        },
    ):
        result = await _fetch_url_with_browser("https://example.com")

    assert result == "<html>crawl4ai result</html>"


@pytest.mark.asyncio
async def test_fetch_url_with_browser_falls_back_to_standard_when_patchright_fails():
    """_fetch_url_with_browser should still use standard crawl4ai if Patchright path crashes."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # First AsyncWebCrawler() call (Patchright path) raises at context enter.
    patchright_crawler = MagicMock()
    patchright_crawler.__aenter__ = AsyncMock(side_effect=RuntimeError("patchright crashed"))
    patchright_crawler.__aexit__ = AsyncMock(return_value=False)

    # Second AsyncWebCrawler() call (standard path) succeeds.
    standard_result = MagicMock()
    standard_result.success = True
    standard_result.html = "<html>standard crawl4ai result</html>"
    standard_crawler = MagicMock()
    standard_crawler.arun = AsyncMock(return_value=standard_result)
    standard_crawler.__aenter__ = AsyncMock(return_value=standard_crawler)
    standard_crawler.__aexit__ = AsyncMock(return_value=False)

    curl_cffi_module = types.ModuleType("curl_cffi")
    curl_requests_module = types.ModuleType("curl_cffi.requests")
    curl_requests_module.AsyncSession = MagicMock(return_value=mock_session)
    curl_cffi_module.requests = curl_requests_module

    crawl4ai_module = types.ModuleType("crawl4ai")
    crawl4ai_module.AsyncWebCrawler = MagicMock(side_effect=[patchright_crawler, standard_crawler])
    crawl4ai_module.BrowserConfig = MagicMock(return_value=MagicMock())

    browser_adapter_module = types.ModuleType("crawl4ai.browser_adapter")
    browser_adapter_module.UndetectedAdapter = MagicMock(return_value=MagicMock())

    strategy_module = types.ModuleType("crawl4ai.async_crawler_strategy")
    strategy_module.AsyncPlaywrightCrawlerStrategy = MagicMock(return_value=MagicMock())

    with patch.dict(
        sys.modules,
        {
            "curl_cffi": curl_cffi_module,
            "curl_cffi.requests": curl_requests_module,
            "crawl4ai": crawl4ai_module,
            "crawl4ai.browser_adapter": browser_adapter_module,
            "crawl4ai.async_crawler_strategy": strategy_module,
        },
    ):
        result = await _fetch_url_with_browser("https://example.com")

    assert result == "<html>standard crawl4ai result</html>"


@pytest.mark.asyncio
async def test_fetch_url_with_browser_falls_back_to_urllib_when_browser_tiers_fail():
    """_fetch_url_with_browser should use urllib if both browser tiers fail."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403

    mock_session = MagicMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    failing_patchright_crawler = MagicMock()
    failing_patchright_crawler.__aenter__ = AsyncMock(side_effect=RuntimeError("patchright failed"))
    failing_patchright_crawler.__aexit__ = AsyncMock(return_value=False)

    failing_standard_crawler = MagicMock()
    failing_standard_crawler.__aenter__ = AsyncMock(side_effect=RuntimeError("standard failed"))
    failing_standard_crawler.__aexit__ = AsyncMock(return_value=False)

    curl_cffi_module = types.ModuleType("curl_cffi")
    curl_requests_module = types.ModuleType("curl_cffi.requests")
    curl_requests_module.AsyncSession = MagicMock(return_value=mock_session)
    curl_cffi_module.requests = curl_requests_module

    crawl4ai_module = types.ModuleType("crawl4ai")
    crawl4ai_module.AsyncWebCrawler = MagicMock(
        side_effect=[failing_patchright_crawler, failing_standard_crawler]
    )
    crawl4ai_module.BrowserConfig = MagicMock(return_value=MagicMock())

    browser_adapter_module = types.ModuleType("crawl4ai.browser_adapter")
    browser_adapter_module.UndetectedAdapter = MagicMock(return_value=MagicMock())

    strategy_module = types.ModuleType("crawl4ai.async_crawler_strategy")
    strategy_module.AsyncPlaywrightCrawlerStrategy = MagicMock(return_value=MagicMock())

    with patch.dict(
        sys.modules,
        {
            "curl_cffi": curl_cffi_module,
            "curl_cffi.requests": curl_requests_module,
            "crawl4ai": crawl4ai_module,
            "crawl4ai.browser_adapter": browser_adapter_module,
            "crawl4ai.async_crawler_strategy": strategy_module,
        },
    ), patch("server.tools.discovery._fetch_url_urllib", new=AsyncMock(return_value="<html>urllib result</html>")):
        result = await _fetch_url_with_browser("https://example.com")

    assert result == "<html>urllib result</html>"
