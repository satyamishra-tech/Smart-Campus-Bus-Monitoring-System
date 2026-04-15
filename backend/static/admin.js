// ── Selectors ──────────────────────────────────────────────
const routeSelect             = document.getElementById('bus-route-select');
const assignRouteSelect       = document.getElementById('assign-route-select');
const assignRouteBusSelect    = document.getElementById('assign-route-bus-select');
const assignBusSelect         = document.getElementById('assign-bus-select');
const assignDriverSelect      = document.getElementById('assign-driver-select');
const assignStudentRouteSelect = document.getElementById('assign-student-route-select');
const routeMapElement         = document.getElementById('route-map');
const mapStatusElement        = document.getElementById('map-status');
const routeStopsTextarea      = document.getElementById('route-stops');

let routeMap;
let routeMarkers = [];
let routePolyline;
let routeStops = [];

// ── Overview Route Map ──────────────────────────────────────
let overviewRouteMap;
let overviewMapInitialised = false;
let overviewRouteMarkers = [];
let overviewRoutePolyline;

function initOverviewRouteMapOnce() {
  if (overviewMapInitialised || typeof L === 'undefined') return;
  const mapEl = document.getElementById('overview-route-map');
  if (!mapEl) return;
  overviewMapInitialised = true;
  try {
    overviewRouteMap = L.map(mapEl).setView([23.0, 72.0], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(overviewRouteMap);
    setTimeout(() => overviewRouteMap.invalidateSize(), 200);
  } catch (err) {
    document.getElementById('overview-map-status').textContent = 'Map init failed';
  }
}

async function displayRouteOnOverviewMap(routeId) {
  if (!routeId) {
    console.warn('displayRouteOnOverviewMap: Missing routeId');
    return;
  }

  // Ensure map is initialized
  if (!overviewMapInitialised) {
    initOverviewRouteMapOnce();
  }

  if (!overviewRouteMap) {
    console.warn('displayRouteOnOverviewMap: overviewRouteMap not initialized');
    return;
  }
  
  // Clear previous markers and polyline
  overviewRouteMarkers.forEach((m) => m.remove());
  overviewRouteMarkers = [];
  if (overviewRoutePolyline) { 
    overviewRoutePolyline.remove(); 
    overviewRoutePolyline = null; 
  }

  try {
    const statusEl = document.getElementById('overview-map-status');
    if (statusEl) statusEl.textContent = 'Loading route...';
    
    const route = await request(`/api/v1/routes/${routeId}`);
    const stops = route.stops || [];
    
    if (!stops.length) {
      if (statusEl) statusEl.textContent = 'Route has no stops';
      return;
    }

    // Validate stops have valid coordinates
    const validStops = stops.filter(s => 
      s.latitude && s.longitude && 
      !isNaN(parseFloat(s.latitude)) && 
      !isNaN(parseFloat(s.longitude))
    );

    if (!validStops.length) {
      if (statusEl) statusEl.textContent = 'Route stops have invalid coordinates';
      return;
    }

    // Try to use geometry for actual road paths (curved lines)
    let geometryCoordinates = [];
    if (route.geometry && route.geometry.coordinates) {
      // Extract coordinates from GeoJSON geometry
      geometryCoordinates = route.geometry.coordinates.map((coord) => {
        // GeoJSON format is [lng, lat], but Leaflet expects [lat, lng]
        return [parseFloat(coord[1]), parseFloat(coord[0])];
      });
    }
    
    // Fallback to straight lines between stops if geometry not available
    const latlngs = geometryCoordinates.length > 0 
      ? geometryCoordinates 
      : validStops.map((s) => [parseFloat(s.latitude), parseFloat(s.longitude)]);
    
    // Add markers with better visibility
    validStops.forEach((s, idx) => {
      try {
        const lat = parseFloat(s.latitude);
        const lng = parseFloat(s.longitude);
        const marker = L.circleMarker([lat, lng], {
          radius: 8,
          fillColor: '#fee08b',
          color: '#bd0026',
          weight: 2,
          opacity: 1,
          fillOpacity: 0.8,
          title: s.name || `Stop ${s.stop_order}`
        }).addTo(overviewRouteMap);
        
        // Add stop name label tooltip
        const popupContent = `<strong>${s.name || 'Stop ' + s.stop_order}</strong><br/>Order: ${s.stop_order}<br/><button onclick="editStop(${s.id}, ${routeId})" style="padding: 4px 12px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; margin-top: 8px;">Edit</button>`;
        marker.bindPopup(popupContent);
        
        // Add click handler to show edit modal
        marker.on('click', () => {
          currentEditingStop = s;
          currentEditingRouteId = routeId;
          showEditStopModal(s);
        });
        
        overviewRouteMarkers.push(marker);
      } catch (e) {
        console.error('Error adding marker for stop', s, e);
      }
    });
    
    // Add polyline - will follow actual roads if geometry is available
    overviewRoutePolyline = L.polyline(latlngs, { 
      color: '#3b82f6', 
      weight: 4,
      opacity: 0.8,
      smoothFactor: 1.0
    }).addTo(overviewRouteMap);
    
    // Fit bounds and refresh map size
    setTimeout(() => {
      try {
        overviewRouteMap.invalidateSize(true);
        if (overviewRoutePolyline && overviewRoutePolyline.getBounds) {
          const bounds = overviewRoutePolyline.getBounds();
          if (bounds.isValid && bounds.isValid()) {
            overviewRouteMap.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
          }
        }
      } catch (e) {
        console.error('Error fitting bounds:', e);
      }
    }, 100);
    
    if (statusEl) statusEl.textContent = `${route.name} — ${validStops.length} stops displayed`;
  } catch (err) {
    console.error('Error displaying route:', err);
    const statusEl = document.getElementById('overview-map-status');
    if (statusEl) statusEl.textContent = 'Failed to load route: ' + err.message;
  }
}

// ── Global variables for edit stop functionality ──────────────
let currentEditingStop = null;
let currentEditingRouteId = null;
let locationSelectorMap = null;
let locationSelectorMarker = null;
let isSelectingLocation = false;

function populateOverviewRouteSelect() {
  const select = document.getElementById('overview-route-select');
  if (!select) return;
  const options = cachedRoutes.map((r) => 
    `<option value="${r.id}">${r.name} (${r.stop_count} stops)</option>`
  ).join('');
  select.innerHTML = `<option value="">Choose a route to view</option>${options}`;
}

// ── Toast ───────────────────────────────────────────────────
let toastTimer;
function showToast(message, isError = false) {
  const el   = document.getElementById('toast');
  const icon = document.getElementById('toast-icon');
  const msg  = document.getElementById('toast-msg');
  icon.textContent = isError ? '✕' : '✓';
  msg.textContent  = message;
  el.className = `toast show ${isError ? 'error' : 'success'}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => { el.className = 'toast hidden'; }, 250);
  }, 3500);
}

// ── Navigation ──────────────────────────────────────────────
const pageMeta = {
  overview: { title: 'Overview',  sub: 'Dashboard summary' },
  routes:   { title: 'Routes',    sub: 'Create and manage bus routes' },
  buses:    { title: 'Buses',     sub: 'Register buses and assign routes' },
  drivers:  { title: 'Drivers',   sub: 'Register drivers and assign to buses' },
  students: { title: 'Students',  sub: 'Assign routes and manage fee status' },
};

document.querySelectorAll('.nav-item').forEach((item) => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;
    document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
    document.querySelectorAll('.page').forEach((p) => p.classList.remove('active'));
    item.classList.add('active');
    document.getElementById(`page-${page}`).classList.add('active');
    document.getElementById('topbar-title').textContent    = pageMeta[page].title;
    document.getElementById('topbar-subtitle').textContent = pageMeta[page].sub;

    if (page === 'routes') {
      refreshRoutesTable();
      // Wait for container to be painted before Leaflet reads its dimensions
      setTimeout(() => {
        if (!mapInitialised) initRouteMapOnce();
        else if (routeMap)   routeMap.invalidateSize();
      }, 80);
    }
    if (page === 'overview') {
      refreshOverview();
      setTimeout(() => {
        if (!overviewMapInitialised) {
          initOverviewRouteMapOnce();
        }
        if (overviewRouteMap) {
          overviewRouteMap.invalidateSize();
        }
      }, 100);
    }
    if (page === 'buses')    refreshBusesTable();
    if (page === 'drivers')  refreshDriversTable();
  });
});

// ── HTTP helper ─────────────────────────────────────────────
async function request(url, method = 'GET', body) {
  const headers = { 'Content-Type': 'application/json' };
  
  // Include admin token if available
  const adminToken = localStorage.getItem('adminToken');
  if (adminToken) {
    headers['Authorization'] = `Bearer ${adminToken}`;
  }
  
  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  
  // Handle 401 - redirect to login if needed
  if (response.status === 401) {
    console.error('Authentication failed. Please ensure you have a valid admin token.');
    throw new Error('Missing or invalid authorization token');
  }
  
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || data.message || 'Request failed');
  return data;
}

// ── Map ─────────────────────────────────────────────────────
let mapInitialised = false;

function setMapStatus(message, isError = false) {
  if (!mapStatusElement) return;
  mapStatusElement.textContent = message;
  mapStatusElement.style.color = isError ? '#b91c1c' : '#6b7280';
}

function updateRouteStopsText() {
  routeStopsTextarea.value = routeStops
    .map((s) => `${s.name},${s.latitude},${s.longitude}`)
    .join('\n');
}

function refreshRouteMarkers() {
  routeMarkers.forEach((m) => m.remove());
  routeMarkers = [];
  if (routePolyline) { routePolyline.remove(); routePolyline = null; }
  if (!routeStops.length || !routeMap) return;

  const latlngs = routeStops.map((s) => [s.latitude, s.longitude]);
  routeStops.forEach((s) => {
    routeMarkers.push(L.marker([s.latitude, s.longitude]).addTo(routeMap).bindPopup(s.name));
  });
  routePolyline = L.polyline(latlngs, { color: '#2563eb' }).addTo(routeMap);
  routeMap.fitBounds(routePolyline.getBounds(), { padding: [20, 20] });
}

function addRouteStop(lat, lng) {
  const n = routeStops.length + 1;
  routeStops.push({ name: `Stop ${n}`, latitude: lat, longitude: lng, stop_order: n });
  updateRouteStopsText();
  refreshRouteMarkers();
}

function initRouteMapOnce() {
  if (mapInitialised || !routeMapElement || typeof L === 'undefined') return;
  mapInitialised = true;
  try {
    routeMap = L.map(routeMapElement).setView([23.0, 72.0], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    })
      .on('load', () => setMapStatus('Map loaded. Click to add stops.'))
      .on('tileerror', () => setMapStatus('Tile loading failed.', true))
      .addTo(routeMap);
    routeMap.on('click', (e) => addRouteStop(e.latlng.lat, e.latlng.lng));
    setTimeout(() => routeMap.invalidateSize(), 200);
  } catch (err) {
    setMapStatus('Map init failed: ' + err.message, true);
  }
}

function parseStops(text) {
  return text.split('\n').map((l) => l.trim()).filter(Boolean).map((l, i) => {
    const p = l.split(',').map((x) => x.trim());
    return { name: p[0] || `Stop ${i + 1}`, latitude: parseFloat(p[1]), longitude: parseFloat(p[2]), stop_order: i + 1 };
  });
}

// ── Data loaders ────────────────────────────────────────────
let cachedRoutes  = [];
let cachedBuses   = [];
let cachedDrivers = [];

async function loadRoutes() {
  cachedRoutes = await request('/api/v1/admin/routes');
  populateRouteSelects();
}

async function loadBuses() {
  cachedBuses = await request('/api/v1/admin/buses');
  populateBusSelects();
}

async function loadDrivers() {
  cachedDrivers = await request('/api/v1/admin/drivers');
  populateDriverSelects();
}

function populateRouteSelects() {
  const options = cachedRoutes.map((r) => `<option value="${r.id}">${r.name} (${r.stop_count} stops)</option>`).join('');
  routeSelect.innerHTML               = `<option value="">No route</option>${options}`;
  assignRouteSelect.innerHTML         = `<option value="">Select route</option>${options}`;
  assignStudentRouteSelect.innerHTML  = `<option value="">Select route</option>${options}`;
  populateOverviewRouteSelect();
  populateSimulationRouteSelect();
}

function populateBusSelects() {
  const options = cachedBuses.map((b) => {
    const route  = b.route_name  ? ` — ${b.route_name}`  : '';
    const driver = b.driver_name ? ` (${b.driver_name})` : '';
    return `<option value="${b.id}">${b.bus_number}${route}${driver}</option>`;
  }).join('');
  assignRouteBusSelect.innerHTML = `<option value="">Select bus</option>${options}`;
  assignBusSelect.innerHTML      = `<option value="">Select bus</option>${options}`;
}

function populateDriverSelects() {
  const options = cachedDrivers.map((d) =>
    `<option value="${d.roll_number}">${d.name} (${d.roll_number})</option>`
  ).join('');
  assignDriverSelect.innerHTML = `<option value="">Select driver</option>${options}`;
}

// ── Table renderers ─────────────────────────────────────────
function badge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}

function renderBusesTable(buses, tableId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!buses.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-row">No buses registered.</td></tr>';
    return;
  }
  tbody.innerHTML = buses.map((b, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><strong>${b.bus_number}</strong></td>
      <td>${b.route_name  || '<span style="color:#9ca3af">—</span>'}</td>
      <td>${b.driver_name || '<span style="color:#9ca3af">—</span>'}</td>
      <td>${badge(b.status)}</td>
    </tr>`).join('');
}

