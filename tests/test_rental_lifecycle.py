
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, Vehicle, Booking
from app.security import hash_password, create_access_token


@pytest.fixture
def rental_env():
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

    with TestingSessionLocal() as db:
        customer = User(
            name="Test Customer",
            email="rental-customer@example.com",
            hashed_password=hash_password("TestPass123!"),
            role="CUSTOMER",
            is_active=True,
        )
        staff = User(
            name="Test Staff",
            email="rental-staff@example.com",
            hashed_password=hash_password("TestPass123!"),
            role="STAFF",
            is_active=True,
        )
        db.add_all([customer, staff])
        db.commit()
        db.refresh(customer)
        db.refresh(staff)

        vehicle = Vehicle(
            name="Test Scooter",
            brand="Honda",
            vehicle_type="SCOOTER",
            registration_number="RENTAL001",
            price_per_day=500,
            status="AVAILABLE",
            current_location="Hyderabad",
            is_available=True,
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)

        booking = Booking(
            user_id=customer.id,
            vehicle_id=vehicle.id,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=12),
            total_price=1000,
            status="CONFIRMED",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        booking_id = booking.id
        vehicle_id = vehicle.id
        customer_id = customer.id
        staff_token = create_access_token(staff.id, staff.role)

    with TestClient(app) as client:
        yield {
            "client": client,
            "SessionLocal": TestingSessionLocal,
            "booking_id": booking_id,
            "vehicle_id": vehicle_id,
            "customer_id": customer_id,
            "staff_headers": {
                "Authorization": f"Bearer {staff_token}"
            },
        }

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_pickup_confirmed_booking(rental_env):
    client = rental_env["client"]

    response = client.post(
        f"/bookings/{rental_env['booking_id']}/pickup",
        json={"odometer": 12000, "fuel_level": 80},
        headers=rental_env["staff_headers"],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"
    assert response.json()["pickup_odometer"] == 12000


def test_pickup_rejects_invalid_fuel_level(rental_env):
    response = rental_env["client"].post(
        f"/bookings/{rental_env['booking_id']}/pickup",
        json={"odometer": 12000, "fuel_level": 120},
        headers=rental_env["staff_headers"],
    )

    assert response.status_code == 422


def test_pickup_updates_vehicle_status(rental_env):
    response = rental_env["client"].post(
        f"/bookings/{rental_env['booking_id']}/pickup",
        json={"odometer": 12000, "fuel_level": 80},
        headers=rental_env["staff_headers"],
    )

    assert response.status_code == 200

    with rental_env["SessionLocal"]() as db:
        vehicle = db.get(Vehicle, rental_env["vehicle_id"])
        assert vehicle.status == "RENTED"
        assert vehicle.is_available is False


def test_return_rejects_booking_not_active(rental_env):
    response = rental_env["client"].post(
        f"/bookings/{rental_env['booking_id']}/return",
        json={"odometer": 12100, "fuel_level": 60},
        headers=rental_env["staff_headers"],
    )

    assert response.status_code == 400


def test_return_rejects_lower_odometer(rental_env):
    client = rental_env["client"]
    headers = rental_env["staff_headers"]
    booking_id = rental_env["booking_id"]

    pickup_response = client.post(
        f"/bookings/{booking_id}/pickup",
        json={"odometer": 12000, "fuel_level": 80},
        headers=headers,
    )
    assert pickup_response.status_code == 200

    return_response = client.post(
        f"/bookings/{booking_id}/return",
        json={"odometer": 11900, "fuel_level": 60},
        headers=headers,
    )

    assert return_response.status_code == 400


def test_return_calculates_final_total(rental_env):
    client = rental_env["client"]
    headers = rental_env["staff_headers"]
    booking_id = rental_env["booking_id"]

    pickup_response = client.post(
        f"/bookings/{booking_id}/pickup",
        json={"odometer": 12000, "fuel_level": 80},
        headers=headers,
    )
    assert pickup_response.status_code == 200

    return_response = client.post(
        f"/bookings/{booking_id}/return",
        json={
            "odometer": 12100,
            "fuel_level": 60,
            "cleaning_charge": 100,
            "damage_charge": 50,
        },
        headers=headers,
    )

    assert return_response.status_code == 200
    data = return_response.json()
    assert data["status"] == "COMPLETED"
    assert data["final_total"] == 1150


def test_return_updates_vehicle_status(rental_env):
    client = rental_env["client"]
    headers = rental_env["staff_headers"]
    booking_id = rental_env["booking_id"]

    pickup_response = client.post(
        f"/bookings/{booking_id}/pickup",
        json={"odometer": 12000, "fuel_level": 80},
        headers=headers,
    )
    assert pickup_response.status_code == 200

    return_response = client.post(
        f"/bookings/{booking_id}/return",
        json={"odometer": 12100, "fuel_level": 60},
        headers=headers,
    )
    assert return_response.status_code == 200

    with rental_env["SessionLocal"]() as db:
        vehicle = db.get(Vehicle, rental_env["vehicle_id"])
        assert vehicle.status == "AVAILABLE"
        assert vehicle.is_available is True
