"""Streamlit entry point for Mapisse."""

import streamlit as st
from streamlit_folium import st_folium
import polars as pl

from mapisse.data import cache
from mapisse.map import renderer


st.set_page_config(
    page_title="Mapisse - Famous Artworks Map",
    page_icon="🎨",
    layout="wide",
)


@st.cache_data
def load_data() -> pl.DataFrame:
    """Load artwork data from cache."""
    return cache.load()


def main() -> None:
    """Main Streamlit application."""
    st.title("Mapisse")
    st.caption("Famous Artworks on a World Map")

    # Load data
    try:
        df = load_data()
    except FileNotFoundError as e:
        st.error("No data found. Run: `uv run python scripts/refresh_data.py`")
        st.stop()

    # Sidebar filters
    st.sidebar.header("Filters")

    # Artist filter
    painters = sorted(df["painter"].unique().to_list())
    selected_painter = st.sidebar.selectbox(
        "Select Artist",
        options=["All Artists"] + painters,
        index=0,
    )

    # Museum filter
    museums = sorted(df["museum"].unique().to_list())
    selected_museum = st.sidebar.selectbox(
        "Select Museum",
        options=["All Museums"] + museums,
        index=0,
    )

    # Normalize selections
    painter_filter = None if selected_painter == "All Artists" else selected_painter
    museum_filter = None if selected_museum == "All Museums" else selected_museum

    # Render map
    if painter_filter is None and museum_filter is None:
        # Default view: all museums clustered
        m = renderer.render_all_museums(df)
        st.info(f"Showing all {df['museum'].n_unique()} museums with artworks from {len(painters)} painters")
    else:
        # Filtered view
        m, total, shown = renderer.render_filtered_museums(
            df,
            painter=painter_filter,
            museum=museum_filter,
        )

        if total == 0:
            st.warning("No museums found matching your filters.")
        elif total > shown:
            st.info(f"Showing top {shown} of {total} museums. Select a specific museum to explore more.")
        else:
            st.info(f"Showing {shown} museum(s)")

    # Display map (returned_objects=[] prevents reruns from map interactions)
    st_folium(m, height=500, returned_objects=[])

    # Data table
    st.subheader("Artworks")

    # Filter data for table
    table_df = df.clone()
    if painter_filter:
        table_df = table_df.filter(pl.col("painter") == painter_filter)
    if museum_filter:
        table_df = table_df.filter(pl.col("museum") == museum_filter)

    # Select and order columns for display
    display_df = table_df.select(["painter", "painting", "museum", "country"])

    st.dataframe(display_df, hide_index=True)

    # Stats in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("Dataset Stats")
    st.sidebar.metric("Paintings", len(df))
    st.sidebar.metric("Painters", df["painter"].n_unique())
    st.sidebar.metric("Museums", df["museum"].n_unique())


if __name__ == "__main__":
    main()