function renderRoutesTable(routes, tableId) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  if (!routes.length) {
    tbody.innerHTML = '<tr><td colspan="3" class="empty-row">No routes created.</td></tr>';
    return;
  }
  tbody.innerHTML = routes.map((r, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><strong>${r.name}</strong></td>
      <td>${r.stop_count}</td>
    </tr>`).join('');
}

function renderDriversTable(drivers, buses) {
  const tbody = document.querySelector('#drivers-table tbody');
  if (!drivers.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-row">No drivers registered.</td></tr>';
    return;
  }
  tbody.innerHTML = drivers.map((d, i) => {
    const bus = buses.find((b) => b.driver_id === d.id);
    return `
      <tr>
        <td>${i + 1}</td>
        <td>${d.roll_number}</td>
        <td><strong>${d.name}</strong></td>
        <td>${bus ? bus.bus_number : '<span style="color:#9ca3af">—</span>'}</td>
      </tr>`;
  }).join('');
}

async function refreshOverview() {
  try {
    await Promise.all([loadBuses(), loadRoutes(), loadDrivers()].map((p) => p.catch(() => null)));
    document.getElementById('stat-buses').textContent        = cachedBuses.length;
    document.getElementById('stat-routes').textContent       = cachedRoutes.length;
    document.getElementById('stat-drivers').textContent      = cachedDrivers.length;
    document.getElementById('stat-active-buses').textContent = cachedBuses.filter((b) => b.status === 'active').length;
    renderBusesTable(cachedBuses, 'overview-buses-table');
    renderRoutesTable(cachedRoutes, 'overview-routes-table');
    
    if (!overviewMapInitialised) {
      initOverviewRouteMapOnce();
    }
  } catch (_) {}
}

async function refreshBusesTable() {
  try { await loadBuses(); renderBusesTable(cachedBuses, 'buses-table'); } catch (_) {}
}

async function refreshRoutesTable() {
  try { await loadRoutes(); renderRoutesTable(cachedRoutes, 'routes-table'); } catch (_) {}
}

async function refreshDriversTable() {
  try {
    await Promise.all([loadDrivers(), loadBuses()]);
    renderDriversTable(cachedDrivers, cachedBuses);
  } catch (_) {}
}

async function refreshStudentsTable() {
  try {
    const students = await request('/api/v1/admin/users');
    const tbody = document.querySelector('#students-table tbody');
    if (!students.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">No students registered.</td></tr>';
      return;
    }
    tbody.innerHTML = students
      .filter((u) => u.role === 'student')
      .map((u, i) => `
        <tr>
          <td>${i + 1}</td>
          <td>${u.roll_number}</td>
          <td><strong>${u.name}</strong></td>
          <td>${u.route_name || '<span style="color:#9ca3af">—</span>'}</td>
          <td>${u.is_fee_paid ? '<span class="badge badge-active"><span class="badge-dot"></span>Paid</span>' : '<span class="badge badge-inactive"><span class="badge-dot"></span>Pending</span>'}</td>
        </tr>`)
      .join('');
  } catch (_) {}
}

// ── Actions ─────────────────────────────────────────────────
async function createRoute() {
  const name      = document.getElementById('route-name').value.trim();
  const stopsText = routeStopsTextarea.value.trim();
  if (!name) { showToast('Route name is required.', true); return; }

  let stops = [];
  if (routeStops.length) {
    stops = routeStops.map((s, i) => ({ ...s, stop_order: i + 1 }));
  } else if (stopsText) {
    stops = parseStops(stopsText);
    if (stops.find((s) => isNaN(s.latitude) || isNaN(s.longitude))) {
      showToast('Each stop needs valid latitude and longitude.', true); return;
    }
  }

  try {
    await request('/api/v1/admin/routes', 'POST', { name, stops });
    showToast('Route created successfully.');
    document.getElementById('route-name').value = '';
    routeStopsTextarea.value = '';
    routeStops = [];
    refreshRouteMarkers();
    await loadRoutes();
    renderRoutesTable(cachedRoutes, 'routes-table');
  } catch (err) { showToast(err.message, true); }
}

async function createBus() {
  const busNumber = document.getElementById('bus-number').value.trim();
  const routeId   = routeSelect.value;
  if (!busNumber) { showToast('Bus number is required.', true); return; }

  try {
    await request('/api/v1/admin/buses', 'POST', {
      bus_number: busNumber,
      route_id: routeId ? Number(routeId) : undefined,
    });
    showToast('Bus created successfully.');
    document.getElementById('bus-number').value = '';
    routeSelect.value = '';
    await loadBuses();
    renderBusesTable(cachedBuses, 'buses-table');
  } catch (err) { showToast(err.message, true); }
}

async function assignBusRoute() {
  const busId   = assignRouteBusSelect.value;
  const routeId = assignRouteSelect.value;
  if (!busId || !routeId) { showToast('Select both a bus and a route.', true); return; }

  try {
    await request(`/api/v1/admin/buses/${busId}/route`, 'POST', { route_id: Number(routeId) });
    showToast('Route assigned to bus.');
    assignRouteBusSelect.value = '';
    assignRouteSelect.value    = '';
    await loadBuses();
    renderBusesTable(cachedBuses, 'buses-table');
  } catch (err) { showToast(err.message, true); }
}

async function registerDriver() {
  const roll     = document.getElementById('driver-roll').value.trim();
  const name     = document.getElementById('driver-name').value.trim();
  const password = document.getElementById('driver-password').value;
  if (!roll || !name || !password) { showToast('All fields are required.', true); return; }

  try {
    await request('/api/v1/admin/drivers', 'POST', { roll_number: roll, name, password, role: 'driver' });
    showToast('Driver registered successfully.');
    document.getElementById('driver-roll').value      = '';
    document.getElementById('driver-name').value      = '';
    document.getElementById('driver-password').value  = '';
    await loadDrivers();
    renderDriversTable(cachedDrivers, cachedBuses);
  } catch (err) { showToast(err.message, true); }
}

async function assignDriver() {
  const busId      = assignBusSelect.value;
  const driverRoll = assignDriverSelect.value;
  if (!busId || !driverRoll) { showToast('Select both a bus and a driver.', true); return; }

  try {
    await request(`/api/v1/admin/buses/${busId}/assign-driver`, 'POST', { driver_roll_number: driverRoll });
    showToast('Driver assigned to bus.');
    assignBusSelect.value    = '';
    assignDriverSelect.value = '';
    await loadBuses();
    renderDriversTable(cachedDrivers, cachedBuses);
    renderBusesTable(cachedBuses, 'buses-table');
  } catch (err) { showToast(err.message, true); }
}

async function assignStudentRoute() {
  const roll    = document.getElementById('assign-student-roll').value.trim();
  const routeId = assignStudentRouteSelect.value;
  if (!roll || !routeId) { showToast('Roll number and route are required.', true); return; }

  try {
    await request(`/api/v1/admin/students/${encodeURIComponent(roll)}/route`, 'PATCH', { route_id: Number(routeId) });
    showToast('Route assigned to student.');
    document.getElementById('assign-student-roll').value = '';
    assignStudentRouteSelect.value = '';
  } catch (err) { showToast(err.message, true); }
}

async function updateStudentFeeStatus() {
  const roll      = document.getElementById('verify-student-roll').value.trim();
  const isFeePaid = document.getElementById('student-fee-paid').checked;
  if (!roll) { showToast('Student roll number is required.', true); return; }

  try {
    await request(`/api/v1/admin/students/${encodeURIComponent(roll)}/fee`, 'PATCH', { is_fee_paid: isFeePaid });
    showToast('Fee status updated.');
    document.getElementById('verify-student-roll').value = '';
    document.getElementById('student-fee-paid').checked  = false;
  } catch (err) { showToast(err.message, true); }
}

// ── Edit Stop Modal Functions ────────────────────────────
function editStop(stopId, routeId) {
  // Find the stop in the current stops list
  // This is a helper function called from popup button
  if (currentEditingStop && currentEditingStop.id === stopId) {
    showEditStopModal(currentEditingStop);
  }
}

function showEditStopModal(stop) {
  document.getElementById('edit-stop-name').value = stop.name || '';
  document.getElementById('edit-stop-latitude').value = stop.latitude || '';
  document.getElementById('edit-stop-longitude').value = stop.longitude || '';
  document.getElementById('edit-stop-order').value = stop.stop_order || 1;
  
  const modal = document.getElementById('edit-stop-modal');
  modal.classList.remove('hidden');
}

function hideEditStopModal() {
  const modal = document.getElementById('edit-stop-modal');
  modal.classList.add('hidden');
  if (locationSelectorMap) {
    locationSelectorMap.remove();
    locationSelectorMap = null;
    locationSelectorMarker = null;
  }
  currentEditingStop = null;
  currentEditingRouteId = null;
  isSelectingLocation = false;
}

function toggleLocationSelector() {
  const mapContainer = document.getElementById('location-selector-map');
  const hint = document.getElementById('location-hint');
  
  if (!isSelectingLocation) {
    // Show map
    isSelectingLocation = true;
    mapContainer.style.display = 'block';
    hint.textContent = 'Click on the map to select a location';
    
    // Initialize map if needed
    if (!locationSelectorMap) {
      initLocationSelectorMap();
    } else {
      locationSelectorMap.invalidateSize();
    }
    
    // Fit map to current coordinates if available
    const lat = parseFloat(document.getElementById('edit-stop-latitude').value);
    const lng = parseFloat(document.getElementById('edit-stop-longitude').value);
    if (!isNaN(lat) && !isNaN(lng)) {
      locationSelectorMap.setView([lat, lng], 15);
    }
  } else {
    // Hide map
    isSelectingLocation = false;
    mapContainer.style.display = 'none';
    hint.textContent = 'Location selected. Click "Choose Location on Map" to change.';
  }
}

function initLocationSelectorMap() {
  const container = document.getElementById('location-selector-map');
  if (!container) return;
  
  if (locationSelectorMap) {
    locationSelectorMap.remove();
  }
  
  locationSelectorMap = L.map(container).setView([28.6139, 77.2090], 13);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors',
  }).addTo(locationSelectorMap);
  
  // Handle map click to select location
  locationSelectorMap.on('click', (e) => {
    const { lat, lng } = e.latlng;
    
    // Update input fields
    document.getElementById('edit-stop-latitude').value = lat.toFixed(6);
    document.getElementById('edit-stop-longitude').value = lng.toFixed(6);
    
    // Remove old marker if exists
    if (locationSelectorMarker) {
      locationSelectorMap.removeLayer(locationSelectorMarker);
    }
    
    // Add new marker
    locationSelectorMarker = L.circleMarker([lat, lng], {
      radius: 8,
      fillColor: '#fee08b',
      color: '#bd0026',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.8,
    }).addTo(locationSelectorMap);
    
    // Show success message
    const hint = document.getElementById('location-hint');
    hint.textContent = `Location selected: ${lat.toFixed(4)}, ${lng.toFixed(4)}. Click again to change or save.`;
  });
  
  // Fit bounds if marker exists
  setTimeout(() => locationSelectorMap.invalidateSize(), 300);
}

async function deleteStop() {
  if (!currentEditingStop || !currentEditingRouteId) {
    showToast('No stop selected for deletion', true);
    return;
  }

  const confirmDelete = confirm(
    `Are you sure you want to delete stop "${currentEditingStop.name}"?\n\nOther stops' order will be automatically adjusted.`
  );
  
  if (!confirmDelete) return;

  try {
    await request(
      `/api/v1/routes/${currentEditingRouteId}/stops/${currentEditingStop.id}`,
      'DELETE'
    );

    showToast('Stop deleted successfully');
    hideEditStopModal();
    
    // Reload the route to show updated data
    const routeSelect = document.getElementById('overview-route-select');
    if (routeSelect && routeSelect.value == currentEditingRouteId) {
      displayRouteOnOverviewMap(currentEditingRouteId);
    }
  } catch (err) {
    showToast(`Error deleting stop: ${err.message}`, true);
  }
}

