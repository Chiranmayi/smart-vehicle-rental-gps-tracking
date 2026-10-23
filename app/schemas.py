
from datetime import datetime, date
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


Role = Literal["CUSTOMER", "ADMIN", "FLEET_MANAGER", "STAFF"]

VehicleType = Literal[
    "BIKE", "SCOOTER", "HATCHBACK", "SEDAN", "SUV", "PREMIUM"
]

VehicleStatus = Literal[
    "AVAILABLE", "RESERVED", "RENTED", "MAINTENANCE",
    "DAMAGED", "BLOCKED", "INACTIVE"
]

BookingStatus = Literal[
    "PENDING", "CONFIRMED", "ACTIVE",
    "COMPLETED", "CANCELLED", "EXPIRED"
]


# ---------------- AUTHENTICATION ----------------

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------- VEHICLES ----------------

class VehicleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    brand: str = Field(min_length=1, max_length=100)
    vehicle_type: VehicleType
    registration_number: str = Field(min_length=3, max_length=30)
    price_per_day: float = Field(gt=0)

    current_location: str = "Hyderabad"
    model: str = "Standard"
    year: int = Field(default=2024, ge=1990, le=2100)
    fuel_type: str = "PETROL"
    transmission: str = "MANUAL"
    seats: int = Field(default=2, ge=1, le=60)

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    gps_device_id: str | None = None


class VehicleUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    vehicle_type: VehicleType | None = None
    registration_number: str | None = None
    price_per_day: float | None = Field(default=None, gt=0)

    current_location: str | None = None
    model: str | None = None
    year: int | None = Field(default=None, ge=1990, le=2100)
    fuel_type: str | None = None
    transmission: str | None = None
    seats: int | None = Field(default=None, ge=1, le=60)

    status: VehicleStatus | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    brand: str
    vehicle_type: str
    registration_number: str
    price_per_day: float
    status: str
    current_location: str
    model: str
    year: int
    fuel_type: str
    transmission: str
    seats: int
    latitude: float | None
    longitude: float | None
    gps_device_id: str | None


# ---------------- BOOKINGS ----------------

class BookingCreate(BaseModel):
    vehicle_id: int
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")

        if self.start_date < date.today():
            raise ValueError("start_date cannot be in the past")

        return self


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    vehicle_id: int
    start_date: date
    end_date: date
    total_price: float
    status: str

    pickup_time: datetime | None = None
    return_time: datetime | None = None

    # Pickup and return details
    pickup_odometer: float | None = None
    return_odometer: float | None = None
    pickup_fuel_level: float | None = None
    return_fuel_level: float | None = None

    final_total: float | None = None


# ---------------- GPS TRACKING ----------------

class LocationUpdate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timestamp: datetime | None = None
    speed: float = Field(default=0, ge=0)
    heading: float = Field(default=0, ge=0, le=360)


# ---------------- RENTAL PICKUP AND RETURN ----------------

class PickupRequest(BaseModel):
    odometer: float = Field(ge=0)
    fuel_level: float = Field(ge=0, le=100)


class ReturnRequest(BaseModel):
    odometer: float = Field(ge=0)
    fuel_level: float = Field(ge=0, le=100)

    # Existing return charges
    cleaning_charge: float = Field(default=0, ge=0)
    damage_charge: float = Field(default=0, ge=0)
    extra_km_charge: float = Field(default=0, ge=0)

    # Additional return charges
    late_fee: float = Field(default=0, ge=0)
    fuel_charge: float = Field(default=0, ge=0)
    delivery_charge: float = Field(default=0, ge=0)
    insurance_charge: float = Field(default=0, ge=0)


# ---------------- MAINTENANCE ----------------

class MaintenanceCreate(BaseModel):
    maintenance_type: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=3, max_length=500)
    scheduled_date: date
    cost: float = Field(default=0, ge=0)


class MaintenanceUpdate(BaseModel):
    maintenance_type: str | None = Field(
        default=None, min_length=2, max_length=100
    )
    description: str | None = Field(
        default=None, min_length=3, max_length=500
    )
    scheduled_date: date | None = None
    cost: float | None = Field(default=None, ge=0)
    status: Literal[
        "SCHEDULED", "IN_PROGRESS", "COMPLETED"
    ] | None = None
