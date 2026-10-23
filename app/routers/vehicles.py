
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import Vehicle
from app.schemas import (
    VehicleCreate,
    VehicleUpdate,
    VehicleResponse,
    LocationUpdate,
)
from app.algorithms import top_k_nearest
from app.gps import save_location, get_history

router = APIRouter(
    prefix="/vehicles",
    tags=["Vehicles"],
)


def sync_availability(vehicle: Vehicle) -> None:
    """Keep the legacy is_available column consistent with status."""
    vehicle.is_available = vehicle.status == "AVAILABLE"


@router.post("", response_model=VehicleResponse, status_code=201)
def create_vehicle(
    payload: VehicleCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN")),
):
    data = payload.model_dump()
    data["registration_number"] = (
        data["registration_number"].strip().upper()
    )

    existing = (
        db.query(Vehicle)
        .filter(
            Vehicle.registration_number == data["registration_number"]
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Registration number already exists",
        )

    # Derive availability from status, if status was supplied.
    status = data.get("status", "AVAILABLE")
    data["status"] = status
    data["is_available"] = status == "AVAILABLE"

    vehicle = Vehicle(**data)
    db.add(vehicle)

    try:
        db.commit()
        db.refresh(vehicle)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Vehicle conflicts with an existing database record",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error while creating vehicle",
        )

    return vehicle


@router.get("", response_model=list[VehicleResponse])
def list_vehicles(
    category: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    fuel_type: str | None = None,
    transmission: str | None = None,
    location: str | None = None,
    availability: bool | None = None,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
):
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=422,
            detail="min_price cannot be greater than max_price",
        )

    query = db.query(Vehicle)

    if category:
        query = query.filter(
            Vehicle.vehicle_type.ilike(category.strip())
        )

    if brand:
        query = query.filter(
            Vehicle.brand.ilike(f"%{brand.strip()}%")
        )

    if model:
        query = query.filter(
            Vehicle.model.ilike(f"%{model.strip()}%")
        )

    if fuel_type:
        query = query.filter(
            Vehicle.fuel_type.ilike(fuel_type.strip())
        )

    if transmission:
        query = query.filter(
            Vehicle.transmission.ilike(transmission.strip())
        )

    if location:
        query = query.filter(
            Vehicle.current_location.ilike(f"%{location.strip()}%")
        )

    if min_price is not None:
        query = query.filter(
            Vehicle.price_per_day >= min_price
        )

    if max_price is not None:
        query = query.filter(
            Vehicle.price_per_day <= max_price
        )

    if availability is not None:
        if availability:
            query = query.filter(
                Vehicle.is_available.is_(True),
                Vehicle.status == "AVAILABLE",
            )
        else:
            query = query.filter(
                Vehicle.status != "AVAILABLE"
            )

    return query.order_by(Vehicle.id.desc()).all()


@router.get("/nearby")
def nearby_vehicles(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=10, gt=0, le=500),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    vehicles = (
        db.query(Vehicle)
        .filter(
            Vehicle.status == "AVAILABLE",
            Vehicle.is_available.is_(True),
            Vehicle.latitude.is_not(None),
            Vehicle.longitude.is_not(None),
        )
        .all()
    )

    results = top_k_nearest(
        vehicles,
        latitude,
        longitude,
        limit,
    )

    return [
        {
            "distance_km": item["distance_km"],
            "vehicle": VehicleResponse.model_validate(
                item["vehicle"]
            ).model_dump(mode="json"),
        }
        for item in results
        if item["distance_km"] <= radius_km
    ]


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
):
    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    payload: VehicleUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN")),
):
    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    changes = payload.model_dump(exclude_unset=True)

    if "registration_number" in changes and changes["registration_number"]:
        changes["registration_number"] = (
            changes["registration_number"].strip().upper()
        )

        duplicate = (
            db.query(Vehicle)
            .filter(
                Vehicle.registration_number == changes["registration_number"],
                Vehicle.id != vehicle_id,
            )
            .first()
        )

        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Registration number already exists",
            )

    for field, value in changes.items():
        if value is not None:
            setattr(vehicle, field, value)

    # Keep status and availability synchronized.
    sync_availability(vehicle)

    try:
        db.commit()
        db.refresh(vehicle)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Vehicle conflicts with an existing database record",
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error while updating vehicle",
        )

    return vehicle


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles("ADMIN")),
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
            detail="Cannot delete a rented vehicle",
        )

    try:
        db.delete(vehicle)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Cannot delete this vehicle because it has related records",
        )

    return None


@router.post("/{vehicle_id}/location")
def update_location(
    vehicle_id: int,
    payload: LocationUpdate,
    db: Session = Depends(get_db),
    user=Depends(
        require_roles("ADMIN", "FLEET_MANAGER", "STAFF")
    ),
):
    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    data = payload.model_dump()

    if data["timestamp"] is not None:
        data["timestamp"] = data["timestamp"].isoformat()

    try:
        mongo_saved = save_location(vehicle_id, data)
    except Exception:
        mongo_saved = False

    vehicle.latitude = payload.latitude
    vehicle.longitude = payload.longitude

    try:
        db.commit()
        db.refresh(vehicle)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error while updating vehicle location",
        )

    return {
        "message": "Location updated",
        "mongo_saved": mongo_saved,
        "vehicle_id": vehicle_id,
        "latitude": vehicle.latitude,
        "longitude": vehicle.longitude,
    }


@router.get("/{vehicle_id}/location")
def current_location(
    vehicle_id: int,
    db: Session = Depends(get_db),
    user=Depends(
        require_roles("ADMIN", "FLEET_MANAGER", "STAFF")
    ),
):
    vehicle = db.get(Vehicle, vehicle_id)

    if vehicle is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    return {
        "vehicle_id": vehicle.id,
        "latitude": vehicle.latitude,
        "longitude": vehicle.longitude,
        "current_location": vehicle.current_location,
    }


@router.get("/{vehicle_id}/location-history")
def location_history(
    vehicle_id: int,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user=Depends(
        require_roles("ADMIN", "FLEET_MANAGER", "STAFF")
    ),
):
    if db.get(Vehicle, vehicle_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found",
        )

    try:
        locations = get_history(vehicle_id, limit)
    except Exception:
        locations = []

    return {
        "vehicle_id": vehicle_id,
        "locations": locations,
    }