async function saveEditedStop() {
  if (!currentEditingStop || !currentEditingRouteId) {
    showToast('No stop selected for editing', true);
    return;
  }

  const name = document.getElementById('edit-stop-name').value.trim();
  const latitude = parseFloat(document.getElementById('edit-stop-latitude').value);
  const longitude = parseFloat(document.getElementById('edit-stop-longitude').value);
  const stopOrder = parseInt(document.getElementById('edit-stop-order').value);

  if (!name) {
    showToast('Stop name is required', true);
    return;
  }

  if (isNaN(latitude) || isNaN(longitude)) {
    showToast('Valid latitude and longitude are required', true);
    return;
  }

  try {
    await request(
      `/api/v1/routes/${currentEditingRouteId}/stops/${currentEditingStop.id}`,
      'PATCH',
      {
        name,
        latitude,
        longitude,
        stop_order: stopOrder,
      }
    );

    showToast('Stop updated successfully');
    hideEditStopModal();
    
    // Reload the route to show updated data
    const routeSelect = document.getElementById('overview-route-select');
    if (routeSelect && routeSelect.value == currentEditingRouteId) {
      displayRouteOnOverviewMap(currentEditingRouteId);
    }
  } catch (err) {
    showToast(`Error updating stop: ${err.message}`, true);
  }
}

