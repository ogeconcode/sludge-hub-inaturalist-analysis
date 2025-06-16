"""
This script performs spatial analysis on iNaturalist observation data
around a specified property and apiary location. It calculates buffer zones,
identifies observations within these zones, and generates interactive
Folium maps to visualize the results.

The primary goal is to provide a more granular spatial analysis
than typically available through iNaturalist's built-in project features,
making the data more actionable for project co-organizers.
"""

import os
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely import wkt # Import wkt for parsing Well-Known Text
import geopandas
import folium
import json
import sqlite3 # Import for database interaction
from typing import List, Tuple, Any

# Import configuration from config.py
from . import config

# --- Configuration for Spatial Analysis and Buffering ---
# These are now imported from config.py
PROJECTED_CRS: str = config.PROJECTED_CRS # WGS 84 / UTM zone 17N (meters) - Ideal for accurate distance calculations in this region of West Virginia
GEOGRAPHIC_CRS: str = config.GEOGRAPHIC_CRS # WGS 84 (Latitude/Longitude) - Standard for GPS coordinates

BUFFER_RADII_MILES: List[int] = config.BUFFER_RADII_MILES # Radii for circular buffer zones around points of interest
MILES_TO_METERS: float = 1609.34 # Conversion factor for miles to meters

# --- Map Visualization Configuration ---
# Maximum distance (in miles) an observation can be from the property center
# to be included on the interactive Folium maps.
MAX_MAP_DISTANCE_MILES: int = config.MAX_MAP_DISTANCE_MILES # Adjust this value as needed

# --- Helper Function for DMS to Decimal Degrees (Kept for general utility) ---
def dms_to_dd(degrees: int, minutes: int, seconds: int, direction: str) -> float:
    """
    Converts Degrees, Minutes, Seconds (DMS) to Decimal Degrees (DD).

    This is particularly useful for converting coordinates often found in older maps
    or specific survey data into a standard decimal format usable by GIS libraries.

    Args:
        degrees (int): The degree component of the coordinate.
        minutes (int): The minute component of the coordinate.
        seconds (int): The second component of the coordinate.
        direction (str): The cardinal direction ('N', 'S', 'E', 'W').
                         'S' and 'W' directions will result in negative decimal degrees.

    Returns:
        float: The coordinate converted to decimal degrees.
    """
    dd = float(degrees) + float(minutes)/60 + float(seconds)/(60*60)
    if direction.upper() in ['S', 'W']:
        dd *= -1
    return dd

# --- Function to Create a Geodesic Buffer ---
def create_geodesic_buffer(
    center_point_lon_lat: Tuple[float, float],
    radius_miles: float,
    target_crs: str,
    source_crs: str = GEOGRAPHIC_CRS
) -> Polygon:
    """
    Creates a circular geodesic buffer around a given point.

    This function handles Coordinate Reference System (CRS) transformations to ensure
    accurate buffer distances are calculated in a projected CRS (meters), and then
    transforms the resulting buffered polygon back to a geographic CRS (latitude/longitude).
    This is critical for accurate spatial analysis over large areas.

    Args:
        center_point_lon_lat (tuple): A tuple containing the (longitude, latitude)
                                       of the center point for the buffer.
        radius_miles (float): The radius of the buffer to create, in miles.
        target_crs (str): The EPSG code (e.g., "EPSG:32617") for the projected CRS
                          into which the point will be transformed for accurate buffering
                          (distances measured in meters).
        source_crs (str, optional): The EPSG code for the input geographic CRS of the
                                    center_point_lon_lat. Defaults to GEOGRAPHIC_CRS (EPSG:4326).

    Returns:
        shapely.geometry.Polygon: The buffered circular polygon, returned in the
                                  original geographic CRS (EPSG:4326).
    """
    center_gdf = geopandas.GeoSeries([Point(center_point_lon_lat)], crs=source_crs)
    center_gdf_proj = center_gdf.to_crs(target_crs)
    buffer_meters = radius_miles * MILES_TO_METERS
    buffered_polygon_proj = center_gdf_proj.buffer(buffer_meters).iloc[0]
    buffered_polygon_geo = geopandas.GeoSeries([buffered_polygon_proj], crs=target_crs).to_crs(source_crs).iloc[0]
    return buffered_polygon_geo


