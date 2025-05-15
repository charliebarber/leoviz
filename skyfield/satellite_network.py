from graph_tool import Graph, GraphView
from graph_tool.topology import shortest_path, shortest_distance # Add shortest_distance
from typing import List, Dict, Tuple # Add Tuple here
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import pandas as pd
import numpy as np
from tqdm import tqdm
import yaml
from pathlib import Path
import time
import json # For saving stats
import random # For random pairs
import logging # For logging

from path_finder import PathFinder

# Speed of light in vacuum (m/s)
SPEED_OF_LIGHT = 299792458.0

class SatelliteNetwork:
    """
    Class to handle the satellite network topology and graph creation using graph-tool.
    """
    def __init__(self, isls_file: str):
        """
        Initialize the satellite network from an ISLs file.
        
        Args:
            isls_file (str): Path to the file containing inter-satellite links
        """
        self.graph = Graph(directed=False)  # Using undirected graph
        
        # Create property maps
        self.vertex_type = self.graph.new_vertex_property("string")
        self.latitude = self.graph.new_vertex_property("double")
        self.longitude = self.graph.new_vertex_property("double")
        self.height = self.graph.new_vertex_property("double")
        self.name = self.graph.new_vertex_property("string")
        self.population = self.graph.new_vertex_property("long")
        
        # Edge properties
        self.edge_type = self.graph.new_edge_property("string")
        self.delay = self.graph.new_edge_property("double")
        self.distance = self.graph.new_edge_property("double")
        self.betweenness = self.graph.new_edge_property("double")
        self.is_spare = self.graph.new_edge_property("bool")

        # Add property maps to graph
        self.graph.vertex_properties["type"] = self.vertex_type
        self.graph.vertex_properties["latitude"] = self.latitude
        self.graph.vertex_properties["longitude"] = self.longitude
        self.graph.vertex_properties["height_km"] = self.height
        self.graph.vertex_properties["name"] = self.name
        self.graph.vertex_properties["population"] = self.population
        
        self.graph.edge_properties["type"] = self.edge_type
        self.graph.edge_properties["distance"] = self.distance
        self.graph.edge_properties["delay"] = self.delay
        self.graph.edge_properties["betweenness"] = self.betweenness
        self.graph.edge_properties["is_spare"] = self.is_spare 
        
        # Create vertex name to index mapping
        self.vertex_map = {}
        self.index_map = {}

        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        self._load_isls(isls_file)

    def _get_or_add_vertex(self, name: str) -> int:
        """Get vertex index, creating new vertex if needed."""
        if name not in self.vertex_map:
            v = self.graph.add_vertex()
            v_int = int(v)
            self.vertex_map[name] = v_int
            self.index_map[v_int] = name  # Changed from v to v_int
        return self.graph.vertex(self.vertex_map[name])
        

    def _load_isls(self, isls_file: str):
        """Load inter-satellite links from file."""
        with open(isls_file, 'r') as file:
            for line in file:
                node1, node2 = line.strip().split()
                v1 = self._get_or_add_vertex(node1)
                v2 = self._get_or_add_vertex(node2)
                e = self.graph.add_edge(v1, v2)
                self.edge_type[e] = "ISL"

    def get_graph(self) -> Graph:
        """Return the graph-tool Graph object."""
        return self.graph

    def update_node_positions(self, position_data: List[Dict], *, node_type: str = 'satellite'):
        for pos in position_data:
            node_id = str(pos['id'])  # Convert ID to string
            v = self._get_or_add_vertex(node_id)
            
            self.vertex_type[v] = node_type
            self.latitude[v] = pos['latitude']
            self.longitude[v] = pos['longitude']
            self.height[v] = pos['height_km']
            
            if node_type == 'ground_station':
                self.name[v] = pos['name']
                self.population[v] = pos['population']

    def find_visible_satellites(self, max_gsl_length_m: float = 1089686.4181956202,
                              min_elevation_angle: float = 25.0) -> List[tuple]:
        """Find visible satellite-ground station pairs."""
        R_EARTH = 6371000.0
        visible_pairs = []
        
        # Create vertex filters for ground stations and satellites
        is_gs = self.graph.new_vertex_property("bool")
        is_sat = self.graph.new_vertex_property("bool")
        
        for v in self.graph.vertices():
            is_gs[v] = self.vertex_type[v] == 'ground_station'
            is_sat[v] = self.vertex_type[v] == 'satellite'
        
        ground_stations = [v for v in self.graph.vertices() if is_gs[v]]
        satellites = [v for v in self.graph.vertices() if is_sat[v]]
        
        print(f"Checking visibility between {len(ground_stations)} ground stations and {len(satellites)} satellites...")
        
        for gs in ground_stations:
            gs_lat = radians(self.latitude[gs])
            gs_lon = radians(self.longitude[gs])
            
            for sat in satellites:
                sat_lat = radians(self.latitude[sat])
                sat_lon = radians(self.longitude[sat])
                sat_alt = self.height[sat]
                
                # Calculate great circle distance
                dlon = sat_lon - gs_lon
                dlat = sat_lat - gs_lat
                a = sin(dlat/2)**2 + cos(gs_lat) * cos(sat_lat) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                ground_distance = R_EARTH * c
                
                # Calculate straight-line distance
                sat_alt_m = sat_alt * 1000
                total_distance = sqrt(ground_distance**2 + sat_alt_m**2)
                
                # Calculate elevation angle
                elevation = degrees(atan2(sat_alt_m, ground_distance))
                
                if total_distance <= max_gsl_length_m and elevation >= min_elevation_angle:
                    visible_pairs.append((int(gs), int(sat), total_distance))
        
        return visible_pairs

    def update_visibility_edges(self, max_gsl_length_m: float = 1089686.4181956202,
                              min_elevation_angle: float = 25.0):
        """Update visibility edges."""
        # Remove old visibility edges
        edges_to_remove = []
        for e in self.graph.edges():
            if self.edge_type[e] == 'visibility':
                edges_to_remove.append(e)
        
        for e in edges_to_remove:
            self.graph.remove_edge(e)
        
        # Add new visibility edges
        visible_pairs = self.find_visible_satellites(max_gsl_length_m, min_elevation_angle)
        for gs, sat, distance in visible_pairs:
            e = self.graph.add_edge(self.graph.vertex(gs), self.graph.vertex(sat))
            self.edge_type[e] = 'visibility'
            self.distance[e] = distance

    def calculate_isl_distance(self, sat1: int, sat2: int) -> float:
        """Calculate straight-line distance between satellites."""
        R_EARTH = 6371000.0
        
        lat1 = radians(self.latitude[sat1])
        lon1 = radians(self.longitude[sat1])
        alt1 = self.height[sat1] * 1000
        
        lat2 = radians(self.latitude[sat2])
        lon2 = radians(self.longitude[sat2])
        alt2 = self.height[sat2] * 1000
        
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        arc1 = (R_EARTH + alt1) * c
        arc2 = (R_EARTH + alt2) * c
        arc_avg = (arc1 + arc2) / 2
        
        delta_h = abs(alt2 - alt1)
        return sqrt(arc_avg**2 + delta_h**2)

    def update_isl_distances(self):
        """Update ISL edge distances."""
        for e in self.graph.edges():
            if self.edge_type[e] == 'ISL':
                distance = self.calculate_isl_distance(e.source(), e.target())
                self.distance[e] = distance

    def update_link_delays(self):
        """Update link delays based on distance attribute."""
        for e in self.graph.edges():
            if self.edge_type[e] == 'ISL':
                distance = self.calculate_isl_distance(e.source(), e.target())
                self.distance[e] = distance 

                delay = distance / SPEED_OF_LIGHT
                self.delay[e] = delay

            # Visible GSLs 
            if self.edge_type[e] == 'visibility':
                distance = self.distance[e]
                
                # Potential for adding constants based on refraction
                delay = distance / SPEED_OF_LIGHT
                self.delay[e] = delay
                

    def get_network_stats(self) -> Dict:
        """Get network statistics."""
        is_gs = self.graph.new_vertex_property("bool")
        is_sat = self.graph.new_vertex_property("bool")
        
        for v in self.graph.vertices():
            is_gs[v] = self.vertex_type[v] == 'ground_station'
            is_sat[v] = self.vertex_type[v] == 'satellite'
        
        num_gs = sum(1 for _ in self.graph.vertices() if is_gs[_])
        num_sats = sum(1 for _ in self.graph.vertices() if is_sat[_])
        
        visibility_edges = sum(1 for e in self.graph.edges() if self.edge_type[e] == 'visibility')
        isl_edges = sum(1 for e in self.graph.edges() if self.edge_type[e] == 'ISL')
        
        return {
            'num_satellites': num_sats,
            'num_ground_stations': num_gs,
            'num_isl_edges': isl_edges,
            'num_visibility_edges': visibility_edges,
            'average_degree': 2 * self.graph.num_edges() / self.graph.num_vertices()
        }

    def calculate_isl_delay_stats_by_distance(self, distance_threshold_km: float = 1500.0) -> Dict:
        """
        Calculates average delay for short (likely intra-orbit) and long (likely inter-orbit) ISLs.

        Args:
            distance_threshold_km (float): The distance in km to separate short and long ISLs.

        Returns:
            Dict: A dictionary containing average delays and counts for short and long ISLs.
        """
        short_isl_delays = []
        long_isl_delays = []
        distance_threshold_m = distance_threshold_km * 1000.0

        for e in self.graph.edges():
            if self.edge_type[e] == 'ISL':
                distance = self.distance[e] # Assumes distance is already calculated and stored
                delay = self.delay[e]       # Assumes delay is already calculated and stored
                if distance <= distance_threshold_m:
                    short_isl_delays.append(delay)
                else:
                    long_isl_delays.append(delay)

        avg_short_delay = sum(short_isl_delays) / len(short_isl_delays) if short_isl_delays else 0.0
        avg_long_delay = sum(long_isl_delays) / len(long_isl_delays) if long_isl_delays else 0.0

        return {
            'short_isl_count': len(short_isl_delays),
            'long_isl_count': len(long_isl_delays),
            'avg_short_isl_delay_ms': avg_short_delay * 1000, # Convert to ms
            'avg_long_isl_delay_ms': avg_long_delay * 1000,   # Convert to ms
            'distance_threshold_km': distance_threshold_km
        }

    def calculate_gs_edge_betweenness(self):
        """Calculates edge betweenness based on ground station demands."""
        start_overall_time = time.perf_counter()
        # Create vertex filter for ground stations
        is_gs = self.graph.new_vertex_property("bool")
        ground_stations = []
        
        # Create reverse mapping for debugging
        reverse_map = {v: k for k, v in self.vertex_map.items()}
        
        for v in self.graph.vertices():
            if self.vertex_type[v] == 'ground_station':
                is_gs[v] = True
                ground_stations.append(int(v))
        
        print(f"Ground stations found: {len(ground_stations)}")
        
        # Initialize edge betweenness property map
        edge_betweenness = self.graph.new_edge_property("double")
        edge_betweenness.a = 0  # Initialize array to zero
        per_pair_times = [] # List to store timing for each pair

        
        # Load demands
        cities_scaled = pd.read_csv('cities_scaled.csv')
        demand_dict = {}
        
        # Print first few rows of cities_scaled for debugging
        print("First few rows of cities_scaled.csv:", cities_scaled.head())
        print("Available vertex IDs:", sorted(self.vertex_map.keys())[:10])
        
        for _, row in cities_scaled.iterrows():
            gs1, gs2 = str(row['gs1']), str(row['gs2'])  # Convert to string
            if gs1 in self.vertex_map and gs2 in self.vertex_map:
                gs1_idx = self.vertex_map[gs1]
                gs2_idx = self.vertex_map[gs2]
                demand_dict[(gs1_idx, gs2_idx)] = row['traffic_demand']
            else:
                print(f"Warning: Ground station pair ({gs1}, {gs2}) not found in vertex map")
        
        # Process all pairs
        total_pairs = len(ground_stations) * (len(ground_stations) - 1) // 2
        with tqdm(total=total_pairs, desc="Calculating betweenness") as pbar:
            for i, gs1 in enumerate(ground_stations):
                gs1_orig = reverse_map[int(gs1)] # Get original ID once per outer loop
                for gs2 in ground_stations[i+1:]:
                    start_pair_time = time.perf_counter() # Start timer for this pair
                    # Get original IDs for demand lookup
                    gs2_orig = reverse_map[int(gs2)]
                    demand = demand_dict.get((gs1, gs2), 0)
                    

                    path_found = False
                    if demand > 0:
                        # Use graph-tool's optimized shortest path
                        vlist, elist = shortest_path(self.graph,
                                                self.graph.vertex(gs1),
                                                self.graph.vertex(gs2),
                                                weights=self.distance)
                        
                        if elist:  # If path exists
                            for e in elist:
                                edge_betweenness[e] += demand
                            path_found = True

                    end_pair_time = time.perf_counter() # End timer for this pair
                    pair_duration = end_pair_time - start_pair_time
                    per_pair_times.append({
                        'gs1': gs1_orig, 'gs2': gs2_orig,
                        'demand': demand, 'path_found': path_found,
                        'time_s': pair_duration
                    })
                    pbar.update(1)
        

        # Convert to dictionary format if needed
        result = {}
        for e in self.graph.edges():
            if edge_betweenness[e] > 0:
                v1_orig = reverse_map[int(e.source())]
                v2_orig = reverse_map[int(e.target())]
                result[(v1_orig, v2_orig)] = edge_betweenness[e]
        
        end_overall_time = time.perf_counter()
        overall_duration = end_overall_time - start_overall_time
        print(f"Overall edge betweenness calculation took: {overall_duration:.2f} seconds")

        return result, overall_duration, per_pair_times
        
    def save_edge_betweenness(self, output_file: str, timestamp: float, output_dir: Path):
        """
        Calculates and saves edge betweenness results and timing information.

        Args:
            output_file (str): Path to save the edge betweenness values.
            timestamp (float): The Unix timestamp for naming timing files.
            output_dir (Path): The base directory for saving timing results.
        """
        edge_betweenness, overall_duration, per_pair_times = self.calculate_gs_edge_betweenness()

        # Save edge betweenness values
        with open(output_file, 'w') as f:
            for (v1, v2), value in sorted(edge_betweenness.items(), key=lambda x: x[1], reverse=True):
                if value > 0:
                    f.write(f"{v1} {v2} {value:.6f}\n")
        print(f"Saved edge betweenness values to {output_file}")

        # Save timing information
        timing_dir = output_dir / "timing_data" # Create a dedicated subdir
        timing_dir.mkdir(parents=True, exist_ok=True)

        overall_timing_file = timing_dir / f"betweenness_timing_overall_{int(timestamp)}.txt"
        with open(overall_timing_file, 'w') as f_time:
            f_time.write(f"{overall_duration:.6f}\n")
        print(f"Saved overall betweenness timing to {overall_timing_file}")

        per_pair_timing_csv = timing_dir / f"betweenness_timing_per_pair_{int(timestamp)}.csv"
        pd.DataFrame(per_pair_times).to_csv(per_pair_timing_csv, index=False, float_format='%.6f')
        print(f"Saved per-pair betweenness timing to {per_pair_timing_csv}")
    
    def save_gsls(self, output_file: str):
        with open(output_file, 'w') as f:
            for e in self.graph.edges():
                if self.edge_type[e] == 'visibility':
                    # Convert vertex indices to original IDs using the reverse mapping
                    reverse_map = {v: k for k, v in self.vertex_map.items()}
                    v1 = reverse_map[int(e.source())]
                    v2 = reverse_map[int(e.target())]
                    f.write(f"{v1} {v2}\n")

    def load_edge_betweenness(self, betweenness_file: str):
        self.betweenness.a = 0
        
        try:
            with open(betweenness_file, 'r') as f:
                for line in f:
                    node1, node2, value = line.strip().split()
                    # Find the edge in the graph
                    if node1 in self.vertex_map and node2 in self.vertex_map:
                        v1 = self.graph.vertex(self.vertex_map[node1])
                        v2 = self.graph.vertex(self.vertex_map[node2])
                        # Find the edge between these vertices
                        for e in v1.out_edges():
                            if e.target() == v2:
                                self.betweenness[e] = float(value)
                                break
        except Exception as e:  
            print(f"Error loading edge betweenness from file: {e}")    

    def get_edge_betweenness_stats(self):
        betweenness_values = [self.betweenness[e] for e in self.graph.edges()]
        
        if not betweenness_values:
            return {
                'min': 0,
                'max': 0,
                'mean': 0,
                'median': 0,
                'num_edges_with_traffic': 0
            }
            
        return {
            'min': min(betweenness_values),
            'max': max(betweenness_values),
            'mean': sum(betweenness_values) / len(betweenness_values),
            'median': sorted(betweenness_values)[len(betweenness_values) // 2],
            'num_edges_with_traffic': sum(1 for v in betweenness_values if v > 0)
        }

    def update_edge_betweenness(self):
        betweenness_dict = self.calculate_gs_edge_betweenness()
        
        self.betweenness.a = 0
        
        reverse_map = {v: k for k, v in self.vertex_map.items()}
        
        for e in self.graph.edges():
            v1_orig = reverse_map[int(e.source())]
            v2_orig = reverse_map[int(e.target())]
            # Check both orientations of the edge
            value = betweenness_dict.get((v1_orig, v2_orig), 0) or betweenness_dict.get((v2_orig, v1_orig), 0)
            self.betweenness[e] = value

    def update_spare_edges(self, percentile: float = 50.0):
        betweenness_values = [self.betweenness[e] for e in self.graph.edges()]
        if not betweenness_values:
            return
            
        # Calculate the percentile threshold
        threshold = np.percentile(betweenness_values, percentile)
        
        # Update is_spare property for each edge
        for e in self.graph.edges():
            self.is_spare[e] = self.betweenness[e] <= threshold

    def write_paths_to_file(self, output_file: str, source: str, target: str, shortest: List, spare: List):
        """
        Write shortest and spare paths to a file in the paths directory.
        
        Args:
            source (str): Source ground station ID
            target (str): Target ground station ID
            shortest (List): List of nodes in shortest path
            spare (List): List of nodes in spare path
        """
        # Write paths to file
        with open(output_file, 'w') as f:
            f.write("SPARE PATH\n")
            f.write(' '.join(str(node) for node in spare))
            f.write("\nSHORTEST PATH\n")
            f.write(' '.join(str(node) for node in shortest))
            f.write("\n")

    def find_paths_via_spare_edges(self, source: str, target: str, target_weight_factor: float, base_output_dir: str) -> list:
        path_finder = PathFinder(self,base_output_dir)
        return path_finder.find_paths_via_spare_edges(source, target, target_weight_factor)

    def get_random_satellite_pairs(self, num_pairs: int) -> List[Tuple[str, str]]:
        """Selects random pairs of distinct satellite nodes."""
        # Iterate through vertices and check their type using the property map
        satellite_indices = [int(v) for v in self.graph.vertices() if self.vertex_type[v] == 'satellite']
        
        if len(satellite_indices) < 2:
            return [] # Not enough satellites for pairs

        pairs = set()
        attempts = 0
        max_attempts = num_pairs * 10 # Avoid infinite loop if num_pairs is large

        while len(pairs) < num_pairs and attempts < max_attempts:
            idx1, idx2 = random.sample(satellite_indices, 2)
            # Ensure pair order doesn't matter for uniqueness
            pair = tuple(sorted((self.index_map[idx1], self.index_map[idx2])))
            pairs.add(pair)
            attempts += 1
            
        if len(pairs) < num_pairs:
             print(f"Warning: Could only generate {len(pairs)} unique satellite pairs out of {num_pairs} requested.")

        return list(pairs)

    def write_path_yaml(self, filename: str, path: List[str]):
        """
        Write path to YAML file using PyYAML library.
        
        Args:
            filename (str): Output YAML file path
            path (List[str]): List of node IDs in path order
        """
        # Create topology dictionary
        topology = {
            'topology': {
                'nodes': [],
                'links': []
            }
        }
        
        # Add nodes
        for i, node_id in enumerate(path):
            topology['topology']['nodes'].append({
                'id': i,
                'name': str(node_id)
            })
        
        # Add links
        for i in range(len(path)-1):
            v1 = self.graph.vertex(self.vertex_map[path[i]])
            v2 = self.graph.vertex(self.vertex_map[path[i+1]])
            
            # Find edge between vertices
            edge = None
            for e in v1.out_edges():
                if e.target() == v2:
                    edge = e
                    break
            
            if edge:
                # Determine data rate based on edge type
                data_rate = "4Gbps" if self.edge_type[edge] == 'visibility' else "20Gbps"
                delay_ms = self.delay[edge] * 1000  # Convert to milliseconds
                
                topology['topology']['links'].append({
                    'source': str(path[i]),
                    'target': str(path[i+1]),
                    'data_rate': data_rate,
                    'delay': f"{delay_ms:.2f}ms"
                })
        
        # Write to YAML file
    def get_spare_nodes(self) -> set:
        """
        Returns a set of satellite vertex indices that are endpoints of spare edges.
        """
        spare_node_indices = set()
        for e in self.graph.edges():
            if self.is_spare[e]:
                src = self.graph.vertex(int(e.source()))
                dst = self.graph.vertex(int(e.target()))
                # Ensure both endpoints are satellites
                if self.vertex_type[src] == 'satellite' and self.vertex_type[dst] == 'satellite':
                    spare_node_indices.add(int(src))
                    spare_node_indices.add(int(dst))
        return spare_node_indices

    def calculate_gs_to_spare_node_delays(self) -> Dict[str, float]:
        """
        Calculates the minimum delay from each ground station to the nearest
        satellite node connected by a spare edge using an optimized approach.

        Returns:
            Tuple[Dict[str, float], Dict[str, float], float]: A tuple containing:
                - Dict mapping ground station ID (str) to minimum delay (float).
                  Returns float('inf') if a GS cannot reach any spare node.
                - Dict mapping ground station ID (str) to calculation time (float seconds).
                - Float representing the calculation duration in seconds.
        """
        start_time = time.perf_counter() # Start timer

        from graph_tool.topology import shortest_distance # Import locally for performance
        from graph_tool.util import find_vertex # Import locally
        from graph_tool import GraphView # Import locally

        gs_min_delays = {}
        original_spare_node_indices = self.get_spare_nodes() # Get indices from original graph

        if not original_spare_node_indices: # Use the correct variable
            print("Warning: No spare nodes found in the network.")
            # Return inf for all ground stations if no spare nodes exist
            for v in self.graph.vertices():
                if self.vertex_type[v] == 'ground_station':
                    gs_id = self.index_map[int(v)]
                    gs_min_delays[gs_id] = float('inf')
            return gs_min_delays, {}, 0.0 # Return empty times and zero duration

        # spare_nodes = [self.graph.vertex(idx) for idx in spare_node_indices] # Remove this incorrect line
        ground_stations = [v for v in self.graph.vertices() if self.vertex_type[v] == 'ground_station']
        num_spare_nodes = len(original_spare_node_indices) # Calculate for logging

        print(f"Optimized Calculation: Delay from {len(ground_stations)} GS to {num_spare_nodes} spare nodes...") # Use correct variable

        # --- Step 1: Calculate shortest delay from any spare node to all other satellites using GraphView ---
        print("Creating satellite-only graph view...")

        # Create filters
        satellite_filter = self.graph.new_vertex_property("bool")
        isl_filter = self.graph.new_edge_property("bool")
        satellite_vertices = []
        for v in self.graph.vertices():
            is_sat = self.vertex_type[v] == 'satellite'
            satellite_filter[v] = is_sat
            if is_sat:
                satellite_vertices.append(v)
        for e in self.graph.edges():
            isl_filter[e] = self.edge_type[e] == 'ISL'

        # Create the GraphView
        sat_view = GraphView(self.graph, vfilt=satellite_filter, efilt=isl_filter)
        print(f"Satellite view created with {sat_view.num_vertices()} vertices and {sat_view.num_edges()} edges.")

        # Find the Vertex objects in the original graph corresponding to spare nodes
        original_spare_nodes = [self.graph.vertex(idx) for idx in original_spare_node_indices]

        # Filter these to ensure they are actually satellites (should be guaranteed by get_spare_nodes)
        # and exist in the view.
        source_vertices_for_shortest_dist = [v for v in original_spare_nodes if satellite_filter[v]]

        # Get the integer indices *within the sat_view* for these source vertices
        # The sat_view.vertex_index property maps original graph vertices to their index in the view
        source_indices_in_view = [int(sat_view.vertex_index[v]) for v in source_vertices_for_shortest_dist]

        if not source_indices_in_view: # Check the list of indices
             print("Warning: No spare nodes are present in the satellite-only graph view.")
             # Return inf for all ground stations
             for v_gs in ground_stations:
                 gs_id = self.index_map[int(v_gs)]
                 gs_min_delays[gs_id] = float('inf')
             return gs_min_delays, {}, time.perf_counter() - start_time # Return empty times

        print(f"Calculating satellite-to-satellite delays from {len(source_indices_in_view)} spare nodes using the view...") # Use the correct count
        # Initialize a property map on the original graph to store the minimum distance
        # from *any* spare node to each satellite.
        min_dist_from_any_spare = self.graph.new_vertex_property("double", val=float('inf'))

        # Iterate through each spare node and calculate shortest distances individually
        print(f"Iterating through {len(source_vertices_for_shortest_dist)} spare nodes to calculate minimum distances...")
        with tqdm(total=len(source_vertices_for_shortest_dist), desc="Spare Node Distances") as pbar_spare:
            for spare_node_orig in source_vertices_for_shortest_dist:
                # Calculate distances from this single spare node within the sat_view
                # The source vertex must be passed as the original graph vertex.
                dist_map_single_source = shortest_distance(sat_view, source=spare_node_orig, weights=sat_view.edge_properties['delay'])

                # Update the minimum distance map for all reachable satellites in the view
                for v_in_view in sat_view.vertices():
                     # Get the corresponding vertex in the original graph
                    orig_v = self.graph.vertex(int(v_in_view)) # Use int() to get original index
                    current_min = min_dist_from_any_spare[orig_v]
                    dist_from_this_spare = dist_map_single_source[v_in_view] # Use vertex from view for lookup
                    min_dist_from_any_spare[orig_v] = min(current_min, dist_from_this_spare)
                pbar_spare.update(1)

        # min_dist_from_any_spare now holds the minimum delay from any spare node
        # to every other satellite node (accessible via original graph vertices).

        print("Finished satellite-to-satellite delay calculation.")

        # --- Step 2: Calculate GS to spare delay using precalculated values ---
        # Use the 'min_dist_from_any_spare' map calculated above.
        print("Calculating GS delays using precomputed satellite data...")
        gs_calc_times = {} # Dictionary to store calculation time per GS

        with tqdm(total=len(ground_stations), desc="GS to Spare Node Delay") as pbar:
            for gs_vertex in ground_stations:
                min_delay_for_gs = float('inf')
                start_gs_time = time.perf_counter() # Start timer for this GS
                gs_id = self.index_map[int(gs_vertex)]

                # Iterate through GSLs for this ground station
                for e in gs_vertex.out_edges(): # Use out_edges as graph is undirected
                    if self.edge_type[e] == 'visibility':
                        # Find the satellite connected by this GSL
                        sat_vertex = e.target() if e.source() == gs_vertex else e.source()

                        # Ensure the other end is indeed a satellite (should always be true)
                        if self.vertex_type[sat_vertex] == 'satellite':
                            gsl_delay = self.delay[e]
                            # Get the precalculated minimum delay from *any* spare node to this satellite
                            sat_to_spare_delay = min_dist_from_any_spare[sat_vertex] # Use the combined map

                            # Check if the satellite is reachable from any spare node
                            if sat_to_spare_delay != float('inf'):
                                total_delay = gsl_delay + sat_to_spare_delay
                                min_delay_for_gs = min(min_delay_for_gs, total_delay)

                gs_min_delays[gs_id] = min_delay_for_gs
                end_gs_time = time.perf_counter() # End timer for this GS
                gs_calc_times[gs_id] = end_gs_time - start_gs_time # Store duration
                pbar.update(1)

        print("Finished GS delay calculation.")
        

        end_time = time.perf_counter() # End timer
        duration = end_time - start_time
        print(f"Spare capacity delay calculation took: {duration:.2f} seconds")

        return gs_min_delays, gs_calc_times, duration

    def get_candidate_gs_pairs_for_long_paths(self, top_k_each: int = 10, num_random: int = 5) -> List[Tuple[str, str]]:
        """
        Identifies candidate GS-GS pairs that might yield long spare paths.
        It selects pairs based on:
        1. Top K by shortest path delay.
        2. Top K by shortest path hops.
        3. A number of random pairs.

        Args:
            top_k_each (int): Number of top pairs to select for delay and hops criteria.
            num_random (int): Number of random GS pairs to add.

        Returns:
            List[Tuple[str, str]]: A list of unique (gs_id1, gs_id2) tuples.
        """
        self.logger.info(f"Identifying candidate GS pairs: top {top_k_each} by lat, lon, combined geographic separation, and {num_random} random.")
        
        ground_station_vertices = [v for v in self.graph.vertices() if self.vertex_type[v] == 'ground_station']
        
        if len(ground_station_vertices) < 2:
            self.logger.warning("Not enough ground stations to form pairs.")
            return []

        all_gs_pairs_geo_diffs = [] # List to store (gs1_id, gs2_id, lat_diff, lon_diff, combined_diff)

        for i in tqdm(range(len(ground_station_vertices)), desc="Calculating Geographic Separations"):
            gs1_v = ground_station_vertices[i]
            gs1_id = self.index_map[int(gs1_v)]
            gs1_lat = self.latitude[gs1_v]
            gs1_lon = self.longitude[gs1_v]

            for j in range(i + 1, len(ground_station_vertices)):
                gs2_v = ground_station_vertices[j]
                gs2_id = self.index_map[int(gs2_v)]
                gs2_lat = self.latitude[gs2_v]
                gs2_lon = self.longitude[gs2_v]

                lat_diff = abs(gs1_lat - gs2_lat)
                
                lon_diff_raw = abs(gs1_lon - gs2_lon)
                # Calculate shortest longitude difference (e.g., -170 and 170 is 20 deg diff, not 340)
                lon_diff = min(lon_diff_raw, 360.0 - lon_diff_raw)
                
                combined_diff = lat_diff + lon_diff # Sum of absolute latitude and shortest longitude differences
                
                all_gs_pairs_geo_diffs.append({
                    'gs1': gs1_id, 
                    'gs2': gs2_id, 
                    'lat_diff': lat_diff, 
                    'lon_diff': lon_diff,
                    'combined_diff': combined_diff
                })

        candidate_pairs = set()

        # Sort by latitude difference (descending) and pick top_k_each
        all_gs_pairs_geo_diffs.sort(key=lambda x: x['lat_diff'], reverse=True)
        for item in all_gs_pairs_geo_diffs[:top_k_each]:
            candidate_pairs.add(tuple(sorted((item['gs1'], item['gs2']))))

        # Sort by longitude difference (descending) and pick top_k_each
        all_gs_pairs_geo_diffs.sort(key=lambda x: x['lon_diff'], reverse=True)
        for item in all_gs_pairs_geo_diffs[:top_k_each]:
            candidate_pairs.add(tuple(sorted((item['gs1'], item['gs2']))))

        # Sort by combined difference (descending) and pick top_k_each
        all_gs_pairs_geo_diffs.sort(key=lambda x: x['combined_diff'], reverse=True)
        for item in all_gs_pairs_geo_diffs[:top_k_each]:
            candidate_pairs.add(tuple(sorted((item['gs1'], item['gs2']))))
            
        # Add random pairs
        all_gs_ids = [self.index_map[int(v)] for v in ground_station_vertices]
        if len(all_gs_ids) >= 2:
            attempts = 0
            random_pairs_added_count = 0
            # Adjust max_attempts if needed, e.g., num_random * 10 + current_candidates
            max_random_attempts = num_random * 10 + len(candidate_pairs) 

            while random_pairs_added_count < num_random and attempts < max_random_attempts:
                pair = tuple(sorted(random.sample(all_gs_ids, 2)))
                if pair not in candidate_pairs:
                    candidate_pairs.add(pair)
                    random_pairs_added_count += 1
                attempts += 1
            if random_pairs_added_count < num_random:
                 self.logger.warning(f"Could only add {random_pairs_added_count} unique random GS pairs out of {num_random} requested after {attempts} attempts.")

        self.logger.info(f"Selected {len(candidate_pairs)} unique candidate GS pairs based on geographic criteria and random sampling.")
        return list(candidate_pairs)

    def report_spare_capacity_coverage(self, timestamp: float, output_dir: Path):
        """
        Calculates, reports, and saves statistics about the delay from ground stations 
        to the nearest spare capacity node for a given timestamp.

        Args:
            timestamp (float): The Unix timestamp for this data.
            output_dir (Path): The base directory for saving results for this timestamp.
        """
        import pandas as pd # Import locally
        import os # Import locally

        gs_delays, gs_calc_times, overall_duration = self.calculate_gs_to_spare_node_delays() # Get delays, times, and overall duration

        coverage_dir = output_dir / "coverage_data"
        coverage_dir.mkdir(parents=True, exist_ok=True)

        # --- Save the raw delay and timing data ---
        # Combine delays and calculation times into a single structure
        output_csv = coverage_dir / f"gs_delays_{int(timestamp)}.csv"

        if gs_delays:
            # Convert delays to ms and handle infinity
            data_to_save = []
            for gs_id, delay_s in gs_delays.items():
                delay_ms = delay_s * 1000 if delay_s != float('inf') else float('inf')
                calc_time_s = gs_calc_times.get(gs_id, 0.0) # Get calc time, default 0 if missing
                calc_time_ms = calc_time_s * 1000
                data_to_save.append({
                    'gs_id': gs_id,
                    'delay_ms': delay_ms,
                    'calc_time_ms': calc_time_ms
                })
            
            df = pd.DataFrame(data_to_save)
            df.to_csv(output_csv, index=False)
            print(f"Saved GS delays and calculation times to {output_csv}")
        else:
            # Create an empty file or file with header if no delays calculated
            with open(output_csv, 'w') as f:
                f.write("gs_id,delay_ms,calc_time_ms\n")
            print(f"No delay data calculated, saved empty file to {output_csv}")
        # -----------------------------

        if not gs_delays:
            print("Cannot report spare capacity coverage: No delay data calculated.")
            return

        valid_delays = {gs_id: delay for gs_id, delay in gs_delays.items() if delay != float('inf')}

        if not valid_delays:
            print("Cannot report spare capacity coverage: No ground stations can reach any spare nodes.")
            num_unreachable = len(gs_delays)
            print(f"Number of unreachable ground stations: {num_unreachable}")
            return

        delays_list = list(valid_delays.values())
        average_delay = sum(delays_list) / len(delays_list)
        min_delay = min(delays_list)
        max_delay = max(delays_list)

        min_gs_ids = [gs_id for gs_id, delay in valid_delays.items() if delay == min_delay]
        max_gs_ids = [gs_id for gs_id, delay in valid_delays.items() if delay == max_delay]
        
        num_unreachable = len(gs_delays) - len(valid_delays)

        print("\n--- Spare Capacity Coverage Report ---")
        print(f"Analysis based on delay to nearest satellite node connected by a spare edge.")
        print(f"Number of Ground Stations Analyzed: {len(gs_delays)}")
        print(f"Number of Reachable Ground Stations: {len(valid_delays)}")
        print(f"Number of Unreachable Ground Stations: {num_unreachable}")
        print(f"Average Delay to Spare Node: {average_delay * 1000:.2f} ms")
        print(f"Minimum Delay to Spare Node: {min_delay * 1000:.2f} ms (GS IDs: {', '.join(min_gs_ids)})")
        print(f"Maximum Delay to Spare Node: {max_delay * 1000:.2f} ms (GS IDs: {', '.join(max_gs_ids)})")
        print(f"Overall Calculation Time: {overall_duration:.2f} seconds") # Print overall duration
        print("--------------------------------------\n")


    def analyze_spare_contiguity(self, timestamp: float, output_dir: Path):
        """
        Analyzes the connected components formed by spare edges.

        Args:
            timestamp (float): The Unix timestamp for this data.
            output_dir (Path): The base directory for saving results.
        """
        from graph_tool import GraphView
        from graph_tool.topology import label_components
        from graph_tool.clustering import global_clustering # Import clustering function

        print("\n--- Analyzing Spare Edge Contiguity ---")

        # Create a view containing only spare edges (and the vertices they connect)
        # We only consider ISLs for spare capacity analysis
        def spare_isl_filter(e):
            return self.is_spare[e] and self.edge_type[e] == 'ISL'

        spare_filter = self.graph.new_edge_property("bool")
        for e in self.graph.edges():
             spare_filter[e] = spare_isl_filter(e)

        spare_view = GraphView(self.graph, efilt=spare_filter)

        total_spare_edges = spare_view.num_edges()
        total_isl_edges = sum(1 for e in self.graph.edges() if self.edge_type[e] == 'ISL')

        if total_spare_edges == 0:
            print("No spare ISL edges found. Cannot analyze contiguity.")
            stats = {
                'timestamp': int(timestamp),
                'total_isl_edges': total_isl_edges,
                'total_spare_edges': 0,
                'num_spare_components': 0,
                'largest_component_edges': 0,
                'largest_component_fraction': 0.0,
                'fragmentation_ratio': 0.0, # Or perhaps NaN? Let's use 0 for simplicity
                'global_clustering_coefficient': 0.0 # Add clustering coeff
            }
        else:
            # Calculate global clustering coefficient (transitivity) for the spare network
            # Returns a tuple (coefficient, standard error) - we only need the coefficient
            # Handles empty or small graphs gracefully (returns 0.0)
            clust_coeff, _ = global_clustering(spare_view)

            # Find connected components in the spare subgraph
            # comp is a property map assigning component ID to each vertex in spare_view
            # hist is a histogram of component sizes (number of vertices per component)
            comp, vertex_hist = label_components(spare_view, directed=False)
            num_components_vertex_based = len(vertex_hist) # Total components including isolated vertices
            # Calculate the size (number of edges) of each component
            component_edges = {}
            component_vertices = {} # <<< THIS IS PRESENT >>>
            component_vertices = {}
            for e in spare_view.edges():
                # Find the component ID of one of the endpoints (doesn't matter which)
                # Need to map the edge endpoints (from spare_view) back to original graph vertices
                # then look up their component ID in the 'comp' map.
                # Note: comp map indices align with spare_view vertices.
                v_in_view = spare_view.vertex(e.source()) # Get vertex in the view
                comp_id = comp[v_in_view]
                component_edges[comp_id] = component_edges.get(comp_id, 0) + 1
                
                # Also count vertices per component if needed
                src_comp_id = comp[spare_view.vertex(e.source())]
                dst_comp_id = comp[spare_view.vertex(e.target())]
                component_vertices.setdefault(src_comp_id, set()).add(int(e.source()))
                component_vertices.setdefault(dst_comp_id, set()).add(int(e.target()))

            # Get edge counts ONLY for components that have edges
            edge_counts_with_edges = list(component_edges.values())
            num_components_with_edges = len(edge_counts_with_edges)
            num_zero_edge_components = num_components_vertex_based - num_components_with_edges

            # Create the distribution using only non-zero edge counts
            component_edge_distribution = sorted(edge_counts_with_edges, reverse=True)
            # Keep the old variable name for sorting if needed elsewhere, but distribution is the primary one
            component_edge_counts = component_edge_distribution[:] # Make a copy if needed
            component_edge_counts.sort(reverse=True) # Sort sizes descending

            largest_component_edges = component_edge_distribution[0] if component_edge_distribution else 0
            largest_component_fraction = largest_component_edges / total_spare_edges if total_spare_edges > 0 else 0.0
            # Fragmentation: number of components per spare edge (higher means more fragmented)
            fragmentation_ratio = num_components_with_edges / total_spare_edges if total_spare_edges > 0 else 0.0

            print(f"Total ISL Edges: {total_isl_edges}")
            print(f"Total Spare ISL Edges: {total_spare_edges}")
            print(f"Number of Spare Components (Vertex-based): {num_components_vertex_based}")
            print(f"Number of Components with Edges: {num_components_with_edges}")
            print(f"Number of Components with Zero Edges (Isolated Vertices): {num_zero_edge_components}")
            # Report distribution instead of just largest
            print(f"Spare Component Size Distribution (Edges > 0): {component_edge_distribution}") # Updated print
            # Keep largest for reference if desired, or remove
            # print(f"Largest Spare Component Size (Edges): {largest_component_edges} ({largest_component_fraction*100:.1f}%)")
            print(f"Fragmentation Ratio (Components/Spare Edge): {fragmentation_ratio:.4f}")
            print(f"Global Clustering Coefficient (Transitivity): {clust_coeff:.4f}") # Print clustering coeff

            stats = {
                'timestamp': int(timestamp),
                'total_isl_edges': total_isl_edges,
                'total_spare_edges': total_spare_edges,
                'num_spare_components': num_components_with_edges, # Store count of components WITH edges
                'component_edge_distribution': component_edge_distribution, # Store distribution of components WITH edges
                'largest_component_edges': largest_component_edges, # Keep largest for reference
                'largest_component_fraction': largest_component_fraction,
                'fragmentation_ratio': fragmentation_ratio,
                'global_clustering_coefficient': clust_coeff
            }

        # Save statistics to JSON file
        coverage_dir = output_dir / "coverage_data"
        coverage_dir.mkdir(parents=True, exist_ok=True)
        contiguity_file = coverage_dir / f"spare_contiguity_{int(timestamp)}.json"
        try:
            with open(contiguity_file, 'w') as f_json:
                json.dump(stats, f_json, indent=4)
            print(f"Saved spare contiguity stats to {contiguity_file}")
        except Exception as e:
            print(f"Warning: Could not save contiguity stats to {contiguity_file}: {e}")

        print("--------------------------------------\n")