// ── Bus Simulation ──────────────────────────────────────────
let simulationStatusInterval = null;

async function startSimulation() {
  const routeSelect = document.getElementById('simulation-route-select');
  const routeId = routeSelect.value;
  
  if (!routeId) {
    showToast('Please select a route to simulate', true);
    return;
  }
  
  try {
    const response = await request(`/api/v1/simulation/start?route_id=${Number(routeId)}`, 'POST');
    showToast(`Simulation started for Route ${routeId}`);
    
    // Show status box and start polling
    document.getElementById('simulation-status-box').style.display = 'block';
    document.getElementById('simulation-message').style.display = 'none';
    
    startSimulationStatusPolling();
  } catch (err) {
    showToast(`Failed to start simulation: ${err.message}`, true);
  }
}

async function stopSimulation() {
  try {
    await request('/api/v1/simulation/stop', 'POST');
    showToast('Simulation stopped');
    
    // Hide status box and clear polling
    if (simulationStatusInterval) {
      clearInterval(simulationStatusInterval);
      simulationStatusInterval = null;
    }
    document.getElementById('simulation-status-box').style.display = 'none';
    document.getElementById('simulation-message').style.display = 'none';
  } catch (err) {
    showToast(`Failed to stop simulation: ${err.message}`, true);
  }
}

