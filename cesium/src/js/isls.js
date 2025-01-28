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

// Function to get color and width based on betweenness value
const getBetweennessStyle = (value, maxBetweenness) => {
  // No betweenness value (not on any shortest path)
  if (value === undefined) {
      return {
          color: Color.GRAY.withAlpha(0.1), // Very faint gray
          width: 1
      };
  }
  
  // Normalize the value between 0 and 1
  const normalized = value / maxBetweenness;
  
  // Define thresholds for extreme values
  const HIGH_THRESHOLD = 0.8;  // Top 20%
  const LOW_THRESHOLD = 0.2;   // Bottom 20%
  
  if (normalized >= HIGH_THRESHOLD) {
      // High betweenness - bright red and thick
      return {
          color: Color.RED.withAlpha(0.9),
          width: 3
      };
  } else if (normalized <= LOW_THRESHOLD) {
      // Low but non-zero betweenness - dim blue and thin
      return {
          color: Color.BLUE.withAlpha(0.3),
          width: 1
      };
  } else {
      // Medium betweenness - gradient from blue to red
      return {
          color: Color.fromHsl(
              (1 - normalized) * 0.6, // Hue: 0.6 is blue, 0 is red
              0.8,                    // Slightly less saturated
              0.5,                    // Lightness
              0.5                     // Medium alpha
          ),
          width: 2
      };
  }
};

// Function to get style for inverted betweenness visualisation
const getInvertedBetweennessStyle = (value, maxBetweenness, percentile20th) => {
  // No betweenness value (not on any shortest path)
  if (value === undefined) {
      return {
          color: Color.RED.withAlpha(0.9), // Bright red for unused paths
          width: 3
      };
  }
  
  // Normalize the value between 0 and 1
  const normalized = value / maxBetweenness;
  
  if (value <= percentile20th) {
      // Low betweenness - bright blue and thick
      return {
          color: Color.BLUE.withAlpha(0.9),
          width: 3
      };
  } else {
      // Higher betweenness - faint gray with decreasing width
      return {
          color: Color.GRAY.withAlpha(0.2),
          width: 1
      };
  }
};

// Function to get style with green to red gradient for low betweenness
const getLowBetweennessStyle = (value, maxBetweenness, percentile25th) => {
  // Default style for higher betweenness values (above 20th percentile)
  if (value > percentile25th) {
      return {
          color: Color.GRAY.withAlpha(0.2),
          width: 1
      };
  }

  if (value === undefined) {
      // No betweenness - bright green
      return {
          color: Color.GREEN.withAlpha(0.9),
          width: 3
      };
  }
  
  // For values between 0 and 25th percentile, create a gradient from green to red
  const normalizedLow = value / percentile25th;  // Will be between 0 and 1
  
  // Create a gradient from green (low) to red (near 25th percentile)
  return {
      color: Color.fromHsl(
          (1 - normalizedLow) * 0.33,  // Hue: 0.33 is green, 0 is red
          0.9,                         // High saturation
          0.5,                         // Medium lightness
          0.8                          // High alpha for visibility
      ),
      width: 3 - normalizedLow         // Width gradually decreases as betweenness increases
  };
};

export const plotISLs = async (isls, satellitePositions, islsCollection, timestamp) => {
  // Load betweenness data
  const betweennessMap = await loadBetweenness(timestamp);
  
  // Get all betweenness values for percentile calculation
  const betweennessValues = Array.from(betweennessMap.values()).sort((a, b) => a - b);
  const maxBetweenness = betweennessValues[betweennessValues.length - 1];
  const percentile25th = betweennessValues[Math.floor(betweennessValues.length * 0.25)];
  
  // Keep track of different categories for logging
  let noPathCount = 0;
  let lowBetweennessCount = 0;
  let highBetweennessCount = 0;
  
  isls.forEach(({ a, b }) => {
      const posA = satellitePositions.get(a);
      const posB = satellitePositions.get(b);
      
      if (posA && posB) {
          const edgeKey = [a, b].sort((a, b) => a - b).join('-');
          const betweennessValue = betweennessMap.get(edgeKey);
          const style = getLowBetweennessStyle(betweennessValue, maxBetweenness, percentile25th);
          
          // Count different categories
          if (betweennessValue === undefined) {
              noPathCount++;
          } else if (betweennessValue <= percentile25th) {
              lowBetweennessCount++;
          } else {
              highBetweennessCount++;
          }
          
          islsCollection.entities.add({
              polyline: {
                  positions: Cartesian3.fromDegreesArrayHeights([
                      posA.longitude, posA.latitude, posA.height,
                      posB.longitude, posB.latitude, posB.height
                  ]),
                  width: style.width,
                  material: style.color,
                  arcType: ArcType.NONE
              }
          });
      }
  });
  
  // Log statistics and threshold values
  console.log(`Betweenness Statistics:
      No shortest paths: ${noPathCount} links (shown in red)
      Low betweenness (≤${percentile25th.toFixed(2)}): ${lowBetweennessCount} links (shown in blue)
      Higher betweenness: ${highBetweennessCount} links (shown faint)
      Total: ${isls.length} links`);
};