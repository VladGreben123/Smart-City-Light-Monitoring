import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css'; // CRITICAL: Required for Leaflet styles
import L from 'leaflet';

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

const generateLamps = () => {
  const lamps = [];
  let id = 1;

  // Function to create a lamp
  const addLamp = (lat, lng, address) => {
    lamps.push({
      id: id++,
      lat,
      lng,
      status: Math.random() > 0.8 ? 'off' : 'on', // Random initial status
      state: Math.random() * 0.5 + 0.5, // Random initial state 0.5-1.0
      address
    });
  };

  // 1. Universitetskaya St (approximate path)
  // Starting near Origin, going South-West
  for (let i = 0; i < 15; i++) {
    addLamp(ORIGIN_LAT - i * 0.0004, ORIGIN_LNG - i * 0.0002, `Universitetskaya St #${i+1}`);
  }

  // 2. Sportivnaya St (approximate path)
  // Perpendicular, going South-East
  for (let i = 0; i < 15; i++) {
    addLamp(ORIGIN_LAT - i * 0.0001, ORIGIN_LNG + i * 0.0005, `Sportivnaya St #${i+1}`);
  }

  // 3. Central Park Ring (approximate circle)
  const parkLat = 55.7510;
  const parkLng = 48.7480;
  const radius = 0.0015;
  for (let i = 0; i < 12; i++) {
    const angle = (i / 12) * 2 * Math.PI;
    addLamp(
      parkLat + radius * Math.cos(angle) * 0.6, // Scale lat to look circular on map
      parkLng + radius * Math.sin(angle),
      `Central Park #${i+1}`
    );
  }

   // 4. Technopark Loop
   const technoLat = 55.751817;
   const technoLng = 48.742578;
   for (let i = 0; i < 10; i++) {
      addLamp(technoLat + i * 0.0003, technoLng - i * 0.0001, `Technopark Loop #${i+1}`);
   }

   // 5. Residential District
   const resLat = 55.754817;
   const resLng = 48.746578;
   for(let i=0; i< 10; i++) {
       addLamp(resLat - i * 0.0002, resLng + i * 0.0004, `Residential District #${i+1}`);
   }


  return lamps;
};

const initialLamps = generateLamps();

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
    case 'on': return 'Operational';
    case 'off': return 'Powered Off';
    case 'broken': return 'Fault Detected';
    default: return 'Unknown';
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
  const [lamps, setLamps] = useState(initialLamps);
  const [wsStatus, setWsStatus] = useState('Connecting...');
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  const [droneStatus, setDroneStatus] = useState('idle');
  const [dronePos, setDronePos] = useState({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
  const [dronePath, setDronePath] = useState([]);
  const [currentTargetIndex, setCurrentTargetIndex] = useState(0);
  const animationRef = useRef(null);
  const dronePosRef = useRef({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
  const lampsRef = useRef(initialLamps);
  const droneStatusRef = useRef('idle');
  const targetIndexRef = useRef(0);
  const waitUntilRef = useRef(null);
  const currentSpeedRef = useRef(0); // For smooth acceleration

  const connectWebSocket = () => {
    // Clear existing timeout if any
    if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);

    try {
      ws.current = new WebSocket('ws://localhost:8000/ws');

      ws.current.onopen = () => {
        console.log('Connected to WebSocket');
        setWsStatus('Connected');
      };

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // console.log('Received update:', data);
          
          if (data.id && data.status) {
            setLamps(prevLamps => 
              prevLamps.map(lamp => 
                lamp.id === data.id ? { ...lamp, status: data.status } : lamp
              )
            );
          }
        } catch (error) {
          console.error('Error parsing message:', error);
        }
      };

      ws.current.onclose = () => {
        console.log('WebSocket closed');
        setWsStatus('Disconnected');
        // Attempt to reconnect after 3 seconds
        reconnectTimeout.current = setTimeout(() => {
          setWsStatus('Reconnecting...');
          connectWebSocket();
        }, 3000);
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsStatus('Error');
        // Close connection to trigger onclose/reconnect logic
        if(ws.current) ws.current.close(); 
      };

    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setWsStatus('Failed');
    }
  };

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

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
    const interval = setInterval(() => {
      setLamps(prev =>
        prev.map(l => {
          const next = l.state - 0.01;
          return { ...l, state: next < 0 ? 0 : next };
        })
      );
    }, 1000);

    return () => clearInterval(interval);
  }, []);

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

          const repairedState = 1;

          setLamps(prev =>
            prev.map(l =>
              l.id === lampId
                ? { ...l, state: repairedState }
                : l
            )
          );

          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({ id: lampId, state: repairedState });
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

  const toggleLampStatus = (id) => {
    const lamp = lamps.find(l => l.id === id);
    if (!lamp) return;

    const newStatus = lamp.status === 'off' ? 'on' : 'off';

    setLamps(prevLamps => 
      prevLamps.map(l => l.id === id ? { ...l, status: newStatus } : l)
    );

    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ id, status: newStatus });
      ws.current.send(message);
      console.log('Sent:', message);
    } else {
      console.warn('WebSocket not open, change not sent to server');
    }
  };

  const startDroneMission = () => {
    if (droneStatus !== 'idle') return;
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
  };

  useEffect(() => {
    if (droneStatus !== 'idle') return;
    if (!lamps.some(l => l.state <= 0.33)) return;
    startDroneMission();
  }, [lamps, droneStatus]);

  return (
    <div style={{ height: '100vh', width: '100%', position: 'relative', fontFamily: 'sans-serif', color: '#333' }}>
      <div style={{ 
        position: 'absolute', 
        top: '10px', 
        right: '10px', 
        zIndex: 1000, 
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
          background: wsStatus === 'Connected' ? '#2ecc71' : '#e74c3c' 
        }}></span>
        {wsStatus}
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
            eventHandlers={{
              click: () => toggleLampStatus(lamp.id),
            }}
          >
            <Popup>
              <div style={{ minWidth: '150px' }}>
                <h4 style={{ margin: '0 0 5px' }}>Lamp #{lamp.id}</h4>
                <p style={{ margin: '2px 0', fontSize: '13px', color: '#555' }}>{lamp.address}</p>
                <p style={{ margin: '2px 0', fontSize: '13px' }}>
                  Status: <strong style={{ color: getBorderColor(lamp.status) }}>{getLabel(lamp.status)}</strong>
                </p>
                <p style={{ margin: '2px 0', fontSize: '13px' }}>
                  Health: <strong style={{ color: getColor(lamp.state) }}>{lamp.state.toFixed(2)}</strong>
                </p>
                <p style={{ margin: '5px 0 0', fontSize: '11px', color: '#888' }}>
                  Click to toggle power
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
