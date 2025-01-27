import {
    Viewer,
    Terrain,
    OpenStreetMapImageryProvider,
    Color,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";

// CesiumJS has a default access token built in but it's not meant for active use.
// please set your own access token can be found at: https://cesium.com/ion/tokens.
// Ion.defaultAccessToken = "YOUR TOKEN HERE";


export const setupViewer = () => {
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

    return viewer;
};