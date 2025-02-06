import {
  Cartesian3,
  Color,
  ArcType,
  HorizontalOrigin,
  VerticalOrigin,
  LabelStyle,
  Cartesian2,
  DistanceDisplayCondition,
  EntityCollection
} from "cesium";

export const loadGSLs = async (filepath) => {
  try {
    const response = await fetch(filepath);
    const text = await response.text();
    return text.split('\n')
      .filter(line => line.trim().length > 0)
      .map(line => {
        const [cityId, satelliteId] = line.split(' ').map(Number);
        return { cityId, satelliteId };
      });
  } catch (error) {
    console.error('Error loading ground station links:', error);
    throw error;
  }
};

export const plotGSLs = async (timestamp, viewer, positionsMap, gslsCollection) => {
  const filepath = `positions/starlink_550_traffic_scaled/${timestamp}/gsls_${timestamp}.txt`;
  const gsls = await loadGSLs(filepath);
  const { cityPositions, satellitePositions } = positionsMap;

  gsls.forEach(({ cityId, satelliteId }) => {
    const city = cityPositions.get(cityId);
    const satellite = satellitePositions.get(satelliteId);

    if (city && satellite) {
      gslsCollection.entities.add({
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
};