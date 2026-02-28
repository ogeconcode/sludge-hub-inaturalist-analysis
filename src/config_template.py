"""
config_template.py

Copy this file to config.py and fill in your own values.
config.py is gitignored and will not be committed to the repository.

This template defines the structure needed by inat_data_pull.py and spatial_analysis.py.
All coordinates used here should be PUBLIC reference points (e.g., town centers, county seats)
to ensure reproducibility across different users and environments.
"""

# --- iNaturalist Project ---
# Your iNaturalist project slug (from the project URL).
# Example: for https://www.inaturalist.org/projects/the-sludge-hub, use "the-sludge-hub"
INATURALIST_PROJECT_ID = "your-project-slug-here"

# --- Study Regions ---
# Define one or more study regions for comparative analysis.
# Each region uses a public center point (town center, county seat, etc.)
# and a bounding box for the iNaturalist API query.
#
# bbox_sw: (latitude, longitude) of the southwest corner
# bbox_ne: (latitude, longitude) of the northeast corner
# center_lat / center_lon: public reference point for map centering

STUDY_REGIONS = {
    "example_region_1": {
        "label": "Example Region 1",
        "center_lat": 39.0000,
        "center_lon": -80.0000,
        "bbox_sw": (38.5, -80.5),
        "bbox_ne": (39.5, -79.5),
        "description": "Counties or area covered by this region"
    },
    "example_region_2": {
        "label": "Example Region 2",
        "center_lat": 38.5000,
        "center_lon": -81.0000,
        "bbox_sw": (38.0, -81.5),
        "bbox_ne": (39.0, -80.5),
        "description": "Counties or area covered by this region"
    },
    # Add more regions as needed...
}

# --- Coordinate Reference Systems ---
# Projected CRS should use an appropriate UTM zone for your study area.
# For West Virginia, EPSG:32617 (UTM zone 17N) works well.
PROJECTED_CRS = "EPSG:32617"
GEOGRAPHIC_CRS = "EPSG:4326"

# --- Map and Analysis Settings ---
# Buffer radii (in miles) around each region's center point.
BUFFER_RADII_MILES = [5, 10, 15]

# Maximum distance (in miles) from a region center for an observation
# to appear on that region's map.
MAX_MAP_DISTANCE_MILES = 20
