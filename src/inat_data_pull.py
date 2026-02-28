"""
inat_data_pull.py

Pulls observation data from the iNaturalist API for:
  1. A specified iNaturalist project (e.g., The Sludge Hub)
  2. Regional bounding boxes across multiple study areas

Handles pagination, performs initial data cleaning, tags observations by source,
and saves the combined dataset to CSV in the 'data' directory.

Configuration is sourced from a local 'config.py' file (gitignored).
See 'config_template.py' for the expected structure.
"""

import requests
import pandas as pd
import time
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Import configuration from local config.py
from . import config

# --- Configuration ---
PROJECT_ID: str = config.INATURALIST_PROJECT_ID
STUDY_REGIONS: dict = config.STUDY_REGIONS

BASE_URL: str = "https://api.inaturalist.org/v1/observations"
PER_PAGE: int = 200  # Max allowed by iNaturalist API


def pull_observations(params_base: Dict[str, Any], source_label: str) -> List[Dict[str, Any]]:
    """
    Generic paginated pull from the iNaturalist API.

    Args:
        params_base: Base query parameters (without page/per_page).
        source_label: Label to identify the source of these observations.

    Returns:
        List of observation dicts, each tagged with '_source'.
    """
    all_observations: List[Dict[str, Any]] = []
    page: int = 1
    total_results: Optional[int] = None

    print(f"  Starting pull: {source_label}")

    while True:
        params = {**params_base, "per_page": PER_PAGE, "page": page, "order_by": "id", "order": "asc"}
        print(f"    Fetching page {page}...")

        try:
            response = requests.get(BASE_URL, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"    Error on page {page}: {e}")
            break

        data = response.json()

        if total_results is None:
            total_results = data.get("total_results", 0)
            print(f"    Total available: {total_results}")
            if total_results == 0:
                break

        observations = data.get("results", [])
        if not observations:
            break

        # Tag each observation with its source
        for obs in observations:
            obs["_source"] = source_label

        all_observations.extend(observations)
        print(f"    Page {page}: {len(observations)} obs (total collected: {len(all_observations)})")

        # iNaturalist caps at 10,000 results per query.
        # For bounding box queries that might exceed this, we stop at 10k.
        if len(all_observations) >= 10000:
            print(f"    Reached 10,000 observation limit for this query.")
            break

        page += 1
        time.sleep(1)  # Rate limiting

    print(f"  Completed: {len(all_observations)} observations for '{source_label}'")
    return all_observations


def pull_project_data(project_id: str) -> List[Dict[str, Any]]:
    """Pull all observations from a specific iNaturalist project."""
    return pull_observations(
        params_base={"project_id": project_id},
        source_label="sludge_hub_project"
    )


def pull_regional_data(region_key: str, region_config: dict) -> List[Dict[str, Any]]:
    """Pull observations within a regional bounding box."""
    sw_lat, sw_lon = region_config["bbox_sw"]
    ne_lat, ne_lon = region_config["bbox_ne"]

    return pull_observations(
        params_base={
            "nelat": ne_lat,
            "nelng": ne_lon,
            "swlat": sw_lat,
            "swlng": sw_lon,
        },
        source_label=f"regional_{region_key}"
    )


