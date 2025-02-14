from graph_tool import Graph
from graph_tool.topology import shortest_path
from typing import List, Dict
from math import radians, cos, sin, asin, sqrt, atan2, degrees
import pandas as pd
import numpy as np
from tqdm import tqdm

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
        self.distance = self.graph.new_edge_property("double")
        
        # Add property maps to graph
        self.graph.vertex_properties["type"] = self.vertex_type
        self.graph.vertex_properties["latitude"] = self.latitude
        self.graph.vertex_properties["longitude"] = self.longitude
        self.graph.vertex_properties["height_km"] = self.height
        self.graph.vertex_properties["name"] = self.name
        self.graph.vertex_properties["population"] = self.population
        
        self.graph.edge_properties["type"] = self.edge_type
        self.graph.edge_properties["distance"] = self.distance
        
        # Create vertex name to index mapping
        self.vertex_map = {}
        
        self._load_isls(isls_file)

    def _get_or_add_vertex(self, name: str) -> int:
        """Get vertex index, creating new vertex if needed."""
        if name not in self.vertex_map:
            v = self.graph.add_vertex()
            self.vertex_map[name] = int(v)
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

    def calculate_gs_edge_betweenness(self):
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
                for gs2 in ground_stations[i+1:]:
                    # Get original IDs for demand lookup
                    gs1_orig = reverse_map[int(gs1)]
                    gs2_orig = reverse_map[int(gs2)]
                    demand = demand_dict.get((gs1, gs2), 0)
                    
                    if demand > 0:
                        # Use graph-tool's optimized shortest path
                        vlist, elist = shortest_path(self.graph,
                                                self.graph.vertex(gs1),
                                                self.graph.vertex(gs2),
                                                weights=self.distance)
                        
                        if elist:  # If path exists
                            for e in elist:
                                edge_betweenness[e] += demand
                    pbar.update(1)
        
        # Convert to dictionary format if needed
        result = {}
        for e in self.graph.edges():
            if edge_betweenness[e] > 0:
                v1_orig = reverse_map[int(e.source())]
                v2_orig = reverse_map[int(e.target())]
                result[(v1_orig, v2_orig)] = edge_betweenness[e]
        
        return result

    def save_edge_betweenness(self, output_file: str):
        """Save edge betweenness results to file."""
        edge_betweenness = self.calculate_gs_edge_betweenness()
        
        with open(output_file, 'w') as f:
            for (v1, v2), value in sorted(edge_betweenness.items(), key=lambda x: x[1], reverse=True):
                if value > 0:
                    f.write(f"{v1} {v2} {value:.6f}\n")
    
    def save_gsls(self, output_file: str):
        with open(output_file, 'w') as f:
            for e in self.graph.edges():
                if self.edge_type[e] == 'visibility':
                    # Convert vertex indices to original IDs using the reverse mapping
                    reverse_map = {v: k for k, v in self.vertex_map.items()}
                    v1 = reverse_map[int(e.source())]
                    v2 = reverse_map[int(e.target())]
                    f.write(f"{v1} {v2}\n")