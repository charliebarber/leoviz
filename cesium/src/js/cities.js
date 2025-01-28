import Papa from 'papaparse';
import {
  Cartesian3,
  Color,
  HorizontalOrigin,
  VerticalOrigin,
  LabelStyle,
  Cartesian2,
  DistanceDisplayCondition,
} from 'cesium';


export const loadCities = async (filepath) => {
  try {
    const response = await fetch(filepath);
    const text = await response.text();

    return new Promise((resolve, reject) => {
      Papa.parse(text, {
        header: false, // Since we know the exact format
        dynamicTyping: true, // Automatically convert numbers
        skipEmptyLines: true,
        complete: (results) => {
          // Transform the data into a more usable format
          const cities = results.data.map(row => ({
            id: row[0],
            name: row[1],
            latitude: row[2],
            longitude: row[3],
            population: row[4]
          }));

          console.log(`Loaded ${cities.length} cities`);
          resolve(cities);
        },
        error: (error) => {
          console.error('Error parsing cities CSV:', error);
          reject(error);
        }
      });
    });
  } catch (error) {
    console.error('Error loading cities CSV:', error);
    throw error;
  }
};

const addCity = (city, gsCollection) => {
  const DOT_SIZE = 50; // Base size in pixels
  const scaleFactor = city.population / 100000;

  return gsCollection.entities.add({
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


export const initCities = async (path, gsCollection) => {
  // Load cities first and store their positions
  console.log('Loading cities data...');
  const cities = await loadCities(path);
  const cityPositions = new Map();

  console.log('Adding cities to the map...');
  cities.forEach(city => {
    addCity(city, gsCollection);
    cityPositions.set(city.id, {
      longitude: city.longitude,
      latitude: city.latitude
    });
  });

  return cityPositions;
};