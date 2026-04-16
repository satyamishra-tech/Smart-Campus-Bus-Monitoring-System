# Smart Campus Bus Monitoring System

A full-stack campus bus tracking and management solution with a Flutter mobile client, FastAPI backend, PostgreSQL database, GPS simulation, route administration, and ETA estimation.

## Project Overview

This project provides:

- Real-time bus GPS tracking and location updates
- Administrative management for routes, buses, drivers, and student assignments
- Bus route details, stop management, and route geometry retrieval via OpenRouteService
- Estimated time of arrival (ETA) calculation for buses to stops
- Driver GPS upload endpoint and route simulation support
- Flutter mobile interface for students and staff

## Architecture

- `backend/`
  - FastAPI application serving REST APIs
  - PostgreSQL database with SQLAlchemy models
  - JWT authentication for secure access
  - Admin static dashboard at `/admin`
  - GPS simulator for active bus route simulations
- `flutter_app/`
  - Flutter client application for mobile use
  - UI and services for interacting with backend APIs
- `docker/`
  - Docker Compose configuration for PostgreSQL and API service

## Features

- User authentication and role-based access (student, driver, admin)
- Route creation, stop management, and route detail retrieval
- Bus registration, driver assignment, and route assignment
- Student route assignment and fee payment tracking
- Active bus listing and latest location retrieval
- ETA calculation based on latest GPS data and average speed
- Simulation endpoints for bus movement testing
- Admin static page for quick administrative access

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Flutter SDK (for mobile app development)
- Python 3.11+ or compatible environment

### Run with Docker Compose

From the repository root:

```bash
cd i:\Confidential\ITM BUS MANAGEMENT\Smart-Campus-Bus-Monitoring-System\docker
docker compose up --build
```

This starts:

- `postgres` on port `5432`
- `fastapi` on port `8000`

The API will be reachable at `http://localhost:8000`.

### Backend Environment Variables

The backend can also run outside Docker if you provide the following environment variables:

- `DATABASE_URL` (e.g. `postgresql://postgres:Password@localhost:5432/campus_bus_db`)
- `SECRET_KEY`
- `ALGORITHM` (default: `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default: `60`)
- `ORS_API_KEY` (optional for route geometry)

### Run Backend Locally

From `backend/`:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Run Flutter App

From `flutter_app/`:

```bash
flutter pub get
flutter run
```

## API Highlights

### Authentication

- `POST /api/v1/auth/login` — student/driver login with `roll_number` and `password`
- `POST /api/v1/auth/admin-login` — quick admin token generation for local testing
- `POST /api/v1/auth/register` — register a new user

### Admin Management

- `POST /api/v1/admin/routes` — create routes with stops
- `GET /api/v1/admin/routes` — list all routes
- `GET /api/v1/admin/users` — list users
- `GET /api/v1/admin/buses` — list buses
- `GET /api/v1/admin/drivers` — list driver accounts
- `POST /api/v1/admin/buses` — create a bus
- `POST /api/v1/admin/buses/{bus_id}/assign-driver` — assign driver
- `POST /api/v1/admin/buses/{bus_id}/route` — assign route to bus
- `PATCH /api/v1/admin/students/{roll_number}/route` — assign student route
- `PATCH /api/v1/admin/students/{roll_number}/fee` — update student fee status

### Route and Bus APIs

- `GET /api/v1/routes` — list all routes
- `GET /api/v1/routes/{route_id}` — route details including stops and geometry
- `PATCH /api/v1/routes/{route_id}/stops/{stop_id}` — update stop data
- `DELETE /api/v1/routes/{route_id}/stops/{stop_id}` — delete a stop
- `GET /api/v1/buses/` — list active buses with latest positions
- `GET /api/v1/buses/{bus_id}/latest` — latest GPS location for a bus
- `GET /api/v1/buses/{bus_id}/eta/{stop_id}` — ETA to a stop
- `GET /api/v1/buses/{bus_id}/details` — bus and driver details

### GPS and Simulation

- `POST /api/v1/gps/driver/{bus_id}` — upload GPS event for a bus
- `POST /api/v1/simulation/start` — start simulation for a route or specific bus
- `POST /api/v1/simulation/start-route` — start all active buses on a route
- `POST /api/v1/simulation/stop` — stop simulation(s)

## Admin UI

The backend serves a simple admin dashboard at:

- `http://localhost:8000/admin`

## Project Structure

- `backend/app/` — FastAPI source code
- `backend/requirements.txt` — backend Python dependencies
- `docker/` — Docker Compose setup
- `flutter_app/` — Flutter mobile application

## Notes

- The backend uses SQLAlchemy ORM and automatically creates database tables on startup.
- Route geometry retrieval uses the OpenRouteService API when `ORS_API_KEY` is set.
- For local testing, the admin login endpoint returns a bearer token without credential validation.

## Contribution

If you want to extend this project:

1. Add stronger admin authentication and RBAC.
2. Enhance route ETA modeling with machine learning or advanced traffic data.
3. Build mobile UI screens for live bus tracking and student route selection.
4. Add automated tests for API endpoints and Flutter widgets.

