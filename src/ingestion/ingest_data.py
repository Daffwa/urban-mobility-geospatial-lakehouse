"""
Data Ingestion Pipeline for Spatio-Temporal Urban Mobility Lakehouse.
Ingests:
1. Historical High-Precision GPS Trajectory Records (NYC Urban Mobility Open Data on AWS S3).
2. Live Real-Time GBFS Telemetry Feed (NYC Department of Transportation & Lyft).
Stores raw data in Apache Parquet format in data/bronze/.
"""

import os
import io
import json
import zipfile
import urllib.request
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRONZE_DIR = os.path.join(BASE_DIR, "data", "bronze")
os.makedirs(BRONZE_DIR, exist_ok=True)

HISTORICAL_MONTHS = ["202401", "202402", "202403"]
BASE_URL_HISTORICAL = "https://s3.amazonaws.com/tripdata/JC-{month}-citibike-tripdata.csv.zip"

LIVE_STATUS_URL = "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"
LIVE_INFO_URL = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"


def ingest_historical_trips():
    print("=" * 60)
    print("STEP 1: Ingesting Historical Urban Mobility Trajectories...")
    print("=" * 60)
    
    all_dfs = []
    total_downloaded_bytes = 0
    
    for month in HISTORICAL_MONTHS:
        url = BASE_URL_HISTORICAL.format(month=month)
        print(f"[>] Downloading batch {month} from: {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "UrbanMobilityLakehouse/1.0"})
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
                total_downloaded_bytes += len(content)
                print(f"    Downloaded {len(content) / 1024 / 1024:.2f} MB")
                
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    csv_names = [name for name in zf.namelist() if name.endswith(".csv") and not name.startswith("__MACOSX")]
                    if csv_names:
                        csv_file = csv_names[0]
                        print(f"    Extracting & parsing: {csv_file}")
                        with zf.open(csv_file) as f:
                            df = pd.read_csv(f, low_memory=False)
                            all_dfs.append(df)
                            print(f"    Parsed {len(df):,} trip records.")
        except Exception as e:
            print(f"    [!] Error downloading/extracting batch {month}: {e}")
            
    if not all_dfs:
        raise RuntimeError("No historical data could be ingested!")
        
    combined_df = pd.concat(all_dfs, ignore_index=True)
    output_parquet = os.path.join(BRONZE_DIR, "raw_mobility_trips.parquet")
    combined_df.to_parquet(output_parquet, index=False, engine="pyarrow", compression="snappy")
    
    file_size_mb = os.path.getsize(output_parquet) / 1024 / 1024
    print(f"\n[+] Successfully saved Bronze Historical Trajectories to: {output_parquet}")
    print(f"    Total Records : {len(combined_df):,}")
    print(f"    Columns       : {list(combined_df.columns)}")
    print(f"    Parquet Size  : {file_size_mb:.2f} MB")
    return combined_df


def ingest_live_station_telemetry():
    print("\n" + "=" * 60)
    print("STEP 2: Ingesting Real-Time Live GBFS Telemetry Feed...")
    print("=" * 60)
    
    headers = {"User-Agent": "Mozilla/5.0 (UrbanMobilityLakehouse/1.0)"}
    
    print(f"[>] Fetching live station information from: {LIVE_INFO_URL}")
    req_info = urllib.request.Request(LIVE_INFO_URL, headers=headers)
    with urllib.request.urlopen(req_info, timeout=20) as resp:
        info_json = json.loads(resp.read().decode("utf-8"))
        stations_info = info_json["data"]["stations"]
        df_info = pd.DataFrame(stations_info)
        print(f"    Fetched metadata for {len(df_info):,} physical stations with GPS.")
        
    print(f"[>] Fetching live station status from: {LIVE_STATUS_URL}")
    req_status = urllib.request.Request(LIVE_STATUS_URL, headers=headers)
    with urllib.request.urlopen(req_status, timeout=20) as resp:
        status_json = json.loads(resp.read().decode("utf-8"))
        stations_status = status_json["data"]["stations"]
        df_status = pd.DataFrame(stations_status)
        print(f"    Fetched live operational status for {len(df_status):,} reporting stations.")
        
    # Merge station information (GPS lat/lon, name, capacity) with live status (num bikes/docks available)
    merged_live = pd.merge(
        df_info[["station_id", "name", "short_name", "lat", "lon", "capacity"]].dropna(subset=["lat", "lon"]),
        df_status[["station_id", "num_bikes_available", "num_ebikes_available", "num_docks_available", "is_renting", "last_reported"]],
        on="station_id",
        how="inner"
    )
    
    # Calculate live capacity utilization and pressure
    merged_live["ingestion_timestamp"] = datetime.utcnow().isoformat()
    merged_live["total_capacity"] = merged_live["capacity"].fillna(merged_live["num_bikes_available"] + merged_live["num_docks_available"])
    merged_live["utilization_rate"] = merged_live.apply(
        lambda r: (r["num_bikes_available"] / r["total_capacity"]) if r["total_capacity"] > 0 else 0.0, axis=1
    )
    
    output_parquet = os.path.join(BRONZE_DIR, "raw_live_stations.parquet")
    merged_live.to_parquet(output_parquet, index=False, engine="pyarrow", compression="snappy")
    
    file_size_kb = os.path.getsize(output_parquet) / 1024
    print(f"\n[+] Successfully saved Bronze Live Telemetry to: {output_parquet}")
    print(f"    Active Live Stations : {len(merged_live):,}")
    print(f"    Total Live Fleet Size: {merged_live['num_bikes_available'].sum():,} bikes on streets right now")
    print(f"    Parquet Size         : {file_size_kb:.2f} KB")
    return merged_live


if __name__ == "__main__":
    t0 = datetime.now()
    trips_df = ingest_historical_trips()
    live_df = ingest_live_station_telemetry()
    elapsed = (datetime.now() - t0).total_seconds()
    print("\n" + "=" * 60)
    print(f"INGESTION COMPLETED in {elapsed:.2f}s! Bronze Lakehouse ready.")
    print("=" * 60)
