import json
import os
import urllib.error
import urllib.request
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.database import get_db
from app.models import Route, Stop

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


def fetch_route_geometry(stops):
    api_key = os.getenv("ORS_API_KEY")
    if not api_key or len(stops) < 2:
        return None

    coordinates = [[stop.longitude, stop.latitude] for stop in stops]
    payload = json.dumps({"coordinates": coordinates}).encode("utf-8")
    request_url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    request_obj = urllib.request.Request(
        request_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request_obj, timeout=20) as response:
            data = json.load(response)
            feature = data.get("features", [{}])[0]
            return feature.get("geometry")
    except urllib.error.HTTPError as exc:
        return None
    except urllib.error.URLError:
        return None


@router.get("/routes")
def list_routes(
    current_user: dict = Depends(get_current_user),
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


@router.get("/routes/{route_id}")
def get_route_details(
    route_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    stops = sorted(route.stops, key=lambda stop: stop.stop_order)
    geometry = fetch_route_geometry(stops)

    return {
        "id": route.id,
        "name": route.name,
        "stops": [
            {
                "id": stop.id,
                "name": stop.name,
                "latitude": stop.latitude,
                "longitude": stop.longitude,
                "stop_order": stop.stop_order,
            }
            for stop in stops
        ],
        "geometry": geometry,
    }


@router.patch("/routes/{route_id}/stops/{stop_id}")
def update_stop(
    route_id: int,
    stop_id: int,
    stop_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a stop's name and/or location."""
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    stop = db.query(Stop).filter(Stop.id == stop_id, Stop.route_id == route_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    # Update stop fields if provided
    if "name" in stop_data and stop_data["name"]:
        stop.name = stop_data["name"]
    if "latitude" in stop_data:
        stop.latitude = float(stop_data["latitude"])
    if "longitude" in stop_data:
        stop.longitude = float(stop_data["longitude"])
    if "stop_order" in stop_data:
        stop.stop_order = int(stop_data["stop_order"])

    db.commit()
    db.refresh(stop)

    return {
        "id": stop.id,
        "name": stop.name,
        "latitude": stop.latitude,
        "longitude": stop.longitude,
        "stop_order": stop.stop_order,
    }


@router.delete("/routes/{route_id}/stops/{stop_id}")
def delete_stop(
    route_id: int,
    stop_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a stop and reorder remaining stops."""
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    stop = db.query(Stop).filter(Stop.id == stop_id, Stop.route_id == route_id).first()
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    deleted_order = stop.stop_order
    
    # Delete the stop
    db.delete(stop)
    db.commit()

    # Reorder remaining stops - decrement order for stops after the deleted one
    remaining_stops = db.query(Stop).filter(
        Stop.route_id == route_id,
        Stop.stop_order > deleted_order
    ).all()
    
    for remaining_stop in remaining_stops:
        remaining_stop.stop_order -= 1
    
    db.commit()

    return {
        "message": "Stop deleted successfully",
        "deleted_stop_id": stop_id,
        "reordered_count": len(remaining_stops),
    }
