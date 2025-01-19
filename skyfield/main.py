from skyfield.api import EarthSatellite, load, utc
from typing import List, Tuple
import datetime
import csv
from datetime import timedelta, timezone

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

    def get_position_snapshots(self, start_timestamp: float, num_snapshots: int, time_step_seconds: int):
        """
        Get multiple snapshots of satellite positions over time.
        
        Args:
            start_timestamp (float): Unix timestamp for start time
            num_snapshots (int): Number of snapshots to take
            time_step_seconds (int): Seconds between snapshots
            
        Returns:
            List of position data dictionaries
        """
        position_data = []
        
        for i in range(num_snapshots):
            # Calculate time for this snapshot
            current_timestamp = start_timestamp + (i * time_step_seconds)
            # Convert Unix timestamp to skyfield time
            t = self.ts.from_datetime(datetime.datetime.fromtimestamp(current_timestamp, tz=timezone.utc))
            
            # Get position for each satellite at this time
            for sat in self.satellites:
                geocentric = sat.at(t)
                subpoint = geocentric.subpoint()
                
                position_data.append({ 
                    'timestamp': current_timestamp,
                    'satellite': sat.name,
                    'latitude': round(subpoint.latitude.degrees, 4),
                    'longitude': round(subpoint.longitude.degrees, 4),
                    'height_km': round(subpoint.elevation.km, 2)
                })
                
        return position_data
    
    def save_positions_to_csv(self, positions, output_file: str):
        """
        Save position data to CSV file.
        
        Args:
            positions: List of position dictionaries
            output_file (str): Path to output CSV file
        """
        fieldnames = ['timestamp', 'satellite', 'latitude', 'longitude', 'height_km']
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(positions)

def main():
    tle_file = "../constellations/starlink_550/tles.txt"  # Replace with your TLE file path
    output_file = "../positions/starlink_550.csv"
    
    parser = TLEParser(tle_file)
    
    try:
        # Create satellite objects
        satellites = parser.create_satellites()
        
        # Configuration for snapshots
        start_timestamp = datetime.datetime.now(timezone.utc).timestamp()  # Current time as Unix timestamp
        num_snapshots = 1  # Take 60 snapshots
        time_step_seconds = 1  # Every 60 seconds
        
        # Get position snapshots
        positions = parser.get_position_snapshots(start_timestamp, num_snapshots, time_step_seconds)
        
        # Save to CSV
        parser.save_positions_to_csv(positions, output_file)
        
        print(f"Saved {len(positions)} position records to {output_file}")
        print(f"Time span: {time_step_seconds * (num_snapshots-1)} seconds")
        print(f"Number of satellites tracked: {len(satellites)}")
        print(f"Start timestamp: {start_timestamp}")
        print(f"End timestamp: {start_timestamp + (time_step_seconds * (num_snapshots-1))}")
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")

if __name__ == "__main__":
    main()


