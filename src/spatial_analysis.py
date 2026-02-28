"""
spatial_analysis.py

Performs spatial analysis on iNaturalist observation data across multiple
West Virginia study regions. Assigns observations to regions, calculates
buffer zones around public reference points (town centers), and generates
interactive Folium maps for each region plus a statewide overview.

Configuration is sourced from a local 'config.py' file (gitignored).
See 'config_template.py' for the expected structure.
"""

import os
import pandas as pd
from shapely.geometry import Point, box
import geopandas
import folium
from typing import List, Tuple, Dict, Any

# Import configuration from config.py
from . import config

# --- Configuration ---
PROJECTED_CRS: str = config.PROJECTED_CRS
GEOGRAPHIC_CRS: str = config.GEOGRAPHIC_CRS
BUFFER_RADII_MILES: List[int] = config.BUFFER_RADII_MILES
MAX_MAP_DISTANCE_MILES: int = config.MAX_MAP_DISTANCE_MILES
STUDY_REGIONS: dict = config.STUDY_REGIONS

MILES_TO_METERS: float = 1609.34

# --- Color scheme for regions ---
REGION_COLORS: Dict[str, str] = {
    "potomac_highlands": "#2196F3",     # Blue
    "monongahela_valley": "#4CAF50",    # Green
    "kanawha_valley": "#FF9800",        # Orange
    "greenbrier_new_river": "#9C27B0",  # Purple
    "eastern_panhandle": "#F44336",     # Red
}
DEFAULT_REGION_COLOR: str = "#607D8B"   # Gray for unassigned

# --- Pollinator-relevant iconic taxon names ---
# iNaturalist's iconic_taxon_name groups. Insecta is the primary pollinator group.
POLLINATOR_ICONIC_TAXA: set = {"Insecta"}

# --- Buffer colors (progressively lighter) ---
BUFFER_COLORS: List[str] = ["#1565C0", "#42A5F5", "#90CAF9"]


def create_geodesic_buffer(
    center_lon: float,
    center_lat: float,
    radius_miles: float,
    projected_crs: str = PROJECTED_CRS,
    geographic_crs: str = GEOGRAPHIC_CRS
):
    """
    Creates a circular geodesic buffer around a given point.

    Transforms to a projected CRS for accurate distance calculation in meters,
    then transforms the buffer polygon back to geographic coordinates.

    Args:
        center_lon: Longitude of center point.
        center_lat: Latitude of center point.
        radius_miles: Buffer radius in miles.
        projected_crs: EPSG code for projected CRS (meters).
        geographic_crs: EPSG code for geographic CRS (lat/lon).

    Returns:
        shapely.geometry.Polygon in geographic CRS.
    """
    center_gdf = geopandas.GeoSeries([Point(center_lon, center_lat)], crs=geographic_crs)
    center_proj = center_gdf.to_crs(projected_crs)
    buffer_meters = radius_miles * MILES_TO_METERS
    buffered_proj = center_proj.buffer(buffer_meters).iloc[0]
    buffered_geo = geopandas.GeoSeries([buffered_proj], crs=projected_crs).to_crs(geographic_crs).iloc[0]
    return buffered_geo


def assign_regions(gdf: geopandas.GeoDataFrame, regions: dict) -> geopandas.GeoDataFrame:
    """
    Assign each observation to its closest study region based on bounding boxes.

    An observation can fall within multiple overlapping bounding boxes.
    In that case, it is assigned to the region whose center is closest.
    Observations outside all bounding boxes are assigned 'other'.

    Args:
        gdf: GeoDataFrame of observations with point geometry.
        regions: Dictionary of study region configurations.

    Returns:
        GeoDataFrame with 'study_region' column added.
    """
    gdf = gdf.copy()
    gdf["study_region"] = "other"

    # Build bounding box polygons for each region
    region_boxes = {}
    region_centers = {}
    for key, cfg in regions.items():
        sw_lat, sw_lon = cfg["bbox_sw"]
        ne_lat, ne_lon = cfg["bbox_ne"]
        region_boxes[key] = box(sw_lon, sw_lat, ne_lon, ne_lat)
        region_centers[key] = Point(cfg["center_lon"], cfg["center_lat"])

    for idx, row in gdf.iterrows():
        pt = row.geometry
        matching_regions = [k for k, bbox_poly in region_boxes.items() if bbox_poly.contains(pt)]

        if len(matching_regions) == 1:
            gdf.at[idx, "study_region"] = matching_regions[0]
        elif len(matching_regions) > 1:
            # Assign to closest region center
            closest = min(matching_regions, key=lambda k: pt.distance(region_centers[k]))
            gdf.at[idx, "study_region"] = closest

    return gdf


