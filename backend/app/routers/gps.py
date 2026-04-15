from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.database import get_db
from app.models import Bus, GPSEvent
from app.schemas import GPSUpdate

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


@router.post("/gps/driver/{bus_id}")
def driver_gps_update(
    bus_id: int,
    payload: GPSUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bus = db.query(Bus).filter(Bus.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bus not found")

    gps_event = GPSEvent(
        bus_id=bus_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed=payload.speed,
    )
    db.add(gps_event)
    db.commit()
    db.refresh(gps_event)

    return {
        "status": "ok",
        "bus_id": bus_id,
        "event_id": gps_event.id,
        "latitude": gps_event.latitude,
        "longitude": gps_event.longitude,
        "speed": gps_event.speed,
        "timestamp": gps_event.timestamp.isoformat() if gps_event.timestamp else None,
    }
