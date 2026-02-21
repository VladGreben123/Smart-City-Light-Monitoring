import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';

// Mock initial data for lamps
const initialLamps = [
  { id: 1, lat: 55.751244, lng: 37.618423, status: 'off', address: 'Center 1' },
  { id: 2, lat: 55.752244, lng: 37.619423, status: 'on', address: 'North East' },
  { id: 3, lat: 55.750244, lng: 37.617423, status: 'broken', address: 'South West' },
  { id: 4, lat: 55.751244, lng: 37.620423, status: 'off', address: 'East' },
  { id: 5, lat: 55.753244, lng: 37.618423, status: 'on', address: 'North' },
];

const getColor = (status) => {
  switch (status) {
    case 'on': return 'green';
    case 'off': return 'gray';
    case 'broken': return 'red';
    default: return 'blue';
  }
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
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '10px', background: '#f0f0f0', textAlign: 'center' }}>
        <h2>City Street Lights Map</h2>
        <p>WebSocket Status: <span style={{ color: wsStatus === 'Connected' ? 'green' : 'red', fontWeight: 'bold' }}>{wsStatus}</span></p>
        <p>Click on a lamp to cycle its state (Off → On → Broken → Off)</p>
      </div>
      
      <div style={{ flex: 1 }}>
        <MapContainer center={[55.751244, 37.618423]} zoom={15} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {lamps.map(lamp => (
            <CircleMarker 
              key={lamp.id} 
              center={[lamp.lat, lamp.lng]}
              pathOptions={{ color: getColor(lamp.status), fillColor: getColor(lamp.status), fillOpacity: 0.7 }}
              radius={10}
              eventHandlers={{
                click: () => toggleLampStatus(lamp.id),
              }}
            >
              <Popup>
                <strong>Lamp ID: {lamp.id}</strong><br />
                Address: {lamp.address}<br />
                Status: {lamp.status}
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
};

export default CityMap;