def get_marker_style(row: pd.Series) -> dict:
    """
    Determine marker color and size based on taxon group.

    Pollinator-relevant taxa (insects) get a distinct style to support
    the pollinator conservation focus of the project.
    """
    iconic_taxon = row.get("taxon.iconic_taxon_name", "")

    if iconic_taxon in POLLINATOR_ICONIC_TAXA:
        return {"color": "#FFD600", "fill_color": "#FFD600", "radius": 4}  # Gold for pollinators
    elif iconic_taxon == "Plantae":
        return {"color": "#66BB6A", "fill_color": "#66BB6A", "radius": 3}  # Green for plants
    elif iconic_taxon == "Aves":
        return {"color": "#42A5F5", "fill_color": "#42A5F5", "radius": 3}  # Blue for birds
    elif iconic_taxon == "Mammalia":
        return {"color": "#EF5350", "fill_color": "#EF5350", "radius": 3}  # Red for mammals
    elif iconic_taxon == "Fungi":
        return {"color": "#AB47BC", "fill_color": "#AB47BC", "radius": 3}  # Purple for fungi
    else:
        return {"color": "#78909C", "fill_color": "#78909C", "radius": 2}  # Gray for other


def generate_statewide_map(gdf: geopandas.GeoDataFrame, regions: dict, output_path: str):
    """
    Generate a statewide overview map showing all observations colored by region.
    """
    print("\n--- Generating Statewide Overview Map ---")

    # Center on West Virginia
    m = folium.Map(location=[38.6, -80.6], zoom_start=7, tiles="OpenStreetMap")

    # Add region bounding boxes
    for key, cfg in regions.items():
        sw_lat, sw_lon = cfg["bbox_sw"]
        ne_lat, ne_lon = cfg["bbox_ne"]
        color = REGION_COLORS.get(key, DEFAULT_REGION_COLOR)

        folium.Rectangle(
            bounds=[[sw_lat, sw_lon], [ne_lat, ne_lon]],
            color=color,
            weight=2,
            fill=True,
            fill_opacity=0.05,
            popup=cfg["label"],
            name=f"Region: {cfg['label']}"
        ).add_to(m)

        # Add region label marker at center
        folium.Marker(
            location=[cfg["center_lat"], cfg["center_lon"]],
            icon=folium.DivIcon(
                html=f'<div style="font-size:10px; font-weight:bold; color:{color}; '
                     f'white-space:nowrap;">{cfg["label"]}</div>'
            )
        ).add_to(m)

    # Filter to only observations within defined study regions
    # (excludes out-of-state Sludge Hub project observations)
    gdf_in_regions = gdf[gdf["study_region"] != "other"]

    # Add observation points
    for idx, row in gdf_in_regions.iterrows():
        region = row.get("study_region", "other")
        color = REGION_COLORS.get(region, DEFAULT_REGION_COLOR)
        taxon = row["taxon.preferred_common_name"] if pd.notna(row.get("taxon.preferred_common_name")) else row.get("taxon.name", "Unknown")

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=2,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
            tooltip=f"Species: {taxon}<br>Region: {region}"
        ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save(output_path)
    print(f"  Statewide map saved to {output_path}")


