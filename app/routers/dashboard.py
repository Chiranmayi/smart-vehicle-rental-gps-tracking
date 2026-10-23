
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import require_roles
from app.models import Vehicle, Booking, Maintenance

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN", "FLEET_MANAGER")),
):
    total_vehicles = db.query(Vehicle).count()

    available_vehicles = (
        db.query(Vehicle)
        .filter(Vehicle.status == "AVAILABLE")
        .count()
    )

    rented_vehicles = (
        db.query(Vehicle)
        .filter(Vehicle.status == "RENTED")
        .count()
    )

    maintenance_vehicles = (
        db.query(Vehicle)
        .filter(Vehicle.status == "MAINTENANCE")
        .count()
    )

    total_bookings = db.query(Booking).count()

    pending_bookings = (
        db.query(Booking)
        .filter(Booking.status == "PENDING")
        .count()
    )

    active_bookings = (
        db.query(Booking)
        .filter(Booking.status == "ACTIVE")
        .count()
    )

    completed_bookings = (
        db.query(Booking)
        .filter(Booking.status == "COMPLETED")
        .count()
    )

    total_maintenance_records = db.query(Maintenance).count()

    revenue = (
        db.query(
            func.coalesce(
                func.sum(
                    func.coalesce(
                        Booking.final_total,
                        Booking.total_price,
                    )
                ),
                0,
            )
        )
        .filter(Booking.status == "COMPLETED")
        .scalar()
    )

    return {
        "fleet": {
            "total_vehicles": total_vehicles,
            "available_vehicles": available_vehicles,
            "rented_vehicles": rented_vehicles,
            "maintenance_vehicles": maintenance_vehicles,
        },
        "bookings": {
            "total_bookings": total_bookings,
            "pending_bookings": pending_bookings,
            "active_bookings": active_bookings,
            "completed_bookings": completed_bookings,
        },
        "maintenance": {
            "total_records": total_maintenance_records,
        },
        "revenue": {
            "completed_booking_revenue": float(revenue or 0),
        },
    }


@router.get("/fleet")
def fleet_status(
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN", "FLEET_MANAGER")),
):
    results = (
        db.query(Vehicle.status, func.count(Vehicle.id))
        .group_by(Vehicle.status)
        .all()
    )

    return {
        "fleet_status": [
            {"status": status, "count": count}
            for status, count in results
        ]
    }


@router.get("/bookings")
def booking_statistics(
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN", "FLEET_MANAGER")),
):
    results = (
        db.query(Booking.status, func.count(Booking.id))
        .group_by(Booking.status)
        .all()
    )

    return {
        "booking_statistics": [
            {"status": status, "count": count}
            for status, count in results
        ]
    }

@router.get("")
def dashboard(
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN", "FLEET_MANAGER")),
):
    return dashboard_summary(db=db, user=user)


@router.get("/revenue")
def dashboard_revenue(
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN", "FLEET_MANAGER")),
):
    revenue = (
        db.query(
            func.coalesce(
                func.sum(
                    func.coalesce(
                        Booking.final_total,
                        Booking.total_price,
                    )
                ),
                0,
            )
        )
        .filter(Booking.status == "COMPLETED")
        .scalar()
    )

    return {"completed_booking_revenue": float(revenue or 0)}


@router.get("/utilization")
def dashboard_utilization(
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN", "FLEET_MANAGER")),
):
    total_vehicles = db.query(Vehicle).count()
    rented_vehicles = (
        db.query(Vehicle)
        .filter(Vehicle.status == "RENTED")
        .count()
    )

    utilization_percentage = (
        round((rented_vehicles / total_vehicles) * 100, 2)
        if total_vehicles
        else 0
    )

    return {
        "total_vehicles": total_vehicles,
        "rented_vehicles": rented_vehicles,
        "utilization_percentage": utilization_percentage,
    }
