
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, Vehicle, Maintenance
from app.security import hash_password, create_access_token


@pytest.fixture
def maintenance_env():
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
        admin = User(
            name="Test Admin",
            email="maintenance-admin@example.com",
            hashed_password=hash_password("TestPass123!"),
            role="ADMIN",
            is_active=True,
        )
        staff = User(
            name="Test Staff",
            email="maintenance-staff@example.com",
            hashed_password=hash_password("TestPass123!"),
            role="STAFF",
            is_active=True,
        )
        customer = User(
            name="Test Customer",
            email="maintenance-customer@example.com",
            hashed_password=hash_password("TestPass123!"),
            role="CUSTOMER",
            is_active=True,
        )

        db.add_all([admin, staff, customer])
        db.commit()

        for user in (admin, staff, customer):
            db.refresh(user)

        vehicle = Vehicle(
            name="Maintenance Scooter",
            brand="Honda",
            vehicle_type="SCOOTER",
            registration_number="MAINT001",
            price_per_day=500,
            status="AVAILABLE",
            current_location="Hyderabad",
            is_available=True,
        )
        db.add(vehicle)
        db.commit()
        db.refresh(vehicle)

        vehicle_id = vehicle.id
        admin_token = create_access_token(admin.id, admin.role)
        staff_token = create_access_token(staff.id, staff.role)
        customer_token = create_access_token(customer.id, customer.role)

    with TestClient(app) as client:
        yield {
            "client": client,
            "SessionLocal": TestingSessionLocal,
            "vehicle_id": vehicle_id,
            "admin_headers": {
                "Authorization": f"Bearer {admin_token}"
            },
            "staff_headers": {
                "Authorization": f"Bearer {staff_token}"
            },
            "customer_headers": {
                "Authorization": f"Bearer {customer_token}"
            },
        }

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def maintenance_payload():
    return {
        "maintenance_type": "Oil Change",
        "description": "Replace engine oil and inspect vehicle",
        "scheduled_date": (
            date.today() + timedelta(days=3)
        ).isoformat(),
        "cost": 1200,
    }


def create_maintenance_record(env):
    response = env["client"].post(
        f"/vehicles/{env['vehicle_id']}/maintenance",
        json=maintenance_payload(),
        headers=env["admin_headers"],
    )
    assert response.status_code == 201
    return response.json()


def test_admin_can_create_maintenance(maintenance_env):
    response = maintenance_env["client"].post(
        f"/vehicles/{maintenance_env['vehicle_id']}/maintenance",
        json=maintenance_payload(),
        headers=maintenance_env["admin_headers"],
    )

    assert response.status_code == 201
    data = response.json()
    assert data["maintenance_type"] == "Oil Change"
    assert data["status"] == "SCHEDULED"


def test_create_maintenance_marks_vehicle_unavailable(maintenance_env):
    create_maintenance_record(maintenance_env)

    with maintenance_env["SessionLocal"]() as db:
        vehicle = db.get(Vehicle, maintenance_env["vehicle_id"])
        assert vehicle.status == "MAINTENANCE"
        assert vehicle.is_available is False


def test_customer_cannot_create_maintenance(maintenance_env):
    response = maintenance_env["client"].post(
        f"/vehicles/{maintenance_env['vehicle_id']}/maintenance",
        json=maintenance_payload(),
        headers=maintenance_env["customer_headers"],
    )

    assert response.status_code == 403


def test_create_maintenance_for_missing_vehicle_returns_404(
    maintenance_env,
):
    response = maintenance_env["client"].post(
        "/vehicles/9999/maintenance",
        json=maintenance_payload(),
        headers=maintenance_env["admin_headers"],
    )

    assert response.status_code == 404


def test_cannot_schedule_maintenance_for_rented_vehicle(
    maintenance_env,
):
    with maintenance_env["SessionLocal"]() as db:
        vehicle = db.get(Vehicle, maintenance_env["vehicle_id"])
        vehicle.status = "RENTED"
        vehicle.is_available = False
        db.commit()

    response = maintenance_env["client"].post(
        f"/vehicles/{maintenance_env['vehicle_id']}/maintenance",
        json=maintenance_payload(),
        headers=maintenance_env["admin_headers"],
    )

    assert response.status_code == 409


def test_staff_can_list_maintenance(maintenance_env):
    create_maintenance_record(maintenance_env)

    response = maintenance_env["client"].get(
        f"/vehicles/{maintenance_env['vehicle_id']}/maintenance",
        headers=maintenance_env["staff_headers"],
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["maintenance_type"] == "Oil Change"


def test_customer_cannot_list_maintenance(maintenance_env):
    response = maintenance_env["client"].get(
        f"/vehicles/{maintenance_env['vehicle_id']}/maintenance",
        headers=maintenance_env["customer_headers"],
    )

    assert response.status_code == 403


def test_admin_can_complete_maintenance(maintenance_env):
    record = create_maintenance_record(maintenance_env)

    response = maintenance_env["client"].patch(
        f"/vehicles/maintenance/{record['id']}",
        json={"status": "COMPLETED"},
        headers=maintenance_env["admin_headers"],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"

    with maintenance_env["SessionLocal"]() as db:
        vehicle = db.get(Vehicle, maintenance_env["vehicle_id"])
        assert vehicle.status == "AVAILABLE"
        assert vehicle.is_available is True


def test_update_maintenance_rejects_empty_payload(maintenance_env):
    record = create_maintenance_record(maintenance_env)

    response = maintenance_env["client"].patch(
        f"/vehicles/maintenance/{record['id']}",
        json={},
        headers=maintenance_env["admin_headers"],
    )

    assert response.status_code == 400


def test_customer_cannot_update_maintenance(maintenance_env):
    record = create_maintenance_record(maintenance_env)

    response = maintenance_env["client"].patch(
        f"/vehicles/maintenance/{record['id']}",
        json={"status": "IN_PROGRESS"},
        headers=maintenance_env["customer_headers"],
    )

    assert response.status_code == 403


def test_update_missing_maintenance_returns_404(maintenance_env):
    response = maintenance_env["client"].patch(
        "/vehicles/maintenance/9999",
        json={"status": "COMPLETED"},
        headers=maintenance_env["admin_headers"],
    )

    assert response.status_code == 404


def test_invalid_maintenance_cost_is_rejected(maintenance_env):
    payload = maintenance_payload()
    payload["cost"] = -100

    response = maintenance_env["client"].post(
        f"/vehicles/{maintenance_env['vehicle_id']}/maintenance",
        json=payload,
        headers=maintenance_env["admin_headers"],
    )

    assert response.status_code == 422
