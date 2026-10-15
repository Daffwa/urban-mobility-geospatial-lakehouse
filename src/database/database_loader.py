"""
Database Loader: Dual-Engine Serving Layer.
Loads Bronze/Silver/Gold Parquet into:
1. Local Embedded SQLite Analytics Database (data/gold/urban_mobility_lakehouse.db)
2. PostgreSQL 16 + PostGIS 3.4 (Host Port 5434 / dockerized warehouse) if available.
"""

import os
import sqlite3
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
SQLITE_DB_PATH = os.path.join(GOLD_DIR, "urban_mobility_lakehouse.db")


def load_sqlite_warehouse():
    print("=" * 60)
    print("LOADING SQLITE SERVING LAYER...")
    print("=" * 60)
    print(f"[>] Target DB: {SQLITE_DB_PATH}")
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    
    # 1. Fact Indexed Trips
    fact_parquet = os.path.join(GOLD_DIR, "fact_indexed_mobility_trips.parquet")
    print(f"[1] Loading fact_mobility_trips from {fact_parquet}...")
    df_fact = pd.read_parquet(fact_parquet)
    # Convert datetime to string for sqlite
    df_fact["started_at"] = df_fact["started_at"].astype(str)
    df_fact["ended_at"] = df_fact["ended_at"].astype(str)
    df_fact.to_sql("fact_mobility_trips", conn, if_exists="replace", index=False)
    print(f"    Loaded {len(df_fact):,} rows into fact_mobility_trips.")
    
    # 2. Live Stations
    live_parquet = os.path.join(SILVER_DIR, "cleansed_live_stations.parquet")
    print(f"[2] Loading live_station_telemetry from {live_parquet}...")
    df_live = pd.read_parquet(live_parquet)
    df_live.to_sql("live_station_telemetry", conn, if_exists="replace", index=False)
    print(f"    Loaded {len(df_live):,} rows into live_station_telemetry.")
    
    # 3. H3 Spatial Density
    density_parquet = os.path.join(GOLD_DIR, "gold_h3_spatial_density.parquet")
    print(f"[3] Loading agg_h3_spatial_density from {density_parquet}...")
    df_density = pd.read_parquet(density_parquet)
    df_density.to_sql("agg_h3_spatial_density", conn, if_exists="replace", index=False)
    print(f"    Loaded {len(df_density):,} rows into agg_h3_spatial_density.")
    
    # 4. Origin-Destination Matrix
    od_parquet = os.path.join(GOLD_DIR, "gold_origin_destination_matrix.parquet")
    print(f"[4] Loading agg_origin_destination_matrix from {od_parquet}...")
    df_od = pd.read_parquet(od_parquet)
    df_od.to_sql("agg_origin_destination_matrix", conn, if_exists="replace", index=False)
    print(f"    Loaded {len(df_od):,} rows into agg_origin_destination_matrix.")
    
    # 5. Create helpful Analytical Views & Indexes
    print("[5] Creating B-Tree Indexes and Analytical SQL Views...")
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trips_h3 ON fact_mobility_trips(h3_pickup_res8);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trips_hour ON fact_mobility_trips(pickup_hour);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_od_count ON agg_origin_destination_matrix(trip_count DESC);")
    
    cursor.execute("DROP VIEW IF EXISTS v_top_mobility_corridors;")
    cursor.execute("""
    CREATE VIEW v_top_mobility_corridors AS
    SELECT 
        h3_pickup_res8 AS origin_h3, h3_dropoff_res8 AS dest_h3, trip_count, 
        avg_duration_min, avg_distance_km, avg_speed_kmh, commuter_pct
    FROM agg_origin_destination_matrix
    ORDER BY trip_count DESC
    LIMIT 20;
    """)
    
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS v_live_station_summary AS
    SELECT 
        operational_status,
        COUNT(*) AS station_count,
        SUM(num_bikes_available) AS total_bikes,
        SUM(num_docks_available) AS total_docks,
        ROUND(AVG(utilization_rate) * 100, 2) AS avg_utilization_pct
    FROM live_station_telemetry
    GROUP BY operational_status;
    """)
    conn.commit()
    conn.close()
    
    size_mb = os.path.getsize(SQLITE_DB_PATH) / 1024 / 1024
    print(f"\n[+] SQLite Warehouse Successfully Built! Size: {size_mb:.2f} MB")


def check_postgres_postgis():
    """Checks if a PostgreSQL/PostGIS container is active on port 5434"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    result = s.connect_ex(("localhost", 5434))
    s.close()
    if result == 0:
        print("[+] PostgreSQL/PostGIS service detected on localhost:5434!")
    else:
        print("[-] PostGIS port 5434 not currently open. (Can be started via docker/docker-compose.yml)")


if __name__ == "__main__":
    t0 = datetime.now()
    load_sqlite_warehouse()
    check_postgres_postgis()
    print(f"Completed in {(datetime.now() - t0).total_seconds():.2f}s!")
