import React, { useRef, useEffect, useState } from 'react';
import Map, { Source, Layer, Marker, NavigationControl } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import droneModelUrl from '../assets/drone.glb?url';

const ORIGIN_LAT = 55.752317;
const ORIGIN_LNG = 48.744578;

const CityMap3D = ({ lamps, droneStatus, path }) => {
    const mapRef = useRef(null);
    const [mapStyle, setMapStyle] = useState(null);

    // Load base style and inject drone model definition
    useEffect(() => {
        fetch("https://tiles.openfreemap.org/styles/liberty")
            .then(res => res.json())
            .then(style => {
                // Ensure absolute URL for the model
                const absoluteModelUrl = new URL(droneModelUrl, window.location.origin).href;
                console.log("Drone Model URL:", absoluteModelUrl);

                // Add model definition to the style spec
                style.models = {
                    "drone-model": absoluteModelUrl
                };
                
                // Add ambient light if not present (MapLibre v5 style uses 'lights' array or 'light' object for global)
                // For v5, we might need to add a sky layer or just rely on default.
                // Let's try adding a simple ambient light configuration if possible.
                // Actually, let's just make sure the model URL is correct first.
                
                setMapStyle(style);
            })
            .catch(err => console.error("Failed to load map style", err));
    }, []);

    const onMapLoad = (e) => {
        // No need to add model manually if it's in the style
    };

    useEffect(() => {
        // Inject styles to filter only the map canvas, not the markers/controls
        const style = document.createElement('style');
        style.innerHTML = `
            .maplibregl-canvas {
                filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%);
            }
            /* Ensure attribution is readable */
            .maplibregl-ctrl-attrib {
                background: rgba(0,0,0,0.5) !important;
                color: #aaa !important;
            }
            .maplibregl-ctrl-attrib a {
                color: #fff !important;
            }

            /* Zoom Controls - Match CityMap.jsx design */
            .maplibregl-ctrl-bottom-left {
                display: flex;
                flex-direction: row;
                margin-left: 10px !important;
                margin-bottom: 24px !important;
                z-index: 1000;
            }

            /* Override default MapLibre group styles */
            .maplibregl-ctrl-group {
                background: transparent !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
                border-radius: 0 !important;
                margin: 0 !important;
                display: flex !important;
                flex-direction: row !important;
                gap: 2px !important; /* Tiny gap for pill effect */
                border: none !important;
            }

            /* Button Styles */
            .maplibregl-ctrl-zoom-in, .maplibregl-ctrl-zoom-out {
                background-color: #2b2d30 !important; /* Yandex Panel Color */
                width: 40px !important;
                height: 40px !important;
                border: none !important;
                margin: 0 !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                transition: all 0.2s ease !important;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3) !important;
                position: relative;
            }

            /* Hide default SVG icons to replace with text like Leaflet */
            .maplibregl-ctrl-icon {
                display: none !important;
            }

            /* Simulate Leaflet text icons for thinner look */
            .maplibregl-ctrl-zoom-in::after {
                content: '+';
                font-size: 24px;
                font-weight: 300;
                color: #f2f2f2;
                font-family: "Lucida Console", Monaco, monospace;
                line-height: 1;
            }

            .maplibregl-ctrl-zoom-out::after {
                content: '\\2212'; /* Minus sign */
                font-size: 24px;
                font-weight: 300;
                color: #f2f2f2;
                font-family: "Lucida Console", Monaco, monospace;
                line-height: 1;
            }

            /* Pill shape logic */
            .maplibregl-ctrl-zoom-in {
                border-top-left-radius: 12px !important;
                border-bottom-left-radius: 12px !important;
                border-top-right-radius: 0 !important;
                border-bottom-right-radius: 0 !important;
                margin-right: 1px !important; /* Thin separator */
            }

            .maplibregl-ctrl-zoom-out {
                border-top-right-radius: 12px !important;
                border-bottom-right-radius: 12px !important;
                border-top-left-radius: 0 !important;
                border-bottom-left-radius: 0 !important;
            }

            /* Hover effects */
            .maplibregl-ctrl-zoom-in:hover, .maplibregl-ctrl-zoom-out:hover {
                background-color: #3c3f41 !important;
                transform: translateY(-1px);
                z-index: 2;
            }

            /* Hide compass if present (just in case) */
            .maplibregl-ctrl-compass {
                display: none !important;
            }
        `;
        document.head.appendChild(style);
        return () => document.head.removeChild(style);
    }, []);

    // ... rest of component
    const buildingLayer = {
        id: '3d-buildings',
        source: 'openfreemap',
        'source-layer': 'building',
        type: 'fill-extrusion',
        minzoom: 14,
        paint: {
            'fill-extrusion-color': '#aaa',
            'fill-extrusion-height': [
                'interpolate', ['linear'], ['zoom'],
                14, 0,
                14.05, ['get', 'render_height']
            ],
            'fill-extrusion-base': [
                'interpolate', ['linear'], ['zoom'],
                14, 0,
                14.05, ['get', 'render_min_height']
            ],
            'fill-extrusion-opacity': 0.8
        }
    };

    // GeoJSON data for path
    const pathGeoJSON = {
        type: 'Feature',
        geometry: {
            type: 'LineString',
            coordinates: path.map(p => [p[1], p[0]]) // MapLibre uses [lng, lat]
        }
    };

    // GeoJSON data for lamps
    const lampsGeoJSON = {
        type: 'FeatureCollection',
        features: lamps.map(l => ({
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [l.lng, l.lat]
            },
            properties: {
                state: l.state
            }
        }))
    };

    const droneGeoJSON = droneStatus ? {
        type: 'Feature',
        geometry: {
            type: 'Point',
            coordinates: [droneStatus.lng, droneStatus.lat]
        }
    } : null;

    if (!mapStyle) return <div style={{color:'white'}}>Loading Map Style...</div>;

    return (
        <Map
            onLoad={onMapLoad}
            initialViewState={{
                longitude: ORIGIN_LNG,
                latitude: ORIGIN_LAT,
                zoom: 16,
                pitch: 60, // 3D tilt
                bearing: -20 // Slight rotation
            }}
            style={{width: '100%', height: '100vh'}}
            mapStyle={mapStyle}
            mapLib={maplibregl}
            ref={mapRef}
            attributionControl={false}
            onError={(e) => console.error("Map Error:", e)}
        >
            <NavigationControl position="bottom-left" showCompass={false} />
            
            {/* 3D Buildings Layer - Explicitly added if not in style */}
            {/* Note: OpenFreeMap liberty style usually includes buildings but maybe not extruded. 
                Let's add a custom layer for 3D buildings if needed.
                However, for simplicity, let's trust the style first or add a simple fill-extrusion layer.
            */}
             <Source id="openfreemap" type="vector" url="https://tiles.openfreemap.org/planet">
                <Layer {...buildingLayer} />
            </Source>

            {/* Lamp Circles */}
            <Source id="lamps" type="geojson" data={lampsGeoJSON}>
                <Layer
                    id="lamp-circles"
                    type="circle"
                    paint={{
                        'circle-radius': 8, // Match Leaflet 8 meters approx? No, pixels.
                        'circle-color': [
                            'case',
                            ['<=', ['get', 'state'], 0.33], '#ff0000',
                            ['<=', ['get', 'state'], 0.66], '#ffff00',
                            '#00ff00'
                        ],
                        'circle-opacity': 0.6,
                        'circle-stroke-width': 1,
                        'circle-stroke-color': '#fff'
                    }}
                />
            </Source>

            {/* Drone Path */}
            <Source id="path" type="geojson" data={pathGeoJSON}>
                <Layer
                    id="path-line"
                    type="line"
                    layout={{
                        'line-join': 'round',
                        'line-cap': 'round'
                    }}
                    paint={{
                        'line-color': '#3388ff',
                        'line-width': 4
                    }}
                />
            </Source>

            {/* Drone 3D Model */}
            {droneStatus && (
                <Source id="drone" type="geojson" data={droneGeoJSON}>
                    <Layer
                        id="drone-model-layer"
                        type="model"
                        layout={{
                            'model-id': 'drone-model'
                        }}
                        paint={{
                            'model-scale': [100, 100, 100],
                            'model-rotation': [0, 0, -45],
                            'model-translation': [0, 0, 100],
                            'model-opacity': 1,
                        }}
                    />
                </Source>
            )}

            {/* Debug Circle - To verify position */}
            {droneStatus && (
                 <Source id="drone-debug" type="geojson" data={droneGeoJSON}>
                    <Layer
                        id="drone-debug-circle"
                        type="circle"
                        paint={{
                            'circle-radius': 10,
                            'circle-color': '#00ff00',
                            'circle-opacity': 0.5,
                            'circle-stroke-width': 2,
                            'circle-stroke-color': '#fff'
                        }}
                    />
                </Source>
            )}

            {/* Fallback Marker - Removed as we expect model to work now */}

        </Map>
    );
};

export default CityMap3D;
