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
    CustomDataSource
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./css/main.css";
import { setupViewer } from "./js/viewer";
import {
    loadSatellites,
    previousTimestamp,
    nextTimestamp,
    getCurrentTimestamp,
    satelliteDataByTimestamp,
    addSatellite,
    plotSatellites
} from "./js/satellites";
import { initCities } from "./js/cities";
import { plotGSLs } from "./js/gsls";
import { plotISLs, loadISLs } from "./js/isls";
import { createEntityToggle } from "./js/ui";

const viewer = setupViewer();

const entities = viewer.entities;

// Create custom DataSources instead of raw EntityCollections
const gslsDataSource = new CustomDataSource('GSLs');
const satellitesDataSource = new CustomDataSource('Satellites');
const gsDataSource = new CustomDataSource('Ground Stations');
const islsDataSource = new CustomDataSource('ISLs');

// Add them to the viewer
viewer.dataSources.add(gslsDataSource);
viewer.dataSources.add(satellitesDataSource);
viewer.dataSources.add(gsDataSource);
viewer.dataSources.add(islsDataSource);


const gslsEntity = entities.add(new EntityCollection());
const satellitesEntity = entities.add(new EntityCollection());
export const gsEntity = entities.add(new EntityCollection( ));
// const islsEntity = entities.add(new EntityCollection());

createEntityToggle(gslsDataSource, 'gslToggler');
createEntityToggle(gsDataSource, 'gsToggler');

// Initial load

// Cities and timestamps stay constant and thus do not need a reload
const cityPositions = await initCities("cities.csv", gsDataSource);

const timestampResponse = await fetch(`/positions/starlink_550_traffic_scaled/timestamps.txt`);
const timestampsText = await timestampResponse.text();
const timestamps = timestampsText.split('\n');

let timestamp_index = 0;

const plot = async (index) => {
    // Plot satellites at given timestamp
    const satellitePositions = await plotSatellites(satellitesDataSource, timestamps[index]);
    // Load and add ISLs
    const isls = await loadISLs('isls.txt');
    plotISLs(isls, satellitePositions, islsDataSource, timestamps[index]);
    // Add ground station links
    console.log('Loading and adding ground station links...');
    plotGSLs(timestamps[index], viewer, {cityPositions, satellitePositions}, gslsDataSource);
};

plot(timestamp_index);


document.getElementById('prevButton').addEventListener('click', async () => {
    const satellites = await previousTimestamp();
    if (satellites) {
        // Clear existing satellites
        satellitesEntity.removeAll();
        // Add new satellites
        satellites.forEach(sat => addSatellite(viewer, sat));
        // Update timestamp display
        document.getElementById('timestamp').textContent =
            new Date(getCurrentTimestamp() * 1000).toLocaleString();
    }
});

document.getElementById('nextButton').addEventListener('click', async () => {
    timestamp_index += 1;
    if (satellitesEntity) {
        satellitesDataSource.entities.removeAll();
        gslsDataSource.entities.removeAll();
        islsDataSource.entities.removeAll();
        console.log("Removed previous timestamp entities");
        plot(timestamp_index);
    }
});