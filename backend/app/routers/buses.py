from fastapi import APIRouter

router = APIRouter()

@router.get("/buses/")
def get_buses():
    return {"message": "Buses endpoint - coming soon!"}