def normalize_and_clean(raw_observations: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Normalize raw API results into a cleaned DataFrame.

    Handles coordinate extraction, column selection, type conversion,
    and quality grade filtering (drops 'casual').
    """
    if not raw_observations:
        return pd.DataFrame()

    df = pd.json_normalize(raw_observations)

    # --- Coordinate handling ---
    for col in ["latitude", "longitude"]:
        if col not in df.columns:
            df[col] = None
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fallback to geojson.coordinates if direct lat/lon missing
    if "geojson.coordinates" in df.columns:
        geojson_lon = df["geojson.coordinates"].apply(
            lambda x: x[0] if isinstance(x, list) and len(x) == 2 else None
        )
        geojson_lat = df["geojson.coordinates"].apply(
            lambda x: x[1] if isinstance(x, list) and len(x) == 2 else None
        )
        geojson_lat = pd.to_numeric(geojson_lat, errors="coerce")
        geojson_lon = pd.to_numeric(geojson_lon, errors="coerce")
        df["latitude"] = df["latitude"].fillna(geojson_lat)
        df["longitude"] = df["longitude"].fillna(geojson_lon)

    # --- Column selection ---
    selected_columns = [
        "id", "uri", "observed_on", "latitude", "longitude",
        "quality_grade", "public_positional_accuracy",
        "taxon.name", "taxon.preferred_common_name", "taxon.rank",
        "taxon.iconic_taxon_name",  # Useful for pollinator highlighting
        "user.login", "license_code", "_source"
    ]
    actual_columns = [col for col in selected_columns if col in df.columns]
    df_cleaned = df[actual_columns].copy()

    # --- Type conversions ---
    df_cleaned["observed_on"] = pd.to_datetime(df_cleaned["observed_on"], errors="coerce")
    for col in ["latitude", "longitude"]:
        if col in df_cleaned.columns:
            df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors="coerce")

    # --- Quality grade filter: drop casual observations ---
    before = len(df_cleaned)
    df_cleaned = df_cleaned[df_cleaned["quality_grade"] != "casual"].copy()
    dropped = before - len(df_cleaned)
    if dropped > 0:
        print(f"  Dropped {dropped} casual-grade observations.")

    return df_cleaned


# --- Main Execution ---
if __name__ == "__main__":
    print("=" * 60)
    print("iNaturalist Data Pull — Multi-Region")
    print("=" * 60)

    all_raw: List[Dict[str, Any]] = []

    # 1. Pull Sludge Hub project observations
    print(f"\n[1/2] Pulling Sludge Hub project: {PROJECT_ID}")
    project_obs = pull_project_data(PROJECT_ID)
    all_raw.extend(project_obs)

    # 2. Pull regional bounding box observations
    print(f"\n[2/2] Pulling regional observations for {len(STUDY_REGIONS)} regions")
    for key, region in STUDY_REGIONS.items():
        print(f"\n  Region: {region['label']} ({region['description']})")
        regional_obs = pull_regional_data(key, region)
        all_raw.extend(regional_obs)

    # 3. Normalize and clean
    print(f"\nTotal raw observations collected: {len(all_raw)}")
    df_cleaned = normalize_and_clean(all_raw)

    if df_cleaned.empty:
        print("No observations collected. Check project ID and region configurations.")
        exit()

    # 4. Deduplicate by observation ID.
    #    If an observation appears in both the project pull and a regional pull,
    #    prefer the project-tagged version.
    before_dedup = len(df_cleaned)
    df_cleaned["_is_project"] = df_cleaned["_source"] == "sludge_hub_project"
    df_cleaned = df_cleaned.sort_values("_is_project", ascending=False)
    df_cleaned = df_cleaned.drop_duplicates(subset=["id"], keep="first")
    df_cleaned = df_cleaned.drop(columns=["_is_project"])
    print(f"Deduplicated: {before_dedup} → {len(df_cleaned)} observations")

    # 5. Save
    os.makedirs("data", exist_ok=True)

    cleaned_path = os.path.join("data", "observations_cleaned.csv")
    df_cleaned.to_csv(cleaned_path, index=False)
    print(f"\nCleaned data saved to {cleaned_path}")

    # Write timestamp for the landing page
    docs_dir = os.path.join("docs")
    os.makedirs(docs_dir, exist_ok=True)
    timestamp_path = os.path.join(docs_dir, "last_updated.txt")
    update_time = datetime.now(timezone.utc).strftime("%B %d, %Y")
    with open(timestamp_path, "w") as f:
        f.write(update_time)
    print(f"Last updated timestamp written to {timestamp_path}: {update_time}")

    print("\nData pull complete.")
