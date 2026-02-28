"""Configuration constants and defaults for Mapisse."""

from pathlib import Path

# Project root (two levels up from this file)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Data paths
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_CACHE_PATH = DATA_DIR / "artworks.parquet"

# Wikidata SPARQL endpoint
WIKIDATA_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

# HTTP settings
USER_AGENT = "Mapisse/1.0 (https://github.com/mapisse; contact@example.com) Python/requests"
REQUEST_TIMEOUT = 60  # seconds

# Rate limiting
RATE_LIMIT_SLEEP = 2  # seconds between requests
RATE_LIMIT_RETRY_SLEEP = 30  # seconds to wait on HTTP 429

# Query parameters
TOP_PAINTERS_COUNT = 250

# Map defaults
DEFAULT_MAP_CENTER = (48, 10)  # Europe
DEFAULT_MAP_ZOOM = 3