# --- Property Coordinates ---
# Property polygon now loaded directly from config.py using WKT
property_polygon: Polygon = wkt.loads(config.PROPERTY_COORDINATES_WKT_POLYGON)
print("Property polygon created successfully!")

property_center: Point = property_polygon.centroid
print(f"Property Center (Lon, Lat): ({property_center.x}, {property_center.y})")


# --- Define Apiary Coordinates ---
# Apiary location now loaded directly from config.py (assumed to be in Decimal Degrees)
apiary_lon: float = config.APIARY_LON_DD
apiary_lat: float = config.APIARY_LAT_DD
apiary_center: Point = Point(apiary_lon, apiary_lat)
print(f"Apiary Center (Lon, Lat): ({apiary_center.x}, {apiary_center.y})")


# --- Load Data ---
# Expects 'sludge_hub_cleaned_data.csv' to be in the 'data' subdirectory.
# This file is generated by the pre-ceding script "inat_data_pull.py"
cleaned_file_path: str = os.path.join('data', 'sludge_hub_cleaned_data.csv')
try:
    df_cleaned: pd.DataFrame = pd.read_csv(cleaned_file_path)
    print(f"Loaded {len(df_cleaned)} observations from {cleaned_file_path}")
except FileNotFoundError:
    print(f"Error: {cleaned_file_path} not found. Please ensure the 'inat_data_pull.py' script has been run or the file exists in the correct 'data' directory.")
    exit()

# Handle potential missing coordinate data in the loaded observations.
original_len: int = len(df_cleaned)
df_cleaned.dropna(subset=['latitude', 'longitude'], inplace=True)
if len(df_cleaned) < original_len:
    print(f"Removed {original_len - len(df_cleaned)} rows with missing latitude/longitude.")

# Convert DataFrame to GeoDataFrame for spatial operations.
gdf_observations = geopandas.GeoDataFrame(
    df_cleaned, geometry=geopandas.points_from_xy(df_cleaned.longitude, df_cleaned.latitude), crs=GEOGRAPHIC_CRS
)


# --- Perform Spatial Analysis for Property Boundary ---
# Determine which observations fall within the defined property polygon.
gdf_observations['within_property'] = gdf_observations.geometry.apply(
    lambda obs_point: property_polygon.contains(obs_point)
)
num_within_property: int = gdf_observations['within_property'].sum()
print(f"Number of observations within your property: {int(num_within_property)}")
count_outside_property: int = len(gdf_observations) - num_within_property
print(f"Total observations outside your property: {int(count_outside_property)}")
print("\nSample observations within your property:")
print(gdf_observations[gdf_observations['within_property']].head())


# --- Create and Test Circular Buffers & Store for Mapping ---
print("\n--- Analyzing Circular Buffer Zones ---")
property_center_buffers: List[Tuple[int, Polygon]] = []
apiary_center_buffers: List[Tuple[int, Polygon]] = []

# Buffers around Property Center
print("\n  - Buffers around Property Center:")
for radius_miles in BUFFER_RADII_MILES:
    buffer_polygon: Polygon = create_geodesic_buffer(
        (property_center.x, property_center.y), radius_miles, PROJECTED_CRS
    )
    property_center_buffers.append((radius_miles, buffer_polygon)) # Store for mapping
    col_name: str = f'within_{radius_miles}mile_property_center'
    gdf_observations[col_name] = gdf_observations.geometry.apply(
        lambda obs_point: buffer_polygon.contains(obs_point)
    )
    num_within_buffer: int = gdf_observations[col_name].sum()
    print(f"    Observations within {radius_miles} mile(s) of Property Center: {int(num_within_buffer)}")

# Buffers around Apiary Center
print("\n  - Buffers around Apiary Center:")
for radius_miles in BUFFER_RADII_MILES:
    buffer_polygon: Polygon = create_geodesic_buffer(
        (apiary_center.x, apiary_center.y), radius_miles, PROJECTED_CRS
    )
    apiary_center_buffers.append((radius_miles, buffer_polygon)) # Store for mapping
    col_name: str = f'within_{radius_miles}mile_apiary_center'
    gdf_observations[col_name] = gdf_observations.geometry.apply(
        lambda obs_point: buffer_polygon.contains(obs_point)
    )
    num_within_buffer: int = gdf_observations[col_name].sum()
    print(f"    Observations within {radius_miles} mile(s) of Apiary Center: {int(num_within_buffer)}")


