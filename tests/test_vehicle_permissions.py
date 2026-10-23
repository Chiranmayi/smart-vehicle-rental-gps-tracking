
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db
from app.models import User
from app.security import hash_password, create_access_token

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest


@pytest.fixture
def customer_client():
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

    from app.database import Base
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
            email="vehicle-customer@example.com",
            hashed_password=hash_password("TestPass123!"),
            role="CUSTOMER",
            is_active=True,
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        token = create_access_token(customer.id, customer.role)

    with TestClient(app) as client:
        client.headers.update(
            {"Authorization": f"Bearer {token}"}
        )
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_customer_cannot_create_vehicle(customer_client):
    response = customer_client.post(
        "/vehicles",
        json={
            "name": "Test Car",
            "brand": "Toyota",
            "vehicle_type": "CAR",
            "registration_number": "CUSTOMER123",
            "price_per_day": 1500,
            "status": "AVAILABLE",
            "current_location": "Hyderabad",
        },
    )
    assert response.status_code == 403


def test_customer_cannot_update_vehicle(customer_client):
    response = customer_client.put(
        "/vehicles/1",
        json={"name": "Updated Car"},
    )
    assert response.status_code == 403


def test_customer_cannot_delete_vehicle(customer_client):
    response = customer_client.delete("/vehicles/1")
    assert response.status_code == 403
