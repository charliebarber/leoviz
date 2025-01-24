import datetime
from pathlib import Path
from datetime import timezone
from tle_parser import TLEParser
from satellite_network import SatelliteNetwork
from ground_stations import GroundStations

def main():
    # File paths
    tle_file = "../constellations/starlink_550/tles.txt"
    isls_file = "../constellations/starlink_550/isls.txt"
    cities_file = "./cities.csv"
    base_output_dir = Path("../positions/starlink_550")
    
    # Create output directory if it doesn't exist
    base_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize all components
    network = SatelliteNetwork(isls_file)
    parser = TLEParser(tle_file)
    ground_stations = GroundStations(cities_file)
    
    try:
        # Create satellite objects
        satellites = parser.create_satellites()
        
        # Configuration for snapshots
        start_timestamp = datetime.datetime.now(timezone.utc).timestamp()
        num_snapshots = 1
        time_step_seconds = 1
        max_gsl_length_m = 1089686.4181956202  # Maximum GSL length in meters
        min_elevation_angle = 25.0  # Minimum elevation angle in degrees
        
        total_positions = 0
        
        # Process each snapshot
        for i in range(num_snapshots):
            current_timestamp = start_timestamp + (i * time_step_seconds)
            
            # Get satellite positions
            sat_positions = parser.get_position_snapshot(current_timestamp)
            
            # Get ground station positions (static)
            gs_positions = ground_stations.get_station_positions()
            
            # Update network with all positions
            network.update_node_positions(sat_positions, node_type='satellite')
            network.update_node_positions(gs_positions, node_type='ground_station')
            
            # Update visibility edges
            network.update_visibility_edges(min_elevation_angle)
            
            # Save only satellite positions to CSV
            output_file = base_output_dir / f"{int(current_timestamp)}.csv"
            parser.save_positions_to_csv(sat_positions, output_file)
            
            # Save GSLs to file
            gsls_file = base_output_dir / f"gsls_{int(current_timestamp)}.txt"
            network.save_gsls(str(gsls_file))
            
            total_positions += len(sat_positions)
            
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{num_snapshots} snapshots...")
        
        # Get and print network statistics
        stats = network.get_network_stats()
        print(f"\nNetwork Statistics:")
        print(f"Number of satellites: {stats['num_satellites']}")
        print(f"Number of ground stations: {stats['num_ground_stations']}")
        print(f"Number of ISL edges: {stats['num_isl_edges']}")
        print(f"Number of visibility edges: {stats['num_visibility_edges']}")
        print(f"Is connected: {stats['is_connected']}")
        print(f"Average node degree: {stats['average_degree']:.2f}")
        
        print(f"\nSaved {total_positions} position records to {base_output_dir}")
        print(f"Time span: {time_step_seconds * (num_snapshots-1)} seconds")
        print(f"Number of satellites tracked: {len(satellites)}")
        print(f"Start timestamp: {start_timestamp}")
        print(f"End timestamp: {start_timestamp + (time_step_seconds * (num_snapshots-1))}")
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")

if __name__ == "__main__":
    main()