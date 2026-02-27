from fastapi import FastAPI
from app.database import engine, Base
from app.routers import auth, buses
 
Base.metadata.create_all(bind=engine)  # Creates tables automatically
 
app = FastAPI(title='Campus Bus API', version='1.0')
 
app.include_router(auth.router,  prefix='/api/v1')
app.include_router(buses.router, prefix='/api/v1')
 
@app.get('/')
def root():
    return {'message': 'Campus Bus API is running!'}