# --- Save Data to CSV and SQLite Database ---
# Convert GeoDataFrame back to a regular DataFrame for saving, dropping the geometry column.
df_analyzed_final: pd.DataFrame = pd.DataFrame(gdf_observations.drop(columns='geometry'))

# Save to CSV
output_csv_file_path: str = os.path.join('data', 'sludge_hub_analyzed_data_with_buffers.csv')
df_analyzed_final.to_csv(output_csv_file_path, index=False)
print(f"\nAnalyzed data with buffer zones saved to {output_csv_file_path}")

# Save to SQLite Database for a queryable data source.
output_db_file_path: str = os.path.join('data', 'sludge_hub_observations.db')
table_name: str = 'inaturalist_observations_analyzed'

try:
    with sqlite3.connect(output_db_file_path) as conn:
        # 'if_exists="replace"' will overwrite the table if it already exists,
        # ensuring the database always reflects the latest analysis.
        df_analyzed_final.to_sql(table_name, conn, if_exists='replace', index=False)
    print(f"Analyzed data also saved to SQLite database: {output_db_file_path} in table '{table_name}'")
except Exception as e:
    print(f"Error saving data to SQLite database: {e}")


# --- Prepare Observations for Mapping by Distance ---
# To manage map performance with growing datasets, observations are filtered
# to a maximum distance from the property's center for visualization.
print("\n--- Preparing Observations for Map Visualization ---")

# Convert property center to the projected CRS for accurate distance calculation
property_center_proj = geopandas.GeoSeries([property_center], crs=GEOGRAPHIC_CRS).to_crs(PROJECTED_CRS).iloc[0]

# Calculate distance of each observation from the property center in the projected CRS (meters)
# Note: gdf_observations is already a GeoDataFrame with 'geometry' in GEOGRAPHIC_CRS
# For distance calculation, we need to temporarily convert observations to the projected CRS
gdf_observations_proj = gdf_observations.to_crs(PROJECTED_CRS)
gdf_observations['distance_from_property_center_meters'] = gdf_observations_proj.geometry.apply(
    lambda obs_point_proj: obs_point_proj.distance(property_center_proj)
)
gdf_observations['distance_from_property_center_miles'] = \
    gdf_observations['distance_from_property_center_meters'] / MILES_TO_METERS

# Filter observations based on the MAX_MAP_DISTANCE_MILES
gdf_observations_for_map = gdf_observations[
    gdf_observations['distance_from_property_center_miles'] <= MAX_MAP_DISTANCE_MILES
].copy() # Use .copy() to avoid SettingWithCopyWarning

print(f"Filtered {len(gdf_observations)} total observations to {len(gdf_observations_for_map)} for map visualization (within {MAX_MAP_DISTANCE_MILES} miles of property center).")


# --- Create Interactive Map 1: Property Center Buffers ---
print("\n--- Generating Map 1: Property Center Buffers ---")

# Initialize map centered on the property's centroid.
m_property_center = folium.Map(location=[property_center.y, property_center.x], zoom_start=12)

# Property boundary *not* added here for privacy.

# Add Property Center Buffer Zones to Map 1 (Blue shading).
for radius, poly in property_center_buffers:
    folium.GeoJson(
        poly.__geo_interface__,
        name=f'{radius} Mile Buffer (Property Center)',
        style_function=lambda x: {
            'fillColor': '#0000FF', # Blue fill for buffer zones
            'color': '#0000FF',     # Blue border
            'weight': 1,
            'fillOpacity': 0.1
        }
    ).add_to(m_property_center)

