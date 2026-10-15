-- ====================================================================
-- SPATIO-TEMPORAL URBAN MOBILITY LAKEHOUSE
-- PostGIS 3.4 + PostgreSQL 16 DDL Schema
-- Features: GIST R-Tree Spatial Indexing, Uber H3 DGGS, OD Matrix
-- ====================================================================

-- 1. Enable Core Spatial Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- 2. Silver Cleansed Fact Trips Table
DROP TABLE IF EXISTS fact_mobility_trips CASCADE;
CREATE TABLE fact_mobility_trips (
    ride_id VARCHAR(64) PRIMARY KEY,
    rideable_type VARCHAR(32) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE NOT NULL,
    start_station_name VARCHAR(255),
    start_station_id VARCHAR(64),
    end_station_name VARCHAR(255),
    end_station_id VARCHAR(64),
    start_lat NUMERIC(9, 6) NOT NULL,
    start_lng NUMERIC(9, 6) NOT NULL,
    end_lat NUMERIC(9, 6) NOT NULL,
    end_lng NUMERIC(9, 6) NOT NULL,
    member_casual VARCHAR(16) NOT NULL,
    trip_duration_min NUMERIC(8, 2) NOT NULL,
    trip_distance_km NUMERIC(8, 3) NOT NULL,
    speed_kmh NUMERIC(8, 2) NOT NULL,
    pickup_hour SMALLINT NOT NULL,
    pickup_day DATE NOT NULL,
    day_of_week VARCHAR(16) NOT NULL,
    is_weekend SMALLINT NOT NULL,
    time_of_day_category VARCHAR(32) NOT NULL,
    h3_pickup_res7 VARCHAR(16) NOT NULL,
    h3_pickup_res8 VARCHAR(16) NOT NULL,
    h3_pickup_res9 VARCHAR(16) NOT NULL,
    h3_dropoff_res8 VARCHAR(16) NOT NULL,
    pickup_geom GEOMETRY(Point, 4326),
    dropoff_geom GEOMETRY(Point, 4326)
);

-- Spatial & Temporal Indexes
CREATE INDEX idx_trips_pickup_geom ON fact_mobility_trips USING GIST (pickup_geom);
CREATE INDEX idx_trips_dropoff_geom ON fact_mobility_trips USING GIST (dropoff_geom);
CREATE INDEX idx_trips_h3_res8 ON fact_mobility_trips (h3_pickup_res8);
CREATE INDEX idx_trips_started_at ON fact_mobility_trips (started_at);
CREATE INDEX idx_trips_time_of_day ON fact_mobility_trips (time_of_day_category);

-- 3. Live Station Telemetry Table
DROP TABLE IF EXISTS live_station_telemetry CASCADE;
CREATE TABLE live_station_telemetry (
    station_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    short_name VARCHAR(64),
    lat NUMERIC(9, 6) NOT NULL,
    lon NUMERIC(9, 6) NOT NULL,
    capacity INT,
    num_bikes_available INT NOT NULL,
    num_ebikes_available INT NOT NULL,
    num_docks_available INT NOT NULL,
    is_renting SMALLINT NOT NULL,
    last_reported BIGINT,
    ingestion_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    total_capacity INT NOT NULL,
    utilization_rate NUMERIC(5, 4) NOT NULL,
    operational_status VARCHAR(32) NOT NULL,
    h3_res8 VARCHAR(16) NOT NULL,
    station_geom GEOMETRY(Point, 4326)
);

CREATE INDEX idx_stations_geom ON live_station_telemetry USING GIST (station_geom);
CREATE INDEX idx_stations_h3 ON live_station_telemetry (h3_res8);
CREATE INDEX idx_stations_status ON live_station_telemetry (operational_status);

-- 4. Gold H3 Spatial Density Mart
DROP TABLE IF EXISTS agg_h3_spatial_density CASCADE;
CREATE TABLE agg_h3_spatial_density (
    h3_index VARCHAR(16) PRIMARY KEY,
    resolution SMALLINT NOT NULL,
    centroid_lat NUMERIC(9, 6) NOT NULL,
    centroid_lng NUMERIC(9, 6) NOT NULL,
    total_pickups INT NOT NULL,
    avg_duration_min NUMERIC(8, 2) NOT NULL,
    avg_distance_km NUMERIC(8, 2) NOT NULL,
    avg_speed_kmh NUMERIC(8, 2) NOT NULL,
    commuter_percentage NUMERIC(5, 1) NOT NULL,
    ebike_percentage NUMERIC(5, 1) NOT NULL,
    morning_rush_pickups INT NOT NULL,
    evening_rush_pickups INT NOT NULL,
    midday_pickups INT NOT NULL,
    night_pickups INT NOT NULL,
    demand_tier VARCHAR(32) NOT NULL,
    hex_geom GEOMETRY(Polygon, 4326)
);

CREATE INDEX idx_density_geom ON agg_h3_spatial_density USING GIST (hex_geom);
CREATE INDEX idx_density_pickups ON agg_h3_spatial_density (total_pickups DESC);

-- 5. Gold Origin-Destination Flow Matrix
DROP TABLE IF EXISTS agg_origin_destination_matrix CASCADE;
CREATE TABLE agg_origin_destination_matrix (
    origin_h3 VARCHAR(16) NOT NULL,
    dest_h3 VARCHAR(16) NOT NULL,
    trip_count INT NOT NULL,
    avg_duration_min NUMERIC(8, 2) NOT NULL,
    avg_distance_km NUMERIC(8, 2) NOT NULL,
    avg_speed_kmh NUMERIC(8, 2) NOT NULL,
    commuter_pct NUMERIC(5, 1) NOT NULL,
    origin_lat NUMERIC(9, 6) NOT NULL,
    origin_lng NUMERIC(9, 6) NOT NULL,
    dest_lat NUMERIC(9, 6) NOT NULL,
    dest_lng NUMERIC(9, 6) NOT NULL,
    flow_line_geom GEOMETRY(LineString, 4326),
    PRIMARY KEY (origin_h3, dest_h3)
);

CREATE INDEX idx_od_flow_geom ON agg_origin_destination_matrix USING GIST (flow_line_geom);
CREATE INDEX idx_od_trip_count ON agg_origin_destination_matrix (trip_count DESC);
