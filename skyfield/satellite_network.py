import networkx as nx
from typing import List, Dict
from math import radians, cos, sin, asin, sqrt
from math import radians, degrees, cos, sin, asin, sqrt, atan2
from concurrent.futures import ThreadPoolExecutor
import itertools
from tqdm import tqdm
import pandas as pd


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
                self.graph.add_edge(node1, node2, type="ISL")
    
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
                    visible_pairs.append((gs, sat, distance))
                    visible_count += 1
            
            # print(f"Ground station {gs}: {visible_count} visible satellites "
                #   f"(distance <= {max_gsl_length_m/1000:.2f}km, elevation >= {min_elevation_angle}°)")
            
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
        for gs, sat, distance in visible_pairs:
            self.graph.add_edge(gs, sat, type='visibility', distance=distance)
    
    def calculate_isl_distance(self, sat1_id: str, sat2_id: str) -> float:
        """Calculate straight-line distance between two satellites in meters."""
        sat1 = self.graph.nodes[sat1_id]
        sat2 = self.graph.nodes[sat2_id]
        
        # Convert to radians
        lat1, lon1 = map(radians, [sat1['latitude'], sat1['longitude']])
        lat2, lon2 = map(radians, [sat2['latitude'], sat2['longitude']])
        
        # Get altitudes in meters
        alt1 = sat1['height_km'] * 1000
        alt2 = sat2['height_km'] * 1000
        R_EARTH = 6371000.0  # Earth radius in meters
        
        # Calculate great circle distance at the satellites' altitude
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        
        # Use haversine formula to get angular distance
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # Calculate arc distance at each satellite's altitude
        arc1 = (R_EARTH + alt1) * c
        arc2 = (R_EARTH + alt2) * c
        
        # Average of arc distances gives approximate chord length
        arc_avg = (arc1 + arc2) / 2
        
        # Calculate straight-line (chord) distance using altitude difference
        delta_h = abs(alt2 - alt1)
        distance = sqrt(arc_avg**2 + delta_h**2)
        
        return distance

    def update_isl_distances(self):
        """Update ISL edges with their distances."""
        isl_edges = [(u, v) for u, v, d in self.graph.edges(data=True) 
                    if d.get('type') == 'ISL']
        
        for sat1, sat2 in isl_edges:
            distance = self.calculate_isl_distance(sat1, sat2)
            self.graph.edges[sat1, sat2]['distance'] = distance
    
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
                f.write(f"{gs} {sat}\n")    
     
    def _process_gs_pair(self, gs_pair):
        gs1, gs2 = gs_pair
        result = {}
        try:
            path = nx.shortest_path(self.graph, gs1, gs2, weight="weight")
            for j in range(len(path) - 1):
                edge = tuple(sorted([path[j], path[j+1]]))
                if edge in result:
                    result[edge] += 1
                else:
                    result[edge] = 1
        except nx.NetworkXNoPath:
            pass
        return result

    def _process_gs_pair_scaled(self, gs_pair):
        gs1, gs2, demand = gs_pair
        result = {}
        try:
            path = nx.shortest_path(self.graph, gs1, gs2, weight="distance")
            for j in range(len(path) - 1):
                edge = tuple(sorted([path[j], path[j+1]]))
                if edge in result:
                    result[edge] += demand
                else:
                    result[edge] = demand
        except nx.NetworkXNoPath:
            pass
        return result

    def calculate_gs_edge_betweenness(self):
        """Calculate edge betweenness centrality for paths between ground station pairs."""

        ground_stations = [n for n, d in self.graph.nodes(data=True) 
                         if d.get('type') == 'ground_station']
        print(f"Ground stations found: {len(ground_stations)}")
        
        # Generate all ground station pairs
        gs_pairs = [(gs1, gs2) for i, gs1 in enumerate(ground_stations) 
                   for gs2 in ground_stations[i+1:]]
        total_pairs = len(gs_pairs)
        print(f"Processing {total_pairs} ground station pairs...")

        cities_scaled_df = pd.read_csv('cities_scaled.csv')
        gs_pairs_scaled = []
        for gs1, gs2 in gs_pairs:
            row = cities_scaled_df.loc[(cities_scaled_df['gs1'] == gs1) & (cities_scaled_df['gs2'] == gs2)]
            demand = row['demand'].iloc[0] if not row.empty else 0
            gs_pairs_scaled.append((gs1, gs2, demand))
        
        # Initialize edge betweenness dictionary
        edge_betweenness = {edge: 0 for edge in self.graph.edges()}
        
        # Process pairs in parallel with progress bar
        with ThreadPoolExecutor() as executor:
            results = list(tqdm(
                executor.map(self._process_gs_pair_scaled, gs_pairs_scaled),
                total=total_pairs,
                desc="Calculating betweenness"
            ))
        
        # Combine results
        for result in results:
            for edge, value in result.items():
                if edge in edge_betweenness:
                    edge_betweenness[edge] += value
        
        return edge_betweenness
    
    def save_edge_betweenness(self, output_file: str):
        """
        Calculate and save edge betweenness centrality for paths between ground station pairs.
        """
        edge_betweenness = self.calculate_gs_edge_betweenness()
        
        with open(output_file, 'w') as f:
            for edge, value in sorted(edge_betweenness.items(), key=lambda x: x[1], reverse=True):
                if value > 0:  # Only save edges that are used
                    f.write(f"{edge[0]} {edge[1]} {value:.6f}\n")