"""
This script pulls observation data from the iNaturalist API for a specified project ID.
It handles pagination to retrieve all observations, performs initial data cleaning,
and saves both raw and partially cleaned datasets to CSV files in the 'data' directory.

The script now sources the iNaturalist Project ID from a local 'config.py' file.
This 'config.py' file should not be publicly shared. Other users wishing to run
this script for their own iNaturalist projects should create their own local
'config.py' and define their 'INATURALIST_PROJECT_ID' there.
"""

import requests
import pandas as pd
import time
import os
from typing import List, Dict, Any, Optional

# --- NEW: Import configuration from local config.py ---
# Make sure config.py is in the same directory (src/) or adjust the import path
from . import config 

# --- Configuration ---
# iNaturalist Project ID is now sourced from config.py for better organization and security.
PROJECT_ID: str = config.INATURALIST_PROJECT_ID


BASE_URL: str = "https://api.inaturalist.org/v1/observations"
PER_PAGE: int = 200 # Max allowed observations per request by iNaturalist API

# --- Main Data Pull Function ---
def pull_inaturalist_data(project_id: str, base_url: str, per_page: int) -> List[Dict[str, Any]]:
    """
    Pulls all observations for a given iNaturalist project ID from the iNaturalist API.
    Handles pagination to retrieve the full dataset.

    Args:
        project_id (str): The ID of the iNaturalist project.
        base_url (str): The base URL for the iNaturalist observations API.
        per_page (int): The number of results to request per page (max 200).

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary
                               represents a raw iNaturalist observation.
    """
    all_observations: List[Dict[str, Any]] = []
    page: int = 1
    total_results: Optional[int] = None # Total observations reported by API

    print(f"Starting data pull for iNaturalist project ID: {project_id}")

    while True:
        params: Dict[str, Any] = {
            "project_id": project_id,
            "per_page": per_page,
            "page": page,
            "order_by": "id",
            "order": "asc"
        }
        print(f"Fetching page {page}...")
        response: requests.Response = requests.get(base_url, params=params)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Error fetching data: {e}")
            print(f"Response content: {response.text}")
            break
        except requests.exceptions.RequestException as e:
            print(f"Network or connection error during request: {e}")
            break

        data: Dict[str, Any] = response.json()

        if total_results is None: # Only set on the first page
            total_results = data.get('total_results', 0)
            print(f"Total observations in project (reported by API): {total_results}")
            if total_results == 0:
                print("No observations found in the project. Exiting data pull.")
                break

        observations: List[Dict[str, Any]] = data.get('results', [])
        
        # This is the primary stop condition for pagination: if the API returns an empty list, it means no more data.
        if not observations:
            print(f"Page {page} returned no observations. Assuming all data fetched.")
            break

        all_observations.extend(observations)
        print(f"DEBUG: Fetched {len(observations)} observations on page {page}. Total collected so far: {len(all_observations)}")
        
        page += 1
        time.sleep(1) # Be kind to the API

    # --- FINAL SUMMARY AFTER THE LOOP ---
    if total_results is not None and len(all_observations) < total_results:
        print(f"Warning: Expected {total_results} observations based on initial API report, but only collected {len(all_observations)}. Data pull might be incomplete.")
    elif total_results is not None and len(all_observations) == total_results:
        print(f"Successfully fetched all {total_results} observations.")
    else: # This covers cases where total_results was never set (e.g., initial error) or no observations were expected
        print(f"Data pull completed. Total observations collected: {len(all_observations)}")

    return all_observations

