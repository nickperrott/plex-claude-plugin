# Change Request: Review-Based Content Discovery Workflow

**Date**: 2026-02-17
**Type**: New Feature - Agentic Workflow
**Priority**: MEDIUM

## Overview

Add an intelligent agentic workflow that searches movie and TV reviews from multiple sources (IMDb, Rotten Tomatoes, Metacritic, etc.), identifies highly-rated content, and creates a prioritized download queue based on ratings, popularity, and user preferences.

## User Story

> As a Plex user, I want to discover new movies and TV shows that are highly rated and popular, without manually browsing review sites, so I can automatically download quality content that I'm likely to enjoy.

## Current Workaround

Currently requires:
1. Manually browsing review aggregator sites (IMDb, RT, Metacritic)
2. Checking ratings and reviews for movies/shows
3. Deciding what's worth downloading
4. Manually searching for torrents
5. Adding to download queue

This is time-consuming and means missing out on highly-rated content you'd enjoy.

## Proposed Solution

### New High-Level Tool

```python
def discover_top_rated_content(
    content_type: str = 'both',  # 'movie', 'tv', 'both'
    min_rating: float = 7.5,
    sources: List[str] = ['imdb', 'rt', 'metacritic'],
    genres: List[str] = None,
    year_range: Tuple[int, int] = None,
    exclude_in_library: bool = True,
    max_results: int = 20,
    auto_queue: bool = False
) -> Dict:
    """
    Discover highly-rated movies and TV shows for download.

    Args:
        content_type: What to search for (movies, TV shows, or both)
        min_rating: Minimum rating threshold (0-10 scale)
        sources: Which review sites to aggregate from
        genres: Filter by genres (e.g., ['drama', 'sci-fi'])
        year_range: (start_year, end_year) - e.g., (2020, 2026)
        exclude_in_library: Skip content already in Plex
        max_results: Maximum items to return
        auto_queue: Automatically search torrents and queue downloads

    Workflow:
        1. Aggregate ratings from multiple sources
        2. Filter by criteria (rating, genre, year, etc.)
        3. Check against existing Plex library
        4. Rank by composite score
        5. Generate curated list
        6. (Optional) Auto-search torrents and queue

    Returns:
        {
            'recommendations': [
                {
                    'title': str,
                    'year': int,
                    'type': 'movie' | 'tv',
                    'ratings': {
                        'imdb': 8.5,
                        'rt_critics': 95,
                        'rt_audience': 92,
                        'metacritic': 88
                    },
                    'composite_score': 8.8,
                    'genres': ['Drama', 'Sci-Fi'],
                    'summary': str,
                    'in_library': False,
                    'tmdb_id': int,
                    'imdb_id': str,
                    'torrent_results': [...]  # if auto_queue=True
                }
            ],
            'total_found': int,
            'filtered_out': int,
            'already_in_library': int
        }
    """
```

## Implementation Details

### Step 1: Multi-Source Rating Aggregation

```python
def aggregate_ratings(title: str, year: int, content_type: str) -> Dict:
    """
    Collect ratings from multiple review sources.

    Sources:
        1. IMDb - User ratings, weighted average
        2. Rotten Tomatoes - Critics & audience scores
        3. Metacritic - Metascore
        4. TMDb - Community ratings
        5. (Optional) Trakt.tv, Letterboxd

    Normalization:
        - Convert all ratings to 0-10 scale
        - RT percentage → divide by 10
        - Metacritic → divide by 10
        - Weight by source reliability

    Returns:
        {
            'imdb': 8.5,
            'rt_critics': 9.5,  # 95% → 9.5
            'rt_audience': 9.2,
            'metacritic': 8.8,
            'tmdb': 8.3,
            'composite': 8.86  # Weighted average
        }
    """
```

### Step 2: Content Discovery Strategies

