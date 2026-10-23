
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import Maintenance, Vehicle, User
from app.schemas import MaintenanceCreate, MaintenanceUpdate


router = APIRouter(
    prefix="/vehicles",
    tags=["Vehicle Maintenance"],
)


@router.post(
    "/{vehicle_id}/maintenance",
    status_code=status.HTTP_201_CREATED,
)
def create_maintenance(
    vehicle_id: int,
    maintenance_data: MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "FLEET_MANAGER")
    ),
):
    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    if vehicle.status == "RENTED":
        raise HTTPException(
            status_code=409,
            detail="Cannot schedule maintenance while the vehicle is rented",
        )

    maintenance = Maintenance(
        vehicle_id=vehicle_id,
        maintenance_type=maintenance_data.maintenance_type,
        description=maintenance_data.description,
        scheduled_date=maintenance_data.scheduled_date,
        cost=maintenance_data.cost,
        status="SCHEDULED",
    )

    vehicle.status = "MAINTENANCE"
    vehicle.is_available = False

    db.add(maintenance)

    try:
        db.commit()
        db.refresh(maintenance)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create maintenance record",
        )

    return maintenance


@router.get("/{vehicle_id}/maintenance")
def list_maintenance(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "FLEET_MANAGER", "STAFF")
    ),
):
    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    return (
        db.query(Maintenance)
        .filter(Maintenance.vehicle_id == vehicle_id)
        .order_by(Maintenance.scheduled_date.desc())
        .all()
    )


@router.patch("/maintenance/{maintenance_id}")
def update_maintenance(
    maintenance_id: int,
    maintenance_data: MaintenanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("ADMIN", "FLEET_MANAGER")
    ),
):
    maintenance = db.get(Maintenance, maintenance_id)

    if maintenance is None:
        raise HTTPException(
            status_code=404,
            detail="Maintenance record not found",
        )

    updates = maintenance_data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update",
        )

    vehicle = db.get(Vehicle, maintenance.vehicle_id)

    for field, value in updates.items():
        setattr(maintenance, field, value)

    if vehicle is not None:
        if maintenance.status == "COMPLETED":
            other_open_maintenance = (
                db.query(Maintenance)
                .filter(
                    Maintenance.vehicle_id == vehicle.id,
                    Maintenance.id != maintenance.id,
                    Maintenance.status != "COMPLETED",
                )
                .first()
            )

            if (
                other_open_maintenance is None
                and vehicle.status == "MAINTENANCE"
            ):
                vehicle.status = "AVAILABLE"
                vehicle.is_available = True

        elif maintenance.status in ("SCHEDULED", "IN_PROGRESS"):
            if vehicle.status != "RENTED":
                vehicle.status = "MAINTENANCE"
                vehicle.is_available = False

    try:
        db.commit()
        db.refresh(maintenance)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update maintenance record",
        )

    return maintenance
