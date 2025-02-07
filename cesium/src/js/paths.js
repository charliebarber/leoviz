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


export const plotPath = (path, color, satellitePositions, cityPositions) => {
  const positions = [];
  
  path.forEach((nodeId, index) => {
    let pos;
    if (index === 0 || index === path.length - 1) {
      pos = cityPositions.get(nodeId);
    } else {
      pos = satellitePositions.get(nodeId);
    }
    
    if (pos) {
      positions.push(pos.longitude, pos.latitude, pos.height);
    }
  });
  
  if (positions.length >= 6) {
    return {
      polyline: {
        positions: Cartesian3.fromDegreesArrayHeights(positions),
        width: 2,
        material: color,
        arcType: ArcType.NONE
      }
    };
  }
  return null;
};

const loadPath = async (filepath) => {
  try {
    const response = await fetch(filepath);
    const text = await response.text();
    const paths = {
      sparePath: [],
      shortestPath: []
    };

    const lines = text.split('\n').filter(line => line.trim().length > 0);
    let currentPath = null;

    for (const line of lines) {
      if (line.includes('SPARE PATH')) {
        currentPath = 'sparePath';
      } else if (line.includes('SHORTEST PATH')) {
        currentPath = 'shortestPath';
      } else if (currentPath && line.trim()) {
        paths[currentPath] = line.trim().split(' ').map(Number);
      }
    }

    return paths;
  } catch (error) {
    console.error('Error loading paths:', error);
    throw error;
  }
};

export const plotPaths = async (pathsCollection, satellitePositions, cityPositions, timestamp) => {
  const src = "10028";
  const dst = "10010";
  const filepath = `positions/starlink_550_traffic_scaled/${timestamp}/paths/path_${src}_${dst}.txt`;
  const { sparePath, shortestPath } = await loadPath(filepath);
  
  const spareLine = plotPath(sparePath, Color.BLUE, satellitePositions, cityPositions);
  const shortestLine = plotPath(shortestPath, Color.RED, satellitePositions, cityPositions);
  
  if (spareLine) pathsCollection.entities.add(spareLine);
  if (shortestLine) pathsCollection.entities.add(shortestLine);
  
  return pathsCollection;
};