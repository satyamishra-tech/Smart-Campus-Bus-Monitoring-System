from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.database import get_db
from app.models import Bus, GPSEvent, Route, Stop
from app.utils import haversine_distance

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


@router.get("/buses/")
def get_buses(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    active_buses = db.query(Bus).filter(Bus.status == "active").all()
    response = []

    for bus in active_buses:
        latest_event = (
            db.query(GPSEvent)
            .filter(GPSEvent.bus_id == bus.id)
            .order_by(desc(GPSEvent.timestamp))
            .first()
        )

        response.append(
            {
                "id": bus.id,
                "bus_number": bus.bus_number,
                "latitude": latest_event.latitude if latest_event else 0.0,
                "longitude": latest_event.longitude if latest_event else 0.0,
                "route_id": bus.route_id,
                "route_name": bus.route.name if bus.route else None,
            }
        )

    return response


@router.get("/buses/{bus_id}/latest")
def get_bus_latest_location(
    bus_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    latest_event = (
        db.query(GPSEvent)
        .filter(GPSEvent.bus_id == bus_id)
        .order_by(desc(GPSEvent.timestamp))
        .first()
    )

    if not latest_event:
        return {
            "bus_id": bus_id,
            "latitude": 0.0,
            "longitude": 0.0,
            "speed": None,
            "timestamp": None,
        }

    return {
        "bus_id": bus_id,
        "latitude": latest_event.latitude,
        "longitude": latest_event.longitude,
        "speed": latest_event.speed,
        "timestamp": latest_event.timestamp.isoformat(),
    }


@router.get("/buses/{bus_id}/eta/{stop_id}")
def get_bus_eta_to_stop(
    bus_id: int,
    stop_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Calculate estimated time of arrival (ETA) for a bus to reach a specific stop.
    Returns ETA in seconds and minutes.
    """
    # Get current bus location
    latest_event = (
        db.query(GPSEvent)
        .filter(GPSEvent.bus_id == bus_id)
        .order_by(desc(GPSEvent.timestamp))
        .first()
    )
    
    if not latest_event:
        raise HTTPException(
            status_code=404,
            detail="No GPS data found for this bus"
        )
    
    # Get stop location
    stop = db.query(Stop).filter(Stop.id == stop_id).first()
    if not stop:
        raise HTTPException(
            status_code=404,
            detail="Stop not found"
        )
    
    # Get bus to check its route
    bus = db.query(Bus).filter(Bus.id == bus_id).first()
    if not bus:
        raise HTTPException(
            status_code=404,
            detail="Bus not found"
        )
    
    # Verify stop is on this bus's route
    if str(bus.route_id) != str(stop.route_id):
        raise HTTPException(
            status_code=400,
            detail="Stop is not on this bus's route"
        )
    
    # Calculate distance from current location to stop
    current_lat = latest_event.latitude
    current_lon = latest_event.longitude
    stop_lat = stop.latitude
    stop_lon = stop.longitude
    
    distance_km = haversine_distance(current_lat, current_lon, stop_lat, stop_lon)
    
    # Get average speed from recent GPS events (last 10 events)
    recent_events = (
        db.query(GPSEvent)
        .filter(GPSEvent.bus_id == bus_id)
        .order_by(desc(GPSEvent.timestamp))
        .limit(10)
        .all()
    )
    
    avg_speed = 25.5  # Default speed in km/h
    if recent_events and len(recent_events) > 0:
        speeds = [e.speed for e in recent_events if e.speed is not None]
        if speeds:
            avg_speed = sum(speeds) / len(speeds)
    
    # Calculate ETA: time = distance / speed
    # Convert speed from km/h to km/s, then multiply by 3600 to get seconds
    if avg_speed > 0:
        eta_hours = distance_km / avg_speed
        eta_seconds = int(eta_hours * 3600)
        eta_minutes = eta_seconds / 60
    else:
        eta_seconds = 0
        eta_minutes = 0
    
    return {
        "bus_id": bus_id,
        "stop_id": stop_id,
        "stop_name": stop.name,
        "stop_lat": stop.latitude,
        "stop_lon": stop.longitude,
        "current_lat": current_lat,
        "current_lon": current_lon,
        "distance_km": round(distance_km, 2),
        "avg_speed_kmh": round(avg_speed, 2),
        "eta_seconds": eta_seconds,
        "eta_minutes": round(eta_minutes, 1),
        "eta_formatted": f"{int(eta_minutes)} min {eta_seconds % 60} sec" if eta_seconds > 0 else "Arrived",
    }


@router.get("/buses/{bus_id}/details")
def get_bus_details(
    bus_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a bus including driver details.
    """
    bus = db.query(Bus).filter(Bus.id == bus_id).first()
    if not bus:
        raise HTTPException(
            status_code=404,
            detail="Bus not found"
        )
    
    driver_name = "No Driver Assigned"
    if bus.driver_id:
        from app.models import User
        driver = db.query(User).filter(User.id == bus.driver_id).first()
        if driver:
            driver_name = driver.name
    
    # Get latest GPS event for current location
    latest_event = (
        db.query(GPSEvent)
        .filter(GPSEvent.bus_id == bus_id)
        .order_by(desc(GPSEvent.timestamp))
        .first()
    )
    
    return {
        "bus_id": bus.id,
        "bus_number": bus.bus_number,
        "driver_name": driver_name,
        "status": bus.status,
        "latitude": latest_event.latitude if latest_event else None,
        "longitude": latest_event.longitude if latest_event else None,
        "last_updated": latest_event.timestamp.isoformat() if latest_event else None,
        "route_id": bus.route_id,
        "route_name": bus.route.name if bus.route else None,
    }