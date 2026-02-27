from fastapi import APIRouter

router = APIRouter()

@router.post("/auth/login")
def login():
    return {"message": "Login endpoint - coming soon!"}