import React, { useRef, useEffect } from 'react';
import Map, { Source, Layer, NavigationControl, Marker } from 'react-map-gl/maplibre';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader';
import droneModelUrl from '../assets/drone.glb?url';

const ORIGIN_LAT = 55.752317;
const ORIGIN_LNG = 48.744578;
const DRONEPORT_LAT = 55.7528;
const DRONEPORT_LNG = 48.7452;

const CityMap3D = ({ lamps, droneStatus, path }) => {
    const mapRef = useRef(null);
    const droneModelRef = useRef(null); // Reference to the THREE.Group or Scene of the drone
    const dronePositionRef = useRef(null);

    // Update drone position when droneStatus changes
    useEffect(() => {
        if (!droneStatus) return;

        // Calculate position in Mercator coordinates
        // maplibregl is imported, so we can use static method
        const modelAsMercatorCoordinate = maplibregl.MercatorCoordinate.fromLngLat(
            [droneStatus.lng, droneStatus.lat],
            100 // Altitude in meters
        );
        
        // Update ref regardless of map/model state
        dronePositionRef.current = modelAsMercatorCoordinate;

        // Trigger repaint if map is ready
        if (mapRef.current) {
            const map = mapRef.current.getMap();
            if (map) map.triggerRepaint();
        }

    }, [droneStatus]);

    const onMapLoad = (e) => {
        const map = e.target;
        
        const absoluteModelUrl = new URL(droneModelUrl, window.location.origin).href;

        // Create Custom Layer
        const customLayer = {
            id: '3d-model',
            type: 'custom',
            renderingMode: '3d',
            onAdd: function (map, gl) {
                this.camera = new THREE.Camera();
                this.scene = new THREE.Scene();

                // Lights
                const ambientLight = new THREE.AmbientLight(0xffffff, 0.25);
                this.scene.add(ambientLight);
                
                const directionalLight = new THREE.DirectionalLight(0xffffff, 0.4);
                directionalLight.position.set(0, 10, 10).normalize();
                this.scene.add(directionalLight);

                // Load Model
                const loader = new GLTFLoader();

                loader.load(absoluteModelUrl, (gltf) => {
                    const model = gltf.scene;

                    droneModelRef.current = model;
                    this.scene.add(model);
                    map.triggerRepaint();
                }, undefined, (error) => {
                    console.error("Error loading drone model:", error);
                });

                this.map = map;
                
                // Use the map's canvas and context
                this.renderer = new THREE.WebGLRenderer({
                    canvas: map.getCanvas(),
                    context: gl,
                    antialias: true
                });
                this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
                this.renderer.toneMappingExposure = 0.5;
                this.renderer.autoClear = false;
            },
            render: function (gl, matrix) {
                const position = dronePositionRef.current;
                
                if (position && droneModelRef.current) {
                    const m = new THREE.Matrix4().fromArray(matrix);
                    
                    // Rotate model to stand up (if Z-up model)
                    const rotateX = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(1, 0, 0), Math.PI / 2);
                    const rotateY = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(0, 1, 0), 0);
                    const rotateZ = new THREE.Matrix4().makeRotationAxis(new THREE.Vector3(0, 0, 1), 0);

                    // Scale factor - adjust based on model size
                    const scale = position.meterInMercatorCoordinateUnits() * 30; 

                    const transform = new THREE.Matrix4()
                        .makeTranslation(position.x, position.y, position.z)
                        .scale(new THREE.Vector3(scale, -scale, scale))
                        .multiply(rotateX)
                        .multiply(rotateY)
                        .multiply(rotateZ);

                    this.camera.projectionMatrix = m.multiply(transform);
                    
                    this.renderer.resetState();
                    this.renderer.render(this.scene, this.camera);
                }
                
                this.map.triggerRepaint();
            }
        };

        if (!map.getLayer('3d-model')) {
             map.addLayer(customLayer);
        }
    };

    useEffect(() => {
        // Inject styles to filter only the map canvas, not the markers/controls
        const style = document.createElement('style');
        style.innerHTML = `
            /* Ensure attribution is readable */
            .maplibregl-ctrl-attrib {
                background: rgba(0,0,0,0.5) !important;
                color: #aaa !important;
            }
            .maplibregl-ctrl-attrib a {
                color: #fff !important;
            }

            /* Custom Map Dark Mode Filter */
            .maplibregl-canvas {
                filter: invert(1) hue-rotate(180deg) brightness(0.85) contrast(1.2) saturate(1.35) !important;
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
        source: 'openmaptiles',
        'source-layer': 'building',
        type: 'fill-extrusion',
        minzoom: 14,
        paint: {
            'fill-extrusion-color': '#aaa', // Revert to lighter color as filter will invert it to dark
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

    if (!droneModelUrl) console.error("Drone model URL missing!");

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
            mapStyle="https://tiles.openfreemap.org/styles/liberty"
            mapLib={maplibregl}
            ref={mapRef}
            attributionControl={false}
            onError={(e) => console.error("Map Error:", e)}
        >
            <NavigationControl position="bottom-left" showCompass={false} />
            
            {/* 3D Buildings Layer - Use existing source from style */}
            <Layer {...buildingLayer} />

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
            
            {/* Droneport Marker */}
            <Marker longitude={DRONEPORT_LNG} latitude={DRONEPORT_LAT} anchor="center">
                <div className="droneport-marker">
                    <div className="droneport-base">
                        <div className="droneport-pad"></div>
                        <div className="droneport-beacon"></div>
                    </div>
                </div>
            </Marker>

            {/* Drone Positioning Shadow/Marker */}
            {droneStatus && (
                <Marker longitude={droneStatus.lng} latitude={droneStatus.lat} anchor="center">
                     <div className="drone-marker">
                        <div className="drone-arm arm-1"></div>
                        <div className="drone-arm arm-2"></div>
                        <div className="drone-body"></div>
                        <div className="drone-prop tl"></div>
                        <div className="drone-prop tr"></div>
                        <div className="drone-prop bl"></div>
                        <div className="drone-prop br"></div>
                    </div>
                </Marker>
            )}

            {/* Drone 3D Model handled by custom Three.js layer */}
            
            {/* Fallback Marker - Removed as we expect model to work now */}

        </Map>
    );
};

export default CityMap3D;
