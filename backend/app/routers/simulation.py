"""
API endpoints for bus route simulation.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import cast, String
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.database import get_db
from app.models import Bus, Route
from app.gps_simulator import (
    BusSimulator,
    get_simulator,
    set_simulator,
    list_simulators,
    remove_simulator,
)

router = APIRouter()
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization token",
        )

    try:
        return decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
        )


@router.post("/simulation/start")
def start_simulation(
    route_id: int,
    bus_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start bus simulation for a specific bus or for all active buses on a route.
    If bus_id is not provided, start route simulations with a 2-minute spacing.
    """
    # Verify user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can start simulations",
        )
    
    # Verify route exists
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    if bus_id is None:
        active_buses = (
            db.query(Bus)
            .filter(cast(Bus.route_id, String) == str(route_id), Bus.status == "active")
            .order_by(Bus.id)
            .all()
        )

        if not active_buses:
            raise HTTPException(
                status_code=404,
                detail="No active buses found on this route",
            )

        started = []
        skipped = []

        for index, bus in enumerate(active_buses):
            if get_simulator(bus.id) and get_simulator(bus.id).is_running:
                skipped.append(bus.id)
                continue

            delay_seconds = index * 120
            simulator = BusSimulator(bus_id=bus.id, route_id=route_id, delay_seconds=delay_seconds)
            if simulator.start():
                set_simulator(simulator)
                started.append({
                    "bus_id": bus.id,
                    "delay_seconds": delay_seconds,
                })
            else:
                skipped.append(bus.id)

        return {
            "status": "success",
            "message": f"Started simulations for active buses on route {route_id}",
            "route_id": route_id,
            "started": started,
            "skipped": skipped,
            "duration_minutes": 40,
        }

    bus = db.query(Bus).filter(Bus.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    if str(bus.route_id) != str(route_id):
        raise HTTPException(
            status_code=400,
            detail="The selected bus does not belong to the provided route",
        )

    existing_sim = get_simulator(bus_id)
    if existing_sim and existing_sim.is_running:
        raise HTTPException(
            status_code=400,
            detail=f"Simulation already running for bus {bus_id}",
        )
    
    simulator = BusSimulator(bus_id=bus_id, route_id=route_id)
    if not simulator.start():
        raise HTTPException(
            status_code=400,
            detail="Failed to start simulation"
        )
    
    set_simulator(simulator)
    
    return {
        "status": "success",
        "message": f"Simulation started for Bus {bus_id} on Route {route_id}",
        "bus_id": bus_id,
        "route_id": route_id,
        "delay_seconds": simulator.delay_seconds,
        "duration_minutes": 40,
        "update_interval_seconds": 2,
    }


@router.post("/simulation/start-route")
def start_route_simulation(
    route_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start simulations for all active buses on a route with a 2-minute spacing."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can start simulations",
        )

    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    active_buses = (
        db.query(Bus)
        .filter(cast(Bus.route_id, String) == str(route_id), Bus.status == "active")
        .order_by(Bus.id)
        .all()
    )

    if not active_buses:
        raise HTTPException(
            status_code=404,
            detail="No active buses found on this route",
        )

    started = []
    skipped = []

    for index, bus in enumerate(active_buses):
        if get_simulator(bus.id) and get_simulator(bus.id).is_running:
            skipped.append(bus.id)
            continue

        delay_seconds = index * 120
        simulator = BusSimulator(bus_id=bus.id, route_id=route_id, delay_seconds=delay_seconds)
        if simulator.start():
            set_simulator(simulator)
            started.append({
                "bus_id": bus.id,
                "delay_seconds": delay_seconds,
            })
        else:
            skipped.append(bus.id)

    return {
        "status": "success",
        "message": f"Started simulations for route {route_id}",
        "route_id": route_id,
        "started": started,
        "skipped": skipped,
        "duration_minutes": 40,
    }


@router.post("/simulation/stop")
def stop_simulation(
    bus_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    """Stop a bus simulation or all running simulations."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can stop simulations",
        )

    if bus_id is not None:
        simulator = get_simulator(bus_id)
        if not simulator or not simulator.is_running:
            raise HTTPException(
                status_code=400,
                detail=f"No running simulation found for bus {bus_id}",
            )
        simulator.stop()
        remove_simulator(bus_id)
        return {
            "status": "success",
            "message": f"Simulation stopped for bus {bus_id}",
        }

    any_stopped = False
    for sim in list_simulators():
        if sim.is_running:
            sim.stop()
            any_stopped = True

    if not any_stopped:
        raise HTTPException(
            status_code=400,
            detail="No simulation is currently running",
        )

    return {
        "status": "success",
        "message": "All simulations stopped",
    }


@router.get("/simulation/status")
def get_simulation_status(
    current_user: dict = Depends(get_current_user),
    bus_id: Optional[int] = None,
):
    """Get current simulation status."""
    if bus_id is not None:
        simulator = get_simulator(bus_id)
        if not simulator:
            return {
                "is_running": False,
                "message": f"No simulation available for bus {bus_id}",
            }
        simulators = [simulator]
    else:
        simulators = list_simulators()

    if not simulators:
        return {
            "is_running": False,
            "message": "No simulation available",
        }

    status_list = []
    for simulator in simulators:
        status_info = simulator.get_status()
        if status_info.get("is_running"):
            remaining = status_info["total_seconds"] - status_info["elapsed_seconds"]
            status_info["remaining_seconds"] = max(0, remaining)
            status_info["progress_percentage"] = round(status_info["progress"] * 100, 2)
        status_list.append(status_info)

    return {
        "is_running": any(item["is_running"] for item in status_list),
        "simulations": status_list,
    }
