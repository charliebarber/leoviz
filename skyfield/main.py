import datetime
from pathlib import Path
from datetime import timezone
import argparse
from satellite_network import SatelliteNetwork
from tle_parser import TLEParser
from ground_stations import GroundStations
import os

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
    base_output_dir = Path(f"../positions/starlink_550_traffic_scaled/{str(int(args.timestamp))}/")

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
        # network.update_isl_distances() # not needed as update_link_delays also calculates
        network.update_visibility_edges(max_gsl_length_m, min_elevation_angle)

        # Calculate and update link delays
        network.update_link_delays()
        
        # Save satellite positions to CSV
        # output_file = base_output_dir / f"{int(timestamp)}.csv"
        # parser.save_positions_to_csv(sat_positions, output_file)
        
        # Save GSLs to file
        # gsls_file = base_output_dir / f"gsls_{int(timestamp)}.txt"
        # network.save_gsls(str(gsls_file))
        
        # Calculate and save edge betweenness
        betweenness_file = base_output_dir / f"betweenness_{int(timestamp)}.txt"
        # network.save_edge_betweenness(str(betweenness_file))

        # Load betweenness from file
        network.load_edge_betweenness(str(betweenness_file))
        print(network.get_edge_betweenness_stats())
        network.update_spare_edges()

        # Pairs: (London, NYC), (Singapore, London), (Paris, Johannesburg), (Birmingham, Tokyo), (Goteborg, Perth), (Kansas City, Philadelphia)
        pairs = [("10028", "10010"), ("10064", "10028"), ("10025", "10035"), ("10179", "10001"), ("10883", "10255"), ("10300", "10065")]
        # pairs = [("10883", "10255"), ("10300", "10065")]
        for (src, dst) in pairs:
            print(f"\n\nProcessing pair ({src}, {dst})")
            shortest_path, spare_path = network.find_paths_via_spare_edges(src, dst, 1.25)
            os.makedirs(f'{base_output_dir}/paths', exist_ok=True)
            os.makedirs(f'{base_output_dir}/paths/path_{src}_{dst}', exist_ok=True)
            print("\nSPARE PATH")
            print(spare_path)
            print("\nSHORTEST PATH")
            print(shortest_path)
            network.write_paths_to_file(f"{base_output_dir}/paths/path_{src}_{dst}/paths.txt", src, dst, shortest_path, spare_path)

            network.write_path_yaml(f"{base_output_dir}/paths/path_{src}_{dst}/spare.yaml", spare_path)
            network.write_path_yaml(f"{base_output_dir}/paths/path_{src}_{dst}/shortest.yaml", shortest_path)
            print("Finished processing pair")

        print(f"Successfully processed timestamp {timestamp} ({datetime.datetime.fromtimestamp(timestamp, tz=timezone.utc)})")

    except Exception as e:
        print(f"Error processing data: {str(e)}")
        raise  # Re-raise the exception to ensure non-zero exit status

if __name__ == "__main__":
    main()