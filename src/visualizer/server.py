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

# Hourly map: { hour: { cell_id: { count, speed } } }
hourly_map = {h: {} for h in range(24)}
for _, row in df_hourly.iterrows():
    h = int(row["pickup_hour"])
    cell = str(row["h3_pickup_res8"])
    hourly_map[h][cell] = {
        "count": int(row["hourly_trip_count"]),
        "speed": round(float(row["avg_speed"]), 1)
    }
HOURLY_PAYLOAD = json.dumps(hourly_map)

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