```python
class DiscoveryStrategy:
    """Different strategies for finding content."""

    @staticmethod
    def trending_now():
        """Popular content in the last 30 days."""
        # Use TMDb trending API
        # Sort by popularity + recent release

    @staticmethod
    def all_time_greats(genre=None):
        """Highest rated content of all time."""
        # IMDb Top 250
        # RT Certified Fresh
        # Metacritic Must-See

    @staticmethod
    def recent_releases(months=6):
        """Highly rated recent content."""
        # Released in last N months
        # Min rating threshold
        # Sort by rating desc

    @staticmethod
    def hidden_gems(max_popularity=5000):
        """Great content that's not mainstream."""
        # High ratings but low popularity
        # Indie films, foreign, documentaries

    @staticmethod
    def awards_season():
        """Oscar/Emmy nominees and winners."""
        # Current year nominations
        # Recent winners
        # Snubs worth watching

    @staticmethod
    def genre_deep_dive(genre, min_year=2000):
        """Best content in a specific genre."""
        # Filter by genre
        # Sort by rating
        # Diverse selection
```

### Step 3: Smart Filtering & Ranking

```python
def filter_and_rank(
    candidates: List[Dict],
    min_rating: float,
    genres: List[str],
    year_range: Tuple[int, int],
    exclude_in_library: bool,
    user_preferences: Dict = None
) -> List[Dict]:
    """
    Filter and rank content based on criteria.

    Filtering:
        1. Rating threshold (composite score >= min_rating)
        2. Genre matching (if specified)
        3. Year range (if specified)
        4. Already in Plex library (if exclude_in_library)
        5. User preferences (avoid certain actors, directors, etc.)

    Ranking Algorithm:
        composite_score = (
            0.3 * imdb_rating +
            0.2 * rt_critics +
            0.2 * rt_audience +
            0.15 * metacritic +
            0.1 * tmdb_rating +
            0.05 * popularity_boost
        )

        Additional boosts:
            + Awards/nominations
            + Recency (newer = higher)
            + Genre match bonus
            - Controversy penalty (wide rating split)

    Returns sorted list by composite_score descending.
    """
```

### Step 4: Plex Library Deduplication

```python
def check_against_library(candidates: List[Dict], plex_library) -> List[Dict]:
    """
    Check which candidates are already in Plex.

    Strategy:
        1. Match by IMDb ID (most reliable)
        2. Match by TMDb ID
        3. Fuzzy match by title + year
        4. Mark items already in library
        5. Optionally exclude them from results

    Returns:
        Updated candidates with 'in_library' boolean flag
    """
```

### Step 5: Auto-Queue Integration

```python
def auto_queue_downloads(
    recommendations: List[Dict],
    quality_preference: str = '1080p',
    max_queue: int = 5,
    require_confirmation: bool = True
) -> Dict:
    """
    Automatically search and queue top recommendations.

    Workflow:
        1. Take top N recommendations (max_queue)
        2. For each:
           a. Search torrents (multiple sources)
           b. Filter by quality preference
           c. Select best torrent (seeders, quality, completeness)
           d. Present to user (if require_confirmation)
           e. Add to Transmission queue

        3. Track queued downloads
        4. Monitor completion
        5. Auto-ingest when ready

    Returns:
        {
            'queued': [...],
            'pending_approval': [...],
            'failed': [...]
        }
    """
```

## Data Sources & APIs

### Primary Sources

1. **TMDb API** (Already configured)
   - Trending content
   - Popular movies/shows
   - Community ratings
   - Genre information

2. **OMDb API** (Requires API key)
   - IMDb ratings
   - Rotten Tomatoes scores
   - Plot summaries
   - Awards information

3. **Trakt.tv API** (Optional)
   - Trending lists
   - User recommendations
   - Watch statistics

### Web Scraping (Fallback)

4. **IMDb Top Lists**
   - Top 250 Movies
   - Top Rated TV Shows
   - Popular titles

5. **Rotten Tomatoes**
   - Certified Fresh
   - Audience favorites
   - Critics consensus

6. **Metacritic**
   - Must-see lists
   - Metascores
   - User scores

## Configuration

