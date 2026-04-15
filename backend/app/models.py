from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    roll_number   = Column(String, unique=True, index=True, nullable=False)
    name          = Column(String, nullable=False)
    role          = Column(String, default="student")  # student / driver / coordinator
    is_fee_paid   = Column(Boolean, default=False)
    password_hash = Column(String, nullable=False)
    route_id      = Column(Integer, ForeignKey("routes.id"), nullable=True)

    buses = relationship("Bus", back_populates="driver")
    route = relationship("Route", back_populates="users")


class Route(Base):
    __tablename__ = "routes"

    id   = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)

    stops = relationship(
        "Stop",
        back_populates="route",
        order_by="Stop.stop_order",
        cascade="all, delete-orphan",
    )
    buses = relationship("Bus", back_populates="route")
    users = relationship("User", back_populates="route")


class Stop(Base):
    __tablename__ = "stops"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id"), nullable=False)
    name = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    stop_order = Column(Integer, nullable=False)

    route = relationship("Route", back_populates="stops")


class Bus(Base):
    __tablename__ = "buses"

    id         = Column(Integer, primary_key=True, index=True)
    bus_number = Column("number", String, unique=True, nullable=False)
    driver_id  = Column(Integer, ForeignKey("users.id"), nullable=True)
    route_id   = Column("route", Integer, ForeignKey("routes.id"), nullable=True)
    status     = Column(String, default="inactive")

    driver     = relationship("User", back_populates="buses")
    route      = relationship("Route", back_populates="buses")
    gps_events = relationship("GPSEvent", back_populates="bus", cascade="all, delete-orphan")


class GPSEvent(Base):
    __tablename__ = "gps_events"

    id         = Column(Integer, primary_key=True, index=True)
    bus_id     = Column(Integer, ForeignKey("buses.id"), nullable=False)
    latitude  = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed     = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    bus = relationship("Bus", back_populates="gps_events")