async function updateSimulationStatus() {
  try {
    const status = await request('/api/v1/simulation/status');
    
    if (!status.is_running) {
      if (simulationStatusInterval) {
        clearInterval(simulationStatusInterval);
        simulationStatusInterval = null;
      }
      document.getElementById('simulation-status-box').style.display = 'none';
      return;
    }
    
    // Update progress bar and text
    const progressPercent = (status.progress || 0) * 100;
    const elapsed = status.elapsed_seconds || 0;
    const remaining = status.remaining_seconds || 0;
    
    // Format time
    const formatTime = (seconds) => {
      const mins = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    };
    
    document.getElementById('sim-progress').textContent = `${progressPercent.toFixed(1)}%`;
    document.getElementById('sim-elapsed').textContent = formatTime(elapsed);
    document.getElementById('sim-progress-bar').style.width = `${progressPercent}%`;
    document.getElementById('sim-remaining').textContent = `Remaining: ~${formatTime(remaining)}`;
    
    // Hide when complete
    if (progressPercent >= 100) {
      if (simulationStatusInterval) {
        clearInterval(simulationStatusInterval);
        simulationStatusInterval = null;
      }
      document.getElementById('simulation-status-box').style.display = 'none';
      showToast('Simulation completed!');
    }
  } catch (err) {
    console.error('Error updating simulation status:', err);
  }
}

