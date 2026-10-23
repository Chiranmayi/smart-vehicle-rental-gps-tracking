
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import Booking, Vehicle, User
from app.schemas import (
    BookingCreate,
    BookingResponse,
    PickupRequest,
    ReturnRequest,
)
from app.algorithms import overlaps


# -------------------- ROUTERS --------------------

router = APIRouter(prefix="/bookings", tags=["Bookings"])
rental_router = APIRouter(prefix="/rentals", tags=["Rentals"])


# -------------------- SHARED BOOKING LOGIC --------------------

def _list_bookings(db: Session, current_user: User):
    """Return all bookings for staff, or only the customer's own bookings."""
    query = db.query(Booking)

    if current_user.role == "CUSTOMER":
        query = query.filter(Booking.user_id == current_user.id)

    return query.order_by(Booking.id.desc()).all()


def _calculate_rental_price(
    price_per_day: float,
    start_date: date,
    end_date: date,
) -> float:
    """Calculate rental price using weekend, peak-season and long-rental rules.

    Saturday/Sunday: 20% surcharge.
    December/January: 30% surcharge.
    Rentals lasting 7 or more days: 10% discount.
    """
    duration_days = (end_date - start_date).days

    if duration_days <= 0:
        raise HTTPException(
            status_code=400,
            detail="Rental duration must be at least one day",
        )

    total_price = 0.0

    for day_number in range(duration_days):
        rental_date = date.fromordinal(
            start_date.toordinal() + day_number
        )
        daily_price = price_per_day

        if rental_date.weekday() >= 5:
            daily_price *= 1.20

        if rental_date.month in (12, 1):
            daily_price *= 1.30

        total_price += daily_price

    if duration_days >= 7:
        total_price *= 0.90

    return round(total_price, 2)


def _extend_booking(
    booking_id: int,
    new_end_date: date,
    db: Session,
    current_user: User,
):
    """Shared logic for extending a booking or rental."""
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if (
        current_user.role == "CUSTOMER"
        and booking.user_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    if booking.status not in ["CONFIRMED", "ACTIVE"]:
        raise HTTPException(
            status_code=400,
            detail="Only confirmed or active bookings can be extended",
        )

    if new_end_date <= booking.end_date:
        raise HTTPException(
            status_code=400,
            detail="New end date must be later than the current end date",
        )

    other_bookings = (
        db.query(Booking)
        .filter(
            Booking.vehicle_id == booking.vehicle_id,
            Booking.id != booking.id,
            Booking.status.in_(["PENDING", "CONFIRMED", "ACTIVE"]),
        )
        .all()
    )

    for other in other_bookings:
        if overlaps(
            booking.start_date,
            new_end_date,
            other.start_date,
            other.end_date,
        ):
            raise HTTPException(
                status_code=409,
                detail="Extension conflicts with another booking",
            )

    vehicle = db.get(Vehicle, booking.vehicle_id)

    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    booking.total_price = _calculate_rental_price(
        price_per_day=vehicle.price_per_day,
        start_date=booking.start_date,
        end_date=new_end_date,
    )
    booking.end_date = new_end_date

    db.commit()
    db.refresh(booking)

    return booking


def _pickup_vehicle(
    booking_id: int,
    pickup_data: PickupRequest,
    db: Session,
):
    """Shared logic for picking up a confirmed rental."""
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "CONFIRMED":
        raise HTTPException(
            status_code=400,
            detail="Only confirmed bookings can be picked up",
        )

    vehicle = db.get(Vehicle, booking.vehicle_id)

    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    booking.status = "ACTIVE"
    booking.pickup_time = datetime.now(timezone.utc)
    booking.pickup_odometer = pickup_data.odometer
    booking.pickup_fuel_level = pickup_data.fuel_level

    vehicle.status = "RENTED"
    vehicle.is_available = False

    db.commit()
    db.refresh(booking)

    return booking


def _return_vehicle(
    booking_id: int,
    return_data: ReturnRequest,
    db: Session,
):
    """Shared logic for returning an active rental."""
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail="Only active rentals can be returned",
        )

    vehicle = db.get(Vehicle, booking.vehicle_id)

    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    if (
        booking.pickup_odometer is not None
        and return_data.odometer < booking.pickup_odometer
    ):
        raise HTTPException(
            status_code=400,
            detail="Return odometer cannot be lower than pickup odometer",
        )

    booking.status = "COMPLETED"
    booking.return_time = datetime.now(timezone.utc)
    booking.return_odometer = return_data.odometer
    booking.return_fuel_level = return_data.fuel_level

    # Charge ₹500 when the return date is later than the booking end date.
    calculated_late_fee = (
        500.0 if booking.return_time.date() > booking.end_date else 0.0
    )

    extra_charges = (
        return_data.cleaning_charge
        + return_data.damage_charge
        + return_data.extra_km_charge
        + calculated_late_fee
        + return_data.fuel_charge
        + return_data.delivery_charge
        + return_data.insurance_charge
    )

    booking.final_total = round(
        booking.total_price + extra_charges,
        2,
    )

    future_confirmed = (
        db.query(Booking)
        .filter(
            Booking.vehicle_id == vehicle.id,
            Booking.id != booking.id,
            Booking.status == "CONFIRMED",
            Booking.start_date > date.today(),
        )
        .count()
    )

    if vehicle.status != "MAINTENANCE" and future_confirmed == 0:
        vehicle.status = "AVAILABLE"
        vehicle.is_available = True

    db.commit()
    db.refresh(booking)

    return booking


