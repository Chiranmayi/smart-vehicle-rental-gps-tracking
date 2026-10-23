
from datetime import date, datetime

from sqlalchemy import (
    String,
    Integer,
    Float,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CUSTOMER",
        server_default="CUSTOMER",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    brand: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    vehicle_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    registration_number: Mapped[str] = mapped_column(
        String(30), unique=True, index=True, nullable=False
    )
    price_per_day: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="AVAILABLE",
        server_default="AVAILABLE",
    )
    current_location: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        default="Hyderabad",
        server_default="Hyderabad",
    )

    # Additional vehicle details
    model: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default="Standard"
    )
    year: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=2024
    )
    fuel_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True, default="PETROL"
    )
    transmission: Mapped[str | None] = mapped_column(
        String(30), nullable=True, default="MANUAL"
    )
    seats: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=2
    )

    # GPS coordinates
    latitude: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    longitude: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    gps_device_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    # Legacy column already present in your database
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id"), nullable=False, index=True
    )

    # Keep DATE to match your existing PostgreSQL columns.
    start_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    end_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )

    total_price: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )

    # Pickup and return information
    pickup_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    return_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pickup_odometer: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    return_odometer: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    pickup_fuel_level: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    return_fuel_level: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    final_total: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )


class Maintenance(Base):
    __tablename__ = "maintenance"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id"), nullable=False, index=True
    )
    maintenance_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    description: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    scheduled_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="SCHEDULED",
        server_default="SCHEDULED",
    )
