from typing import List, Optional
from pydantic import BaseModel

class LoginRequest(BaseModel):
    roll_number: str
    password:    str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    role:         str
    name:         str
    route_id:     Optional[int] = None
    route_name:   Optional[str] = None

class UserCreate(BaseModel):
    roll_number: str
    name:        str
    password:    str
    role:        str = "student"
    is_fee_paid: bool = False
    route_id:   Optional[int] = None


class StopCreate(BaseModel):
    name: Optional[str] = None
    latitude: float
    longitude: float
    stop_order: Optional[int] = None


class RouteCreate(BaseModel):
    name: str
    stops: Optional[List[StopCreate]] = []


class FeeUpdate(BaseModel):
    is_fee_paid: bool


class StopResponse(BaseModel):
    id: int
    name: Optional[str]
    latitude: float
    longitude: float
    stop_order: int

    class Config:
        from_attributes = True


class RouteDetail(BaseModel):
    id: int
    name: str
    stops: List[StopResponse]
    geometry: Optional[dict] = None

    class Config:
        from_attributes = True


class GPSUpdate(BaseModel):
    latitude: float
    longitude: float
    speed: Optional[float] = None


class GPSEventRecord(BaseModel):
    timestamp: Optional[str]
    latitude: float
    longitude: float
    speed: Optional[float] = None
    eta: Optional[str] = None
