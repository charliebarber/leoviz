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

const loadBetweenness = async (timestamp) => {
  try {
    const response = await fetch(`positions/starlink_550/betweenness_${timestamp}.txt`);
    const text = await response.text();
    const betweennessMap = new Map();

    // Parse the betweenness data
    text.split('\n').forEach(line => {
      if (line.trim()) {
        const [node1, node2, value] = line.split(' ');
        // Create a unique key for each edge (order nodes to ensure consistency)
        const key = [Number(node1), Number(node2)].sort((a, b) => a - b).join('-');
        betweennessMap.set(key, Number(value));
      }
    });

    return betweennessMap;
  } catch (error) {
    console.error('Error loading betweenness data:', error);
    return new Map();
  }
};

const getBetweennessColor = (value, maxBetweenness) => {
  if (value === undefined) {
    return Color.GRAY.withAlpha(0.3); // Default color for edges without betweenness
  }

  // Normalize the value between 0 and 1
  const normalized = value / maxBetweenness;

  // Create a color gradient from blue (low) to red (high)
  // You can adjust these colors to your preference
  return Color.fromHsl(
    (1 - normalized) * 0.6, // Hue: 0.6 is blue, 0 is red
    1.0,                    // Saturation
    0.5,                    // Lightness
    0.8                     // Alpha
  );
};

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

export const plotISLs = async (isls, satellitePositions, islsCollection, timestamp) => {
  // Load betweenness data
  const betweennessMap = await loadBetweenness(timestamp);

  // Find maximum betweenness value for scaling
  const maxBetweenness = Math.max(...Array.from(betweennessMap.values()));

  isls.forEach(({ a, b }) => {
    const posA = satellitePositions.get(a);
    const posB = satellitePositions.get(b);

    if (posA && posB) {
      // Create edge key in same format as betweenness map
      const edgeKey = [a, b].sort((a, b) => a - b).join('-');
      const betweennessValue = betweennessMap.get(edgeKey);

      islsCollection.entities.add({
        polyline: {
          positions: Cartesian3.fromDegreesArrayHeights([
            posA.longitude, posA.latitude, posA.height,
            posB.longitude, posB.latitude, posB.height
          ]),
          width: 2, // Made slightly wider to better show colors
          material: getBetweennessColor(betweennessValue, maxBetweenness),
          arcType: ArcType.NONE
        }
      });
    }
  });
};