import {
  Cartesian3,
  Color,
  ArcType,
  HorizontalOrigin,
  VerticalOrigin,
  LabelStyle,
  Cartesian2,
  DistanceDisplayCondition,
  EntityCollection,
  Entity,
} from "cesium";

export const loadISLs = async (filepath) => {
  const response = await fetch(filepath);
  const text = await response.text();
  return text.split('\n')
    .filter(line => line.trim().length > 0)
    .map(line => {
      const [a, b] = line.split(' ').map(Number);
      return { a, b };
    });
};

export const plotISLs = async (isls, satellitePositions, islsCollection) => {
  isls.forEach(({ a, b }) => {
      const posA = satellitePositions.get(a);
      const posB = satellitePositions.get(b);
      
      if (posA && posB) {
          islsCollection.entities.add({
              polyline: {
                  positions: Cartesian3.fromDegreesArrayHeights([
                      posA.longitude, posA.latitude, posA.height,
                      posB.longitude, posB.latitude, posB.height
                  ]),
                  width: 1,
                  material: Color.BLUE.withAlpha(0.5),
                  arcType: ArcType.NONE
              }
          });
      }
  });
};