```yaml
videodrome:
  discover_content:
    # API Keys
    omdb_api_key: "YOUR_KEY"
    trakt_api_key: "YOUR_KEY"

    # Default preferences
    min_rating: 7.5
    preferred_genres:
      - Drama
      - Sci-Fi
      - Thriller
      - Mystery
    avoid_genres:
      - Horror
      - Romance

    # Rating source weights
    rating_weights:
      imdb: 0.30
      rt_critics: 0.20
      rt_audience: 0.20
      metacritic: 0.15
      tmdb: 0.10
      popularity: 0.05

    # Discovery strategies
    strategies:
      trending: true
      recent_releases: true
      all_time_greats: false
      hidden_gems: true
      awards_season: true

    # Filtering
    exclude_in_library: true
    year_range: [2020, 2026]  # Last 6 years
    max_results: 20

    # Auto-queue
    auto_queue: false
    auto_approve: false
    quality_preference: "1080p"
    max_concurrent_downloads: 3
```

## Use Cases

### 1. Weekly New Releases

```python
# Find highly-rated movies from the last 2 weeks
discover_top_rated_content(
    content_type='movie',
    min_rating=7.0,
    year_range=(2026, 2026),
    max_results=10,
    auto_queue=True
)
```

### 2. Binge-Worthy TV Shows

```python
# Find complete TV series with high ratings
discover_top_rated_content(
    content_type='tv',
    min_rating=8.0,
    genres=['Drama', 'Sci-Fi'],
    exclude_in_library=True,
    max_results=15
)
```

### 3. Genre Deep Dive

```python
# Explore best sci-fi content
discover_top_rated_content(
    content_type='both',
    min_rating=7.5,
    genres=['Sci-Fi'],
    year_range=(2015, 2026),
    max_results=30
)
```

### 4. Awards Season Catch-Up

```python
# Find Oscar/Emmy nominees
discover_top_rated_content(
    strategy='awards_season',
    min_rating=7.0,
    year_range=(2025, 2026),
    auto_queue=True
)
```

## User Experience

### CLI Usage

```bash
# Discover trending movies
claude-code "find trending movies to download"

# Discover top-rated sci-fi
claude-code "show me the best sci-fi shows from the last 5 years"

# Auto-queue top recommendations
claude-code "find and download top 5 movies released this month"
```

### Output Format

```
🎬 TOP RATED CONTENT RECOMMENDATIONS
====================================

1. Dune: Part Two (2024) - Movie
   ⭐ Composite: 9.2/10
   📊 IMDb: 8.9 | RT: 93% | Metacritic: 86
   🎭 Genres: Sci-Fi, Adventure, Drama
   📝 Epic continuation of Paul Atreides' journey...
   ✅ Not in library | 🔍 Torrents available

2. Severance (2022) - TV Series
   ⭐ Composite: 9.0/10
   📊 IMDb: 8.7 | RT: 97% | Metacritic: 83
   🎭 Genres: Drama, Mystery, Sci-Fi, Thriller
   📝 Employees undergo a procedure that separates...
   ❌ Already in library (Season 1-2)

3. Shogun (2024) - TV Mini-Series
   ⭐ Composite: 8.9/10
   📊 IMDb: 8.8 | RT: 99% | Metacritic: 90
   🎭 Genres: Drama, History, War
   📝 An English pilot arrives in Japan in 1600...
   ✅ Not in library | 🔍 Torrents available

...

📊 SUMMARY
- Found: 47 titles matching criteria
- Filtered out: 12 (below rating threshold)
- Already in library: 15
- Recommendations: 20

💾 AUTO-QUEUE
- Queued for download: 3 titles
- Pending approval: 2 titles
- Download size: ~45 GB
```

## Testing Scenarios

1. **Rating Aggregation**: Verify accurate rating collection from all sources
2. **Filtering**: Test genre, rating, year filters work correctly
3. **Deduplication**: Ensure items in library are detected properly
4. **Ranking**: Verify composite scores rank content appropriately
5. **API Failures**: Graceful degradation when sources unavailable
6. **Torrent Integration**: Successful search and queue for recommendations
7. **Large Result Sets**: Performance with 100+ candidates