def generate_region_map(
    gdf_region: geopandas.GeoDataFrame,
    region_key: str,
    region_config: dict,
    output_path: str
):
    """
    Generate an interactive map for a single study region.

    Features buffer zones around the public region center (town center)
    and observation markers colored by taxon group with pollinator highlighting.
    """
    label = region_config["label"]
    center_lat = region_config["center_lat"]
    center_lon = region_config["center_lon"]
    print(f"\n--- Generating Map: {label} ---")

    m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="OpenStreetMap")

    # Add buffer zones around the public region center
    for i, radius in enumerate(BUFFER_RADII_MILES):
        buffer_poly = create_geodesic_buffer(center_lon, center_lat, radius)
        color = BUFFER_COLORS[i % len(BUFFER_COLORS)]

        folium.GeoJson(
            buffer_poly.__geo_interface__,
            name=f"{radius} Mile Radius",
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": c,
                "weight": 1,
                "fillOpacity": 0.08
            }
        ).add_to(m)

    # Add region center marker
    folium.Marker(
        location=[center_lat, center_lon],
        icon=folium.Icon(color="darkblue", icon="info-sign"),
        tooltip=f"Region Center: {label}"
    ).add_to(m)

    # Add observation markers
    for idx, row in gdf_region.iterrows():
        style = get_marker_style(row)
        taxon = row["taxon.preferred_common_name"] if pd.notna(row.get("taxon.preferred_common_name")) else row.get("taxon.name", "Unknown")
        source = row.get("_source", "")
        source_label = "Sludge Hub Project" if source == "sludge_hub_project" else "iNaturalist Community"

        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=style["radius"],
            color=style["color"],
            fill=True,
            fill_color=style["fill_color"],
            fill_opacity=0.7,
            tooltip=f"Species: {taxon}<br>Source: {source_label}<br>Quality: {row.get('quality_grade', '')}"
        ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save(output_path)

    obs_count = len(gdf_region)
    print(f"  {label}: {obs_count} observations mapped → {output_path}")


# --- Main Execution ---
if __name__ == "__main__":
    print("=" * 60)
    print("Spatial Analysis — Multi-Region")
    print("=" * 60)

    # --- Load Data ---
    cleaned_path = os.path.join("data", "observations_cleaned.csv")
    try:
        df = pd.read_csv(cleaned_path)
        print(f"Loaded {len(df)} observations from {cleaned_path}")
    except FileNotFoundError:
        print(f"Error: {cleaned_path} not found. Run inat_data_pull.py first.")
        exit()

    # Drop rows with missing coordinates
    original_len = len(df)
    df = df.dropna(subset=["latitude", "longitude"])
    if len(df) < original_len:
        print(f"Dropped {original_len - len(df)} rows with missing coordinates.")

    # Convert to GeoDataFrame
    gdf = geopandas.GeoDataFrame(
        df,
        geometry=geopandas.points_from_xy(df.longitude, df.latitude),
        crs=GEOGRAPHIC_CRS
    )

    # --- Assign observations to study regions ---
    print("\n--- Assigning Observations to Study Regions ---")
    gdf = assign_regions(gdf, STUDY_REGIONS)

    region_counts = gdf["study_region"].value_counts()
    print("\nObservations per region:")
    for region, count in region_counts.items():
        label = STUDY_REGIONS[region]["label"] if region in STUDY_REGIONS else "Other"
        print(f"  {label}: {count}")

# --- Save analyzed data ---
    output_dir = os.path.join("data")
    os.makedirs(output_dir, exist_ok=True)

    df_output = pd.DataFrame(gdf.drop(columns="geometry"))
    output_csv = os.path.join(output_dir, "observations_analyzed.csv")
    df_output.to_csv(output_csv, index=False)
    print(f"\nAnalyzed data saved to {output_csv}")

    # --- Generate Maps ---
    map_dir = os.path.join("docs", "maps")
    os.makedirs(map_dir, exist_ok=True)

    # Statewide overview
    generate_statewide_map(
        gdf,
        STUDY_REGIONS,
        os.path.join(map_dir, "wv_statewide_overview.html")
    )

    # Per-region maps
    for region_key, region_config in STUDY_REGIONS.items():
        gdf_region = gdf[gdf["study_region"] == region_key].copy()

        if gdf_region.empty:
            print(f"\n  Skipping {region_config['label']}: no observations in region.")
            continue

        map_filename = f"map_{region_key}.html"
        generate_region_map(
            gdf_region,
            region_key,
            region_config,
            os.path.join(map_dir, map_filename)
        )

    # --- Summary ---
    print("\n" + "=" * 60)
    print("Analysis complete.")
    print(f"  Total observations analyzed: {len(gdf)}")
    print(f"  Maps generated in: {map_dir}/")
    print(f"  Analyzed data: {output_csv}")
    print("=" * 60)
