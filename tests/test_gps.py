
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, Vehicle
from app.security import hash_password, create_access_token


@pytest.fixture
def gps_test_env():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def create_user(db, email, role="CUSTOMER"):
    user = User(
        name="GPS Test User",
        email=email,
        hashed_password=hash_password("TestPass123!"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_vehicle(db):
    vehicle = Vehicle(
        name="GPS Test Scooter",
        brand="Honda",
        vehicle_type="SCOOTER",
        registration_number="GPS123",
        price_per_day=500,
        status="AVAILABLE",
        current_location="Hyderabad",
        is_available=True,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def auth_headers(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_gps_update_requires_authentication(gps_test_env):
    client, SessionLocal = gps_test_env

    with SessionLocal() as db:
        vehicle = create_vehicle(db)
        vehicle_id = vehicle.id

    response = client.post(
        f"/vehicles/{vehicle_id}/location",
        json={
            "latitude": 17.3850,
            "longitude": 78.4867,
            "speed": 30,
            "heading": 90,
        },
    )

    assert response.status_code == 401


def test_customer_cannot_update_gps_location(gps_test_env):
    client, SessionLocal = gps_test_env

    with SessionLocal() as db:
        user = create_user(db, "gps_customer@example.com")
        vehicle = create_vehicle(db)
        headers = auth_headers(user)
        vehicle_id = vehicle.id

    response = client.post(
        f"/vehicles/{vehicle_id}/location",
        json={
            "latitude": 17.3850,
            "longitude": 78.4867,
            "speed": 30,
            "heading": 90,
        },
        headers=headers,
    )

    assert response.status_code == 403


def test_authorized_staff_can_update_gps_location(gps_test_env):
    client, SessionLocal = gps_test_env

    with SessionLocal() as db:
        user = create_user(
            db,
            "gps_staff@example.com",
            role="STAFF",
        )
        vehicle = create_vehicle(db)
        headers = auth_headers(user)
        vehicle_id = vehicle.id

    response = client.post(
        f"/vehicles/{vehicle_id}/location",
        json={
            "latitude": 17.3850,
            "longitude": 78.4867,
            "speed": 30,
            "heading": 90,
        },
        headers=headers,
    )

    assert response.status_code == 200


def test_gps_update_rejects_invalid_coordinates(gps_test_env):
    client, SessionLocal = gps_test_env

    with SessionLocal() as db:
        user = create_user(
            db,
            "gps_admin@example.com",
            role="ADMIN",
        )
        vehicle = create_vehicle(db)
        headers = auth_headers(user)
        vehicle_id = vehicle.id

    response = client.post(
        f"/vehicles/{vehicle_id}/location",
        json={
            "latitude": 120,
            "longitude": 78.4867,
            "speed": 30,
            "heading": 90,
        },
        headers=headers,
    )

    assert response.status_code == 422
    


def test_get_current_location_requires_authentication(gps_test_env):
    client, SessionLocal = gps_test_env

    with SessionLocal() as db:
        vehicle = create_vehicle(db)
        vehicle_id = vehicle.id

    response = client.get(
        f"/vehicles/{vehicle_id}/location"
    )

    assert response.status_code == 401


def test_get_location_history_requires_authentication(gps_test_env):
    client, SessionLocal = gps_test_env

    with SessionLocal() as db:
        vehicle = create_vehicle(db)
        vehicle_id = vehicle.id

    response = client.get(
        f"/vehicles/{vehicle_id}/location-history"
    )

    assert response.status_code == 401

