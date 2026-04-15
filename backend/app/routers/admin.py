from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Bus, Route, Stop, User
from app.schemas import FeeUpdate, RouteCreate, UserCreate
from app import auth as auth_utils

router = APIRouter()


@router.post("/admin/routes", status_code=201)
def create_route(
    payload: RouteCreate,
    db: Session = Depends(get_db),
):
    payload_data = payload.dict()
    route_name = payload_data.get("name")
    if not route_name:
        raise HTTPException(status_code=400, detail="Route name is required")

    existing = db.query(Route).filter(Route.name == route_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Route name already exists")

    route = Route(name=route_name)
    db.add(route)
    db.commit()
    db.refresh(route)

    stops = []
    for index, stop_payload in enumerate(payload_data.get("stops") or []):
        stop_order = stop_payload.get("stop_order") if stop_payload.get("stop_order") is not None else index + 1
        stop = Stop(
            route_id=route.id,
            name=stop_payload.get("name"),
            latitude=stop_payload.get("latitude"),
            longitude=stop_payload.get("longitude"),
            stop_order=stop_order,
        )
        stops.append(stop)

    if stops:
        db.add_all(stops)
        db.commit()

    return {"message": "Route created successfully", "id": route.id}


@router.get("/admin/routes")
def list_routes(
    db: Session = Depends(get_db),
):
    routes = db.query(Route).all()
    return [
        {
            "id": route.id,
            "name": route.name,
            "stop_count": len(route.stops),
        }
        for route in routes
    ]


@router.get("/admin/users")
def list_users(
    db: Session = Depends(get_db),
):
    users = db.query(User).all()
    return [
        {
            "id": user.id,
            "roll_number": user.roll_number,
            "name": user.name,
            "role": user.role,
            "route_id": user.route_id,
            "route_name": user.route.name if user.route else None,
            "is_fee_paid": user.is_fee_paid,
        }
        for user in users
    ]


@router.get("/admin/buses")
def list_buses(
    db: Session = Depends(get_db),
):
    buses = db.query(Bus).all()
    return [
        {
            "id": bus.id,
            "bus_number": bus.bus_number,
            "status": bus.status,
            "route_id": bus.route_id,
            "route_name": bus.route.name if bus.route else None,
            "driver_id": bus.driver_id,
            "driver_name": bus.driver.name if bus.driver else None,
        }
        for bus in buses
    ]


@router.get("/admin/drivers")
def list_drivers(
    db: Session = Depends(get_db),
):
    drivers = db.query(User).filter(User.role == "driver").all()
    return [
        {
            "id": driver.id,
            "roll_number": driver.roll_number,
            "name": driver.name,
        }
        for driver in drivers
    ]


@router.post("/admin/buses", status_code=201)
def create_bus(
    payload: dict,
    db: Session = Depends(get_db),
):
    bus_number = payload.get("bus_number")
    route_id = payload.get("route_id")

    if not bus_number:
        raise HTTPException(status_code=400, detail="Bus number is required")

    existing = db.query(Bus).filter(Bus.bus_number == bus_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bus number already exists")

    route = None
    if route_id is not None:
        route = db.query(Route).filter(Route.id == route_id).first()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")

    bus = Bus(bus_number=bus_number, route=route, status="inactive")
    db.add(bus)
    db.commit()
    db.refresh(bus)
    return {"message": "Bus created successfully", "id": bus.id}


@router.post("/admin/buses/{bus_id}/assign-driver")
def assign_driver_to_bus(
    bus_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    driver_roll = payload.get("driver_roll_number")
    if not driver_roll:
        raise HTTPException(status_code=400, detail="Driver roll number is required")

    bus = db.query(Bus).filter(Bus.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    driver = db.query(User).filter(User.roll_number == driver_roll, User.role == "driver").first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    bus.driver_id = driver.id
    bus.status = "active"
    db.commit()
    return {"message": "Driver assigned successfully", "bus_id": bus.id, "driver_id": driver.id}


@router.post("/admin/buses/{bus_id}/route")
def assign_bus_route(
    bus_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    route_id = payload.get("route_id")
    if route_id is None:
        raise HTTPException(status_code=400, detail="Route ID is required")

    bus = db.query(Bus).filter(Bus.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    bus.route_id = route.id
    db.commit()
    return {"message": "Bus route updated successfully", "bus_id": bus.id, "route_id": route.id}


@router.patch("/admin/students/{roll_number}/route")
def assign_student_route(
    roll_number: str,
    payload: dict,
    db: Session = Depends(get_db),
):
    student = db.query(User).filter(User.roll_number == roll_number, User.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    route_id = payload.get("route_id")
    if route_id is not None:
        route = db.query(Route).filter(Route.id == route_id).first()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")

    student.route_id = route_id
    db.commit()
    return {
        "message": "Student route updated successfully",
        "roll_number": student.roll_number,
        "route_id": student.route_id,
    }


@router.post("/admin/drivers", status_code=201)
def register_driver(
    payload: UserCreate,
    db: Session = Depends(get_db),
):
    if payload.role != "driver":
        raise HTTPException(status_code=400, detail="Role must be 'driver'")

    existing = db.query(User).filter(User.roll_number == payload.roll_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Roll number already registered")

    driver = User(
        roll_number=payload.roll_number,
        name=payload.name,
        role="driver",
        is_fee_paid=False,
        password_hash=auth_utils.hash_password(payload.password),
        route_id=None,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return {"message": "Driver registered successfully", "id": driver.id}


@router.patch("/admin/students/{roll_number}/fee")
def update_student_fee_status(
    roll_number: str,
    payload: FeeUpdate,
    db: Session = Depends(get_db),
):
    student = db.query(User).filter(User.roll_number == roll_number, User.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student.is_fee_paid = payload.is_fee_paid
    db.commit()
    return {
        "message": "Student fee status updated successfully",
        "roll_number": student.roll_number,
        "is_fee_paid": student.is_fee_paid,
    }
