"""
API endpoints for bus route simulation.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.database import get_db
from app.models import Bus, Route
from app.gps_simulator import BusSimulator, get_simulator, set_simulator

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
    Start bus simulation for a route.
    If bus_id is not provided, use the first active bus on the route.
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
    
    # Get or find bus
    if bus_id is None:
        # Get first active bus on this route
        bus = db.query(Bus).filter(
            Bus.route_id == str(route_id),
            Bus.status == "active"
        ).first()
        
        if not bus:
            raise HTTPException(
                status_code=404,
                detail="No active bus found on this route"
            )
        bus_id = bus.id
    else:
        bus = db.query(Bus).filter(Bus.id == bus_id).first()
        if not bus:
            raise HTTPException(status_code=404, detail="Bus not found")
    
    # Stop any existing simulation
    existing_sim = get_simulator()
    if existing_sim and existing_sim.is_running:
        existing_sim.stop()
    
    # Create and start new simulator
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
        "duration_minutes": 40,
        "update_interval_seconds": 10,
    }


@router.post("/simulation/stop")
def stop_simulation(
    current_user: dict = Depends(get_current_user),
):
    """Stop the current bus simulation."""
    # Verify user is admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can stop simulations",
        )
    
    simulator = get_simulator()
    if not simulator or not simulator.is_running:
        raise HTTPException(
            status_code=400,
            detail="No simulation is currently running"
        )
    
    simulator.stop()
    
    return {
        "status": "success",
        "message": "Simulation stopped",
    }


@router.get("/simulation/status")
def get_simulation_status(
    current_user: dict = Depends(get_current_user),
):
    """Get current simulation status."""
    simulator = get_simulator()
    
    if not simulator:
        return {
            "is_running": False,
            "message": "No simulation available",
        }
    
    status_info = simulator.get_status()
    
    # Calculate remaining time
    if status_info["is_running"]:
        remaining = status_info["total_seconds"] - status_info["elapsed_seconds"]
        status_info["remaining_seconds"] = max(0, remaining)
        status_info["progress_percentage"] = round(status_info["progress"] * 100, 2)
    
    return status_info
