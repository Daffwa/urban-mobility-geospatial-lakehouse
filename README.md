# Spatio-Temporal Urban Mobility Lakehouse Platform
### Enterprise Big Data Architecture: Discrete Global Grid Systems (Uber H3), PostGIS 3.4, Real-Time GBFS Telemetry & 3D Geospatial Visualization

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Engine: Uber H3](https://img.shields.io/badge/DGGS-Uber%20H3%20v4.5-black.svg)](https://h3geo.org/)
[![Database: PostGIS](https://img.shields.io/badge/Database-PostGIS%203.4%20%7C%20Postgres%2016-336791.svg)](https://postgis.net/)
[![Storage: Apache Parquet](https://img.shields.io/badge/Storage-Apache%20Parquet-orange.svg)](https://parquet.apache.org/)
[![Cloud Native: Kubernetes](https://img.shields.io/badge/Kubernetes-K8s%20Ready-326CE5.svg)](https://kubernetes.io/)
[![DataOps Tests: 100% Passing](https://img.shields.io/badge/DataOps-100%25%20Passing-success.svg)](tests/)

---

## 1. Executive Summary

The **Spatio-Temporal Urban Mobility Lakehouse Platform** is an enterprise-grade Big Data infrastructure engineered to solve the continuous spatial indexing problem across high-density urban transit networks. Traditional relational B-Tree and Euclidean grids suffer from the **Modifiable Areal Unit Problem (MAUP)** and edge quantization distortion. 

This platform implements a **Hybrid Medallion & Speed Layer Architecture**:
* **Historical Lakehouse (Batch Layer)**: Ingests, cleanses, and partitions **161,890+ real GPS trajectories** into hierarchical **Uber H3 Discrete Global Grid Systems (DGGS)** at Resolutions 7, 8, and 9.
* **Real-Time Telemetry (Speed Layer)**: Consumes official live feeds from **2,519 active smart mobility hubs** across New York City via the **General Bikeshare Feed Specification (GBFS)**, tracking live fleet distribution (**34,255 bikes on streets right now**).
* **3D Visualizer & Analytics Control Center**: High-performance WebGL-accelerated 3D geospatial engine built on **Deck.gl** and **MapLibre GL**, featuring extruded 3D hexagonal prisms, 3D ballistic origin-destination flow arcs, and diurnal 24-hour temporal sliders.

---

## 2. 3D Geospatial Visualizer Display

![Urban Mobility 3D Dashboard](screenshots/urban_mobility_3d_dashboard.png)

*Figure 1: Full-screen display of the 3D Deck.gl geospatial dashboard showing extruded Uber H3 hexagonal columns (elevation = trip volume, color = surge tier), 3D ballistic origin-destination vector arcs, real-time reporting stations, and executive KPI ribbons.*

---

## 3. System Architecture Blueprint

```
                      [ NYC URBAN MOBILITY SOURCES ]
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          ▼                                                   ▼
[ HISTORICAL BATCH LAKEHOUSE ]                    [ REAL-TIME SPEED LAYER ]
• AWS S3 Open Data (161,890+ Trips)               • NYC DOT & Lyft GBFS Feed
• Precise 6-decimal GPS Coordinates               • 2,519 Active Reporting Stations
• Timestamps, Modes & Commuter Types              • Live Fleet & Dock Capacities
          │                                                   │
          ▼                                                   ▼
[ BRONZE INGESTION LAYER ]                        [ BRONZE TELEMETRY INGESTION ]
• data/bronze/raw_mobility_trips.parquet          • data/bronze/raw_live_stations.parquet
          │                                                   │
          ▼                                                   ▼
[ SILVER SPATIAL CLEANSING ]                      [ SILVER STATUS CATEGORIZATION ]
• Bounding Box Filter: NYC Metro [40.5, 40.95]    • GeoJSON Point Geometries
• Duration Anomaly: 1 min ≤ t ≤ 180 min           • Real-time Fleet Utilization Rates
• Speed Outliers: 0.5 ≤ km/h ≤ 60.0 (Haversine)   • Operational Classification:
• PostGIS WKT Generation: POINT, LINESTRING         Empty, Critical Low, Balanced, Surge
          │                                                   │
          └─────────────────────────┬─────────────────────────┘
                                    │
                                    ▼
[ GOLD LAYER: UBER H3 DISCRETE GLOBAL GRID (DGGS) ]
• Resolution 7 (~1.22 km): Macro Borough Mobility Corridors
• Resolution 8 (~461 m)  : Neighborhood-level Transit Density & Demand Tiers
• Resolution 9 (~174 m)  : Micro Street-Block Pickup Hotspots
• 3D Origin-Destination (OD) Matrix: 625 Directional Mobility Corridors
• Diurnal 24-Hour Mobility Pulse Mart
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          ▼                                                   ▼
[ SERVING LAYER: POSTGIS & SQLITE ]               [ 3D DECK.GL / KEPLER.GL VISUALIZER ]
• PostgreSQL 16 + PostGIS 3.4 (Port 5434)         • Port 8060 (WebGL / MapLibre)
• GIST Spatial R-Tree Indexing                    • 3D Extruded Hexagons & Elevation Scaler
• SQLite High-Speed Local Replica (Port 8060)      • Dynamic 3D Ballistic Trajectory Arcs
• Analytical SQL Views: v_top_mobility_corridors  • Diurnal 24-Hour Interactive Slider
```

---

## 4. Key Performance Indicators (KPIs)

| Metric | Measured Value | Architecture Layer |
| :--- | :--- | :--- |
| **Total Cleansed Trips** | **161,890** | Silver Layer Fact (`cleansed_mobility_trips.parquet`) |
| **Live Reporting Stations** | **2,519 Stations** | Real-Time Speed Layer (GBFS Feed) |
| **Total Live Fleet on Streets** | **34,255 Bikes** | Real-Time Telemetry Layer |
| **Active H3 Hexagons (Res 8)** | **38 Hexagons** | Gold Spatial Density Mart (`gold_h3_spatial_density.parquet`) |
| **Active 3D OD Corridors** | **625 Corridors** | Gold Flow Matrix (`gold_origin_destination_matrix.parquet`) |
| **Mean Trip Distance** | **2.37 km** | Geodesic Great-Circle (Haversine WGS84) |
| **Mean Trip Speed** | **15.55 km/h** | Velocity Normalization Engine |
| **Commuter Subscription Share** | **85.2%** | User Segmentation Dimension |
| **Top Super-Surge Hexagon** | `882a1072e7fffff` (21,355 pickups) | Downtown / Transit Exchange Hub |
| **DataOps Validation Pass Rate** | **100% (5/5 Passing)** | Automated Pytest Suite (`tests/test_data_quality.py`) |

---

## 5. Academic Grounding & Literature Citations

This platform is rigorously engineered based on foundational peer-reviewed literature in spatial databases and trajectory mining (detailed in [`docs/ACADEMIC_REFERENCES.md`](docs/ACADEMIC_REFERENCES.md)):

* **Sahr, K., White, D., & Kimerling, A. J. (2003).** Geodesic discrete global grid systems. *Cartography and Geographic Information Science*, 30(2), 121–134. *(Proves mathematical superiority of hexagonal cells over square grids due to uniform centroid-to-neighbor distances).*
* **Brodsky, I. (2018).** *H3: Uber’s Hexagonal Hierarchical Spatial Index*. Uber Engineering Technical Publications. *(Defines hierarchical aperture 7 subdivision algorithms used in this project).*
* **Zheng, Y. (2015).** Trajectory data mining: An overview. *ACM Transactions on Intelligent Systems and Technology (TIST)*, 6(3), 1–41. *(Survey for trajectory segmentation, anomaly rejection, and OD-matrix extraction).*
* **Openshaw, S. (1984).** *The Modifiable Areal Unit Problem*. CATMOG 38, Geo Books. *(Foundational proof for eliminating municipal boundary bias via uniform geometric partitions).*
* **Guttman, A. (1984).** R-trees: A dynamic index structure for spatial searching. *ACM SIGMOD Record*, 14(2), 47–57. *(Core algorithm for PostGIS GIST spatial indexing).*

---

## 6. Project Structure

```
urban_mobility_geospatial_lakehouse/
├── data/
│   ├── bronze/                   # Raw Parquet lakehouse archives
│   ├── silver/                   # Cleansed PostGIS geometry Parquets
│   └── gold/                     # H3 spatial density, OD matrix & SQLite DB
├── docker/
│   ├── docker-compose.yml        # Multi-container orchestration (PostGIS 16 + Visualizer)
│   └── Dockerfile                # Lightweight container image for visualizer
├── docs/
│   └── ACADEMIC_REFERENCES.md    # Comprehensive APA 7th academic literature
├── k8s/
│   └── k8s-all-in-one.yaml       # Kubernetes Cloud-Native production manifests
├── screenshots/
│   └── urban_mobility_3d_dashboard.png # High-resolution 3D dashboard capture
├── src/
│   ├── ingestion/
│   │   └── ingest_data.py        # Bronze ingestion (AWS S3 + Live GBFS)
│   ├── processing/
│   │   ├── process_silver.py     # Silver cleansing & PostGIS geometries
│   │   └── process_gold.py       # Uber H3 DGGS indexing & OD matrix
│   ├── database/
│   │   ├── schema_postgis.sql    # PostGIS 3.4 DDL & GIST spatial indexing
│   │   └── database_loader.py    # Dual serving loader (PostGIS & SQLite)
│   └── visualizer/
│       ├── app.html              # 3D Deck.gl + MapLibre GL geospatial UI
│       ├── server.py             # Threaded REST API & web server
│       └── capture_screenshot.py # Automated headless screenshot capture
├── tests/
│   └── test_data_quality.py      # Automated DataOps quality test suite
├── requirements.txt              # Production Python dependencies
├── LICENSE                       # MIT License
└── README.md                     # Engineering documentation
```

---

## 7. How to Run & Reproduce

### Prerequisites
* Python 3.10+
* (Optional) Docker / Docker Compose for containerized PostGIS warehouse

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/Daffwa/urban-mobility-geospatial-lakehouse.git
cd urban-mobility-geospatial-lakehouse
pip install -r requirements.txt
```

### 2. Execute Data Pipeline (Bronze -> Silver -> Gold)
```bash
# 1. Ingest Raw Trajectories & Live GBFS Telemetry
python src/ingestion/ingest_data.py

# 2. Cleansing, Haversine Geodesics & Spatial Geometries
python src/processing/process_silver.py

# 3. Uber H3 DGGS Indexing & Origin-Destination Matrix
python src/processing/process_gold.py

# 4. Build Serving Layer Database
python src/database/database_loader.py
```

### 3. Run Automated DataOps Validation Suite
```bash
python -m pytest -v tests/test_data_quality.py
```

### 4. Launch 3D Interactive Geospatial Visualizer
```bash
python src/visualizer/server.py 8060
```
Open your browser and navigate to: **`http://localhost:8060/`**

### 5. (Optional) Run with Docker Compose
```bash
docker compose -f docker/docker-compose.yml up -d
```

### 6. (Optional) Deploy to Kubernetes Cluster (EKS / GKE)
```bash
kubectl apply -f k8s/k8s-all-in-one.yaml
```

---

## 8. License
This project is licensed under the terms of the [MIT License](LICENSE).  
Copyright &copy; 2026 Muhammad Daffa Wardana.
