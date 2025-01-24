from skyfield.api import EarthSatellite, load, utc
from typing import List, Tuple, Dict
import datetime
import csv
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

    def get_position_snapshot(self, timestamp: float) -> List[Dict]:
        """
        Get a single snapshot of satellite positions.
        
        Args:
            timestamp (float): Unix timestamp for the snapshot
            
        Returns:
            List[Dict]: List of satellite position dictionaries
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
        
        return position_data

    def save_positions_to_csv(self, positions: List[Dict], output_file: Path):
        """
        Save position data to a CSV file.
        
        Args:
            positions (List[Dict]): List of position dictionaries
            output_file (Path): Path to the output CSV file
        """
        fieldnames = ['timestamp', 'satellite', 'id', 'latitude', 'longitude', 'height_km']
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(positions)