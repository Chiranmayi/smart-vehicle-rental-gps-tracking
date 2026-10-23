
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
def booking_test_env():
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


def create_customer(db, email):
    user = User(
        name="Test Customer",
        email=email,
        hashed_password=hash_password("TestPass123!"),
        role="CUSTOMER",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_vehicle(db):
    vehicle = Vehicle(
        name="Test Scooter",
        brand="Honda",
        vehicle_type="SCOOTER",
        registration_number="TEST123",
        price_per_day=500,
        status="AVAILABLE",
        current_location="Hyderabad",
        is_available=True,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def customer_headers(user):
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_create_booking_success(booking_test_env):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        user = create_customer(db, "booking1@example.com")
        vehicle = create_vehicle(db)
        vehicle_id = vehicle.id
        headers = customer_headers(user)

    start_date = date.today() + timedelta(days=10)
    end_date = start_date + timedelta(days=2)

    response = client.post(
        "/bookings/",
        json={
            "vehicle_id": vehicle_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["vehicle_id"] == vehicle_id
    assert data["status"] == "PENDING"
    assert data["total_price"] > 0


def test_create_booking_rejects_invalid_dates(booking_test_env):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        user = create_customer(db, "booking2@example.com")
        vehicle = create_vehicle(db)
        vehicle_id = vehicle.id
        headers = customer_headers(user)

    start_date = date.today() + timedelta(days=10)
    end_date = start_date - timedelta(days=1)

    response = client.post(
        "/bookings/",
        json={
            "vehicle_id": vehicle_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_customer_can_cancel_own_booking(booking_test_env):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        user = create_customer(db, "booking3@example.com")
        vehicle = create_vehicle(db)

        booking = Booking(
            user_id=user.id,
            vehicle_id=vehicle.id,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=12),
            total_price=1000,
            status="PENDING",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        booking_id = booking.id
        headers = customer_headers(user)

    response = client.patch(
        f"/bookings/{booking_id}/cancel",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


def test_customer_cannot_view_another_customers_booking(
    booking_test_env,
):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        owner = create_customer(db, "owner@example.com")
        other_customer = create_customer(db, "other@example.com")
        vehicle = create_vehicle(db)

        booking = Booking(
            user_id=owner.id,
            vehicle_id=vehicle.id,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=12),
            total_price=1000,
            status="PENDING",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        booking_id = booking.id
        other_headers = customer_headers(other_customer)

    response = client.get(
        f"/bookings/{booking_id}",
        headers=other_headers,
    )

    assert response.status_code == 403


def test_overlapping_booking_is_rejected(booking_test_env):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        user1 = create_customer(db, "conflict1@example.com")
        user2 = create_customer(db, "conflict2@example.com")
        vehicle = create_vehicle(db)
        vehicle_id = vehicle.id
        headers1 = customer_headers(user1)
        headers2 = customer_headers(user2)

    start_date = date.today() + timedelta(days=20)
    end_date = start_date + timedelta(days=3)

    first_response = client.post(
        "/bookings/",
        json={
            "vehicle_id": vehicle_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        headers=headers1,
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/bookings/",
        json={
            "vehicle_id": vehicle_id,
            "start_date": (start_date + timedelta(days=1)).isoformat(),
            "end_date": (end_date + timedelta(days=1)).isoformat(),
        },
        headers=headers2,
    )

    assert second_response.status_code == 409


def test_non_overlapping_booking_is_allowed(booking_test_env):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        user1 = create_customer(db, "separate1@example.com")
        user2 = create_customer(db, "separate2@example.com")
        vehicle = create_vehicle(db)
        vehicle_id = vehicle.id
        headers1 = customer_headers(user1)
        headers2 = customer_headers(user2)

    start_date = date.today() + timedelta(days=20)
    end_date = start_date + timedelta(days=3)

    first_response = client.post(
        "/bookings/",
        json={
            "vehicle_id": vehicle_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        headers=headers1,
    )
    assert first_response.status_code == 201

    second_start = end_date
    second_end = second_start + timedelta(days=3)

    second_response = client.post(
        "/bookings/",
        json={
            "vehicle_id": vehicle_id,
            "start_date": second_start.isoformat(),
            "end_date": second_end.isoformat(),
        },
        headers=headers2,
    )

    assert second_response.status_code == 201


# ---------------- BOOKING EXTENSION TESTS ----------------

def test_customer_can_extend_own_confirmed_booking(booking_test_env):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        user = create_customer(db, "extend-owner@example.com")
        vehicle = create_vehicle(db)

        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=2)

        booking = Booking(
            user_id=user.id,
            vehicle_id=vehicle.id,
            start_date=start_date,
            end_date=end_date,
            total_price=1000,
            status="CONFIRMED",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        booking_id = booking.id
        headers = customer_headers(user)

    new_end_date = end_date + timedelta(days=2)

    response = client.patch(
        f"/bookings/{booking_id}/extend",
        params={"new_end_date": new_end_date.isoformat()},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["end_date"] == new_end_date.isoformat()
    assert data["total_price"] > 1000


def test_extension_rejects_same_or_earlier_end_date(booking_test_env):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        user = create_customer(db, "extend-invalid@example.com")
        vehicle = create_vehicle(db)

        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=3)

        booking = Booking(
            user_id=user.id,
            vehicle_id=vehicle.id,
            start_date=start_date,
            end_date=end_date,
            total_price=1500,
            status="CONFIRMED",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        booking_id = booking.id
        headers = customer_headers(user)

    response = client.patch(
        f"/bookings/{booking_id}/extend",
        params={"new_end_date": end_date.isoformat()},
        headers=headers,
    )

    assert response.status_code == 400


def test_extension_rejects_conflict_with_another_booking(
    booking_test_env,
):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        owner = create_customer(db, "extend-conflict-owner@example.com")
        other_user = create_customer(db, "extend-conflict-other@example.com")
        vehicle = create_vehicle(db)

        start_date = date.today() + timedelta(days=10)
        original_end_date = start_date + timedelta(days=2)

        booking = Booking(
            user_id=owner.id,
            vehicle_id=vehicle.id,
            start_date=start_date,
            end_date=original_end_date,
            total_price=1000,
            status="CONFIRMED",
        )

        other_booking = Booking(
            user_id=other_user.id,
            vehicle_id=vehicle.id,
            start_date=original_end_date + timedelta(days=1),
            end_date=original_end_date + timedelta(days=4),
            total_price=1500,
            status="CONFIRMED",
        )

        db.add_all([booking, other_booking])
        db.commit()
        db.refresh(booking)

        booking_id = booking.id
        headers = customer_headers(owner)

    response = client.patch(
        f"/bookings/{booking_id}/extend",
        params={
            "new_end_date": (
                original_end_date + timedelta(days=2)
            ).isoformat()
        },
        headers=headers,
    )

    assert response.status_code == 409


def test_customer_cannot_extend_another_customers_booking(
    booking_test_env,
):
    client, SessionLocal = booking_test_env

    with SessionLocal() as db:
        owner = create_customer(db, "extend-private-owner@example.com")
        other_user = create_customer(db, "extend-private-other@example.com")
        vehicle = create_vehicle(db)

        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=2)

        booking = Booking(
            user_id=owner.id,
            vehicle_id=vehicle.id,
            start_date=start_date,
            end_date=end_date,
            total_price=1000,
            status="CONFIRMED",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        booking_id = booking.id
        other_headers = customer_headers(other_user)

    response = client.patch(
        f"/bookings/{booking_id}/extend",
        params={
            "new_end_date": (
                end_date + timedelta(days=2)
            ).isoformat()
        },
        headers=other_headers,
    )

    assert response.status_code == 403
