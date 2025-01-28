import datetime
from pathlib import Path
from datetime import timezone
import argparse
from satellite_network import SatelliteNetwork
from tle_parser import TLEParser
from ground_stations import GroundStations

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process satellite positions and connections')
    parser.add_argument('--timestamp', type=float, required=True,
                        help='Unix timestamp to process')
    args = parser.parse_args()

    # File paths
    tle_file = "../constellations/starlink_550/tles.txt"
    isls_file = "../constellations/starlink_550/isls.txt"
    cities_file = "./cities.csv"
    base_output_dir = Path("../positions/starlink_550_scaled")

    # Create output directory if it doesn't exist
    base_output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize all components
    network = SatelliteNetwork(isls_file)
    parser = TLEParser(tle_file)
    ground_stations = GroundStations(cities_file)

    try:
        # Create satellite objects
        satellites = parser.create_satellites()

        # Configuration
        max_gsl_length_m = 1089686.4181956202  # Maximum GSL length in meters
        min_elevation_angle = 25.0  # Minimum elevation angle in degrees

        timestamp = args.timestamp  # Using the passed timestamp

        # Get satellite positions for this timestamp
        sat_positions = parser.get_position_snapshot(timestamp)
        
        # Get ground station positions (static)
        gs_positions = ground_stations.get_station_positions()
        
        # Update network with all positions
        network.update_node_positions(sat_positions, node_type='satellite')
        network.update_node_positions(gs_positions, node_type='ground_station')
        
        # Update ISL distances and visibility edges
        network.update_isl_distances()
        network.update_visibility_edges(max_gsl_length_m, min_elevation_angle)
        
        # Save satellite positions to CSV
        output_file = base_output_dir / f"{int(timestamp)}.csv"
        parser.save_positions_to_csv(sat_positions, output_file)
        
        # Save GSLs to file
        gsls_file = base_output_dir / f"gsls_{int(timestamp)}.txt"
        network.save_gsls(str(gsls_file))
        
        # Calculate and save edge betweenness
        betweenness_file = base_output_dir / f"betweenness_{int(timestamp)}.txt"
        network.save_edge_betweenness(str(betweenness_file))

        print(f"Successfully processed timestamp {timestamp} ({datetime.datetime.fromtimestamp(timestamp, tz=timezone.utc)})")

    except Exception as e:
        print(f"Error processing data: {str(e)}")
        raise  # Re-raise the exception to ensure non-zero exit status

if __name__ == "__main__":
    main()