# -------------------- BOOKING ENDPOINTS --------------------

@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = db.get(Vehicle, booking_data.vehicle_id)

    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    if vehicle.status != "AVAILABLE" or not vehicle.is_available:
        raise HTTPException(
            status_code=400,
            detail="Vehicle is not available for booking",
        )

    if booking_data.start_date < date.today():
        raise HTTPException(
            status_code=400,
            detail="Booking start date cannot be in the past",
        )

    existing_bookings = (
        db.query(Booking)
        .filter(
            Booking.vehicle_id == vehicle.id,
            Booking.status.in_(["PENDING", "CONFIRMED", "ACTIVE"]),
        )
        .all()
    )

    for existing in existing_bookings:
        if overlaps(
            booking_data.start_date,
            booking_data.end_date,
            existing.start_date,
            existing.end_date,
        ):
            raise HTTPException(
                status_code=409,
                detail="Vehicle is already booked for these dates",
            )

    total_price = _calculate_rental_price(
        price_per_day=vehicle.price_per_day,
        start_date=booking_data.start_date,
        end_date=booking_data.end_date,
    )

    booking = Booking(
        user_id=current_user.id,
        vehicle_id=vehicle.id,
        start_date=booking_data.start_date,
        end_date=booking_data.end_date,
        total_price=total_price,
        status="PENDING",
    )

    db.add(booking)
    db.commit()
    db.refresh(booking)

    return booking


@router.get("/", response_model=list[BookingResponse])
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list_bookings(db, current_user)


@rental_router.get("", response_model=list[BookingResponse])
def list_rentals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _list_bookings(db, current_user)


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if (
        current_user.role == "CUSTOMER"
        and booking.user_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    return booking


@router.patch("/{booking_id}/confirm", response_model=BookingResponse)
def confirm_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN")),
):
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail="Only pending bookings can be confirmed",
        )

    vehicle = db.get(Vehicle, booking.vehicle_id)

    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    other_bookings = (
        db.query(Booking)
        .filter(
            Booking.vehicle_id == vehicle.id,
            Booking.id != booking.id,
            Booking.status.in_(["CONFIRMED", "ACTIVE"]),
        )
        .all()
    )

    for other in other_bookings:
        if overlaps(
            booking.start_date,
            booking.end_date,
            other.start_date,
            other.end_date,
        ):
            raise HTTPException(
                status_code=409,
                detail="Another confirmed booking overlaps these dates",
            )

    booking.status = "CONFIRMED"
    vehicle.status = "RESERVED"
    vehicle.is_available = False

    db.commit()
    db.refresh(booking)

    return booking


@router.patch("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    booking = db.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if (
        current_user.role == "CUSTOMER"
        and booking.user_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    if booking.status not in ["PENDING", "CONFIRMED"]:
        raise HTTPException(
            status_code=400,
            detail="Only pending or confirmed bookings can be cancelled",
        )

    was_confirmed = booking.status == "CONFIRMED"
    booking.status = "CANCELLED"

    if was_confirmed:
        vehicle = db.get(Vehicle, booking.vehicle_id)

        if vehicle is not None:
            other_bookings = (
                db.query(Booking)
                .filter(
                    Booking.vehicle_id == vehicle.id,
                    Booking.id != booking.id,
                    Booking.status.in_(["CONFIRMED", "ACTIVE"]),
                )
                .all()
            )

            has_conflict = any(
                overlaps(
                    booking.start_date,
                    booking.end_date,
                    other.start_date,
                    other.end_date,
                )
                for other in other_bookings
            )

            if not has_conflict and vehicle.status == "RESERVED":
                vehicle.status = "AVAILABLE"
                vehicle.is_available = True

    db.commit()
    db.refresh(booking)

    return booking


@router.patch("/{booking_id}/extend", response_model=BookingResponse)
def extend_booking(
    booking_id: int,
    new_end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _extend_booking(booking_id, new_end_date, db, current_user)


@rental_router.patch("/{booking_id}/extend", response_model=BookingResponse)
def extend_rental(
    booking_id: int,
    new_end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _extend_booking(booking_id, new_end_date, db, current_user)


@router.post("/{booking_id}/pickup", response_model=BookingResponse)
def pickup_booking(
    booking_id: int,
    pickup_data: PickupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "STAFF")),
):
    return _pickup_vehicle(booking_id, pickup_data, db)


@rental_router.post("/{booking_id}/pickup", response_model=BookingResponse)
def pickup_rental(
    booking_id: int,
    pickup_data: PickupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "STAFF")),
):
    return _pickup_vehicle(booking_id, pickup_data, db)


@router.post("/{booking_id}/return", response_model=BookingResponse)
def return_booking(
    booking_id: int,
    return_data: ReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "STAFF")),
):
    return _return_vehicle(booking_id, return_data, db)


@rental_router.post("/{booking_id}/return", response_model=BookingResponse)
def return_rental(
    booking_id: int,
    return_data: ReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN", "STAFF")),
):
    return _return_vehicle(booking_id, return_data, db)
