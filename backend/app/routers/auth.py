from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Route, User
from app.schemas import LoginRequest, TokenResponse, UserCreate
from app import auth as auth_utils

router = APIRouter()

@router.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # Find user by roll number
    user = db.query(User).filter(User.roll_number == request.roll_number).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid roll number or password")

    if not auth_utils.verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid roll number or password")

    if not user.is_fee_paid and user.role == "student":
        raise HTTPException(status_code=403, detail="Bus fee not paid. Access denied.")

    route_id = user.route_id
    route_name = user.route.name if user.route else None

    token = auth_utils.create_access_token({
        "sub":  user.roll_number,
        "role": user.role,
        "name": user.name,
        "route_id": route_id,
        "route_name": route_name,
    })

    return TokenResponse(
        access_token=token,
        role=user.role,
        name=user.name,
        route_id=route_id,
        route_name=route_name,
    )


@router.post("/auth/admin-login")
def admin_login():
    """Generate an admin access token without requiring credentials."""
    token = auth_utils.create_access_token({
        "sub": "admin",
        "role": "admin",
        "name": "Administrator",
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "admin",
        "name": "Administrator",
    }


@router.post("/auth/register", status_code=201)
def register(request: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.roll_number == request.roll_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Roll number already registered")

    route_id = request.route_id
    if route_id is not None:
        from app.models import Route
        route = db.query(Route).filter(Route.id == route_id).first()
        if not route:
            raise HTTPException(status_code=404, detail="Route not found")

    new_user = User(
        roll_number   = request.roll_number,
        name          = request.name,
        role          = request.role,
        is_fee_paid   = request.is_fee_paid,
        password_hash = auth_utils.hash_password(request.password),
        route_id      = route_id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully", "id": new_user.id}