function startSimulationStatusPolling() {
  // Poll every 2 seconds
  if (simulationStatusInterval) {
    clearInterval(simulationStatusInterval);
  }
  updateSimulationStatus();
  simulationStatusInterval = setInterval(updateSimulationStatus, 2000);
}

// Populate simulation route select with same routes
function populateSimulationRouteSelect() {
  const select = document.getElementById('simulation-route-select');
  if (!select) return;
  const options = cachedRoutes.map((r) => 
    `<option value="${r.id}">${r.name} (${r.stop_count} stops)</option>`
  ).join('');
  select.innerHTML = `<option value="">Choose a route</option>${options}`;
}

// ── Init ────────────────────────────────────────────────────

// Initialize admin token before loading data
async function initAdmin() {
  try {
    // Check if we already have a valid token
    const existingToken = localStorage.getItem('adminToken');
    if (existingToken) {
      console.log('Using existing admin token');
      return;
    }
    
    // Get a new admin token
    const response = await fetch('/api/v1/auth/admin-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get admin token: ${response.status}`);
    }
    
    const data = await response.json();
    if (data.access_token) {
      localStorage.setItem('adminToken', data.access_token);
      console.log('Admin token stored successfully');
    }
  } catch (err) {
    console.error('Error initializing admin:', err);
    showToast('Warning: Could not initialize admin session', true);
  }
}

