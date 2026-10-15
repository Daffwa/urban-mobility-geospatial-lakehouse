"""
Unit and integration tests for the Urban Mobility 3D Visualizer API and dynamic contracts.
Validates the dynamic response structures for Indicators 3, 4, and 5.
"""
import json
import urllib.request
import pytest

SERVER_BASE_URL = "http://localhost:8060"


def fetch_json(endpoint):
    url = f"{SERVER_BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "UrbanMobilityTest/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        assert resp.status == 200, f"Expected 200 OK from {endpoint}, got {resp.status}"
        return json.loads(resp.read().decode("utf-8"))


def test_api_summary_contract():
    """Validates baseline indicators 1 & 2 plus initial stats."""
    data = fetch_json("/api/summary")
    assert "total_cleansed_trips" in data
    assert data["total_cleansed_trips"] == 161890  # Static baseline anchor
    assert data["active_hexagons_res8"] == 38     # Static baseline anchor
    assert "active_od_corridors" in data
    assert "total_live_fleet" in data
    assert data["total_live_fleet"] > 10000        # Dynamic fleet count > 10k


def test_api_od_flows_contract():
    """Validates Indicator 3 dynamic data source (corridor vectors)."""
    corridors = fetch_json("/api/od_flows")
    assert isinstance(corridors, list)
    assert len(corridors) > 100
    first = corridors[0]
    assert "trip_count" in first
    assert "origin" in first
    assert "destination" in first
    assert len(first["origin"]) == 2
    assert len(first["destination"]) == 2


def test_api_live_stations_contract():
    """Validates Indicator 4 dynamic data source (live GBFS telemetry stream)."""
    stations = fetch_json("/api/live_stations")
    assert isinstance(stations, list)
    assert len(stations) >= 2000
    sample = stations[0]
    assert "coordinates" in sample
    assert "bikes_available" in sample
    assert "docks_available" in sample
    assert "operational_status" in sample


def test_api_hourly_pulse_contract():
    """Validates Indicator 5 dynamic velocity & space-time diurnal pulse contract."""
    data = fetch_json("/api/hourly_pulse")
    assert "cells" in data
    assert "hourly_speeds" in data
    assert "hourly_trip_totals" in data
    assert "global_mean_speed" in data

    hourly_speeds = data["hourly_speeds"]
    # Check all 24 hours are represented
    for h in range(24):
        h_str = str(h)
        assert h_str in hourly_speeds, f"Hour {h} missing from hourly_speeds payload"
        speed = hourly_speeds[h_str]
        assert isinstance(speed, (int, float)), f"Speed for hour {h} is not numeric"
        assert 5.0 <= speed <= 35.0, f"Speed {speed} km/h for hour {h} out of plausible urban bike range"

    # Confirm morning/evening rush hour speeds are slower than early morning free flow
    speed_morning_rush = hourly_speeds["8"]
    speed_free_flow = hourly_speeds["5"]
    assert speed_morning_rush < speed_free_flow, (
        f"Traffic physics assertion: Morning rush ({speed_morning_rush} km/h) should be slower "
        f"than early morning free flow ({speed_free_flow} km/h)"
    )


def test_api_hexagons_geojson():
    """Validates Uber H3 GeoJSON FeatureCollection."""
    geojson = fetch_json("/api/hexagons")
    assert geojson.get("type") == "FeatureCollection"
    features = geojson.get("features", [])
    assert len(features) == 38
    first_prop = features[0]["properties"]
    assert "h3_index" in first_prop
    assert "total_pickups" in first_prop
