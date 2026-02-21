import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';

// Innopolis Origin Point (University)
const ORIGIN_LAT = 55.752317;
const ORIGIN_LNG = 48.744578;

// Mock initial data for lamps (Local coordinates in meters relative to Origin)
const initialLamps = [
  { id: 1, lat: 55.752317, lng: 48.744578, status: 'off', address: 'Origin (University)' },
  { id: 2, lat: 55.753817, lng: 48.746578, status: 'on', address: 'Sport Complex Area' },
  { id: 3, lat: 55.751817, lng: 48.742578, status: 'broken', address: 'Technopark Area' },
  { id: 4, lat: 55.754817, lng: 48.746578, status: 'off', address: 'Residential Area East' },
  { id: 5, lat: 55.753317, lng: 48.745578, status: 'on', address: 'Campus North' },
];

const getColor = (status) => {
  switch (status) {
    case 'on': return 'green';
    case 'off': return 'gray';
    case 'broken': return 'red';
    default: return 'blue';
  }
};

// Component to fix map rendering issues
const MapUpdater = () => {
  const map = useMap();
  
  useEffect(() => {
    // Invalidate size after a short delay to ensure container is ready
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 100);
    return () => clearTimeout(timer);
  }, [map]);

  return null;
};

const CityMap = () => {
  const [lamps, setLamps] = useState(initialLamps);
  const [wsStatus, setWsStatus] = useState('Disconnected');
  const ws = useRef(null);

  useEffect(() => {
    // Connect to WebSocket
    // Assuming FastAPI backend at ws://localhost:8000/ws
    ws.current = new WebSocket('ws://localhost:8000/ws');

    ws.current.onopen = () => {
      console.log('Connected to WebSocket');
      setWsStatus('Connected');
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received update:', data);
        
        // Update lamp state if id matches
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
      console.log('Disconnected from WebSocket');
      setWsStatus('Disconnected');
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  const toggleLampStatus = (id) => {
    const lamp = lamps.find(l => l.id === id);
    if (!lamp) return;

    let newStatus = 'off';
    if (lamp.status === 'off') newStatus = 'on';
    else if (lamp.status === 'on') newStatus = 'broken';
    else newStatus = 'off'; // Cycle: off -> on -> broken -> off

    // Optimistic update
    setLamps(prevLamps => 
      prevLamps.map(l => l.id === id ? { ...l, status: newStatus } : l)
    );

    // Send to backend
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ id, status: newStatus });
      ws.current.send(message);
      console.log('Sent:', message);
    }
  };

  return (
    <div style={{ height: '100%', width: '100%', position: 'relative' }}>
      <div style={{ 
        position: 'absolute', 
        top: '10px', 
        right: '10px', 
        zIndex: 1000, 
        background: 'rgba(255, 255, 255, 0.8)', 
        padding: '5px 10px', 
        borderRadius: '5px',
        fontSize: '12px'
      }}>
        <span style={{color: 'black'}}>WS:</span> <span style={{ color: wsStatus === 'Connected' ? 'green' : 'red', fontWeight: 'bold' }}>{wsStatus}</span>
      </div>
      
      <MapContainer center={[55.752317, 48.744578]} zoom={15} style={{ height: '100%', width: '100%' }}>
        <MapUpdater />
        <TileLayer
          attribution='&copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={19}
        />
        {lamps.map(lamp => {
          const [lat, lng] = [lamp.lat, lamp.lng];
          return (
            <CircleMarker 
              key={lamp.id} 
              center={[lat, lng]}
              pathOptions={{ color: getColor(lamp.status), fillColor: getColor(lamp.status), fillOpacity: 1 }}
              radius={7}
              eventHandlers={{
                click: () => toggleLampStatus(lamp.id),
              }}
            >
              <Popup>
                <strong>Lamp ID: {lamp.id}</strong><br />
                Address: {lamp.address}<br />
                Status: {lamp.status}<br />
                Local Pos: ({lamp.x}, {lamp.y})
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
};

export default CityMap;
