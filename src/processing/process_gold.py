"""
Gold Layer Processing: Uber H3 Discrete Global Grid System (DGGS) Indexing,
Multi-Resolution Spatial Aggregation, Origin-Destination (OD) Matrix, and Live Spatial Pressure.
"""

import os
import json
import numpy as np
import pandas as pd
import h3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")
os.makedirs(GOLD_DIR, exist_ok=True)


def get_hex_geojson(cell_id):
    """
    Returns GeoJSON geometry dict {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}
    for an H3 cell. Note: h3 returns (lat, lng), GeoJSON requires [lng, lat].
    """
    boundary = h3.cell_to_boundary(cell_id)
    coords = [[round(lng, 6), round(lat, 6)] for lat, lng in boundary]
    coords.append(coords[0])  # Close polygon
    return json.dumps({"type": "Polygon", "coordinates": [coords]})


def process_gold_layer():
    print("=" * 60)
    print("GOLD PROCESSING: Uber H3 Discrete Global Grid Indexing...")
    print("=" * 60)
    
    trips_parquet = os.path.join(SILVER_DIR, "cleansed_mobility_trips.parquet")
    live_parquet = os.path.join(SILVER_DIR, "cleansed_live_stations.parquet")
    
    print(f"[>] Loading Silver Cleansed Trips: {trips_parquet}")
    df_trips = pd.read_parquet(trips_parquet)
    print(f"    Loaded {len(df_trips):,} trips.")
    
    # -------------------------------------------------------------
    # 1. Uber H3 Indexing across Resolutions 7, 8, and 9
    # -------------------------------------------------------------
    print("[1] Computing H3 Hexagonal Hashes (Res 7, 8, 9)...")
    
    # Vectorized / list comprehension mapping for speed
    start_lats = df_trips["start_lat"].values
    start_lngs = df_trips["start_lng"].values
    end_lats = df_trips["end_lat"].values
    end_lngs = df_trips["end_lng"].values
    
    df_trips["h3_pickup_res7"] = [h3.latlng_to_cell(lat, lng, 7) for lat, lng in zip(start_lats, start_lngs)]
    df_trips["h3_pickup_res8"] = [h3.latlng_to_cell(lat, lng, 8) for lat, lng in zip(start_lats, start_lngs)]
    df_trips["h3_pickup_res9"] = [h3.latlng_to_cell(lat, lng, 9) for lat, lng in zip(start_lats, start_lngs)]
    df_trips["h3_dropoff_res8"] = [h3.latlng_to_cell(lat, lng, 8) for lat, lng in zip(end_lats, end_lngs)]
    
    print(f"    Unique H3 Res 7 Cells (Macro)        : {df_trips['h3_pickup_res7'].nunique():,}")
    print(f"    Unique H3 Res 8 Cells (Neighborhood) : {df_trips['h3_pickup_res8'].nunique():,}")
    print(f"    Unique H3 Res 9 Cells (Micro-Block)  : {df_trips['h3_pickup_res9'].nunique():,}")
    
    # Save enriched trips back to silver / gold fact
    gold_fact_path = os.path.join(GOLD_DIR, "fact_indexed_mobility_trips.parquet")
    df_trips.to_parquet(gold_fact_path, index=False, engine="pyarrow", compression="snappy")
    print(f"[+] Saved Fact Indexed Trips: {gold_fact_path}")
    
    # -------------------------------------------------------------
    # 2. Gold Mart: H3 Spatial Density (Res 8)
    # -------------------------------------------------------------
    print("\n[2] Building H3 Spatial Density Mart (Resolution 8)...")
    
    density_records = []
    grouped_res8 = df_trips.groupby("h3_pickup_res8")
    
    for h3_cell, group in grouped_res8:
        lat, lng = h3.cell_to_latlng(h3_cell)
        total_pickups = len(group)
        avg_duration = group["trip_duration_min"].mean()
        avg_distance = group["trip_distance_km"].mean()
        avg_speed = group["speed_kmh"].mean()
        commuter_pct = (group["member_casual"] == "member").mean() * 100.0
        ebike_pct = (group["rideable_type"] == "electric_bike").mean() * 100.0
        
        morning_rush = (group["time_of_day_category"] == "Morning Rush (06:00-10:00)").sum()
        evening_rush = (group["time_of_day_category"] == "Evening Rush (16:00-20:00)").sum()
        midday = (group["time_of_day_category"] == "Midday (10:00-16:00)").sum()
        night = (group["time_of_day_category"] == "Night (20:00-06:00)").sum()
        
        density_records.append({
            "h3_index": h3_cell,
            "resolution": 8,
            "centroid_lat": round(lat, 6),
            "centroid_lng": round(lng, 6),
            "total_pickups": total_pickups,
            "avg_duration_min": round(avg_duration, 2),
            "avg_distance_km": round(avg_distance, 2),
            "avg_speed_kmh": round(avg_speed, 2),
            "commuter_percentage": round(commuter_pct, 1),
            "ebike_percentage": round(ebike_pct, 1),
            "morning_rush_pickups": morning_rush,
            "evening_rush_pickups": evening_rush,
            "midday_pickups": midday,
            "night_pickups": night,
            "hex_geojson": get_hex_geojson(h3_cell)
        })
        
    df_density = pd.DataFrame(density_records)
    # Calculate demand quantile / surge tier (Low, Moderate, High, Surge)
    q75 = df_density["total_pickups"].quantile(0.75)
    q90 = df_density["total_pickups"].quantile(0.90)
    df_density["demand_tier"] = df_density["total_pickups"].apply(
        lambda x: "Tier 1: Super Surge" if x >= q90 else ("Tier 2: High Demand" if x >= q75 else "Tier 3: Standard")
    )
    
    density_parquet = os.path.join(GOLD_DIR, "gold_h3_spatial_density.parquet")
    df_density.to_parquet(density_parquet, index=False, engine="pyarrow", compression="snappy")
    print(f"[+] Saved H3 Spatial Density Mart: {density_parquet} ({len(df_density):,} hexagons)")
    
    # -------------------------------------------------------------
    # 3. Gold Mart: Origin-Destination (OD) Matrix & 3D Flow Vectors
    # -------------------------------------------------------------
    print("\n[3] Building Origin-Destination (OD) Flow Matrix...")
    od_grouped = df_trips.groupby(["h3_pickup_res8", "h3_dropoff_res8"]).agg(
        trip_count=("ride_id", "count"),
        avg_duration_min=("trip_duration_min", "mean"),
        avg_distance_km=("trip_distance_km", "mean"),
        avg_speed_kmh=("speed_kmh", "mean"),
        commuter_pct=("member_casual", lambda s: (s == "member").mean() * 100.0)
    ).reset_index()
    
    # Filter corridors to those with meaningful volume (trip_count >= 5)
    od_filtered = od_grouped[od_grouped["trip_count"] >= 5].copy()
    
    # Compute centroid coordinates
    origin_centroids = [h3.cell_to_latlng(cell) for cell in od_filtered["h3_pickup_res8"]]
    dest_centroids = [h3.cell_to_latlng(cell) for cell in od_filtered["h3_dropoff_res8"]]
    
    od_filtered["origin_lat"] = [round(c[0], 6) for c in origin_centroids]
    od_filtered["origin_lng"] = [round(c[1], 6) for c in origin_centroids]
    od_filtered["dest_lat"] = [round(c[0], 6) for c in dest_centroids]
    od_filtered["dest_lng"] = [round(c[1], 6) for c in dest_centroids]
    
    # Flow LineString WKT
    od_filtered["flow_line_wkt"] = (
        "LINESTRING(" +
        od_filtered["origin_lng"].astype(str) + " " + od_filtered["origin_lat"].astype(str) + ", " +
        od_filtered["dest_lng"].astype(str) + " " + od_filtered["dest_lat"].astype(str) +
        ")"
    )
    
    od_parquet = os.path.join(GOLD_DIR, "gold_origin_destination_matrix.parquet")
    od_filtered.to_parquet(od_parquet, index=False, engine="pyarrow", compression="snappy")
    print(f"[+] Saved OD Flow Matrix: {od_parquet} ({len(od_filtered):,} active corridors)")
    
    # -------------------------------------------------------------
    # 4. Gold Mart: Live Station Telemetry Aggregated to H3
    # -------------------------------------------------------------
    print("\n[4] Integrating Live Station Telemetry with H3 Grid...")
    df_live = pd.read_parquet(live_parquet)
    
    live_lats = df_live["lat"].values
    live_lngs = df_live["lon"].values
    df_live["h3_res8"] = [h3.latlng_to_cell(lat, lng, 8) for lat, lng in zip(live_lats, live_lngs)]
    
    live_h3_agg = df_live.groupby("h3_res8").agg(
        station_count=("station_id", "count"),
        total_bikes=("num_bikes_available", "sum"),
        total_ebikes=("num_ebikes_available", "sum"),
        total_docks=("num_docks_available", "sum"),
        avg_utilization=("utilization_rate", "mean")
    ).reset_index()
    
    live_centroids = [h3.cell_to_latlng(cell) for cell in live_h3_agg["h3_res8"]]
    live_h3_agg["lat"] = [round(c[0], 6) for c in live_centroids]
    live_h3_agg["lng"] = [round(c[1], 6) for c in live_centroids]
    live_h3_agg["hex_geojson"] = [get_hex_geojson(cell) for cell in live_h3_agg["h3_res8"]]
    
    live_gold_parquet = os.path.join(GOLD_DIR, "gold_live_h3_telemetry.parquet")
    live_h3_agg.to_parquet(live_gold_parquet, index=False, engine="pyarrow", compression="snappy")
    print(f"[+] Saved Live H3 Telemetry: {live_gold_parquet} ({len(live_h3_agg):,} active live hexagons)")
    
    # -------------------------------------------------------------
    # 5. Gold Mart: Diurnal Hourly Temporal Pulse (24-Hour Dynamics)
    # -------------------------------------------------------------
    print("\n[5] Building 24-Hour Diurnal Temporal Pulse Mart...")
    hourly_pulse = df_trips.groupby(["h3_pickup_res8", "pickup_hour"]).agg(
        hourly_trip_count=("ride_id", "count"),
        avg_duration=("trip_duration_min", "mean"),
        avg_speed=("speed_kmh", "mean")
    ).reset_index()
    
    hourly_parquet = os.path.join(GOLD_DIR, "gold_hourly_temporal_pulse.parquet")
    hourly_pulse.to_parquet(hourly_parquet, index=False, engine="pyarrow", compression="snappy")
    print(f"[+] Saved Hourly Temporal Pulse: {hourly_parquet} ({len(hourly_pulse):,} space-time buckets)")
    
    print("\n" + "=" * 60)
    print("GOLD LAYER GENERATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    t0 = datetime.now()
    process_gold_layer()
    print(f"Finished in {(datetime.now() - t0).total_seconds():.2f}s!")
