# Smart Vehicle Rental & GPS Tracking Platform

A backend API built with FastAPI for managing vehicle rentals, bookings, GPS tracking, maintenance, and fleet operations.

## Features

- User registration, login, and JWT authentication
- Role-based access control for customers, administrators, fleet managers, and staff
- Vehicle creation, management, filtering, and nearby search
- Booking creation, confirmation, cancellation, and extension
- Rental pickup and return with odometer and fuel details
- Rental pricing with weekend, peak-season, and long-rental adjustments
- GPS location updates and location history
- MongoDB-based GPS history storage
- Vehicle maintenance management
- Fleet dashboard and reporting endpoints
- Automated tests using pytest

## Technology Stack

- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL
- MongoDB
- Pydantic
- JWT authentication
- pytest

## Project Structure

text
vehicle-rental/
├── app/
│   ├── routers/
│   ├── algorithms.py
│   ├── config.py
│   ├── database.py
│   ├── gps.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   └── security.py
├── docs/
├── screenshots/
├── tests/
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md


## Setup

### 1. Clone the repository

bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd vehicle-rental


Replace `YOUR_GITHUB_REPOSITORY_URL` with your repository URL.

### 2. Create and activate a virtual environment

On Windows PowerShell:

`powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1


### 3. Install dependencies

powershell
python -m pip install -r requirements.txt


### 4. Configure environment variables

Create a local `.env` file using `.env.example` as a template.

Configure the PostgreSQL connection URL, a strong JWT secret, and the MongoDB connection settings. Make sure both databases are available before running the application.

Never commit real passwords, connection credentials, or JWT secrets.

### 5. Start the API

powershell
python -m uvicorn app.main:app --reload


### 6. Open the API documentation

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/health

## Run Tests
powershell
python -m pytest -v


The current test suite has **69 passing tests** in the development environment. Results may depend on the database configuration and available services.

## Algorithms

The project includes:

- **Haversine distance:** calculates the distance between GPS coordinates.
- **Booking overlap detection:** identifies conflicting rental date ranges.
- **Top-K nearest vehicles:** selects nearby vehicles based on GPS distance.

## Project Status

The backend includes authentication, vehicle management, bookings, rental lifecycle operations, GPS endpoints, maintenance, dashboard endpoints, and automated tests.

Additional deployment, integration, and frontend requirements should be verified against the project specification before claiming full assignment completion.
