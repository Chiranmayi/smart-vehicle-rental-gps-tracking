from fastapi import FastAPI

from app.database import Base, engine
from app import models
from app.routers import auth, vehicles, bookings, maintenance, dashboard


# Create database tables defined by the imported models.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Smart Vehicle Rental & GPS Tracking Platform",
    description=(
        "Backend API for vehicle rentals, bookings, GPS tracking, "
        "maintenance, and fleet management."
    ),
    version="1.0.0",
)


app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(bookings.router)
app.include_router(bookings.rental_router)
app.include_router(maintenance.router)
app.include_router(dashboard.router)


@app.get("/", tags=["Health"])
def home():
    return {
        "message": "Smart Vehicle Rental & GPS Tracking API is running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
