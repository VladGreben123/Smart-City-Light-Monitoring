import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css'; // CRITICAL: Required for Leaflet styles

const ORIGIN_LAT = 55.752317;
const ORIGIN_LNG = 48.744578;

const DRONEPORT_LAT = 55.7528;
const DRONEPORT_LNG = 48.7452;

const initialLamps = [
  { id: 1, lat: 55.752317, lng: 48.744578, status: 'off', address: 'Origin (University)' },
  { id: 2, lat: 55.753817, lng: 48.746578, status: 'on', address: 'Sport Complex Area' },
  { id: 3, lat: 55.751817, lng: 48.742578, status: 'broken', address: 'Technopark Area' },
  { id: 4, lat: 55.754817, lng: 48.746578, status: 'broken', address: 'Residential Area East' },
  { id: 5, lat: 55.753317, lng: 48.745578, status: 'on', address: 'Campus North' },
];

const getColor = (status) => {
  switch (status) {
    case 'on': return '#2ecc71';   // Green
    case 'off': return '#95a5a6';  // Gray
    case 'broken': return '#e74c3c'; // Red
    default: return '#3498db';     // Blue
  }
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

// Legend Component
const MapLegend = () => (
  <div style={{
    position: 'absolute',
    bottom: '30px',
    left: '20px',
    zIndex: 1000,
    background: 'white',
    padding: '10px',
    borderRadius: '8px',
    boxShadow: '0 0 10px rgba(0,0,0,0.2)',
    fontSize: '12px',
    fontFamily: 'sans-serif'
  }}>
    <h4 style={{ margin: '0 0 5px', fontSize: '14px' }}>Lamp Status</h4>
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
      <span style={{ width: '12px', height: '12px', background: '#2ecc71', borderRadius: '50', display: 'inline-block', marginRight: '8px' }}></span> On
    </div>
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
      <span style={{ width: '12px', height: '12px', background: '#95a5a6', borderRadius: '50', display: 'inline-block', marginRight: '8px' }}></span> Off
    </div>
    <div style={{ display: 'flex', alignItems: 'center' }}>
      <span style={{ width: '12px', height: '12px', background: '#e74c3c', borderRadius: '50', display: 'inline-block', marginRight: '8px' }}></span> Broken
    </div>
  </div>
);

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
          console.log('Received update:', data);
          
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
    if (droneStatus !== 'toLamp' && droneStatus !== 'return') return;
    if (dronePath.length === 0) return;

    const speed = 0.00001;

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

      if (dist < 0.00005) {
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

          setLamps(prev =>
            prev.map(l =>
              l.id === lampId && l.status === 'broken'
                ? { ...l, status: 'off' }
                : l
            )
          );

          if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({ id: lampId, status: 'off' });
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
        const ratio = speed / dist;
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

    let newStatus = 'off';
    if (lamp.status === 'off') newStatus = 'on';
    else if (lamp.status === 'on') newStatus = 'broken';
    else newStatus = 'off';

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
    const brokenLamps = lamps.filter(l => l.status === 'broken');
    if (brokenLamps.length === 0) return;

    const pathIds = brokenLamps.map(l => l.id);
    setDronePath(pathIds);
    setCurrentTargetIndex(0);
    setDronePos({ lat: DRONEPORT_LAT, lng: DRONEPORT_LNG });
    setDroneStatus('toLamp');
  };

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
      <div style={{ 
        position: 'absolute',
        top: '50px',
        right: '10px',
        zIndex: 1000,
        background: 'white',
        padding: '10px 12px',
        borderRadius: '8px',
        boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
        fontSize: '13px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px'
      }}>
        <div>Дрон: {droneStatus === 'idle' ? 'ожидает' : droneStatus === 'toLamp' ? 'обслуживает лампы' : 'возвращается'}</div>
        <button 
          onClick={startDroneMission}
          disabled={droneStatus !== 'idle' || !lamps.some(l => l.status === 'broken')}
          style={{
            padding: '6px 10px',
            borderRadius: '6px',
            border: 'none',
            background: droneStatus === 'idle' && lamps.some(l => l.status === 'broken') ? '#3498db' : '#bdc3c7',
            color: 'white',
            cursor: droneStatus === 'idle' && lamps.some(l => l.status === 'broken') ? 'pointer' : 'default',
            fontSize: '13px'
          }}
        >
          Запустить дрона
        </button>
      </div>
      
      <MapLegend />

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
        <CircleMarker 
          center={[DRONEPORT_LAT, DRONEPORT_LNG]}
          pathOptions={{ 
            color: '#34495e', 
            fillColor: '#34495e', 
            fillOpacity: 1,
            weight: 2
          }}
          radius={10}
        >
          <Popup>
            <div style={{ minWidth: '150px' }}>
              <h4 style={{ margin: '0 0 5px' }}>Дронопорт</h4>
              <p style={{ margin: '2px 0', fontSize: '13px', color: '#555' }}>База обслуживания дронов</p>
            </div>
          </Popup>
        </CircleMarker>
        <CircleMarker 
          center={[dronePos.lat, dronePos.lng]}
          pathOptions={{ 
            color: '#2980b9', 
            fillColor: '#2980b9', 
            fillOpacity: 1,
            weight: 2
          }}
          radius={12}
        >
          <Popup>
            <div style={{ minWidth: '150px' }}>
              <h4 style={{ margin: '0 0 5px' }}>Сервисный дрон</h4>
              <p style={{ margin: '2px 0', fontSize: '13px', color: '#555' }}>Патрулирует сломанные лампы и заменяет их</p>
            </div>
          </Popup>
        </CircleMarker>
        {lamps.map(lamp => (
          <CircleMarker 
            key={lamp.id} 
            center={[lamp.lat, lamp.lng]}
            pathOptions={{ 
              color: getColor(lamp.status), 
              fillColor: getColor(lamp.status), 
              fillOpacity: 1,
              weight: 2
            }}
            radius={10}
            eventHandlers={{
              click: () => toggleLampStatus(lamp.id),
              mouseover: (e) => {
                e.target.setRadius(14);
              },
              mouseout: (e) => {
                e.target.setRadius(10);
              }
            }}
          >
            <Popup>
              <div style={{ minWidth: '150px' }}>
                <h4 style={{ margin: '0 0 5px' }}>Lamp #{lamp.id}</h4>
                <p style={{ margin: '2px 0', fontSize: '13px', color: '#555' }}>{lamp.address}</p>
                <p style={{ margin: '2px 0', fontSize: '13px' }}>
                  Status: <strong style={{ color: getColor(lamp.status) }}>{getLabel(lamp.status)}</strong>
                </p>
                <p style={{ margin: '5px 0 0', fontSize: '11px', color: '#888' }}>
                  Click to toggle state
                </p>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
};

export default CityMap;