// Initialize admin then load data
initAdmin().then(() => refreshOverview());

document.getElementById('clear-stops-button').addEventListener('click', () => {
  routeStops = []; routeStopsTextarea.value = ''; refreshRouteMarkers();
  showToast('Stops cleared.');
});

routeStopsTextarea.addEventListener('input', () => {
  if (!routeStopsTextarea.value.trim()) { routeStops = []; refreshRouteMarkers(); }
});

// Safely add event listeners - check if element exists before listening
function safeAddListener(elementId, event, handler) {
  const el = document.getElementById(elementId);
  if (el) {
    el.addEventListener(event, handler);
  } else {
    console.warn(`Element not found for listener: ${elementId}`);
  }
}

// Add all event listeners with safety checks
safeAddListener('create-route-button', 'click', createRoute);
safeAddListener('create-bus-button', 'click', createBus);
safeAddListener('assign-bus-route-button', 'click', assignBusRoute);
safeAddListener('register-driver-button', 'click', registerDriver);
safeAddListener('assign-driver-button', 'click', assignDriver);
safeAddListener('assign-student-route-button', 'click', assignStudentRoute);
safeAddListener('update-fee-status-button', 'click', updateStudentFeeStatus);

safeAddListener('refresh-overview-btn', 'click', refreshOverview);
safeAddListener('refresh-routes-btn', 'click', refreshRoutesTable);
safeAddListener('refresh-buses-btn', 'click', refreshBusesTable);
safeAddListener('refresh-drivers-btn', 'click', refreshDriversTable);
safeAddListener('refresh-students-btn', 'click', refreshStudentsTable);

