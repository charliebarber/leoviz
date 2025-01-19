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