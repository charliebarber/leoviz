from skyfield.api import EarthSatellite, load, utc
from typing import List, Tuple
import datetime
import csv
import os
from datetime import timedelta, timezone
from pathlib import Path

class TLEParser:
    def __init__(self, filename: str):
        """
        Initialize the TLE parser with the filename containing TLE data.
        
        Args:
            filename (str): Path to the TLE file
        """
        self.filename = filename
        self.satellites = []
        self.ts = load.timescale(builtin=True)
    
    def read_tle_file(self) -> List[Tuple[str, str, str]]:
        """
        Read and parse the TLE file into a list of (name, line1, line2) tuples.
        
        Returns:
            List[Tuple[str, str, str]]: List of TLE data tuples
        """
        tle_data = []
        
        with open(self.filename, 'r') as file:
            # Skip the first line (assumed to be the header with counts)
            next(file)
            
            while True:
                try:
                    # Read three lines at a time (name and two TLE lines)
                    name = next(file).strip()
                    line1 = next(file).strip()
                    line2 = next(file).strip()
                    
                    tle_data.append((name, line1, line2))
                except StopIteration:
                    break
                    
        return tle_data
    
    def create_satellites(self) -> List[EarthSatellite]:
        """
        Create EarthSatellite objects from the TLE data.
        
        Returns:
            List[EarthSatellite]: List of created satellite objects
        """
        tle_data = self.read_tle_file()
        
        for name, line1, line2 in tle_data:
            satellite = EarthSatellite(line1, line2, name, self.ts)
            self.satellites.append(satellite)
            
        return self.satellites

    def get_and_save_position_snapshot(self, timestamp: float, output_dir: Path):
        """
        Get and save a single snapshot of satellite positions.
        
        Args:
            timestamp (float): Unix timestamp for the snapshot
            output_dir (Path): Directory to save the snapshot
        """
        # Convert Unix timestamp to skyfield time
        t = self.ts.from_datetime(datetime.datetime.fromtimestamp(timestamp, tz=timezone.utc))
        
        # Create list to store positions for this timestamp
        position_data = []
        
        # Get position for each satellite
        for sat in self.satellites:
            geocentric = sat.at(t)
            subpoint = geocentric.subpoint()
            id = sat.name.split("-")[1].split(" ")[1]
            
            position_data.append({
                'timestamp': timestamp,
                'satellite': sat.name,
                'id': id,
                'latitude': round(subpoint.latitude.degrees, 4),
                'longitude': round(subpoint.longitude.degrees, 4),
                'height_km': round(subpoint.elevation.km, 2)
            })
        
        # Create filename with timestamp
        filename = output_dir / f"{int(timestamp)}.csv"
        
        # Save to CSV
        fieldnames = ['timestamp', 'satellite', 'id', 'latitude', 'longitude', 'height_km']
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(position_data)
        
        return len(position_data)

def main():
    tle_file = "../constellations/starlink_550/tles.txt"
    base_output_dir = Path("../positions/starlink_550")
    
    # Create output directory if it doesn't exist
    base_output_dir.mkdir(parents=True, exist_ok=True)
    
    parser = TLEParser(tle_file)
    
    try:
        # Create satellite objects
        satellites = parser.create_satellites()
        
        # Configuration for snapshots
        start_timestamp = datetime.datetime.now(timezone.utc).timestamp()
        num_snapshots = 10
        time_step_seconds = 60
        
        total_positions = 0
        
        # Process each snapshot
        for i in range(num_snapshots):
            current_timestamp = start_timestamp + (i * time_step_seconds)
            positions_count = parser.get_and_save_position_snapshot(current_timestamp, base_output_dir)
            total_positions += positions_count
            
            # Print progress
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{num_snapshots} snapshots...")
        
        print(f"Saved {total_positions} position records to {base_output_dir}")
        print(f"Time span: {time_step_seconds * (num_snapshots-1)} seconds")
        print(f"Number of satellites tracked: {len(satellites)}")
        print(f"Start timestamp: {start_timestamp}")
        print(f"End timestamp: {start_timestamp + (time_step_seconds * (num_snapshots-1))}")
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")

if __name__ == "__main__":
    main()