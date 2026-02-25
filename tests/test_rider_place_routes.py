import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

rider_route = pytest.importorskip("api.v1.rider_route")
from schemas.response_schema import APIResponse


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rider_route.router, prefix="/api/v1")
    return TestClient(app)


def test_allowed_countries_route_requires_no_query_params(client):
    response = client.get("/api/v1/riders/place/allowedCountries")
    assert response.status_code == 200
    body = response.json()
    assert body["status_code"] == 200
    assert isinstance(body["data"], list)
    assert "us" in body["data"]


def test_reverse_geocode_route_validates_coordinate_range(client):
    response = client.get(
        "/api/v1/riders/place/reverse-geocode",
        params={"lat": 100.0, "lng": 20.0},
    )
    assert response.status_code == 422


def test_reverse_geocode_route_success(monkeypatch, client):
    async def fake_reverse_geocode(latitude: float, longitude: float, country=None):
        assert latitude == 10.0
        assert longitude == 20.0
        assert country == "us"
        return APIResponse(
            status_code=200,
            data={
                "place_id": "p1",
                "description": "Current location",
                "name": "Current location",
                "address": "Current location",
                "lat": 10.0,
                "lng": 20.0,
            },
            detail="ok",
        )

    monkeypatch.setattr(rider_route, "get_reverse_geocode", fake_reverse_geocode)

    response = client.get(
        "/api/v1/riders/place/reverse-geocode",
        params={"lat": 10.0, "lng": 20.0, "country": "us"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status_code"] == 200
    assert body["data"]["place_id"] == "p1"
