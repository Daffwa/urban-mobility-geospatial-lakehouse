"""
High-Performance Visualization Server for Urban Mobility Geospatial Lakehouse.
Serves interactive 3D Deck.gl / Kepler.gl Map UI and REST API endpoints:
- GET /                    : Interactive 3D Geospatial Map UI
- GET /api/summary         : Executive KPI statistics
- GET /api/hexagons        : Uber H3 spatial density GeoJSON & metrics
- GET /api/od_flows        : 3D Origin-Destination flow vectors
- GET /api/live_stations   : 2,519 live reporting stations telemetry
- GET /api/hourly_pulse    : 24-hour diurnal space-time mobility pulse
"""

import os
import sys
import json
import sqlite3
import pandas as pd
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOLD_DIR = os.path.join(BASE_DIR, "data", "gold")
SILVER_DIR = os.path.join(BASE_DIR, "data", "silver")
HTML_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.html")

# Preload Lakehouse Data into Memory for Sub-Millisecond API Latency
print("[*] Pre-loading Gold & Silver Lakehouse Data for Visualizer...")

DENSITY_PARQUET = os.path.join(GOLD_DIR, "gold_h3_spatial_density.parquet")
OD_PARQUET = os.path.join(GOLD_DIR, "gold_origin_destination_matrix.parquet")
LIVE_PARQUET = os.path.join(SILVER_DIR, "cleansed_live_stations.parquet")
HOURLY_PARQUET = os.path.join(GOLD_DIR, "gold_hourly_temporal_pulse.parquet")

df_density = pd.read_parquet(DENSITY_PARQUET)
df_od = pd.read_parquet(OD_PARQUET)
df_live = pd.read_parquet(LIVE_PARQUET)
df_hourly = pd.read_parquet(HOURLY_PARQUET)

# Prepare JSON payloads
# Hexagon FeatureCollection
hex_features = []
for _, row in df_density.iterrows():
    geom = json.loads(row["hex_geojson"])
    props = {
        "h3_index": row["h3_index"],
        "resolution": int(row["resolution"]),
        "centroid": [row["centroid_lng"], row["centroid_lat"]],
        "total_pickups": int(row["total_pickups"]),
        "avg_duration_min": float(row["avg_duration_min"]),
        "avg_distance_km": float(row["avg_distance_km"]),
        "avg_speed_kmh": float(row["avg_speed_kmh"]),
        "commuter_percentage": float(row["commuter_percentage"]),
        "ebike_percentage": float(row["ebike_percentage"]),
        "demand_tier": str(row["demand_tier"])
    }
    hex_features.append({
        "type": "Feature",
        "geometry": geom,
        "properties": props
    })
HEX_GEOJSON_PAYLOAD = json.dumps({"type": "FeatureCollection", "features": hex_features})

# OD Flows payload
od_records = []
for _, row in df_od.iterrows():
    od_records.append({
        "origin_h3": row["h3_pickup_res8"],
        "dest_h3": row["h3_dropoff_res8"],
        "origin": [float(row["origin_lng"]), float(row["origin_lat"])],
        "destination": [float(row["dest_lng"]), float(row["dest_lat"])],
        "trip_count": int(row["trip_count"]),
        "avg_duration_min": float(row["avg_duration_min"]),
        "avg_distance_km": float(row["avg_distance_km"]),
        "avg_speed_kmh": float(row["avg_speed_kmh"]),
        "commuter_pct": float(row["commuter_pct"])
    })
OD_PAYLOAD = json.dumps(od_records)

# Live Stations payload
live_records = []
for _, row in df_live.iterrows():
    live_records.append({
        "station_id": str(row["station_id"]),
        "name": str(row["name"]),
        "coordinates": [float(row["lon"]), float(row["lat"])],
        "capacity": int(row["total_capacity"]),
        "bikes_available": int(row["num_bikes_available"]),
        "ebikes_available": int(row["num_ebikes_available"]),
        "docks_available": int(row["num_docks_available"]),
        "utilization_rate": round(float(row["utilization_rate"]) * 100, 1),
        "operational_status": str(row["operational_status"]),
        "last_reported": int(row["last_reported"]) if pd.notna(row["last_reported"]) else 0
    })
LIVE_PAYLOAD = json.dumps(live_records)

# Summary KPI payload
SUMMARY_PAYLOAD = json.dumps({
    "total_cleansed_trips": 161890,
    "total_live_stations": len(df_live),
    "total_live_fleet": int(df_live["num_bikes_available"].sum()),
    "active_hexagons_res8": len(df_density),
    "active_od_corridors": len(df_od),
    "mean_trip_distance_km": round(float(df_density["avg_distance_km"].mean()), 2),
    "mean_trip_duration_min": round(float(df_density["avg_duration_min"].mean()), 2),
    "mean_speed_kmh": round(float(df_density["avg_speed_kmh"].mean()), 2),
    "overall_commuter_pct": round(float(df_density["commuter_percentage"].mean()), 1),
    "peak_hexagon": str(df_density.loc[df_density["total_pickups"].idxmax(), "h3_index"]),
    "peak_hexagon_pickups": int(df_density["total_pickups"].max()),
    "status": "HEALTHY",
    "timestamp": pd.Timestamp.now().isoformat()
})

