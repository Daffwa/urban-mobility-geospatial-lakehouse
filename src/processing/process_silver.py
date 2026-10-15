"""
Silver Layer Processing: Spatio-Temporal Data Cleansing, PostGIS Geometry Generation,
and Trajectory Validation.
"""

import os
import math
import numpy as np
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
os.makedirs(SILVER_DIR, exist_ok=True)

# NYC Metro Metropolitan Bounding Box
LAT_MIN, LAT_MAX = 40.50, 40.95
LON_MIN, LON_MAX = -74.30, -73.65


def haversine_vectorized(lat1, lon1, lat2, lon2):
    """
    Computes great-circle distance between pairs of coordinates on Earth (WGS84 sphere).
    Returns distance in kilometers.
    """
    R = 6371.0088  # Earth mean radius in kilometers
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    
    a = np.sin(dphi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c


def categorize_time_of_day(hour):
    if 6 <= hour < 10:
        return "Morning Rush (06:00-10:00)"
    elif 10 <= hour < 16:
        return "Midday (10:00-16:00)"
    elif 16 <= hour < 20:
        return "Evening Rush (16:00-20:00)"
    else:
        return "Night (20:00-06:00)"


def process_silver_trips():
    print("=" * 60)
    print("SILVER PROCESSING: Cleansing & Spatial Geometry Generation...")
    print("=" * 60)
    
    input_parquet = os.path.join(BRONZE_DIR, "raw_mobility_trips.parquet")
    print(f"[>] Loading Bronze Parquet: {input_parquet}")
    df = pd.read_parquet(input_parquet)
    initial_count = len(df)
    print(f"    Raw records: {initial_count:,}")
    
    # 1. Coordinate Validity & Bounding Box Filter
    print("[1] Applying Spatial Bounding Box Filter (NYC Metro)...")
    valid_coords = (
        (df["start_lat"].between(LAT_MIN, LAT_MAX)) &
        (df["start_lng"].between(LON_MIN, LON_MAX)) &
        (df["end_lat"].between(LAT_MIN, LAT_MAX)) &
        (df["end_lng"].between(LON_MIN, LON_MAX))
    )
    df = df[valid_coords].copy()
    print(f"    Retained after bounding box: {len(df):,} ({len(df)/initial_count*100:.1f}%)")
    
    # 2. Datetime Parsing & Duration Validation
    print("[2] Parsing Datetime & Filtering Durations (1 min <= t <= 180 min)...")
    df["started_at"] = pd.to_datetime(df["started_at"])
    df["ended_at"] = pd.to_datetime(df["ended_at"])
    df["trip_duration_min"] = (df["ended_at"] - df["started_at"]).dt.total_seconds() / 60.0
    
    valid_durations = df["trip_duration_min"].between(1.0, 180.0)
    df = df[valid_durations].copy()
    print(f"    Retained after duration filter: {len(df):,}")
    
    # 3. Geodesic Distance Calculation (Haversine)
    print("[3] Calculating Geodesic Haversine Distances...")
    df["trip_distance_km"] = haversine_vectorized(
        df["start_lat"].values, df["start_lng"].values,
        df["end_lat"].values, df["end_lng"].values
    )
    
    # 4. Speed Anomaly Filtering (0.5 km/h <= speed <= 60 km/h)
    print("[4] Filtering Speed Anomalies...")
    df["speed_kmh"] = (df["trip_distance_km"] / (df["trip_duration_min"] / 60.0))
    valid_speed = (df["speed_kmh"] >= 0.5) & (df["speed_kmh"] <= 60.0)
    df = df[valid_speed].copy()
    print(f"    Retained after speed filter: {len(df):,}")
    
    # 5. Temporal Dimensional Attributes
    print("[5] Generating Temporal Features...")
    df["pickup_hour"] = df["started_at"].dt.hour
    df["pickup_day"] = df["started_at"].dt.date.astype(str)
    df["day_of_week"] = df["started_at"].dt.day_name()
    df["is_weekend"] = df["started_at"].dt.dayofweek.isin([5, 6]).astype(int)
    df["time_of_day_category"] = df["pickup_hour"].apply(categorize_time_of_day)
    
    # 6. PostGIS WKT Spatial Geometries
    print("[6] Generating PostGIS WKT Geometry Strings...")
    df["pickup_geom_wkt"] = "POINT(" + df["start_lng"].round(6).astype(str) + " " + df["start_lat"].round(6).astype(str) + ")"
    df["dropoff_geom_wkt"] = "POINT(" + df["end_lng"].round(6).astype(str) + " " + df["end_lat"].round(6).astype(str) + ")"
    df["trajectory_wkt"] = (
        "LINESTRING(" +
        df["start_lng"].round(6).astype(str) + " " + df["start_lat"].round(6).astype(str) + ", " +
        df["end_lng"].round(6).astype(str) + " " + df["end_lat"].round(6).astype(str) +
        ")"
    )
    
    output_parquet = os.path.join(SILVER_DIR, "cleansed_mobility_trips.parquet")
    df.to_parquet(output_parquet, index=False, engine="pyarrow", compression="snappy")
    
    file_size_mb = os.path.getsize(output_parquet) / 1024 / 1024
    print(f"\n[+] Successfully saved Silver Cleansed Trips: {output_parquet}")
    print(f"    Final Cleansed Records: {len(df):,}")
    print(f"    Mean Trip Distance    : {df['trip_distance_km'].mean():.2f} km")
    print(f"    Mean Trip Duration    : {df['trip_duration_min'].mean():.2f} min")
    print(f"    Mean Speed            : {df['speed_kmh'].mean():.2f} km/h")
    print(f"    File Size             : {file_size_mb:.2f} MB")
    return df


def process_silver_live_stations():
    print("\n" + "=" * 60)
    print("SILVER PROCESSING: Cleansing Live Station Telemetry...")
    print("=" * 60)
    
    input_parquet = os.path.join(BRONZE_DIR, "raw_live_stations.parquet")
    df_live = pd.read_parquet(input_parquet)
    
    # Filter NYC bounding box
    df_live = df_live[
        df_live["lat"].between(LAT_MIN, LAT_MAX) &
        df_live["lon"].between(LON_MIN, LON_MAX)
    ].copy()
    
    # Station WKT geometry
    df_live["station_geom_wkt"] = "POINT(" + df_live["lon"].round(6).astype(str) + " " + df_live["lat"].round(6).astype(str) + ")"
    
    # Status categorisation: Empty, Critical Low (<15%), Balanced, Critical Full (>85%)
    def categorize_station_status(utilization):
        if utilization <= 0.05:
            return "Depleted / Empty"
        elif utilization < 0.20:
            return "Low Availability"
        elif utilization > 0.85:
            return "Surge / Near Full"
        else:
            return "Optimal Balance"
            
    df_live["operational_status"] = df_live["utilization_rate"].apply(categorize_station_status)
    
    output_parquet = os.path.join(SILVER_DIR, "cleansed_live_stations.parquet")
    df_live.to_parquet(output_parquet, index=False, engine="pyarrow", compression="snappy")
    print(f"[+] Successfully saved Silver Live Stations: {output_parquet}")
    print(f"    Valid Stations: {len(df_live):,}")
    print("    Operational Breakdown:")
    for status, count in df_live["operational_status"].value_counts().items():
        print(f"      - {status:20s}: {count:,} stations ({count/len(df_live)*100:.1f}%)")
    return df_live


if __name__ == "__main__":
    t0 = datetime.now()
    process_silver_trips()
    process_silver_live_stations()
    print(f"\nSilver Layer processing finished in {(datetime.now() - t0).total_seconds():.2f}s!")
