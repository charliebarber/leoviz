import {
  Viewer,
  Cartesian3,
  Terrain,
  createOsmBuildingsAsync,
  Color,
  OpenStreetMapImageryProvider,
  ArcType,
  HorizontalOrigin,
  VerticalOrigin,
  LabelStyle,
  Cartesian2,
  DistanceDisplayCondition
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./css/main.css";
import { loadSatellites, loadISLs, loadCities, loadGSLs } from "./satellites-parser";


// CesiumJS has a default access token built in but it's not meant for active use.
// please set your own access token can be found at: https://cesium.com/ion/tokens.
// Ion.defaultAccessToken = "YOUR TOKEN HERE";

// Initialize the Cesium Viewer in the HTML element with the `cesiumContainer` ID.
const viewer = new Viewer("cesiumContainer", {
  terrain: Terrain.fromWorldTerrain(),
  skyBox: false,
  skyAtmosphere: false,
  baseLayerPicker: false,
  geocoder: false,
  homeButton: false,
  infoBox: false,
  sceneModePicker: false,
  navigationHelpButton: false,
  shouldAnimate: true,
  contextOptions: {
    webgl: {
      alpha: true
    }
  },
  timeline: false,
  animation: false,
});

// Scene setup
const scene = viewer.scene;
scene.backgroundColor = Color.WHITE;
scene.highDynamicRange = false;

// Canvas setup
const canvas = viewer.canvas;
canvas.setAttribute('tabindex', '0');
canvas.onclick = () => canvas.focus();

// Globe setup
const globe = scene.globe;
globe.imageryLayers.removeAll();
globe.baseColor = Color.fromCssColorString('#f7fbff');

// Add toner layer
const tonerLayer = globe.imageryLayers.addImageryProvider(
  new OpenStreetMapImageryProvider({
    url: 'https://tiles.stadiamaps.com/tiles/stamen_toner_background/',
    credit: 'Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under CC BY SA.'
  })
);
tonerLayer.alpha = 0.3;
tonerLayer.brightness = 3;
tonerLayer.contrast = 0.7;

// // Add OSM Buildings
// const addBuildings = async () => {
//   const osmBuildingsTileset = await createOsmBuildingsAsync();
//   viewer.scene.primitives.add(osmBuildingsTileset);
// };
// addBuildings();


// Add satellite function with smaller size and better visibility
const addSatellite = (longitude, latitude, height = 550000) => {
  const entity = viewer.entities.add({
    position: Cartesian3.fromDegrees(longitude, latitude, height),
    ellipsoid: {
      radii: new Cartesian3(20000.0, 20000.0, 20000.0), // Made satellites smaller
      material: Color.BLACK.withAlpha(1), // Made them red and slightly transparent
      outline: true,
      outlineColor: Color.BLACK,
    }
  });
  return entity;
};

const addCity = (viewer, city) => {
  const DOT_SIZE = 50; // Base size in pixels
  const scaleFactor = city.population / 100000;
  
  return viewer.entities.add({
      name: city.name,
      position: Cartesian3.fromDegrees(city.longitude, city.latitude),
      point: {
          pixelSize: DOT_SIZE * Math.sqrt(scaleFactor), // Using square root for more reasonable scaling
          color: Color.YELLOW.withAlpha(0.8),
          outlineColor: Color.BLACK,
          outlineWidth: 1,
          // Add a scale-based minimum size to ensure all cities are visible
          pixelSize: Math.max(3, DOT_SIZE * Math.sqrt(scaleFactor))
      },
      label: {
          text: city.name,
          font: '12px sans-serif',
          horizontalOrigin: HorizontalOrigin.LEFT,
          verticalOrigin: VerticalOrigin.BOTTOM,
          pixelOffset: new Cartesian2(5, 5),
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 2,
          style: LabelStyle.FILL_AND_OUTLINE,
          // Only show labels when zoomed in
          distanceDisplayCondition: new DistanceDisplayCondition(0, 5000000)
      }
  });
};

// Initialize satellites function with batch processing
const initializeSatellites = async () => {
  try {
      // Load cities first and store their positions
      console.log('Loading cities data...');
      const cities = await loadCities('cities.csv');
      const cityPositions = new Map();
      
      console.log('Adding cities to the map...');
      cities.forEach(city => {
          addCity(viewer, city);
          cityPositions.set(city.id, {
              longitude: city.longitude,
              latitude: city.latitude
          });
      });

      const satellites = await loadSatellites('starlink_550.csv');
      console.log(`Starting to add ${satellites.length} satellites...`);
      
      // Create map of satellite ID to position
      const satellitePositions = new Map();
      
      satellites.forEach((sat) => {
          const entity = addSatellite(sat.longitude, sat.latitude, sat.height);
          if (entity) {
              entity.name = sat.name;
              satellitePositions.set(sat.id, {
                  longitude: sat.longitude,
                  latitude: sat.latitude,
                  height: sat.height
              });
              console.log(`added ${sat.id} with longitude ${sat.longitude}`)
          }
      });

      // Load and add ISLs
      const isls = await loadISLs('isls.txt');
      isls.forEach(({ a, b }) => {
          const posA = satellitePositions.get(a);
          const posB = satellitePositions.get(b);

          console.log(`Sats ${a} and ${b} link, posA ${posA} posB ${posB}`)
          
          if (posA && posB) {
              viewer.entities.add({
                  polyline: {
                      positions: Cartesian3.fromDegreesArrayHeights([
                          posA.longitude, posA.latitude, posA.height,
                          posB.longitude, posB.latitude, posB.height
                      ]),
                      width: 1,
                      material: Color.BLUE.withAlpha(0.5),
                      arcType: ArcType.NONE  // Straight line instead of following the curve of the Earth
                  }
              });
          }
      });

      // Add ground station links
      console.log('Loading and adding ground station links...');
      const gsls = await loadGSLs('gsls.txt');
      gsls.forEach(({ cityId, satelliteId }) => {
          const city = cityPositions.get(cityId);
          const satellite = satellitePositions.get(satelliteId);
          
          if (city && satellite) {
              // console.log(`City: ${city} Satellite ${satellite}`)
              viewer.entities.add({
                  polyline: {
                      positions: Cartesian3.fromDegreesArrayHeights([
                          city.longitude, city.latitude, 0, // City at ground level
                          satellite.longitude, satellite.latitude, satellite.height
                      ]),
                      width: 1,
                      material: Color.YELLOW.withAlpha(0.2), // Faint yellow line
                      arcType: ArcType.NONE
                  }
              });
          }
      });

  } catch (error) {
      console.error('Failed to load satellites and ISLs:', error);
  }
};

// Call initialization
initializeSatellites();