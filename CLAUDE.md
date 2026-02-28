# Mapisse — Famous Artworks on a World Map

## Project Overview
Mapisse is a Streamlit dashboard that displays paintings by the top 250 most famous painters on an interactive world map. Each marker represents a museum, and users can explore which paintings are held where. Data comes from Wikidata via SPARQL queries and is cached locally as a Parquet file.

## Tech Stack
- **Language**: Python 3.12+ (no other languages — the developer only writes Python)
- **Package manager**: `uv` (use `uv add` to add dependencies, never `pip install`)
- **Frontend/Dashboard**: Streamlit
- **Map**: Folium with MarkerCluster (via `streamlit-folium`)
- **Data**: Polars + Parquet for local caching
- **SPARQL client**: `requests` library (direct HTTP to Wikidata SPARQL endpoint)
- **Deployment target**: Streamlit Community Cloud initially, GCP Cloud Run later

## Project Structure
```
mapisse/
├── CLAUDE.md                          # This file
├── pyproject.toml
├── uv.lock
├── README.md
├── .gitignore
├── .python-version
├── src/
│   └── mapisse/
│       ├── __init__.py
│       ├── app.py                     # Streamlit entry point
│       ├── data/
│       │   ├── __init__.py
│       │   ├── wikidata.py            # SPARQL fetching logic
│       │   └── cache.py               # Parquet read/write
│       ├── map/
│       │   ├── __init__.py
│       │   └── renderer.py            # Folium map construction
│       └── config.py                  # Constants and defaults
├── data/
│   └── artworks.parquet               # Cached dataset (gitignored)
├── scripts/
│   └── refresh_data.py                # CLI to re-fetch from Wikidata
└── tests/
    └── __init__.py
```

## Data Model

The cached Parquet file has these columns:

| Column     | Type   | Description                          | Example                    |
|------------|--------|--------------------------------------|----------------------------|
| `painter`  | str    | Artist name                          | "Claude Monet"             |
| `painting` | str    | Painting title                       | "Water Lilies"             |
| `museum`   | str    | Museum name                          | "Musée de l'Orangerie"     |
| `city`     | str    | City (may be "Unknown")              | "Paris"                    |
| `country`  | str    | Country (may be "Unknown")           | "France"                   |
| `lat`      | float  | Latitude of museum (nullable)        | 48.8606                    |
| `lon`      | float  | Longitude of museum (nullable)       | 2.3225                     |

Rows without valid coordinates (lat/lon) should be kept in the dataset but excluded from map rendering. They can appear in tables/lists.

## Data Pipeline

### How data is fetched (`wikidata.py`)
The fetch is a two-step process matching the existing SPARQL approach:

1. **Query 1**: Fetch top 250 painters ranked by Wikidata sitelink count (a proxy for fame).
2. **Query 2**: For each painter, fetch their paintings that are held in a museum, along with museum coordinates, city, and country. One HTTP request per painter.

Important implementation details:
- Use `requests.get()` against `https://query.wikidata.org/sparql` with JSON accept headers.
- Set a descriptive `User-Agent` header (Wikidata requires this).
- Handle HTTP 429 (rate limit) by sleeping 30 seconds and retrying.
- Sleep 2 seconds between per-artist requests to stay under rate limits.
- Parse `Point(lon lat)` coordinate strings into separate float columns.
- Filter out rows where painting or museum labels start with "Q" (untranslated Wikidata IDs).
- Print progress to stdout (`[1/250] Fetching works by: Claude Monet`).
- The full fetch takes ~10 minutes. This is expected for MVP.

### How data is cached (`cache.py`)
- `save(df, path)`: Write Polars DataFrame to Parquet (`df.write_parquet()`).
- `load(path)`: Read Parquet into Polars DataFrame (`pl.read_parquet()`). Raise a clear error if file doesn't exist.
- Default cache path: `data/artworks.parquet` (relative to project root).

### Refresh script (`scripts/refresh_data.py`)
- Calls wikidata fetch, saves result to Parquet cache.
- Prints summary stats on completion (number of painters, paintings, museums).

## App Features & UI

### Layout
The Streamlit app has:
- A **sidebar** with filters/controls
- A **main area** with the Folium map and optional data displays below it

