import networkx as nx
from typing import List, Dict

class SatelliteNetwork:
    """
    Class to handle the satellite network topology and graph creation.
    """
    def __init__(self, isls_file: str):
        """
        Initialize the satellite network from an ISLs file.
        
        Args:
            isls_file (str): Path to the file containing inter-satellite links
        """
        self.isls_file = isls_file
        self.graph = nx.Graph()  # Using undirected graph
        self._load_isls()
    
    def _load_isls(self):
        """
        Load inter-satellite links from the file and create undirected edges.
        """
        with open(self.isls_file, 'r') as file:
            for line in file:
                # Parse the two node IDs from each line
                node1, node2 = map(str, line.strip().split())
                # Add single undirected edge
                self.graph.add_edge(node1, node2)
    
    def get_graph(self) -> nx.Graph:
        """
        Return the undirected graph representing the satellite network.
        
        Returns:
            nx.Graph: Undirected graph with satellite connections
        """
        return self.graph
    
    def update_node_positions(self, position_data: List[Dict], *, node_type: str = 'satellite'):
        """
        Update node attributes with current positions.
        
        Args:
            position_data: List of dictionaries containing position information
            node_type: Type of node ('satellite' or 'ground_station')
        """
        for pos in position_data:
            # Add node if it doesn't exist
            if pos['id'] not in self.graph:
                self.graph.add_node(pos['id'])
            
            # Create attribute dictionary
            attrs = {
                'latitude': pos['latitude'],
                'longitude': pos['longitude'],
                'height_km': pos['height_km'],
                'type': node_type
            }
            
            # Add additional attributes for ground stations
            if node_type == 'ground_station':
                attrs.update({
                    'name': pos['name'],
                    'population': pos['population']
                })
            
            # Update node attributes
            self.graph.nodes[pos['id']].update(attrs)
  
    def find_visible_satellites(self, max_gsl_length_m: float = 1089686.4181956202, min_elevation_angle: float = 25.0) -> List[tuple]:
        """
        Find pairs of ground stations and satellites that are visible to each other.
        
        Args:
            max_gsl_length_m (float): Maximum ground-to-satellite link length in meters
            min_elevation_angle (float): Minimum elevation angle in degrees
            
        Returns:
            List[tuple]: List of (ground_station_id, satellite_id) pairs
        """
        from math import radians, degrees, cos, sin, asin, sqrt, atan2
        
        visible_pairs = []
        R_EARTH = 6371000.0  # Earth radius in meters
        
        # Find all ground stations and satellites
        ground_stations = [n for n, d in self.graph.nodes(data=True) 
                         if d.get('type') == 'ground_station']
        satellites = [n for n, d in self.graph.nodes(data=True) 
                    if d.get('type') == 'satellite']
        
        print(f"Checking visibility between {len(ground_stations)} ground stations and {len(satellites)} satellites...")
        
        def calculate_distance_and_elevation(gs_lat, gs_lon, sat_lat, sat_lon, sat_alt):
            """Calculate the distance and elevation angle between ground station and satellite."""
            # Convert to radians
            gs_lat, gs_lon = map(radians, [gs_lat, gs_lon])
            sat_lat, sat_lon = map(radians, [sat_lat, sat_lon])
            
            # Calculate great circle distance
            dlon = sat_lon - gs_lon
            dlat = sat_lat - gs_lat
            a = sin(dlat/2)**2 + cos(gs_lat) * cos(sat_lat) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            ground_distance = R_EARTH * c
            
            # Calculate straight-line distance
            sat_alt_m = sat_alt * 1000  # Convert altitude to meters
            total_distance = sqrt(ground_distance**2 + sat_alt_m**2)
            
            # Calculate elevation angle
            elevation = degrees(atan2(sat_alt_m, ground_distance))
            
            return total_distance, elevation
        
        for gs in ground_stations:
            gs_data = self.graph.nodes[gs]
            visible_count = 0
            
            for sat in satellites:
                sat_data = self.graph.nodes[sat]
                
                distance, elevation = calculate_distance_and_elevation(
                    gs_data['latitude'], 
                    gs_data['longitude'],
                    sat_data['latitude'],
                    sat_data['longitude'],
                    sat_data['height_km']
                )
                
                if distance <= max_gsl_length_m and elevation >= min_elevation_angle:
                    visible_pairs.append((gs, sat))
                    visible_count += 1
            
            print(f"Ground station {gs}: {visible_count} visible satellites "
                  f"(distance <= {max_gsl_length_m/1000:.2f}km, elevation >= {min_elevation_angle}°)")
            
        print(f"Total visible pairs found: {len(visible_pairs)}")
        return visible_pairs
        
    def update_visibility_edges(self, max_gsl_length_m: float = 1089686.4181956202, min_elevation_angle: float = 25.0):
        """
        Update the graph with edges between ground stations and visible satellites.
        
        Args:
            max_gsl_length_m (float): Maximum ground-to-satellite link length in meters
            min_elevation_angle (float): Minimum elevation angle in degrees
        """
        # Remove old visibility edges
        visibility_edges = [(u, v) for u, v, d in self.graph.edges(data=True) 
                          if d.get('type') == 'visibility']
        self.graph.remove_edges_from(visibility_edges)
        
        # Add new visibility edges
        visible_pairs = self.find_visible_satellites(max_gsl_length_m, min_elevation_angle)
        for gs, sat in visible_pairs:
            self.graph.add_edge(gs, sat, type='visibility')
    
    def get_network_stats(self) -> Dict:
        """
        Get basic statistics about the network.
        
        Returns:
            Dict: Dictionary containing network statistics
        """
        satellites = [n for n, d in self.graph.nodes(data=True) 
                    if d.get('type') == 'satellite']
        ground_stations = [n for n, d in self.graph.nodes(data=True) 
                         if d.get('type') == 'ground_station']
        visibility_edges = [(u, v) for u, v, d in self.graph.edges(data=True) 
                          if d.get('type') == 'visibility']
        isl_edges = [(u, v) for u, v, d in self.graph.edges(data=True) 
                    if d.get('type') != 'visibility']
        
        return {
            'num_satellites': len(satellites),
            'num_ground_stations': len(ground_stations),
            'num_isl_edges': len(isl_edges),
            'num_visibility_edges': len(visibility_edges),
            'is_connected': nx.is_connected(self.graph),
            'average_degree': sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes()
        }
    
    def save_gsls(self, output_file: str):
        """
        Save ground station to satellite links to a file.
        
        Args:
            output_file (str): Path to the output file
        """
        visibility_edges = [(u, v) for u, v, d in self.graph.edges(data=True) 
                          if d.get('type') == 'visibility']
        
        with open(output_file, 'w') as f:
            for sat, gs in visibility_edges:
                print(f"visibility edge: {gs} {sat}")
                f.write(f"{gs} {sat}\n")    