# Add Observation Points to Map 1.
# Now using the distance-filtered gdf_observations_for_map.
for idx, row in gdf_observations_for_map.iterrows():
    obs_lat: float = row['latitude']
    obs_lon: float = row['longitude']
    obs_id: int = row['id']
    # Use preferred common name if available, otherwise fallback to scientific name.
    obs_taxon: str = row['taxon.preferred_common_name'] if pd.notna(row['taxon.preferred_common_name']) else row['taxon.name']
    
    # Color-code observation points based on their spatial relationship.
    if row['within_property']:
        color_val = 'red'
        fill_color_val = 'red'
        radius_val = 5 # Larger dot for observations inside the main property
    elif any(row[f'within_{r}mile_property_center'] for r in BUFFER_RADII_MILES):
        color_val = 'orange'
        fill_color_val = 'orange'
        radius_val = 3 # Slightly larger for observations within any property buffer
    else:
        color_val = 'blue'
        fill_color_val = 'blue'
        radius_val = 2 # Standard dot for observations outside defined zones

    folium.CircleMarker(
        location=[obs_lat, obs_lon],
        radius=radius_val,
        color=color_val,
        fill=True,
        fill_color=fill_color_val,
        fill_opacity=0.7,
        tooltip=f"ID: {obs_id}<br>Species: {obs_taxon}<br>Within Property: {row['within_property']}"
    ).add_to(m_property_center)

# Add Layer Control to allow users to toggle layers on/off.
folium.LayerControl().add_to(m_property_center)

# --- Map Output Paths ---
# Ensure the docs/maps directory exists
output_map_dir: str = os.path.join('docs', 'maps')
os.makedirs(output_map_dir, exist_ok=True) # Create the directory if it doesn't exist

# Save Map 1 to an HTML file in the 'docs/maps' directory.
map1_file_path: str = os.path.join(output_map_dir, 'sludge_hub_map_property_center.html')
m_property_center.save(map1_file_path)
print(f"Interactive Map 1 (Property Center Buffers) saved to {map1_file_path}")


# --- Create Interactive Map 2: Apiary Center Buffers ---
print("\n--- Generating Map 2: Apiary Center Buffers ---")

# Initialize map centered on the Apiary.
m_apiary_center = folium.Map(location=[apiary_center.y, apiary_center.x], zoom_start=12)

# Property boundary *not* added here for privacy.

# Add Apiary Center Buffer Zones to Map 2 (Green shading).
for radius, poly in apiary_center_buffers:
    folium.GeoJson(
        poly.__geo_interface__,
        name=f'{radius} Mile Buffer (Apiary Center)',
        style_function=lambda x: {
            'fillColor': '#00FF00', # Green fill
            'color': '#00FF00',     # Green border
            'weight': 1,
            'fillOpacity': 0.1
        }
    ).add_to(m_apiary_center)

# Add Observation Points to Map 2.
# Now using the distance-filtered gdf_observations_for_map.
for idx, row in gdf_observations_for_map.iterrows():
    obs_lat = row['latitude']
    obs_lon = row['longitude']
    obs_id = row['id']
    obs_taxon = row['taxon.preferred_common_name'] if pd.notna(row['taxon.preferred_common_name']) else row['taxon.name']
    
    # Color-code observation points based on their spatial relationship.
    # On this map, orange now signifies proximity to the Apiary Center.
    if row['within_property']:
        color_val = 'red'
        fill_color_val = 'red'
        radius_val = 5 # Larger dot for observations inside the main property
    elif any(row[f'within_{r}mile_apiary_center'] for r in BUFFER_RADII_MILES): # Check any apiary buffer
        color_val = 'orange'
        fill_color_val = 'orange'
        radius_val = 3 # Slightly larger for observations within any apiary buffer
    else:
        color_val = 'blue'
        fill_color_val = 'blue'
        radius_val = 2 # Standard dot for observations outside defined zones

    folium.CircleMarker(
        location=[obs_lat, obs_lon],
        radius=radius_val,
        color=color_val,
        fill=True,
        fill_color=fill_color_val,
        fill_opacity=0.7,
        tooltip=f"ID: {obs_id}<br>Species: {obs_taxon}<br>Within Property: {row['within_property']}"
    ).add_to(m_apiary_center)

# Add Layer Control to allow users to toggle layers on/off.
folium.LayerControl().add_to(m_apiary_center)

# Save Map 2 to an HTML file in the 'docs/maps' directory.
map2_file_path: str = os.path.join(output_map_dir, 'sludge_hub_map_apiary_center.html')
m_apiary_center.save(map2_file_path)
print(f"Interactive Map 2 (Apiary Center Buffers) saved to {map2_file_path}")