# Hourly map & city-wide hourly metrics
hourly_map = {h: {} for h in range(24)}
for _, row in df_hourly.iterrows():
    h = int(row["pickup_hour"])
    cell = str(row["h3_pickup_res8"])
    hourly_map[h][cell] = {
        "count": int(row["hourly_trip_count"]),
        "speed": round(float(row["avg_speed"]), 1)
    }

hourly_speeds = {}
hourly_trip_totals = {}
for h in range(24):
    h_subset = df_hourly[df_hourly["pickup_hour"] == h]
    if len(h_subset) > 0 and h_subset["hourly_trip_count"].sum() > 0:
        weighted_spd = (h_subset["hourly_trip_count"] * h_subset["avg_speed"]).sum() / h_subset["hourly_trip_count"].sum()
        hourly_speeds[h] = round(float(weighted_spd), 2)
        hourly_trip_totals[h] = int(h_subset["hourly_trip_count"].sum())
    else:
        hourly_speeds[h] = 15.55
        hourly_trip_totals[h] = 0

HOURLY_PAYLOAD = json.dumps({
    "cells": hourly_map,
    "hourly_speeds": hourly_speeds,
    "hourly_trip_totals": hourly_trip_totals,
    "global_mean_speed": round(float(df_density["avg_speed_kmh"].mean()), 2)
})


def background_telemetry_poller():
    global LIVE_PAYLOAD, SUMMARY_PAYLOAD, live_records
    import time
    import urllib.request
    url_status = "https://gbfs.citibikenyc.com/gbfs/en/station_status.json"
    headers = {"User-Agent": "Mozilla/5.0 (UrbanMobilityLakehouse/1.0)"}
    
    print("[*] Background Live Telemetry Poller thread started (Polling every 20s)...")
    while True:
        time.sleep(20)
        try:
            req = urllib.request.Request(url_status, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                status_json = json.loads(resp.read().decode("utf-8"))
                stations_status = {s["station_id"]: s for s in status_json["data"]["stations"]}
                last_updated = status_json.get("last_updated", int(time.time()))
                
                updated_records = []
                total_fleet = 0
                for rec in live_records:
                    sid = rec["station_id"]
                    if sid in stations_status:
                        st = stations_status[sid]
                        bikes = int(st.get("num_bikes_available", 0))
                        ebikes = int(st.get("num_ebikes_available", 0))
                        docks = int(st.get("num_docks_available", 0))
                        cap = rec["capacity"] if rec["capacity"] > 0 else (bikes + docks)
                        util = round((bikes / cap) * 100, 1) if cap > 0 else 0.0
                        
                        if util <= 5:
                            op_status = "Depleted / Empty"
                        elif util < 20:
                            op_status = "Low Availability"
                        elif util > 85:
                            op_status = "Surge / Near Full"
                        else:
                            op_status = "Optimal Balance"
                            
                        rec["bikes_available"] = bikes
                        rec["ebikes_available"] = ebikes
                        rec["docks_available"] = docks
                        rec["utilization_rate"] = util
                        rec["operational_status"] = op_status
                        rec["last_reported"] = st.get("last_reported", last_updated)
                        total_fleet += bikes
                    updated_records.append(rec)
                    
                LIVE_PAYLOAD = json.dumps(updated_records)
                
                sum_dict = json.loads(SUMMARY_PAYLOAD)
                sum_dict["total_live_fleet"] = total_fleet
                sum_dict["last_live_sync_epoch"] = last_updated
                sum_dict["timestamp"] = pd.Timestamp.now().isoformat()
                SUMMARY_PAYLOAD = json.dumps(sum_dict)
                print(f"[LIVE GBFS SYNC] Updated {len(updated_records):,} stations. Current live fleet: {total_fleet:,} bikes.")
        except Exception as e:
            print(f"[!] Warning polling live telemetry: {e}")


import threading
poller_thread = threading.Thread(target=background_telemetry_poller, daemon=True)
poller_thread.start()

print("[+] Visualizer Cache Ready!")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class VisualizerRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(HTML_FILE_PATH, "rb") as f:
                self.wfile.write(f.read())
        elif self.path == "/api/summary":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(SUMMARY_PAYLOAD.encode("utf-8"))
        elif self.path == "/api/hexagons":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(HEX_GEOJSON_PAYLOAD.encode("utf-8"))
        elif self.path == "/api/od_flows":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(OD_PAYLOAD.encode("utf-8"))
        elif self.path == "/api/live_stations":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(LIVE_PAYLOAD.encode("utf-8"))
        elif self.path == "/api/hourly_pulse":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(HOURLY_PAYLOAD.encode("utf-8"))
        else:
            self.send_error(404, "Endpoint Not Found")

    def log_message(self, format, *args):
        # Suppress noisy logs
        pass


def run_server(port=8060):
    server_address = ("0.0.0.0", port)
    httpd = ThreadedHTTPServer(server_address, VisualizerRequestHandler)
    print(f"\n[+] Urban Mobility 3D Visualizer Server running at: http://localhost:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping visualizer server...")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8060
    run_server(port)
