import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, ZoomControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css'; // CRITICAL: Required for Leaflet styles
import L from 'leaflet';
import WeatherCalendar from './WeatherCalendar';
import CityMap3D from './CityMap3D';
import RoutePanel from './RoutePanel';

const ORIGIN_LAT = 55.752317;
const ORIGIN_LNG = 48.744578;

const DRONEPORT_LAT = 55.7528;
const DRONEPORT_LNG = 48.7452;

// --- Helper Functions for Icons ---

const createLampIcon = (status, is_on, state) => {
  const borderColor = getBorderColor(is_on);
  const coreColor = getColor(state);
  return L.divIcon({
    className: 'custom-lamp-icon',
    html: `
      <div class="lamp-marker">
        <div class="lamp-halo" style="border-color: ${borderColor}; color: ${borderColor}"></div>
        <div class="lamp-core" style="background-color: ${coreColor}; color: ${coreColor}"></div>
      </div>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15]
  });
};

const createDroneIcon = () => {
  return L.divIcon({
    className: 'custom-drone-icon',
    html: `
      <div class="drone-marker">
        <div class="drone-arm arm-1"></div>
        <div class="drone-arm arm-2"></div>
        <div class="drone-body"></div>
        <div class="drone-prop tl"></div>
        <div class="drone-prop tr"></div>
        <div class="drone-prop bl"></div>
        <div class="drone-prop br"></div>
      </div>
    `,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -15]
  });
};

const createDroneportIcon = () => {
  return L.divIcon({
    className: 'custom-droneport-icon',
    html: `
      <div class="droneport-marker">
        <div class="droneport-base">
          <div class="droneport-pad"></div>
          <div class="droneport-beacon"></div>
        </div>
      </div>
    `,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20]
  });
};

const mapLampFromApi = (item) => {
  const state = 1 - (item.failure_prob ?? 0);
  const isBroken = item.status === 'burned_out' || item.status === 'absent' || item.status === 'maintenance';
  
  return {
    id: item.id,
    lat: item.lat,
    lng: item.lng,
    status: isBroken ? 'broken' : 'ok', // Internal logic: 'ok' or 'broken' for Label
    is_on: item.is_on ?? false,         // Explicit ON/OFF for Border
    state: isBroken ? 0.0 : Math.max(0, Math.min(1, state)), // Force 0 if broken
    address: item.address
  };
};

const getBorderColor = (is_on) => {
  return is_on ? '#2ecc71' : '#95a5a6'; // Green if ON, Grey if OFF
};

const getColor = (stat) => {
  if (stat <= 0.34) return '#e74c3c';  // failure_probability >= 0.66 → нужна замена
  if (stat < 0.66) return '#e4f312';
  return '#2ecc71';
};

const getLabel = (status) => {
  return status === 'broken' ? 'Сломана' : 'Работает';
};

// Component to fix map rendering issues on resize/mount
const MapUpdater = () => {
  const map = useMap();
  
  useEffect(() => {
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 100);
    return () => clearTimeout(timer);
  }, [map]);

  return null;
};

const CityMap = () => {
  const [is3D, setIs3D] = useState(false); // Toggle 3D mode
  const [lamps, setLamps] = useState([]);
  const [, setWsStatus] = useState('Отключено');
  const [isBadWeather, setIsBadWeather] = useState(false); // New state for weather
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  const connectWebSocketRef = useRef(null);
  const [droneStatus, setDroneStatus] = useState('idle');
  const [dronePos, setDronePos] = useState({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
  const [dronePath, setDronePath] = useState([]);
  const [currentTargetIndex, setCurrentTargetIndex] = useState(0);
  const animationRef = useRef(null);
  const dronePosRef = useRef({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
  const lampsRef = useRef([]);
  const droneStatusRef = useRef('idle');
  const targetIndexRef = useRef(0);
  const waitUntilRef = useRef(null);
  const currentSpeedRef = useRef(0); // For smooth acceleration
  
  const [routeData, setRouteData] = useState(null); // Data from Routing-AI
  const isPlanningRef = useRef(false); // Prevent multiple concurrent mission starts

  const [activeScenario, setActiveScenario] = useState(null);
  const [showScenarios, setShowScenarios] = useState(false);

  const SCENARIOS = [
    { id: 1, label: 'Сценарий 1', desc: '3 лампы', lampIds: [2, 8, 20], color: '#e67e22' },
    { id: 2, label: 'Сценарий 2', desc: '5 ламп',  lampIds: [1, 6, 13, 21, 27], color: '#8e44ad' },
    { id: 3, label: 'Сценарий 3', desc: '8 ламп',  lampIds: [3, 7, 11, 15, 18, 23, 26, 29], color: '#c0392b' },
  ];

  const resetAllLamps = async () => {
    setActiveScenario(null);
    // Send request to backend, no optimistic update
    fetch('http://localhost:8000/api/lamps/scenario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lamp_ids: Array.from({length: 30}, (_, i) => i + 1), action: 'fix' }),
    }).catch(() => {});
  };

  const activateScenario = async (scenario) => {
    setActiveScenario(scenario.id);
    // 1. Reset everything first (optional, but good for consistency)
    await fetch('http://localhost:8000/api/lamps/scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lamp_ids: Array.from({length: 30}, (_, i) => i + 1), action: 'fix' }),
    }).catch(() => {});

    // 2. Break specific lamps
    fetch('http://localhost:8000/api/lamps/scenario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lamp_ids: scenario.lampIds, action: 'break' }),
    }).catch(() => {});
  };

  const connectWebSocket = useCallback(() => {
    // Clear existing timeout if any
    if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);

    try {
      ws.current = new WebSocket('ws://localhost:8000/api/ws');

      ws.current.onopen = () => {
        console.log('Connected to WebSocket');
        setWsStatus('Подключено');
      };

      ws.current.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          // console.log('WS Update:', parsed); // Debug
          // Handle both single update and array of updates
          const updates = Array.isArray(parsed) ? parsed : [parsed];
          
          setLamps(prevLamps => {
            let newLamps = [...prevLamps];
            let hasChanges = false;

            updates.forEach(data => {
              if (!data.id) return;

              const index = newLamps.findIndex(lamp => lamp.id === data.id);
              const prev = index >= 0 ? newLamps[index] : null;
              
              // New parsing logic based on explicit fields
              const isBroken = data.status === 'burned_out' || data.status === 'absent' || data.status === 'maintenance' || data.status === 'broken';
              const newInternalStatus = isBroken ? 'broken' : 'ok';
              const newIsOn = data.is_on ?? prev?.is_on ?? false;

              // Logic for state (health):
              // Purely from backend now.
              let newState = isBroken ? 0.0 : (typeof data.state === 'number' ? data.state : (prev?.state ?? 1));

              const nextLamp = {
                id: data.id,
                lat: data.lat ?? prev?.lat ?? ORIGIN_LAT,
                lng: data.lng ?? prev?.lng ?? ORIGIN_LNG,
                address: data.address ?? prev?.address ?? '',
                status: newInternalStatus,
                is_on: newIsOn,
                state: newState
              };

              if (index === -1) {
                newLamps.push(nextLamp);
                hasChanges = true;
              } else if (JSON.stringify(prev) !== JSON.stringify(nextLamp)) {
                 newLamps[index] = nextLamp;
                 hasChanges = true;
              }
            });

            return hasChanges ? newLamps : prevLamps;
          });
        } catch (error) {
          console.error('Error parsing message:', error);
        }
      };

      ws.current.onclose = () => {
        console.log('WebSocket closed');
        setWsStatus('Отключено');
        // Attempt to reconnect after 3 seconds
        reconnectTimeout.current = setTimeout(() => {
          setWsStatus('Переподключение...');
          connectWebSocketRef.current?.();
        }, 3000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsStatus('Ошибка');
        // Close connection to trigger onclose/reconnect logic
        if(ws.current) ws.current.close(); 
      };

    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setWsStatus('Сбой');
    }
  }, []);

  useEffect(() => {
    connectWebSocketRef.current = connectWebSocket;
  }, [connectWebSocket]);

  useEffect(() => {
    const controller = new AbortController();
    fetch('http://localhost:8000/api/lamps', { signal: controller.signal })
      .then(res => res.json())
      .then(data => {
        const mapped = data
          .filter(item => item.id)
          .map(mapLampFromApi);
        setLamps(mapped);
      })
      .catch(() => {});

    const wsTimeout = setTimeout(() => connectWebSocket(), 0);

    return () => {
      clearTimeout(wsTimeout);
      controller.abort();
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [connectWebSocket]);

  useEffect(() => {
    dronePosRef.current = dronePos;
  }, [dronePos]);

  useEffect(() => {
    lampsRef.current = lamps;
  }, [lamps]);

  useEffect(() => {
    droneStatusRef.current = droneStatus;
  }, [droneStatus]);

  useEffect(() => {
    targetIndexRef.current = currentTargetIndex;
  }, [currentTargetIndex]);

  useEffect(() => {
    if (droneStatus !== 'toLamp' && droneStatus !== 'return') {
        if (animationRef.current) {
            cancelAnimationFrame(animationRef.current);
            animationRef.current = null;
        }
        return;
    }
    
    // Safety check for empty path
    if (droneStatus === 'toLamp' && (!dronePath || dronePath.length === 0)) {
        setDroneStatus('return');
        return;
    }

    // Reset wait timer on new target/status
    waitUntilRef.current = null;

    const maxSpeed = 0.00001; // Slower speed for better precision
    const acceleration = 0.0000005;
    const decelerationDist = 0.0005;
    let lastTime = performance.now();

    const step = (time) => {
      try {
        const dt = time - lastTime;
        lastTime = time;
        
        // Limit dt to avoid huge jumps if tab was inactive
        const safeDt = Math.min(dt, 50);

        const pos = dronePosRef.current;
        let target;

        // Use direct variables from closure where possible to avoid Ref desync
        // currentTargetIndex is fixed for this effect instance
        const currentIdx = currentTargetIndex; 
        const currentPath = dronePath;
        const currentStatus = droneStatus;

        if (currentStatus === 'toLamp') {
          if (currentIdx >= currentPath.length) {
              setDroneStatus('return');
              return;
          }

          const lampId = currentPath[currentIdx];
          const lamp = lampsRef.current.find(l => l.id === lampId);

          if (!lamp) {
            console.warn(`Lamp ${lampId} not found, skipping`);
            if (currentIdx + 1 < currentPath.length) {
              setCurrentTargetIndex(prev => prev + 1);
            } else {
              setDroneStatus('return');
            }
            return;
          }

          target = { lat: lamp.lat, lng: lamp.lng };
        } else {
          target = { lat: DRONEPORT_LAT, lng: DRONEPORT_LNG };
        }

        const dx = target.lng - pos.lng;
        const dy = target.lat - pos.lat;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // Animation Logic - High precision arrival
        if (dist < 0.000005) {
          // Reached target
          currentSpeedRef.current = 0; // Reset speed
          
          // Snap to exact target position to avoid visual gap
          if (dist > 0) {
              setDronePos(target);
          }

          if (currentStatus === 'toLamp') {
            const now = performance.now();

            if (!waitUntilRef.current) {
              // Start waiting
              console.log("Arrived at lamp, starting repair...");
              waitUntilRef.current = now + 1000;
              animationRef.current = requestAnimationFrame(step);
              return;
            }

            if (now < waitUntilRef.current) {
              // Still waiting
              animationRef.current = requestAnimationFrame(step);
              return;
            }

            // Waiting done
            waitUntilRef.current = null;

            const lampId = currentPath[currentIdx];
            console.log(`Repairing lamp ${lampId}...`);
            
            // Sync with backend (ALWAYS repair)
            fetch(`http://localhost:8000/api/lamps/${lampId}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ status: 'ok' })
            }).catch(e => console.error("Repair sync failed", e));

            // Force local update for immediate feedback
            setLamps(prev => prev.map(l => 
                l.id === lampId ? { ...l, state: 1.0, status: 'ok' } : l
            ));

            if (ws.current && ws.current.readyState === WebSocket.OPEN) {
              const message = JSON.stringify({ id: lampId, state: 1 });
              ws.current.send(message);
            }

            if (currentIdx + 1 < currentPath.length) {
              console.log(`Moving to next lamp. Current: ${currentIdx}, Next: ${currentIdx + 1}`);
              setCurrentTargetIndex(prev => prev + 1);
              return; // Stop this loop, let effect restart
            } else {
              console.log("All lamps visited, returning");
              setDroneStatus('return');
              return; // Stop this loop, let effect restart
            }
          } else {
            // Reached Droneport
            console.log("Returned to base");
            setDroneStatus('idle');
            setDronePath([]);
            setCurrentTargetIndex(0);
            setDronePos({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
            return; // Stop animation
          }
        } else {
          // Move towards target
          
          // Acceleration / Deceleration
          if (dist < decelerationDist) {
            // Decelerate
            currentSpeedRef.current = Math.max(0.000005, currentSpeedRef.current - acceleration * safeDt);
          } else {
            // Accelerate
            currentSpeedRef.current = Math.min(maxSpeed, currentSpeedRef.current + acceleration * safeDt);
          }

          const moveDist = currentSpeedRef.current * safeDt; // Scale by dt
          // Ensure we don't overshoot
          const actualMove = Math.min(moveDist, dist); 
          const ratio = actualMove / dist;

          setDronePos(prev => ({
            lat: prev.lat + dy * ratio,
            lng: prev.lng + dx * ratio
          }));
        }

        animationRef.current = requestAnimationFrame(step);
      } catch (e) {
        console.error("Animation step error:", e);
        // Try to recover?
        // animationRef.current = requestAnimationFrame(step);
      }
    };

    animationRef.current = requestAnimationFrame(step);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [droneStatus, dronePath, currentTargetIndex]);

  const MIN_BROKEN_TO_FLY = 1;

  const startDroneMission = useCallback(async () => {
    if (droneStatus !== 'idle') return;
    if (isBadWeather) return;
    if (isPlanningRef.current) return;

    isPlanningRef.current = true;

    try {
        const brokenLamps = lampsRef.current.filter(l => l.state <= 0.34);
        if (brokenLamps.length < MIN_BROKEN_TO_FLY) return;

        // Запрашиваем оптимальный маршрут для всех случаев (даже 1 лампа) для получения метрик
        let pathIds = brokenLamps.map(l => l.id);
        
        if (brokenLamps.length >= 1) {
        try {
            // Add abort controller with 3s timeout to prevent long hangs
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3000);

            const resp = await fetch('http://localhost:8000/api/route/optimize', { 
                method: 'POST',
                signal: controller.signal
            });
            clearTimeout(timeoutId);

            if (resp.ok) {
            const data = await resp.json();
            // Only update if we got a valid route, preserving last flight stats otherwise
            if (!data.message) {
                setRouteData({ ...data, timestamp: Date.now() });
            }
            
            if (data.route_ids?.length > 0) {
                const brokenIdSet = new Set(brokenLamps.map(l => l.id));
                const ordered = data.route_ids.map(Number).filter(id => brokenIdSet.has(id));
                const remaining = brokenLamps.map(l => l.id).filter(id => !ordered.includes(id));
                pathIds = [...ordered, ...remaining];
            }
            }
        } catch (e) {
            console.error('Route optimization failed or timed out, using local Nearest Neighbor fallback', e);
            
            // Local Nearest Neighbor Algorithm
            const remaining = [...brokenLamps];
            const sortedIds = [];
            let currentPos = { lat: DRONEPORT_LAT, lng: DRONEPORT_LNG };

            while (remaining.length > 0) {
                // Find nearest
                let nearestIdx = -1;
                let minDist = Infinity;

                remaining.forEach((lamp, idx) => {
                    const d = Math.sqrt(
                        Math.pow(lamp.lat - currentPos.lat, 2) + 
                        Math.pow(lamp.lng - currentPos.lng, 2)
                    );
                    if (d < minDist) {
                        minDist = d;
                        nearestIdx = idx;
                    }
                });

                if (nearestIdx !== -1) {
                    const nearest = remaining[nearestIdx];
                    sortedIds.push(nearest.id);
                    currentPos = { lat: nearest.lat, lng: nearest.lng };
                    remaining.splice(nearestIdx, 1);
                } else {
                    break; // Should not happen
                }
            }
            pathIds = sortedIds;
        }
        }

        if (pathIds.length > 0) {
            setDronePath(pathIds);
            setCurrentTargetIndex(0);
            setDronePos({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
            setDroneStatus('toLamp');
        }
    } finally {
        isPlanningRef.current = false;
    }
  }, [droneStatus, isBadWeather]);

  // Memoize broken lamps identifier to avoid unnecessary resets on noisy updates
  const brokenLampIdsHash = lamps
    .filter(l => l.state <= 0.34)
    .map(l => l.id)
    .sort()
    .join(',');

  useEffect(() => {
    if (droneStatus !== 'idle') return;
    if (isBadWeather) return;
    if (!brokenLampIdsHash) return;

    // Delay before launch (0.5s - 1.0s requirement)
    // Using 600ms to be safe above 0.5s
    const timeout = setTimeout(() => startDroneMission(), 600);
    return () => clearTimeout(timeout);
  }, [brokenLampIdsHash, droneStatus, startDroneMission, isBadWeather]);

  useEffect(() => {
    // Inject custom styles for zoom controls
    const style = document.createElement('style');
    style.innerHTML = `
      .leaflet-control-zoom {
        border: none !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
        margin-left: 10px !important;
        margin-bottom: 24px !important; /* Raised slightly */
        display: flex !important;
        flex-direction: row !important;
        gap: 2px !important; /* Tiny gap for pill effect */
        background: transparent !important;
        overflow: visible !important;
      }
      .leaflet-control-zoom-in, .leaflet-control-zoom-out {
        background-color: #2b2d30 !important; /* Yandex Panel Color */
        color: #f2f2f2 !important;
        width: 40px !important;
        height: 40px !important;
        line-height: 40px !important;
        margin: 0 !important;
        font-size: 18px !important;
        border: none !important;
        transition: all 0.2s ease;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;
      }
      /* Pill shape logic */
      .leaflet-control-zoom-in {
        border-top-left-radius: 12px !important;
        border-bottom-left-radius: 12px !important;
        border-top-right-radius: 0 !important;
        border-bottom-right-radius: 0 !important;
        margin-right: 1px !important; /* Thin separator */
      }
      .leaflet-control-zoom-out {
        border-top-right-radius: 12px !important;
        border-bottom-right-radius: 12px !important;
        border-top-left-radius: 0 !important;
        border-bottom-left-radius: 0 !important;
      }
      .leaflet-control-zoom-in:hover, .leaflet-control-zoom-out:hover {
        background-color: #3c3f41 !important;
        color: white !important;
        transform: translateY(-1px);
      }
      .leaflet-bottom .leaflet-control {
        margin-bottom: 10px;
      }
      .leaflet-left .leaflet-control {
        margin-left: 10px;
      }
      /* Yandex-like Dark Map Style using CSS Filters */
      .leaflet-layer,
      .leaflet-control-zoom-in,
      .leaflet-control-zoom-out,
      .leaflet-control-attribution {
        filter: none !important;
      }
      .leaflet-tile-pane {
        filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%);
      }
      /* Keep attribution readable */
      .leaflet-control-attribution {
        background: rgba(43, 45, 48, 0.8) !important;
        color: #8f9298 !important;
        font-size: 10px !important;
      }
      .leaflet-control-attribution a {
        color: #5ac45e !important;
      }
      .leaflet-container {
        background: #2b2d30 !important;
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative', fontFamily: 'sans-serif', color: '#eee' }}>
      <div style={{ 
        position: 'absolute', 
        top: '10px', 
        right: '10px', 
        zIndex: 1000, 
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: '8px'
      }}>
        <WeatherCalendar onTodayWeatherChange={setIsBadWeather} />
 
        <button
          className="glass-button"
          style={{
            padding: '8px 12px',
            fontSize: '12px',
            fontWeight: '600',
            cursor: 'pointer',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            color: '#f2f2f2'
          }}
          onClick={() => setShowScenarios(v => !v)}
        >
          <span>⚙</span>
          <span>Сценарии</span>
        </button>

        {showScenarios && (
          <div
            className="glass-panel"
            style={{
              padding: '8px 10px',
              display: 'flex',
              flexDirection: 'column',
              gap: '5px',
              minWidth: '150px'
            }}
          >
            <div style={{ fontSize: '11px', fontWeight: '600', color: '#8f9298', marginBottom: '2px' }}>
              Сценарии миссий
            </div>
            {SCENARIOS.map(s => (
              <button
                key={s.id}
                onClick={() => activateScenario(s)}
                className="glass-button"
                style={{
                  padding: '5px 10px',
                  background: activeScenario === s.id ? s.color : '#3c3f41',
                  color: '#f2f2f2',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: '500',
                  textAlign: 'left',
                  transition: 'all 0.2s'
                }}
              >
                {s.label} <span style={{ opacity: 0.6, fontSize: '11px' }}>({s.desc})</span>
              </button>
            ))}
            <button
              onClick={resetAllLamps}
              className="glass-button"
              style={{
                padding: '5px 10px',
                background: activeScenario ? '#2ecc71' : '#3c3f41',
                color: activeScenario ? 'white' : '#8f9298',
                border: 'none',
                cursor: 'pointer',
                fontSize: '11px',
                marginTop: '2px',
                transition: 'all 0.2s'
              }}
            >
              ✓ Сбросить
            </button>
          </div>
        )}
      </div>

      <div
        style={{
          position: 'absolute',
          top: '10px',
          left: '10px',
          zIndex: 1000
        }}
      >
        <RoutePanel
          brokenCount={lamps.filter(l => l.state <= 0.34).length}
          minToFly={MIN_BROKEN_TO_FLY}
          routeData={routeData}
          droneStatus={droneStatus}
        />
      </div>

      {is3D ? (
        <CityMap3D 
          lamps={lamps}
          droneStatus={dronePos}
          path={dronePath}
        />
      ) : (
      <MapContainer 
        center={[ORIGIN_LAT, ORIGIN_LNG]} 
        zoom={16} 
        minZoom={15}
        zoomSnap={0.3} // More steps for smoother zoom
        zoomDelta={0.5} // Smaller steps
        wheelPxPerZoomLevel={240} // Slower wheel zoom
        maxBounds={[
          [ORIGIN_LAT - 0.015, ORIGIN_LNG - 0.025],
          [ORIGIN_LAT + 0.015, ORIGIN_LNG + 0.025]
        ]}
        maxBoundsViscosity={1.0}
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
        zoomControl={false} // Disable default top-left
      >
        <MapUpdater />
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={19}
        />
        
        {/* Custom Zoom Control at Bottom Left */}
        <ZoomControl position="bottomleft" />

        
        {/* Droneport Marker */}
        <Marker 
          position={[DRONEPORT_LAT, DRONEPORT_LNG]}
          icon={createDroneportIcon()}
        >
          <Popup>
            <div style={{ minWidth: '150px' }}>
              <h4 style={{ margin: '0 0 5px' }}>Дронопорт</h4>
              <p style={{ margin: '2px 0', fontSize: '13px', color: '#555' }}>База обслуживания дронов</p>
            </div>
          </Popup>
        </Marker>

        {/* Drone Marker */}
        <Marker 
          position={[dronePos.lat, dronePos.lng]}
          icon={createDroneIcon()}
        >
          <Popup>
            <div style={{ minWidth: '150px' }}>
              <h4 style={{ margin: '0 0 5px' }}>Сервисный дрон</h4>
              <p style={{ margin: '2px 0', fontSize: '13px', color: '#555' }}>Патрулирует сломанные лампы и заменяет их</p>
            </div>
          </Popup>
        </Marker>

        {/* Lamp Markers */}
        {lamps.map(lamp => (
          <Marker 
            key={lamp.id} 
            position={[lamp.lat, lamp.lng]}
            icon={createLampIcon(lamp.status, lamp.is_on, lamp.state)}
          >
            <Popup>
            <div style={{ minWidth: '150px' }}>
              <h4 style={{ margin: '0 0 5px' }}>Лампа №{lamp.id}</h4>
              <p style={{ margin: '2px 0', fontSize: '13px', color: '#555' }}>{lamp.address}</p>
              <p style={{ margin: '2px 0', fontSize: '13px' }}>
                Состояние: <strong style={{ color: getBorderColor(lamp.status) }}>{getLabel(lamp.status)}</strong>
              </p>
              <p style={{ margin: '2px 0', fontSize: '13px' }}>
                Целостность: <strong style={{ color: getColor(lamp.state) }}>{(lamp.state * 100).toFixed(0)}%</strong>
              </p>
            </div>
          </Popup>
          </Marker>
        ))}
      </MapContainer>
      )}

      <button 
        onClick={() => setIs3D(!is3D)}
        className="glass-button"
        style={{
          position: 'absolute',
          bottom: '20px',
          right: '20px',
          zIndex: 1000,
          padding: '0',
          width: '64px',
          height: '64px',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'transparent',
          transform: is3D
              ? 'perspective(120px) rotateX(45deg) rotateY(0deg)'
              : 'none'
        }}
      >
        <div
          style={{
            width: '46px',
            height: '46px',
            borderRadius: '12px',
            background: is3D
              ? 'linear-gradient(145deg, #3c3f41, #1f2023)'
              : 'linear-gradient(145deg, #3c3f41, #1f2023)',
            boxShadow: '0 10px 25px rgba(0,0,0,0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#f2f2f2',
            fontWeight: '800',
            fontSize: '16px',
            letterSpacing: '1px',
          }}
        >
          {is3D ? '2D' : '3D'}
        </div>
      </button>
    </div>
  );
};

export default CityMap;
