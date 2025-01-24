import csv
from typing import List, Dict
from pathlib import Path

class GroundStations:
    """
    Class to handle ground station data and management.
    """
    def __init__(self, cities_file: str):
        """
        Initialize ground stations from a cities CSV file.
        
        Args:
            cities_file (str): Path to the CSV file containing city information
        """
        self.cities_file = cities_file
        self.stations = {}  # Dictionary to store ground station data
        self._load_stations()
    
    def _load_stations(self):
        """
        Load ground station data from the CSV file.
        """
        with open(self.cities_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                self.stations[row['id']] = {
                    'name': row['name'],
                    'latitude': float(row['latitude']),
                    'longitude': float(row['longitude']),
                    'population': float(row['population'])
                }
    
    def get_station_positions(self) -> List[Dict]:
        """
        Get position data for all ground stations.
        
        Returns:
            List[Dict]: List of ground station position dictionaries
        """
        position_data = []
        
        for station_id, data in self.stations.items():
            position_data.append({
                'id': f"{station_id}",  # Prefix to distinguish from satellites
                'name': data['name'],
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'height_km': 0.0,  # Ground stations are at surface level
                'population': data['population']
            })
        
        return position_data
    
    def get_station_ids(self) -> List[str]:
        """
        Get list of ground station IDs with GS_ prefix.
        
        Returns:
            List[str]: List of ground station IDs
        """
        return [f"GS_{id}" for id in self.stations.keys()]