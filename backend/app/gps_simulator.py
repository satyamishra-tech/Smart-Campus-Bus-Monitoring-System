"""
GPS Simulator for bus route simulation.
Generates realistic GPS positions along a route over 40 minutes.
"""
import asyncio
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional, List, Tuple

ROUTE_DURATION_SECONDS = 2400  # 40 minutes
GPS_UPDATE_INTERVAL_SECONDS = 2  # Update every 2 seconds (for smooth marker movement)


def _fetch_route_geometry(stops):
    """Fetch route geometry from OpenRouteService API."""
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


class BusSimulator:
    """Manages bus simulation for a specific route and bus."""
    
    def __init__(self, bus_id: int, route_id: int):
        self.bus_id = bus_id
        self.route_id = route_id
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.thread: Optional[threading.Thread] = None
        self.route_points: List[Tuple[float, float]] = []
        self.total_route_distance_km: float = 0.0  # Will be calculated
        self.actual_avg_speed_kmh: float = 25.5  # Will be updated
    
    def _load_route_points(self) -> bool:
        """Load route geometry from OpenRouteService or fall back to stops interpolation."""
        from app.models import Route
        from app.database import SessionLocal
        from app.utils import haversine_distance
        
        db = SessionLocal()
        try:
            route = db.query(Route).filter(Route.id == self.route_id).first()
            if not route:
                return False
            
            geometry_points = []
            
            # Try to fetch actual route geometry from OpenRouteService API
            stops = sorted(route.stops, key=lambda s: s.stop_order)
            if not stops:
                return False
            
            geometry = _fetch_route_geometry(stops)
            
            # Extract coordinates from geometry if available
            if geometry and isinstance(geometry, dict):
                coords = geometry.get("coordinates", [])
                for coord in coords:
                    if isinstance(coord, (list, tuple)) and len(coord) >= 2:
                        # Coordinates are in [longitude, latitude] format from OpenRouteService
                        lon, lat = coord[0], coord[1]
                        geometry_points.append((lat, lon))
            
            # Fallback to stops with interpolation if no geometry available
            if not geometry_points:
                # Add intermediate points between stops for smoother interpolation
                interpolated_points = []
                for i in range(len(stops)):
                    interpolated_points.append((stops[i].latitude, stops[i].longitude))
                    
                    # Add intermediate points to the next stop (if not last stop)
                    if i < len(stops) - 1:
                        lat1, lon1 = stops[i].latitude, stops[i].longitude
                        lat2, lon2 = stops[i + 1].latitude, stops[i + 1].longitude
                        distance = haversine_distance(lat1, lon1, lat2, lon2)
                        
                        # Add intermediate point every ~0.1 km (or at least 3 points per segment)
                        num_intermediate = max(3, int(distance / 0.1))
                        for j in range(1, num_intermediate):
                            t = j / num_intermediate
                            intermediate_lat = lat1 + (lat2 - lat1) * t
                            intermediate_lon = lon1 + (lon2 - lon1) * t
                            interpolated_points.append((intermediate_lat, intermediate_lon))
                
                geometry_points = interpolated_points
                source = "stops interpolation"
            else:
                source = f"route geometry ({len(geometry_points)} points)"
            
            self.route_points = geometry_points
            
            # Calculate total route distance
            total_distance = 0.0
            for i in range(len(self.route_points) - 1):
                lat1, lon1 = self.route_points[i]
                lat2, lon2 = self.route_points[i + 1]
                total_distance += haversine_distance(lat1, lon1, lat2, lon2)
            
            self.total_route_distance_km = total_distance
            
            # Calculate actual average speed: distance / time
            # time = ROUTE_DURATION_SECONDS / 3600 (convert seconds to hours)
            route_duration_hours = ROUTE_DURATION_SECONDS / 3600
            if route_duration_hours > 0:
                self.actual_avg_speed_kmh = total_distance / route_duration_hours
            
            print(f"[GPS SIMULATOR] Route {self.route_id}: Using {source}, {total_distance:.2f}km, avg speed {self.actual_avg_speed_kmh:.2f}km/h")
            
            return True
        finally:
            db.close()
    
    def _interpolate_position(self, progress: float) -> Tuple[float, float]:
        """
        Interpolate bus position based on progress through route.
        progress: 0.0 (start) to 1.0 (end)
        """
        if not self.route_points or len(self.route_points) < 2:
            return self.route_points[0] if self.route_points else (0, 0)
        
        # Map progress to route_points
        total_segments = len(self.route_points) - 1
        segment_index = int(progress * total_segments)
        
        # Clamp to valid range
        segment_index = min(segment_index, total_segments - 1)
        
        # Get segment start and end points
        start_lat, start_lon = self.route_points[segment_index]
        end_lat, end_lon = self.route_points[min(segment_index + 1, total_segments)]
        
        # Calculate position within segment
        segment_progress = (progress * total_segments) - segment_index
        
        # Linear interpolation
        lat = start_lat + (end_lat - start_lat) * segment_progress
        lon = start_lon + (end_lon - start_lon) * segment_progress
        
        return (lat, lon)
    
    def _create_gps_event(self, latitude: float, longitude: float) -> None:
        """Create a GPS event in the database."""
        from app.models import GPSEvent
        from app.database import SessionLocal
        from datetime import timezone
        
        db = SessionLocal()
        try:
            gps_event = GPSEvent(
                bus_id=self.bus_id,
                latitude=latitude,
                longitude=longitude,
                speed=self.actual_avg_speed_kmh,  # Use calculated speed based on actual route
                timestamp=datetime.now(timezone.utc),
            )
            db.add(gps_event)
            db.commit()
            print(f"[GPS SIMULATOR] Bus {self.bus_id}: GPS Event created at ({latitude:.6f}, {longitude:.6f})")
        finally:
            db.close()
    
    def _simulation_loop(self) -> None:
        """Main simulation loop - runs in separate thread."""
        elapsed_time = 0
        
        while self.is_running and elapsed_time < ROUTE_DURATION_SECONDS:
            try:
                # Calculate progress (0 to 1)
                progress = elapsed_time / ROUTE_DURATION_SECONDS
                
                # Get interpolated position
                lat, lon = self._interpolate_position(progress)
                
                # Create GPS event
                self._create_gps_event(lat, lon)
                
                # Sleep for update interval
                elapsed_seconds = 0
                while elapsed_seconds < GPS_UPDATE_INTERVAL_SECONDS and self.is_running:
                    threading.Event().wait(1)
                    elapsed_seconds += 1
                
                elapsed_time += GPS_UPDATE_INTERVAL_SECONDS
                
            except Exception as e:
                print(f"[GPS SIMULATOR] Error in simulation loop: {e}")
                break
        
        # Create final position at end
        if self.is_running and len(self.route_points) > 0:
            final_lat, final_lon = self.route_points[-1]
            self._create_gps_event(final_lat, final_lon)
        
        print(f"[GPS SIMULATOR] Bus {self.bus_id} simulation completed!")
        self.is_running = False
    
    def start(self) -> bool:
        """Start the simulation."""
        if self.is_running:
            return False
        
        # Load route points
        if not self._load_route_points():
            print(f"[GPS SIMULATOR] Failed to load route {self.route_id}")
            return False
        
        self.is_running = True
        self.start_time = datetime.now()
        
        # Start simulation in background thread
        self.thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self.thread.start()
        
        print(f"[GPS SIMULATOR] Started simulation for Bus {self.bus_id} on Route {self.route_id}")
        return True
    
    def stop(self) -> bool:
        """Stop the simulation."""
        if not self.is_running:
            return False
        
        self.is_running = False
        print(f"[GPS SIMULATOR] Stopped simulation for Bus {self.bus_id}")
        return True
    
    def get_status(self) -> dict:
        """Get current simulation status."""
        if not self.is_running or not self.start_time:
            return {
                "is_running": False,
                "bus_id": self.bus_id,
                "route_id": self.route_id,
                "progress": 0,
                "elapsed_seconds": 0,
            }
        
        from datetime import datetime
        elapsed = (datetime.now() - self.start_time).total_seconds()
        progress = min(elapsed / ROUTE_DURATION_SECONDS, 1.0)
        
        return {
            "is_running": True,
            "bus_id": self.bus_id,
            "route_id": self.route_id,
            "progress": progress,
            "elapsed_seconds": int(elapsed),
            "total_seconds": ROUTE_DURATION_SECONDS,
        }


# Global simulator instance
_current_simulator: Optional[BusSimulator] = None


def get_simulator() -> Optional[BusSimulator]:
    """Get the current simulator instance."""
    return _current_simulator


def set_simulator(simulator: Optional[BusSimulator]) -> None:
    """Set the current simulator instance."""
    global _current_simulator
    _current_simulator = simulator