// Route dropdown event listener for overview route map
const overviewRouteSelect = document.getElementById('overview-route-select');
if (overviewRouteSelect) {
  overviewRouteSelect.addEventListener('change', (e) => {
    const routeId = e.target.value;
    if (routeId) {
      console.log('Selected route ID:', routeId);
      displayRouteOnOverviewMap(Number(routeId));
    } else {
      overviewRouteMarkers.forEach((m) => m.remove());
      overviewRouteMarkers = [];
      if (overviewRoutePolyline) overviewRoutePolyline.remove();
      if (document.getElementById('overview-map-status')) {
        document.getElementById('overview-map-status').textContent = 'Select a route to display';
      }
    }
  });
}

// Modal event listeners
const modal = document.getElementById('edit-stop-modal');
const modalOverlay = document.getElementById('modal-overlay');
const closeModalBtn = document.getElementById('close-modal-btn');
const cancelEditBtn = document.getElementById('cancel-edit-btn');
const saveEditBtn = document.getElementById('save-edit-btn');
const selectLocationBtn = document.getElementById('select-location-btn');
const deleteStopBtn = document.getElementById('delete-stop-btn');

if (closeModalBtn) closeModalBtn.addEventListener('click', hideEditStopModal);
if (cancelEditBtn) cancelEditBtn.addEventListener('click', hideEditStopModal);
if (modalOverlay) modalOverlay.addEventListener('click', hideEditStopModal);
if (saveEditBtn) saveEditBtn.addEventListener('click', saveEditedStop);
if (selectLocationBtn) selectLocationBtn.addEventListener('click', toggleLocationSelector);
if (deleteStopBtn) deleteStopBtn.addEventListener('click', deleteStop);

// Simulation event listeners
safeAddListener('start-simulation-btn', 'click', startSimulation);
safeAddListener('stop-simulation-btn', 'click', stopSimulation);
safeAddListener('refresh-sim-status-btn', 'click', updateSimulationStatus);