### Primary Feature: Artist Explorer
1. Sidebar contains a **searchable dropdown** (selectbox with search) listing all 250 painters, sorted alphabetically.
2. When a painter is selected, the map highlights all museums holding their works.
3. **If the artist has paintings in ≤10 museums**: show all museums as markers.
4. **If the artist has paintings in >10 museums**: show the top 10 museums (by number of paintings held) as markers. Display a Streamlit info banner: "Showing top 10 of {N} museums. {Artist} has works in {remaining} more museums."
5. Each marker popup shows:
   - Museum name
   - City, Country
   - List of paintings by that artist held there
6. A default state (no artist selected) shows all museums with marker clustering enabled.

### Secondary Feature: Museum/Painting Browser
1. Below the map, show a **data table** filtered to the current selection.
2. Add a second sidebar section with:
   - A museum filter (searchable dropdown, populated from data)
   - When a museum is selected, the map centers on it and the table shows all paintings held there (across all artists).
3. Artist and museum filters can be independent or combined — if both are set, show the intersection.

### Map Rendering (`renderer.py`)
- Use Folium with `MarkerCluster` for the default (all museums) view.
- When filtering to a specific artist, disable clustering and show individual markers with distinct styling.
- Map starts centered on Europe (lat=48, lon=10, zoom=3) since that's where museum density is highest.
- Use a clean tile set (e.g., CartoDB positron) for a modern look.
- Popup HTML should be minimal but readable — no complex styling needed for MVP.

## Coding Standards

### General
- Write simple, readable Python. Favor clarity over cleverness.
- Use type hints on all function signatures.
- Use docstrings (Google style) for all public functions.
- Keep functions short — under ~30 lines. Split if longer.
- No classes unless clearly justified. Prefer functions + Polars DataFrames.
- Use Polars expressions and method chaining for data manipulation. Do not convert to Pandas unless required by a library (e.g., Streamlit's `st.dataframe()` accepts Polars natively, but some older Streamlit widgets may need `.to_pandas()`).
- Use f-strings for string formatting.

### Streamlit-specific
- Use `@st.cache_data` for loading the Parquet file. Note: Polars DataFrames are not natively hashable by Streamlit, so return the result of `pl.read_parquet()` inside the cached function — Streamlit will handle serialization.
- Use `st.sidebar` for all controls.
- Never call `st.rerun()` unless absolutely necessary.

### Error Handling
- If the Parquet cache is missing, show `st.error("No data found. Run: uv run python scripts/refresh_data.py")` and stop.
- Wrap all Wikidata HTTP calls in try/except. Log errors, continue to next artist on failure.
- Handle edge cases: artists with 0 paintings, museums with no coordinates, empty filter results.

### Dependencies
- Add with `uv add <package>`. Never pip.
- Expected dependencies:
  - `streamlit`
  - `streamlit-folium`
  - `folium`
  - `polars`
  - `requests`

### Git Practices
- Small, focused commits.
- Format: `type: description` (e.g., `feat: add artist filter`, `fix: handle missing coords`)
- Never commit `data/*.parquet`.

## How to Run

```bash
# Setup
uv sync

# Fetch data (~10 min)
uv run python scripts/refresh_data.py

# Run app
uv run streamlit run src/mapisse/app.py
```

## Future Improvements (DO NOT implement unless asked)
- Batch SPARQL queries using VALUES clauses to reduce from 250 requests to ~5
- Artwork thumbnail images from Wikidata/Commons
- Time slider to filter by painting year/century
- Painting detail pages with Wikipedia links
- GCP Cloud Run deployment with scheduled data refresh
- Artist comparison mode (select 2+ artists, see overlap)

## What NOT to Do
- Do NOT use JavaScript, TypeScript, or any non-Python code.
- Do NOT add a database. Parquet files are the data store.
- Do NOT over-engineer. This is an MVP.
- Do NOT add authentication or user accounts.
- Do NOT use pip, poetry, or conda. Only uv.
- Do NOT query Wikidata on every page load. Always read from Parquet cache.
- Do NOT add features not listed above. Ask first.
- Do NOT make the UI pretty. Functional is fine. No custom CSS.
