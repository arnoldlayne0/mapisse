"""Folium map construction for Mapisse."""

import html

import folium
from folium.plugins import MarkerCluster
import polars as pl

from mapisse.config import DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM


def create_base_map() -> folium.Map:
    """Create a base Folium map centered on Europe.

    Returns:
        A Folium Map object with CartoDB positron tiles.
    """
    return folium.Map(
        location=DEFAULT_MAP_CENTER,
        zoom_start=DEFAULT_MAP_ZOOM,
        tiles="CartoDB positron",
    )


def _build_popup_html(
    museum: str,
    country: str,
    paintings_by_painter: dict[str, list[tuple[str, str]]],
) -> str:
    """Build HTML content for a marker popup.

    Args:
        museum: Museum name.
        country: Country name.
        paintings_by_painter: Dict mapping painter name to list of
            (painting_title, wikipedia_url) tuples.

    Returns:
        HTML string for the popup.
    """
    museum_escaped = html.escape(museum)
    country_escaped = html.escape(country)

    content = f"<b>{museum_escaped}</b><br><i>{country_escaped}</i><br><br>"

    total_shown = 0
    total_paintings = sum(len(p) for p in paintings_by_painter.values())

    for painter, paintings in sorted(paintings_by_painter.items()):
        painter_escaped = html.escape(painter)

        # Get Wikipedia URL (use first non-empty one)
        wiki_url = next((url for _, url in paintings if url), "")

        if wiki_url:
            content += f'<b><a href="{wiki_url}" target="_blank">{painter_escaped}</a></b>'
        else:
            content += f"<b>{painter_escaped}</b>"

        content += "<ul style='margin: 2px 0 8px 0; padding-left: 16px;'>"

        for painting_title, _ in paintings[:5]:
            painting_escaped = html.escape(painting_title)
            content += f"<li>{painting_escaped}</li>"
            total_shown += 1

        if len(paintings) > 5:
            content += f"<li><i>...+{len(paintings) - 5} more</i></li>"

        content += "</ul>"

        if total_shown >= 15:
            remaining_painters = len(paintings_by_painter) - list(paintings_by_painter.keys()).index(painter) - 1
            if remaining_painters > 0:
                content += f"<p><i>...and {remaining_painters} more artists</i></p>"
            break

    return content


def render_all_museums(df: pl.DataFrame) -> folium.Map:
    """Render all museums on a clustered map.

    Args:
        df: DataFrame with museum data.

    Returns:
        Folium Map with MarkerCluster.
    """
    m = create_base_map()

    # Filter to rows with valid coordinates
    df_valid = df.filter(pl.col("lat").is_not_null() & pl.col("lon").is_not_null())

    if df_valid.is_empty():
        return m

    # Check if wikipedia_url column exists
    has_wiki = "wikipedia_url" in df_valid.columns

    # Group paintings by museum, then by painter
    museum_groups = df_valid.group_by(["museum", "country", "lat", "lon"]).agg(
        pl.col("painter"),
        pl.col("painting"),
        pl.col("wikipedia_url") if has_wiki else pl.lit("").alias("wikipedia_url"),
    )

    marker_cluster = MarkerCluster().add_to(m)

    for row in museum_groups.iter_rows(named=True):
        # Build paintings_by_painter dict
        paintings_by_painter: dict[str, list[tuple[str, str]]] = {}
        painters = row["painter"]
        paintings = row["painting"]
        wiki_urls = row["wikipedia_url"] if has_wiki else [""] * len(painters)

        for painter, painting, wiki_url in zip(painters, paintings, wiki_urls):
            if painter not in paintings_by_painter:
                paintings_by_painter[painter] = []
            paintings_by_painter[painter].append((painting, wiki_url or ""))

        popup_html = _build_popup_html(
            row["museum"],
            row["country"],
            paintings_by_painter,
        )
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=folium.Popup(popup_html, max_width=350),
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(marker_cluster)

    return m


def render_filtered_museums(
    df: pl.DataFrame,
    painter: str | None = None,
    museum: str | None = None,
) -> tuple[folium.Map, int, int]:
    """Render filtered museums on a map without clustering.

    Args:
        df: DataFrame with artwork data.
        painter: Optional painter name to filter by.
        museum: Optional museum name to filter by.

    Returns:
        Tuple of (Folium Map, total museums count, shown museums count).
    """
    m = create_base_map()

    # Apply filters
    filtered = df.clone()
    if painter:
        filtered = filtered.filter(pl.col("painter") == painter)
    if museum:
        filtered = filtered.filter(pl.col("museum") == museum)

    # Filter to rows with valid coordinates
    filtered = filtered.filter(
        pl.col("lat").is_not_null() & pl.col("lon").is_not_null()
    )

    if filtered.is_empty():
        return m, 0, 0

    # Check if wikipedia_url column exists
    has_wiki = "wikipedia_url" in filtered.columns

    # Group by museum
    museum_data = (
        filtered
        .group_by(["museum", "country", "lat", "lon"])
        .agg([
            pl.col("painter"),
            pl.col("painting"),
            pl.col("wikipedia_url") if has_wiki else pl.lit("").alias("wikipedia_url"),
            pl.len().alias("count"),
        ])
        .sort("count", descending=True)
    )

    total_museums = len(museum_data)

    # Limit to top 10 if more than 10 museums
    if total_museums > 10:
        museum_data = museum_data.head(10)

    shown_museums = len(museum_data)

    # Center map on first museum if filtering
    if shown_museums > 0:
        first = museum_data.row(0, named=True)
        m.location = [first["lat"], first["lon"]]
        m.zoom_start = 4 if shown_museums > 1 else 10

    for row in museum_data.iter_rows(named=True):
        # Build paintings_by_painter dict
        paintings_by_painter: dict[str, list[tuple[str, str]]] = {}
        painters = row["painter"]
        paintings = row["painting"]
        wiki_urls = row["wikipedia_url"] if has_wiki else [""] * len(painters)

        for p_painter, p_painting, wiki_url in zip(painters, paintings, wiki_urls):
            if p_painter not in paintings_by_painter:
                paintings_by_painter[p_painter] = []
            paintings_by_painter[p_painter].append((p_painting, wiki_url or ""))

        popup_html = _build_popup_html(
            row["museum"],
            row["country"],
            paintings_by_painter,
        )
        folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=folium.Popup(popup_html, max_width=350),
            icon=folium.Icon(color="red", icon="star"),
        ).add_to(m)

    return m, total_museums, shown_museums
