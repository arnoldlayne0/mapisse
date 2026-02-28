"""Parquet cache read/write functionality."""

from pathlib import Path

import polars as pl

from mapisse.config import DEFAULT_CACHE_PATH


def save(df: pl.DataFrame, path: Path | None = None) -> None:
    """Save a Polars DataFrame to Parquet.

    Args:
        df: The DataFrame to save.
        path: Path to save to. Defaults to data/artworks.parquet.
    """
    if path is None:
        path = DEFAULT_CACHE_PATH

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    df.write_parquet(path)


def load(path: Path | None = None) -> pl.DataFrame:
    """Load a Polars DataFrame from Parquet.

    Args:
        path: Path to load from. Defaults to data/artworks.parquet.

    Returns:
        The loaded DataFrame.

    Raises:
        FileNotFoundError: If the cache file does not exist.
    """
    if path is None:
        path = DEFAULT_CACHE_PATH

    if not path.exists():
        raise FileNotFoundError(
            f"Cache file not found: {path}\n"
            "Run: uv run python scripts/refresh_data.py"
        )

    return pl.read_parquet(path)