# --- Main Execution Block ---
if __name__ == "__main__":
    raw_observations: List[Dict[str, Any]] = pull_inaturalist_data(PROJECT_ID, BASE_URL, PER_PAGE)

    if raw_observations:
        # Normalize the JSON data into a pandas DataFrame.
        # This flattens nested JSON structures into columns (e.g., 'taxon.name').
        df: pd.DataFrame = pd.json_normalize(raw_observations)

        # --- Coordinate Handling and Standardization ---
        # iNaturalist API generally provides 'latitude' and 'longitude' directly.
        # However, for obscured observations or specific geojson types,
        # 'geojson.coordinates' might be the primary source or available when direct lat/lon is not.
        
        # Ensure 'latitude' and 'longitude' columns exist and are numeric where possible.
        for col in ['latitude', 'longitude']:
            if col not in df.columns:
                df[col] = None # Initialize with None if missing
            # Explicitly convert to numeric before fillna to avoid FutureWarnings
            df[col] = pd.to_numeric(df[col], errors='coerce') 

        # If 'geojson.coordinates' is present and direct lat/lon are missing/null,
        # use geojson.coordinates as a fallback for point geometries.
        if 'geojson.coordinates' in df.columns:
            # Create temporary series for geojson coordinates
            geojson_lon = df['geojson.coordinates'].apply(
                lambda x: x[0] if isinstance(x, list) and len(x) == 2 else None
            )
            geojson_lat = df['geojson.coordinates'].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) == 2 else None
            )
            
            # Ensure geojson_lat/lon are numeric before filling
            geojson_lat = pd.to_numeric(geojson_lat, errors='coerce')
            geojson_lon = pd.to_numeric(geojson_lon, errors='coerce')

            # Fill NaN in 'latitude' and 'longitude' with values from geojson.coordinates
            df['latitude'] = df['latitude'].fillna(geojson_lat)
            df['longitude'] = df['longitude'].fillna(geojson_lon)
            
            # Drop the raw 'geojson.coordinates' column after extraction if no longer needed
            # df = df.drop(columns=['geojson.coordinates']) # Uncomment if you want to drop it

        print(f"DEBUG: Columns in raw DataFrame (df): {df.columns.tolist()}")

        # --- Basic Cleaning and Column Selection ---
        # Define the set of columns relevant for subsequent analysis.
        selected_columns: List[str] = [
            'id', 'uri', 'observed_on', 'latitude', 'longitude',
            'quality_grade', 'public_positional_accuracy',
            'taxon.name', 'taxon.preferred_common_name', 'taxon.rank',
            'user.login', 'license_code' # Added 'license_code' for completeness in a public dataset
        ]
        
        # Filter to only include columns that actually exist in the DataFrame.
        actual_columns: List[str] = [col for col in selected_columns if col in df.columns]
        df_cleaned: pd.DataFrame = df[actual_columns].copy()

        print(f"DEBUG: Columns in cleaned DataFrame (df_cleaned): {df_cleaned.columns.tolist()}")

        # Convert 'observed_on' to datetime format, coercing errors to NaT (Not a Time).
        df_cleaned['observed_on'] = pd.to_datetime(df_cleaned['observed_on'], errors='coerce')
        
        # Convert latitude and longitude to numeric types, coercing errors.
        # This is important for spatial operations in the next script.
        if 'latitude' in df_cleaned.columns:
            df_cleaned['latitude'] = pd.to_numeric(df_cleaned['latitude'], errors='coerce')
        if 'longitude' in df_cleaned.columns:
            df_cleaned['longitude'] = pd.to_numeric(df_cleaned['longitude'], errors='coerce')
            
        # --- Save Data ---
        # Ensure the 'data' directory exists.
        if not os.path.exists('data'):
            os.makedirs('data')

        raw_file_path: str = os.path.join('data', 'sludge_hub_raw_data.csv')
        cleaned_file_path: str = os.path.join('data', 'sludge_hub_cleaned_data.csv')

        # Save the full raw data DataFrame.
        df.to_csv(raw_file_path, index=False)
        print(f"Raw data saved to {raw_file_path}")

        # Save the partially cleaned and selected data DataFrame.
        df_cleaned.to_csv(cleaned_file_path, index=False)
        print(f"Partially cleaned data saved to {cleaned_file_path}")

    else:
        print("No observations were pulled. Check project ID and API response.")