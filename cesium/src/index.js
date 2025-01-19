import {
  Viewer,
  Cartesian3,
  Math,
  Terrain,
  createOsmBuildingsAsync,
  Color,
  OpenStreetMapImageryProvider
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./css/main.css";
import { loadSatellites } from "./satellites-parser";


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
  }
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
      radii: new Cartesian3(10000.0, 10000.0, 10000.0), // Made satellites smaller
      material: Color.BLACK.withAlpha(1), // Made them red and slightly transparent
      outline: true,
      outlineColor: Color.BLACK,
    }
  });
  return entity;
};

// Initialize satellites function with batch processing
const initializeSatellites = async () => {
  try {
    const satellites = await loadSatellites('starlink_550.csv');
    console.log(`Starting to add ${satellites.length} satellites...`);
    
    // Create an entity collection for better performance
    const entityCollection = viewer.entities;
    let successCount = 0;

    // Process satellites in batches
    satellites.forEach((sat, index) => {
      const entity = addSatellite(
        sat.longitude,
        sat.latitude,
        sat.height
      );
      
      if (entity) {
        entity.name = sat.name;
        successCount++;
      }

      // Log progress every 100 satellites
      if ((index + 1) % 100 === 0) {
        console.log(`Processed ${index + 1} satellites out of ${satellites.length}`);
      }
    });

    console.log(`Successfully added ${successCount} out of ${satellites.length} satellites`);
    
    // Adjust the camera to see all satellites
    viewer.zoomTo(entityCollection, new HeadingPitchRange(0, -Math.PI/2, 20000000));
    
  } catch (error) {
    console.error('Failed to load satellites:', error);
  }
};

// Call initialization
initializeSatellites();