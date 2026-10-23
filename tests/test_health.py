
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200


def test_vehicles_list_endpoint():
    response = client.get("/vehicles")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_vehicle_details_not_found():
    response = client.get("/vehicles/999999")
    assert response.status_code == 404


def test_bookings_require_authentication():
    response = client.get("/bookings/")
    assert response.status_code == 401


def test_create_booking_requires_authentication():
    response = client.post(
        "/bookings/",
        json={
            "vehicle_id": 6,
            "start_date": "2026-10-24",
            "end_date": "2026-10-26",
        },
    )
    assert response.status_code == 401


def test_nearby_vehicles_endpoint():
    response = client.get("/vehicles/nearby")
    assert response.status_code in (200, 422)


def test_vehicle_location_requires_authentication():
    response = client.post(
        "/vehicles/6/location",
        json={
            "latitude": 17.3850,
            "longitude": 78.4867,
            "speed": 30,
            "heading": 90,
        },
    )
    assert response.status_code == 401


def test_dashboard_requires_authentication():
    response = client.get("/dashboard/summary")
    assert response.status_code == 401


def test_create_vehicle_requires_authentication():
    response = client.post(
        "/vehicles",
        json={
            "name": "Test Car",
            "brand": "Toyota",
            "vehicle_type": "CAR",
            "registration_number": "AUTH123",
            "price_per_day": 1500,
            "status": "AVAILABLE",
            "current_location": "Hyderabad",
        },
    )
    assert response.status_code == 401


def test_update_vehicle_requires_authentication():
    response = client.put(
        "/vehicles/1",
        json={"name": "Updated Car"},
    )
    assert response.status_code == 401


def test_delete_vehicle_requires_authentication():
    response = client.delete("/vehicles/1")
    assert response.status_code == 401