## Success Metrics

- Can aggregate ratings from 3+ sources reliably
- 90%+ accuracy in Plex library matching
- Composite score correlates with user satisfaction
- Recommendations are diverse (not just blockbusters)
- < 5 seconds to generate 20 recommendations
- 80%+ of queued downloads succeed

## Future Enhancements

1. **Machine Learning**
   - Learn user preferences from watch history
   - Personalized recommendations
   - Predict what user will enjoy

2. **Social Integration**
   - Friends' recommendations
   - Shared watchlists
   - Group voting

3. **Smart Scheduling**
   - Download during off-peak hours
   - Prioritize by upcoming free time
   - Seasonal recommendations

4. **Multi-Language Support**
   - Foreign films with high ratings
   - Subtitle availability checking
   - Language preference filtering

5. **Advanced Filtering**
   - Avoid certain actors/directors
   - Runtime preferences
   - Content warnings (violence, etc.)

## Implementation Plan

### Phase 1: Rating Aggregation (FOUNDATION)
- [ ] Implement OMDb API integration (IMDb + RT data)
- [ ] Add TMDb rating collection (already have API)
- [ ] Build rating normalization (0-10 scale)
- [ ] Create composite scoring algorithm
- [ ] Test with sample titles

### Phase 2: Discovery Strategies (CORE)
- [ ] Implement trending_now() strategy
- [ ] Implement recent_releases() strategy
- [ ] Implement all_time_greats() strategy
- [ ] Add genre filtering
- [ ] Add year range filtering
- [ ] Build ranking algorithm

### Phase 3: Plex Integration (DEDUPLICATION)
- [ ] Implement library checking by IMDb ID
- [ ] Add TMDb ID matching
- [ ] Add fuzzy title+year matching
- [ ] Test deduplication accuracy
- [ ] Add exclude_in_library option

### Phase 4: Reporting & UX (OUTPUT)
- [ ] Design recommendation output format
- [ ] Add summary statistics
- [ ] Implement formatted console output
- [ ] Generate markdown reports
- [ ] Add export options (JSON, CSV)

### Phase 5: Auto-Queue Integration (AUTOMATION)
- [ ] Connect to torrent search (from find_new_seasons workflow)
- [ ] Implement auto-queue logic
- [ ] Add user confirmation prompts
- [ ] Track queued downloads
- [ ] Monitor and report status

### Phase 6: Advanced Features (POLISH)
- [ ] Add Trakt.tv integration
- [ ] Implement awards_season strategy
- [ ] Add hidden_gems discovery
- [ ] Build user preference learning
- [ ] Add scheduling/automation

## Dependencies

### Required
- ✅ TMDb API access (already configured)
- ✅ Plex API access (via plugin)
- ✅ Transmission integration (via plugin)
- 🔧 OMDb API key (for IMDb/RT data)

### Optional
- Trakt.tv API key (enhanced recommendations)
- Web scraping capabilities (fallback for ratings)
- Machine learning libraries (preference learning)

## Related Workflows

- **Find New Seasons**: Discovers missing content for existing shows
- **Review-Based Discovery**: Discovers new content based on ratings ← THIS
- **Quality Upgrade**: Finds better quality versions of existing content
- **Watchlist Sync**: Syncs with IMDb/Letterboxd watchlists

## Notes

This workflow complements the "Find New Seasons" workflow:
- **Find New Seasons**: Reactive - fills gaps in existing library
- **Review-Based Discovery**: Proactive - finds new content to add

Together they provide comprehensive library management:
1. Keep existing shows up to date (new seasons)
2. Discover new highly-rated content (discovery)
3. Maintain quality and completeness

## API Cost Considerations

- **TMDb**: Free tier (40 requests/10 sec) - sufficient
- **OMDb**: Free tier (1000 requests/day) - may need paid tier for heavy use
- **Trakt.tv**: Free tier - sufficient for most users

Caching strategies:
- Cache ratings for 7 days (don't change frequently)
- Cache trending lists for 24 hours
- Cache library matches indefinitely (until library changes)
