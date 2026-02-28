# Mapisse 🗺️🎨

A dashboard showing famous artworks on an interactive world map. Data sourced from Wikidata.

## Setup

```bash
# Install dependencies
uv sync

# Fetch artwork data from Wikidata
uv run python scripts/refresh_data.py

# Run the app
uv run streamlit run src/mapisse/app.py
```

## Refreshing Data

To update the artwork dataset from Wikidata:

```bash
uv run python scripts/refresh_data.py
```

This fetches fresh data and saves it as a local Parquet file.
