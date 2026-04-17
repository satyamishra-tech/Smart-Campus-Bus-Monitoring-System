# Proposed System Design for Smart Campus Bus Monitoring System

## 1. Overview
This proposal describes the current architecture and recommended system design for the Smart Campus Bus Monitoring System. The app is a full-stack solution with:
- Flutter mobile client
- FastAPI backend
- PostgreSQL database
- GPS ingestion and simulation service
- Lightweight admin dashboard

The design supports campus users, drivers, and administrators with real-time bus tracking, route management, ETA estimation, and route assignment.

## 2. High-Level Architecture

### 2.1 Components
- **Mobile Client** (`flutter_app/`)
  - Student, driver, and coordinator interfaces
  - Authentication and token management
  - Calls backend REST APIs
- **Backend API** (`backend/app/`)
  - FastAPI application exposing REST endpoints
  - JWT-based authentication for protected actions
  - Static admin page served under `/admin`
- **Database**
  - PostgreSQL as persistent storage
  - SQLAlchemy models for entities, relationships, and query management
- **Simulation / GPS**
  - GPS upload endpoint for driver updates
  - Simulation endpoints for route testing
  - ETA estimation logic using GPS event history

### 2.2 Deployment
- Docker Compose for backend + PostgreSQL
- Flutter app runs on mobile or emulator
- Optional environment support for local direct run

## 3. Proposed Data Model

### 3.1 Entities

#### User
- `id`: integer PK
- `roll_number`: unique identifier
- `name`
- `role`: `student` / `driver` / `coordinator`
- `is_fee_paid`: boolean
- `password_hash`
- `route_id`: optional FK to a route

Relationships:
- One `User` can be assigned to one `Route`
- Drivers have one-to-many relationship with `Bus`

#### Bus
- `id`: integer PK
- `bus_number`: unique bus identity
- `driver_id`: optional FK to `User`
- `route_id`: optional FK to `Route`
- `status`: `inactive` / `active`

Relationships:
- One `Bus` belongs to one `Route`
- One `Bus` can have many `GPSEvent`s

#### Route
- `id`: integer PK
- `name`: unique route name

Relationships:
- One `Route` contains ordered `Stop`s
- One `Route` can have many `Bus`es
- One `Route` can have many assigned `User`s (students)

#### Stop
- `id`: integer PK
- `route_id`: FK to `Route`
- `name`
- `latitude`
- `longitude`
- `stop_order`: integer order for stop sequencing

#### GPSEvent
- `id`: integer PK
- `bus_id`: FK to `Bus`
- `latitude`
- `longitude`
- `speed`
- `timestamp`

### 3.2 Relationships Summary
- `User` 1 - N `Bus` (driver assignment)
- `Route` 1 - N `Stop`
- `Route` 1 - N `Bus`
- `Route` 1 - N `User` (student assignments)
- `Bus` 1 - N `GPSEvent`

## 4. API & Functional Design

### 4.1 Authentication
- `POST /api/v1/auth/login`
  - login with `roll_number` and `password`
  - returns JWT access token and user role
- `POST /api/v1/auth/register`
  - create new account for students or drivers
- `POST /api/v1/auth/admin-login`
  - admin access for local tests

### 4.2 Admin Management
- `POST /api/v1/admin/routes`
  - create route with stop list
- `GET /api/v1/admin/routes`
  - list all routes
- `GET /api/v1/admin/users`
  - list users with assigned route and fee status
- `GET /api/v1/admin/buses`
  - list buses with driver and route
- `GET /api/v1/admin/drivers`
  - list drivers
- `POST /api/v1/admin/buses`
  - create new bus
- `POST /api/v1/admin/buses/{bus_id}/assign-driver`
  - assign driver by roll number
- `POST /api/v1/admin/buses/{bus_id}/route`
  - assign route to bus
- `PATCH /api/v1/admin/students/{roll_number}/route`
  - assign student to route
- `PATCH /api/v1/admin/students/{roll_number}/fee`
  - update fee status

### 4.3 Route and Bus APIs
- `GET /api/v1/routes`
  - list all routes
- `GET /api/v1/routes/{route_id}`
  - route details, stops, optional geometry
- `PATCH /api/v1/routes/{route_id}/stops/{stop_id}`
  - update stop coordinates/order
- `DELETE /api/v1/routes/{route_id}/stops/{stop_id}`
  - remove stop
- `GET /api/v1/buses/`
  - list active buses and latest GPS
- `GET /api/v1/buses/{bus_id}/latest`
  - latest location for a bus
- `GET /api/v1/buses/{bus_id}/eta/{stop_id}`
  - ETA to a stop based on GPS history
- `GET /api/v1/buses/{bus_id}/details`
  - bus and driver detail

### 4.4 GPS and Simulation
- `POST /api/v1/gps/driver/{bus_id}`
  - driver uploads current GPS event
  - authenticated via bearer token
- `POST /api/v1/simulation/start`
  - start a bus movement simulation
- `POST /api/v1/simulation/start-route`
  - start simulation for all buses on a route
- `POST /api/v1/simulation/stop`
  - stop simulation

## 5. Proposed System Design Patterns

### 5.1 Layered Architecture
- **Presentation Layer**
  - Flutter UI and static admin page
- **API Layer**
  - FastAPI endpoints and request validation
- **Business Logic Layer**
  - route management, assignment, GPS ingestion, ETA calculations
- **Persistence Layer**
  - PostgreSQL + SQLAlchemy models

### 5.2 Data Flow
1. Admin creates routes and buses via admin API.
2. Drivers authenticate and send GPS events.
3. Backend stores GPS events and updates bus tracking.
4. Students view assigned route and bus ETA.
5. Simulation API can generate route movement for testing.

### 5.3 Security
- Use JWT for authenticated API access
- Separate admin operations from driver/student actions
- Protect GPS update endpoints with token-based access
- Add role validation in future for stronger RBAC

## 6. Proposed Enhancements

### 6.1 Short-term Improvements
- Add explicit role-based access control for admin, driver, and student routes
- Add better validation in endpoints and stronger password policies
- Return route geometry consistently from route detail endpoint
- Persist current bus position in a dedicated table for faster queries

### 6.2 Medium-term Enhancements
- Add push notifications for ETA alerts
- Add map-based tracking on mobile UI
- Add route analytics and bus utilization reports
- Add a proper admin dashboard with login flow and RBAC

### 6.3 Long-term Enhancements
- Add traffic-aware ETA using external data
- Add driver route optimization and scheduling
- Add student boarding confirmation and attendance tracking

## 7. Proposed Entity Diagram (Text)

User(role: student|driver|coordinator)
  ├─ route_id -> Route.id
  └─ driver relationship -> Bus.driver_id

Route(name)
  ├─ stops -> Stop.route_id
  ├─ buses -> Bus.route_id
  └─ users -> User.route_id

Bus(bus_number, status)
  ├─ driver_id -> User.id
  ├─ route_id -> Route.id
  └─ gps_events -> GPSEvent.bus_id

Stop(name, latitude, longitude, stop_order)
  └─ route_id -> Route.id

GPSEvent(latitude, longitude, speed, timestamp)
  └─ bus_id -> Bus.id

## 8. Conclusion
This design document aligns with the existing project structure and recommends a clear architecture for future enhancement. The current model supports campus route management, driver tracking, and student assignment while remaining extensible for richer ETA, map visualization, and access control.
