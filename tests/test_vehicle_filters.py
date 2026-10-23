
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, Vehicle
from app.security import hash_password


@pytest.fixture
def vehicle_filter_env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        with TestingSessionLocal() as db:
            vehicles = [
                Vehicle(
                    name="City Scooter",
                    brand="Honda",
                    vehicle_type="SCOOTER",
                    registration_number="FILTER001",
                    price_per_day=500,
                    status="AVAILABLE",
                    current_location="Hyderabad",
                    model="Activa",
                    year=2024,
                    fuel_type="PETROL",
                    transmission="AUTOMATIC",
                    seats=2,
                    is_available=True,
                ),
                Vehicle(
                    name="Family SUV",
                    brand="Toyota",
                    vehicle_type="SUV",
                    registration_number="FILTER002",
                    price_per_day=2000,
                    status="AVAILABLE",
                    current_location="Chennai",
                    model="Innova",
                    year=2023,
                    fuel_type="DIESEL",
                    transmission="MANUAL",
                    seats=7,
                    is_available=True,
                ),
                Vehicle(
                    name="Reserved Sedan",
                    brand="Honda",
                    vehicle_type="SEDAN",
                    registration_number="FILTER003",
                    price_per_day=1200,
                    status="RESERVED",
                    current_location="Hyderabad",
                    model="City",
                    year=2022,
                    fuel_type="PETROL",
                    transmission="MANUAL",
                    seats=5,
                    is_available=False,
                ),
            ]

            db.add_all(vehicles)
            db.commit()

        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_filter_vehicles_by_brand(vehicle_filter_env):
    response = vehicle_filter_env.get(
        "/vehicles",
        params={"brand": "Honda"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all("Honda" in item["brand"] for item in data)


def test_filter_vehicles_by_category(vehicle_filter_env):
    response = vehicle_filter_env.get(
        "/vehicles",
        params={"category": "SUV"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["vehicle_type"] == "SUV"


def test_filter_vehicles_by_location(vehicle_filter_env):
    response = vehicle_filter_env.get(
        "/vehicles",
        params={"location": "Hyderabad"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(
        "Hyderabad" in item["current_location"]
        for item in data
    )


def test_filter_vehicles_by_minimum_price(vehicle_filter_env):
    response = vehicle_filter_env.get(
        "/vehicles",
        params={"min_price": 1000},
    )

    assert response.status_code == 200
    assert all(
        item["price_per_day"] >= 1000
        for item in response.json()
    )


def test_filter_vehicles_by_maximum_price(vehicle_filter_env):
    response = vehicle_filter_env.get(
        "/vehicles",
        params={"max_price": 1000},
    )

    assert response.status_code == 200
    assert all(
        item["price_per_day"] <= 1000
        for item in response.json()
    )


def test_filter_available_vehicles(vehicle_filter_env):
    response = vehicle_filter_env.get(
        "/vehicles",
        params={"availability": "true"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(item["status"] == "AVAILABLE" for item in data)


def test_filter_unavailable_vehicles(vehicle_filter_env):
    response = vehicle_filter_env.get(
        "/vehicles",
        params={"availability": "false"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "RESERVED"


def test_reject_invalid_price_range(vehicle_filter_env):
    response = vehicle_filter_env.get(
        "/vehicles",
        params={
            "min_price": 2000,
            "max_price": 500,
        },
    )

    assert response.status_code == 422
