import Papa from 'papaparse';

export const loadSatellites = async (csvPath) => {
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

// Helper function to load ISLs
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
