from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from app.database import engine, Base
from app.routers import auth, admin, buses, gps, routes, simulation
import app.models  # ensures tables are created

BASE_DIR = Path(__file__).resolve().parent.parent

Base.metadata.create_all(bind=engine)

inspector = inspect(engine)
if 'users' in inspector.get_table_names():
    columns = [column['name'] for column in inspector.get_columns('users')]
    if 'route_id' not in columns:
        with engine.connect() as connection:
            connection.execute(
                text('ALTER TABLE users ADD COLUMN route_id INTEGER REFERENCES routes(id)')
            )
            connection.commit()

app = FastAPI(title="Campus Bus API", version="1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(auth.router,       prefix="/api/v1")
app.include_router(admin.router,      prefix="/api/v1")
app.include_router(buses.router,      prefix="/api/v1")
app.include_router(gps.router,        prefix="/api/v1")
app.include_router(routes.router,     prefix="/api/v1")
app.include_router(simulation.router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Campus Bus API is running!"}

@app.get("/admin")
def admin_page():
    return FileResponse(BASE_DIR / "static" / "admin.html")