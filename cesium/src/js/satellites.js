import Papa from 'papaparse';
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

// Store all satellite data and timestamps
let satelliteDataByTimestamp = new Map();
let currentTimestampIndex = 0;

// Load a single CSV file
const loadSingleCSV = async (timestamp) => {
    try {
        const response = await fetch(`/positions/starlink_550/${timestamp}.csv`);
        const csvText = await response.text();
        
        return new Promise((resolve, reject) => {
            Papa.parse(csvText, {
                header: true,
                dynamicTyping: true,
                skipEmptyLines: true,
                complete: (results) => {
                    if (results.errors.length) {
                        console.error('CSV parsing errors:', results.errors);
                    }
                    const satellites = results.data.map(row => ({
                        name: row.satellite,
                        id: row.id,
                        latitude: row.latitude,
                        longitude: row.longitude,
                        height: row.height_km * 1000 // Convert to meters for Cesium
                    }));
                    resolve(satellites);
                },
                error: reject
            });
        });
    } catch (error) {
        console.error(`Error loading CSV for timestamp ${timestamp}:`, error);
        throw error;
    }
};

// Load all CSVs into memory
const loadAllSatelliteData = async () => {
    try {
        // First, get list of files from directory
        const response = await fetch('/positions/starlink_550/');
        const files = await response.text();
        
        // Parse the directory listing to get timestamps
        // This assumes the directory listing shows all .csv files
        timestamps = files.match(/\d+\.csv/g)
            .map(filename => parseInt(filename.replace('.csv', '')))
            .sort((a, b) => a - b);

        console.log(`Found ${timestamps.length} timestamp files`);

        // Load all CSVs in parallel
        const loadPromises = timestamps.map(async timestamp => {
            const data = await loadSingleCSV(timestamp);
            satelliteDataByTimestamp.set(timestamp, data);
        });

        await Promise.all(loadPromises);
        console.log('All satellite data loaded');
        
        return timestamps[0]; // Return first timestamp for initial display
    } catch (error) {
        console.error('Error loading satellite data:', error);
        throw error;
    }
};

// Navigation functions
const nextTimestamp = () => {
    if (currentTimestampIndex < timestamps.length - 1) {
        currentTimestampIndex++;
        return satelliteDataByTimestamp.get(timestamps[currentTimestampIndex]);
    }
    return null;
};

const previousTimestamp = () => {
    if (currentTimestampIndex > 0) {
        currentTimestampIndex--;
        return satelliteDataByTimestamp.get(timestamps[currentTimestampIndex]);
    }
    return null;
};

const getCurrentTimestamp = () => timestamps[currentTimestampIndex];

export const loadSatellites = async (timestamp) => {
    const csvPath = `/positions/starlink_550/${timestamp}.csv`
    try {
        const response = await fetch(csvPath);
        const csvText = await response.text();
        
        return new Promise((resolve, reject) => {
            Papa.parse(csvText, {
                header: true,
                dynamicTyping: true, // Automatically convert numbers
                skipEmptyLines: true,
                complete: (results) => {
                    if (results.errors.length) {
                        console.error('CSV parsing errors:', results.errors);
                    }

                    // Process the data to get unique latest positions for each satellite
                    const satellites = results.data.reduce((acc, row) => {
                        acc.push({
                            name: row.satellite,
                            id: row.id,
                            latitude: row.latitude,
                            longitude: row.longitude,
                            height: row.height_km * 1000 // Convert to meters for Cesium
                        });
                        return acc;
                    }, []);

                    resolve(satellites);
                },
                error: (error) => {
                    console.error('Error parsing CSV:', error);
                    reject(error);
                }
            });
        });
    } catch (error) {
        console.error('Error loading CSV:', error);
        throw error;
    }
};

export const addSatellite = (satellitesCollection, longitude, latitude, height = 550000) => {
    const entity = satellitesCollection.entities.add({
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

export const plotSatellites = async (satellitesCollection, timestamp) => {
    const satellites = await loadSatellites(timestamp);
    console.log(`Starting to add ${satellites.length} satellites...`);

    // Create map of satellite ID to position
    const satellitePositions = new Map();
    satellites.forEach((sat) => {
        const entity = addSatellite(satellitesCollection, sat.longitude, sat.latitude, sat.height);
        if (entity) {
            entity.name = sat.name;
            satellitePositions.set(sat.id, {
                longitude: sat.longitude,
                latitude: sat.latitude,
                height: sat.height
            });
        }
    });
    
    return satellitePositions;
}

export {
    satelliteDataByTimestamp,
    currentTimestampIndex,
    nextTimestamp,
    previousTimestamp,
    getCurrentTimestamp
}