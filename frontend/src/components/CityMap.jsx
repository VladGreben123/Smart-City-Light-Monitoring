import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css'; // CRITICAL: Required for Leaflet styles
import L from 'leaflet';
import WeatherCalendar from './WeatherCalendar';

const ORIGIN_LAT = 55.752317;
const ORIGIN_LNG = 48.744578;

const DRONEPORT_LAT = 55.7528;
const DRONEPORT_LNG = 48.7452;

// --- Helper Functions for Icons ---

const createLampIcon = (status, state) => {
  const borderColor = getBorderColor(status);
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

const mapStatusFromApi = (status, isOn) => {
    // If status comes from WebSocket (already mapped)
    if (status === 'on' || status === 'off') {
      return status;
    }
    // For any other status (ok, burned_out, etc), rely on isOn (time of day)
    return isOn ? 'on' : 'off';
  };

const mapLampFromApi = (item) => {
  const state = 1 - (item.failure_probability ?? 0);
  return {
    id: item.lamp_id,
    lat: item.latitude,
    lng: item.longitude,
    status: mapStatusFromApi(item.status, item.is_on),
    state: Math.max(0, Math.min(1, state)),
    address: item.address
  };
};

const getBorderColor = (status) => {
  switch (status) {
    case 'on': return '#2ecc71';
    case 'off': return '#95a5a6';
    case 'broken': return '#e74c3c';
    default: return '#bdc3c7';
  }
};

const getColor = (stat) => {
  if (stat < 0.33) return '#e74c3c';
  if (stat < 0.66) return '#e4f312';
  return '#2ecc71';
};

const getLabel = (status) => {
  switch (status) {
    case 'on': return 'Работает';
    case 'off': return 'Выключена';
    default: return 'Неизвестно';
  }
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
  const [lamps, setLamps] = useState([]);
  const [wsStatus, setWsStatus] = useState('Отключено');
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
  
  // Track manually broken lamps for testing (IDs)
  const brokenLampIdsRef = useRef(new Set());
  // Track recently repaired lamps to prevent race conditions
  const recentlyRepairedLampIdsRef = useRef(new Set());
  const [randomFailureEnabled, setRandomFailureEnabled] = useState(false);
  const failureProbability = 0.3;
  const checkInterval = 5000;

  const breakRandomLamp = () => {
    setRandomFailureEnabled(true);
  };

  const fixAllLamps = () => {
    brokenLampIdsRef.current.clear();
    setRandomFailureEnabled(false);
    setLamps(prev => prev.map(l => ({ ...l, state: 1.0 })));
  };

  useEffect(() => {
    if (!randomFailureEnabled) return;
    const id = setInterval(() => {
      setLamps(prev => prev.map(l => {
        if (brokenLampIdsRef.current.has(l.id)) return l;
        if (Math.random() < failureProbability) {
          brokenLampIdsRef.current.add(l.id);
          return { ...l, state: 0.0 };
        }
        return l;
      }));
    }, checkInterval);
    return () => clearInterval(id);
  }, [randomFailureEnabled]);

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
          const data = JSON.parse(event.data);
          // console.log('Received update:', data);
          
          if (data.id) {
            setLamps(prevLamps => {
              const index = prevLamps.findIndex(lamp => lamp.id === data.id);
              const prev = index >= 0 ? prevLamps[index] : null;
              const nextLamp = {
                id: data.id,
                lat: data.lat ?? prev?.lat ?? ORIGIN_LAT,
                lng: data.lng ?? prev?.lng ?? ORIGIN_LNG,
                address: data.address ?? prev?.address ?? '',
                status: data.status ? mapStatusFromApi(data.status, data.is_on ?? (prev?.status === 'on')) : (prev?.status ?? 'off'),
                state: brokenLampIdsRef.current.has(data.id) ? 0.0 : 
                       (recentlyRepairedLampIdsRef.current.has(data.id) ? 1.0 :
                       (typeof data.state === 'number' ? data.state : (prev?.state ?? 1)))
              };

              if (index === -1) {
                return [...prevLamps, nextLamp];
              }

              return prevLamps.map(lamp =>
                lamp.id === data.id ? nextLamp : lamp
              );
            });
          }
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
          .filter(item => item.lamp_id)
          .map(mapLampFromApi)
          .map(l => {
            if (brokenLampIdsRef.current.has(l.id)) l.state = 0.0;
            return l;
          });
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
    if (droneStatus !== 'toLamp' && droneStatus !== 'return') return;
    if (dronePath.length === 0 && droneStatus === 'toLamp') return;

    const maxSpeed = 0.00003;
    const acceleration = 0.0000005;
    const decelerationDist = 0.0005;

    const step = () => {
      const pos = dronePosRef.current;
      let target;

      if (droneStatusRef.current === 'toLamp') {
        const path = dronePath;
        const idx = targetIndexRef.current;
        const lampId = path[idx];
        const lamp = lampsRef.current.find(l => l.id === lampId);

        if (!lamp) {
          if (idx + 1 < path.length) {
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

      // Animation Logic
      if (dist < 0.00005) {
        // Reached target
        currentSpeedRef.current = 0; // Reset speed

        if (droneStatusRef.current === 'toLamp') {
          const now = performance.now();

          if (!waitUntilRef.current) {
            waitUntilRef.current = now + 1000;
            animationRef.current = requestAnimationFrame(step);
            return;
          }

          if (now < waitUntilRef.current) {
            animationRef.current = requestAnimationFrame(step);
            return;
          }

          waitUntilRef.current = null;

          const path = dronePath;
          const idx = targetIndexRef.current;
          const lampId = path[idx];

          // Simulate repair locally
          if (brokenLampIdsRef.current.has(lampId)) {
            brokenLampIdsRef.current.delete(lampId);
          }
          
          // Mark as recently repaired to ignore stale backend updates
          recentlyRepairedLampIdsRef.current.add(lampId);
          setTimeout(() => {
            recentlyRepairedLampIdsRef.current.delete(lampId);
          }, 10000);

          setLamps(prev => prev.map(l => 
            l.id === lampId ? { ...l, state: 1.0 } : l
          ));

          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({ id: lampId, state: 1 });
            ws.current.send(message);
          }

          if (idx + 1 < path.length) {
            setCurrentTargetIndex(prev => prev + 1);
          } else {
            setDroneStatus('return');
          }
        } else {
          setDroneStatus('idle');
          setDronePath([]);
          setCurrentTargetIndex(0);
          setDronePos({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
        }
      } else {
        // Move towards target
        
        // Acceleration / Deceleration
        if (dist < decelerationDist) {
          // Decelerate
          currentSpeedRef.current = Math.max(0.000005, currentSpeedRef.current - acceleration);
        } else {
          // Accelerate
          currentSpeedRef.current = Math.min(maxSpeed, currentSpeedRef.current + acceleration);
        }

        const moveDist = currentSpeedRef.current;
        const ratio = moveDist / dist;

        setDronePos(prev => ({
          lat: prev.lat + dy * ratio,
          lng: prev.lng + dx * ratio
        }));
      }

      animationRef.current = requestAnimationFrame(step);
    };

    animationRef.current = requestAnimationFrame(step);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [droneStatus, dronePath]);

  const startDroneMission = useCallback(() => {
    if (droneStatus !== 'idle') return;
    if (isBadWeather) return; // Drone cannot fly in bad weather
    const brokenLamps = lamps.filter(l => l.state <= 0.33);
    if (brokenLamps.length === 0) return;

    // Sort lamps by distance to optimize path (simple greedy)
    // Actually, let's just keep it simple for now or random
    // But sorting by distance from droneport then next closest would be better
    // For now, let's just take them as is
    
    const pathIds = brokenLamps.map(l => l.id);
    setDronePath(pathIds);
    setCurrentTargetIndex(0);
    setDronePos({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
    setDroneStatus('toLamp');
  }, [droneStatus, lamps, isBadWeather]);

  useEffect(() => {
    if (droneStatus !== 'idle') return;
    if (isBadWeather) return; // Do not auto-start in bad weather
    if (!lamps.some(l => l.state <= 0.33)) return;
    const timeout = setTimeout(() => startDroneMission(), 0);
    return () => clearTimeout(timeout);
  }, [lamps, droneStatus, startDroneMission, isBadWeather]);

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative', fontFamily: 'sans-serif', color: '#333' }}>
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

        <div style={{
          background: 'white', 
          padding: '8px 12px', 
          borderRadius: '20px',
          boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
          fontSize: '13px',
          fontWeight: '500',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <span style={{ 
            width: '8px', 
            height: '8px', 
            borderRadius: '50%', 
            background: wsStatus === 'Подключено' ? '#2ecc71' : '#e74c3c' 
          }}></span>
          {wsStatus}
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={breakRandomLamp}
            style={{
              padding: '8px 12px',
              background: '#e74c3c',
              color: 'white',
              border: 'none',
              borderRadius: '20px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: '500',
              boxShadow: '0 2px 5px rgba(0,0,0,0.2)'
            }}
          >
            Включить случайные поломки
          </button>
          <button 
            onClick={fixAllLamps}
            style={{
              padding: '8px 12px',
              background: '#2ecc71',
              color: 'white',
              border: 'none',
              borderRadius: '20px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: '500',
              boxShadow: '0 2px 5px rgba(0,0,0,0.2)'
            }}
          >
            Выключить случайные поломки и починить все
          </button>
        </div>
      </div>

      <MapContainer 
        center={[ORIGIN_LAT, ORIGIN_LNG]} 
        zoom={15} 
        style={{ height: '100%', width: '100%' }}
        scrollWheelZoom={true}
      >
        <MapUpdater />
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={19}
        />
        
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
            icon={createLampIcon(lamp.status, lamp.state)}
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
    </div>
  );
};

export default CityMap;
