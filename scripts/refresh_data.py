#!/usr/bin/env python3
"""CLI script to refresh artwork data from Wikidata."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mapisse.config import DEFAULT_CACHE_PATH
from mapisse.data import cache, wikidata


def main() -> None:
    """Fetch artwork data from Wikidata and save to cache."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    print("=" * 60)
    print("Mapisse Data Refresh")
    print("=" * 60)
    if verbose:
        print("(Verbose mode enabled)")
    print()

    # Fetch all artworks
    df = wikidata.fetch_all_artworks(verbose=verbose)

    # Save to cache
    print()
    print("Saving to cache...")
    cache.save(df)
    print(f"Saved to: {DEFAULT_CACHE_PATH}")

    # Print summary stats
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total paintings:  {len(df):,}")
    print(f"Unique painters:  {df['painter'].n_unique():,}")
    print(f"Unique museums:   {df['museum'].n_unique():,}")

    if len(df) == 0:
        print("No data fetched!")
        return

    # Count rows with valid coordinates
    with_coords = df.filter(df["lat"].is_not_null() & df["lon"].is_not_null())
    print(f"With coordinates: {len(with_coords):,} ({100 * len(with_coords) / len(df):.1f}%)")

    # Count rows with Wikipedia links
    if "wikipedia_url" in df.columns:
        with_wiki = df.filter(df["wikipedia_url"] != "")
        print(f"With Wikipedia:   {len(with_wiki):,} ({100 * len(with_wiki) / len(df):.1f}%)")

    print()
    print("Done!")


if __name__ == "__main__":
    main()
