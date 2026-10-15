"""
Automated DataOps Quality Suite for Urban Mobility Geospatial Lakehouse.
Performs end-to-end data integrity, spatial geometry, and DGGS validations.
"""

import os
import sqlite3
import pandas as pd
import pytest
import h3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")
SQLITE_DB = os.path.join(GOLD_DIR, "urban_mobility_lakehouse.db")


def test_bronze_lakehouse_integrity():
    trips_path = os.path.join(BRONZE_DIR, "raw_mobility_trips.parquet")
    live_path = os.path.join(BRONZE_DIR, "raw_live_stations.parquet")
    
    assert os.path.exists(trips_path), "Bronze trips parquet must exist"
    assert os.path.exists(live_path), "Bronze live stations parquet must exist"
    
    df_trips = pd.read_parquet(trips_path)
    df_live = pd.read_parquet(live_path)
    
    assert len(df_trips) >= 100000, f"Expected at least 100k raw trips, got {len(df_trips)}"
    assert len(df_live) >= 2000, f"Expected at least 2k live stations, got {len(df_live)}"


def test_silver_cleansing_and_geometries():
    silver_trips_path = os.path.join(SILVER_DIR, "cleansed_mobility_trips.parquet")
    df = pd.read_parquet(silver_trips_path)
    
    # Check no null coordinates
    assert df["start_lat"].isna().sum() == 0, "No null start_lat allowed"
    assert df["start_lng"].isna().sum() == 0, "No null start_lng allowed"
    assert df["end_lat"].isna().sum() == 0, "No null end_lat allowed"
    assert df["end_lng"].isna().sum() == 0, "No null end_lng allowed"
    
    # Check bounding box
    assert df["start_lat"].between(40.50, 40.95).all(), "All start_lat must be in NYC Metro"
    assert df["start_lng"].between(-74.30, -73.65).all(), "All start_lng must be in NYC Metro"
    
    # Check speed bounds
    assert (df["speed_kmh"] >= 0.5).all(), "Speed must be >= 0.5 km/h"
    assert (df["speed_kmh"] <= 60.0).all(), "Speed must be <= 60 km/h (speed anomaly rejection)"
    
    # Check PostGIS WKT formats
    assert df["pickup_geom_wkt"].str.startswith("POINT(").all(), "pickup_geom must be WKT POINT"
    assert df["trajectory_wkt"].str.startswith("LINESTRING(").all(), "trajectory must be WKT LINESTRING"


def test_gold_h3_hexagonal_dggs():
    density_path = os.path.join(GOLD_DIR, "gold_h3_spatial_density.parquet")
    df_density = pd.read_parquet(density_path)
    
    assert len(df_density) > 0, "H3 density mart must not be empty"
    
    # Verify H3 resolution and validity
    for _, row in df_density.iterrows():
        cell = row["h3_index"]
        assert h3.is_valid_cell(cell), f"Cell {cell} must be a valid H3 cell"
        assert h3.get_resolution(cell) == 8, f"Cell {cell} resolution must be 8"
        
        # Verify centroid is inside NYC metro
        lat, lng = row["centroid_lat"], row["centroid_lng"]
        assert 40.50 <= lat <= 40.95
        assert -74.30 <= lng <= -73.65


def test_gold_origin_destination_matrix():
    od_path = os.path.join(GOLD_DIR, "gold_origin_destination_matrix.parquet")
    df_od = pd.read_parquet(od_path)
    
    assert len(df_od) > 0, "OD Matrix must have corridors"
    assert (df_od["trip_count"] >= 5).all(), "Filtered OD corridors must have >= 5 trips"
    assert df_od["flow_line_wkt"].str.startswith("LINESTRING(").all(), "Flow lines must be WKT"


def test_sqlite_serving_layer():
    assert os.path.exists(SQLITE_DB), "SQLite database must exist"
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    tables = [
        "fact_mobility_trips",
        "live_station_telemetry",
        "agg_h3_spatial_density",
        "agg_origin_destination_matrix"
    ]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        assert count > 0, f"Table {table} must have records (found {count})"
        
    # Check Analytical Views
    cursor.execute("SELECT COUNT(*) FROM v_top_mobility_corridors")
    view_count = cursor.fetchone()[0]
    assert view_count > 0, "View v_top_mobility_corridors must return records"
    
    conn.close()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
