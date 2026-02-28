"""SPARQL fetching logic for Wikidata."""

import re
import time

import polars as pl
import requests

from mapisse.config import (
    RATE_LIMIT_RETRY_SLEEP,
    RATE_LIMIT_SLEEP,
    USER_AGENT,
    WIKIDATA_SPARQL_ENDPOINT,
)

# Query settings
MAX_RETRIES = 5
REQUEST_TIMEOUT = 90
BATCH_SIZE = 200  # Results per batch query


def _execute_sparql(query: str, max_retries: int = MAX_RETRIES) -> list[dict]:
    """Execute a SPARQL query against Wikidata using POST."""
    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
    }

    retries = 0
    while retries < max_retries:
        try:
            response = requests.post(
                WIKIDATA_SPARQL_ENDPOINT,
                data={"query": query},
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429:
                print(f"Rate limited. Sleeping {RATE_LIMIT_RETRY_SLEEP}s...")
                time.sleep(RATE_LIMIT_RETRY_SLEEP)
                retries += 1
                continue

            if response.status_code in (500, 502, 503, 504):
                retries += 1
                wait_time = RATE_LIMIT_RETRY_SLEEP * retries
                print(f"Server error ({response.status_code}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

            response.raise_for_status()
            return response.json()["results"]["bindings"]

        except requests.exceptions.Timeout:
            retries += 1
            wait_time = RATE_LIMIT_RETRY_SLEEP * retries
            print(f"Timeout (attempt {retries}/{max_retries}). Retrying in {wait_time}s...")
            time.sleep(wait_time)

        except requests.exceptions.RequestException as e:
            retries += 1
            wait_time = RATE_LIMIT_RETRY_SLEEP * retries
            print(f"Request error: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise requests.exceptions.RequestException(f"Query failed after {max_retries} retries")


def _parse_coordinates(coord_str: str | None) -> tuple[float | None, float | None]:
    """Parse a Point(lon lat) string into (lat, lon) tuple."""
    if not coord_str:
        return None, None

    match = re.match(r"Point\(([-\d.]+)\s+([-\d.]+)\)", coord_str)
    if not match:
        return None, None

    try:
        lon = float(match.group(1))
        lat = float(match.group(2))
        return lat, lon
    except ValueError:
        return None, None


def _is_qid(label: str) -> bool:
    """Check if a label is an untranslated Wikidata Q-ID."""
    if not label:
        return True
    return label.startswith("Q") and label[1:].replace("-", "").isdigit()


def fetch_notable_paintings_batch(offset: int, limit: int) -> list[dict]:
    """Fetch a batch of notable paintings from famous painters.

    Uses P800 (notable work) to find paintings that are considered
    notable works of their creators, ensuring we get important paintings.

    Args:
        offset: Number of results to skip.
        limit: Maximum results to return.

    Returns:
        List of painting records.
    """
    # Query paintings that are notable works of painters
    # P800 = notable work (links person to their famous works)
    # P170 = creator
    # P195 = collection (museum)
    query = f"""
    SELECT DISTINCT ?painterLabel ?paintingLabel ?museumLabel ?countryLabel ?coords ?article WHERE {{
      # Find painters and their notable works
      ?painter wdt:P800 ?painting .
      ?painter wdt:P106 wd:Q1028181 .  # occupation: painter

      # Painting must be a painting
      ?painting wdt:P31 wd:Q3305213 .

      # In a museum collection
      ?painting wdt:P195 ?museum .
      ?museum wdt:P31 wd:Q33506 .

      # Get museum details
      OPTIONAL {{ ?museum wdt:P625 ?coords . }}
      OPTIONAL {{ ?museum wdt:P17 ?country . }}

      # Wikipedia article for painter
      OPTIONAL {{
        ?article schema:about ?painter ;
                 schema:isPartOf <https://en.wikipedia.org/> .
      }}

      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    OFFSET {offset}
    LIMIT {limit}
    """

    results = _execute_sparql(query)

    paintings = []
    for row in results:
        painter_label = row.get("painterLabel", {}).get("value", "")
        painting_label = row.get("paintingLabel", {}).get("value", "")
        museum_label = row.get("museumLabel", {}).get("value", "")
        country_label = row.get("countryLabel", {}).get("value", "Unknown")
        coords_str = row.get("coords", {}).get("value")
        wiki_url = row.get("article", {}).get("value", "")

        # Skip untranslated Q-IDs
        if _is_qid(painter_label) or _is_qid(painting_label) or _is_qid(museum_label):
            continue

        lat, lon = _parse_coordinates(coords_str)

        paintings.append({
            "painter": painter_label,
            "painting": painting_label,
            "museum": museum_label,
            "city": "Unknown",
            "country": country_label,
            "lat": lat,
            "lon": lon,
            "wikipedia_url": wiki_url,
        })

    return paintings


def fetch_museum_paintings_batch(offset: int, limit: int) -> list[dict]:
    """Fetch a batch of paintings from museum collections.

    Directly queries paintings in museums without relying on pre-built
    painter lists. Gets creator info from the painting itself.

    Args:
        offset: Number of results to skip.
        limit: Maximum results to return.

    Returns:
        List of painting records.
    """
    # Direct query for paintings in museum collections
    query = f"""
    SELECT DISTINCT ?painterLabel ?paintingLabel ?museumLabel ?countryLabel ?coords ?article WHERE {{
      # Painting by a painter
      ?painting wdt:P170 ?painter .
      ?painter wdt:P106 wd:Q1028181 .
      ?painting wdt:P31 wd:Q3305213 .

      # In a museum collection
      ?painting wdt:P195 ?museum .
      ?museum wdt:P31 wd:Q33506 .

      # Museum details
      OPTIONAL {{ ?museum wdt:P625 ?coords . }}
      OPTIONAL {{ ?museum wdt:P17 ?country . }}

      # Wikipedia
      OPTIONAL {{
        ?article schema:about ?painter ;
                 schema:isPartOf <https://en.wikipedia.org/> .
      }}

      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
    }}
    OFFSET {offset}
    LIMIT {limit}
    """

    results = _execute_sparql(query)

    paintings = []
    for row in results:
        painter_label = row.get("painterLabel", {}).get("value", "")
        painting_label = row.get("paintingLabel", {}).get("value", "")
        museum_label = row.get("museumLabel", {}).get("value", "")
        country_label = row.get("countryLabel", {}).get("value", "Unknown")
        coords_str = row.get("coords", {}).get("value")
        wiki_url = row.get("article", {}).get("value", "")

        if _is_qid(painter_label) or _is_qid(painting_label) or _is_qid(museum_label):
            continue

        lat, lon = _parse_coordinates(coords_str)

        paintings.append({
            "painter": painter_label,
            "painting": painting_label,
            "museum": museum_label,
            "city": "Unknown",
            "country": country_label,
            "lat": lat,
            "lon": lon,
            "wikipedia_url": wiki_url,
        })

    return paintings


def fetch_all_artworks(verbose: bool = False) -> pl.DataFrame:
    """Fetch paintings from museums using multiple query strategies.

    Strategy 1: Notable works (P800) - gets famous paintings
    Strategy 2: Direct museum collection query - gets comprehensive data

    Args:
        verbose: If True, print detailed debug info.

    Returns:
        Polars DataFrame with columns: painter, painting, museum, city,
        country, lat, lon, wikipedia_url.
    """
    all_rows: list[dict] = []

    # Strategy 1: Notable works of painters
    print("Phase 1: Fetching notable works of famous painters...")
    offset = 0
    batch_num = 0

    while True:
        batch_num += 1
        print(f"  [Batch {batch_num}] Fetching notable works {offset+1}-{offset+BATCH_SIZE}...", end=" ", flush=True)

        try:
            batch = fetch_notable_paintings_batch(offset, BATCH_SIZE)
            print(f"got {len(batch)} paintings")

            if not batch:
                print("  No more notable works.")
                break

            all_rows.extend(batch)
            offset += BATCH_SIZE

            # Stop after reasonable amount to avoid timeout
            if offset >= 2000:
                print(f"  Reached limit for notable works ({offset} checked)")
                break

            time.sleep(RATE_LIMIT_SLEEP)

        except Exception as e:
            print(f"error: {e}")
            break

    print(f"  Notable works: {len(all_rows)} paintings")

    # Strategy 2: Direct museum collection queries (sample from different offsets)
    print("\nPhase 2: Sampling paintings from museum collections...")

    # Sample from different parts of the dataset
    sample_offsets = [0, 5000, 10000, 20000, 30000, 50000]

    for sample_offset in sample_offsets:
        print(f"  [Sample at offset {sample_offset}] Fetching...", end=" ", flush=True)

        try:
            batch = fetch_museum_paintings_batch(sample_offset, BATCH_SIZE)
            print(f"got {len(batch)} paintings")

            if batch:
                all_rows.extend(batch)

            time.sleep(RATE_LIMIT_SLEEP)

        except Exception as e:
            print(f"error: {e}")
            continue

    print(f"\nTotal raw results: {len(all_rows)}")

    # Create DataFrame
    if not all_rows:
        return pl.DataFrame(
            schema={
                "painter": pl.Utf8,
                "painting": pl.Utf8,
                "museum": pl.Utf8,
                "city": pl.Utf8,
                "country": pl.Utf8,
                "lat": pl.Float64,
                "lon": pl.Float64,
                "wikipedia_url": pl.Utf8,
            }
        )

    df = pl.DataFrame(
        all_rows,
        schema={
            "painter": pl.Utf8,
            "painting": pl.Utf8,
            "museum": pl.Utf8,
            "city": pl.Utf8,
            "country": pl.Utf8,
            "lat": pl.Float64,
            "lon": pl.Float64,
            "wikipedia_url": pl.Utf8,
        },
    )

    # Deduplicate
    df = df.unique(subset=["painter", "painting", "museum"])

    print(f"After deduplication: {len(df)} unique paintings")
    print(f"Unique painters: {df['painter'].n_unique()}")
    print(f"Unique museums: {df['museum'].n_unique()}")

    return df
