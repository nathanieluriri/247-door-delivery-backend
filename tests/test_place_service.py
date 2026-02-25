import json

import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException

place_service = pytest.importorskip("services.place_service")


class FakeCache:
    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def json(self):
        return self.payload


def install_http_stub(monkeypatch, dispatcher):
    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            return FakeResponse(dispatcher(url, params or {}))

    monkeypatch.setattr(place_service.httpx, "AsyncClient", FakeAsyncClient)


@pytest.fixture
def fake_cache(monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(place_service, "cache_db", cache)
    monkeypatch.setattr(place_service, "API_KEY", "test-key")
    return cache


@pytest.mark.asyncio
async def test_get_autocomplete_returns_cache_hit(fake_cache, monkeypatch):
    cached_results = [
        {
            "place_id": "p1",
            "description": "Main Street",
            "name": "Main Street",
            "address": "Main Street, Test City",
            "lat": 10.1,
            "lng": 20.2,
        }
    ]
    key = place_service._autocomplete_cache_key("main street", "us")
    fake_cache.setex(key, 10, json.dumps(cached_results))

    install_http_stub(monkeypatch, lambda *_args, **_kwargs: {"status": "OK"})

    response = await place_service.get_autocomplete("  Main   Street ", "us")
    assert response.status_code == 200
    assert response.data == cached_results


@pytest.mark.asyncio
async def test_get_autocomplete_zero_results(fake_cache, monkeypatch):
    def dispatcher(url, _params):
        if url.endswith("/autocomplete/json"):
            return {"status": "ZERO_RESULTS", "predictions": []}
        raise AssertionError(f"Unexpected URL: {url}")

    install_http_stub(monkeypatch, dispatcher)

    response = await place_service.get_autocomplete("ab", "us")
    assert response.status_code == 200
    assert response.data == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_http"),
    [
        ("INVALID_REQUEST", 400),
        ("OVER_QUERY_LIMIT", 429),
        ("REQUEST_DENIED", 403),
    ],
)
async def test_get_autocomplete_maps_google_status(fake_cache, monkeypatch, status, expected_http):
    def dispatcher(url, _params):
        if url.endswith("/autocomplete/json"):
            return {"status": status, "error_message": "upstream error"}
        raise AssertionError(f"Unexpected URL: {url}")

    install_http_stub(monkeypatch, dispatcher)

    with pytest.raises(HTTPException) as exc:
        await place_service.get_autocomplete("ab", "us")
    assert exc.value.status_code == expected_http


@pytest.mark.asyncio
async def test_get_reverse_geocode_returns_result_and_cache_hit(fake_cache, monkeypatch):
    call_count = {"count": 0}

    def dispatcher(url, _params):
        call_count["count"] += 1
        if url == place_service.GEOCODE_URL:
            return {
                "status": "OK",
                "results": [
                    {
                        "place_id": "place123",
                        "formatted_address": "1 Test Ave, Test City, US",
                        "geometry": {"location": {"lat": 40.7128, "lng": -74.006}},
                        "types": ["street_address"],
                        "address_components": [
                            {"short_name": "US", "types": ["country", "political"]}
                        ],
                    }
                ],
            }
        raise AssertionError(f"Unexpected URL: {url}")

    install_http_stub(monkeypatch, dispatcher)

    first = await place_service.get_reverse_geocode(40.7128, -74.0060, "us")
    assert first.status_code == 200
    assert first.data["place_id"] == "place123"

    second = await place_service.get_reverse_geocode(40.7128, -74.0060, "us")
    assert second.status_code == 200
    assert second.data["place_id"] == "place123"
    assert call_count["count"] == 1


@pytest.mark.asyncio
async def test_get_reverse_geocode_zero_results(fake_cache, monkeypatch):
    def dispatcher(url, _params):
        if url == place_service.GEOCODE_URL:
            return {"status": "ZERO_RESULTS", "results": []}
        raise AssertionError(f"Unexpected URL: {url}")

    install_http_stub(monkeypatch, dispatcher)

    response = await place_service.get_reverse_geocode(1.1, 2.2, None)
    assert response.status_code == 200
    assert response.data is None


@pytest.mark.asyncio
async def test_get_reverse_geocode_invalid_coordinates(fake_cache):
    with pytest.raises(HTTPException) as exc:
        await place_service.get_reverse_geocode(91.0, 1.0, None)
    assert exc.value.status_code == 400
