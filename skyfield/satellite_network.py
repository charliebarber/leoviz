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
        self.graph.edge_properties["betweenness"] = self.betweenness
        self.graph.edge_properties["is_spare"] = self.is_spare 
        
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

    def update_spare_edges(self, percentile: float = 25.0):
        betweenness_values = [self.betweenness[e] for e in self.graph.edges()]
        if not betweenness_values:
            return
            
        # Calculate the percentile threshold
        threshold = np.percentile(betweenness_values, percentile)
        
        # Update is_spare property for each edge
        for e in self.graph.edges():
            self.is_spare[e] = self.betweenness[e] <= threshold

    def find_paths_via_spare_edges(self, source: str, target: str, target_weight_factor: float = 1.25) -> list:
        """
        Find paths between ground stations via spare edges.
        
        Args:
            source (str): Source ground station ID
            target (str): Target ground station ID
            target_weight_factor (float): Target path length multiplier compared to shortest path
            
        Returns:
            list: List of paths found, where each path is a list of node IDs
        """
        if source not in self.vertex_map or target not in self.vertex_map:
            print("Source or target not found in graph")
            return []
            
        # Get vertex objects for source and target
        source_v = self.graph.vertex(self.vertex_map[source])
        target_v = self.graph.vertex(self.vertex_map[target])
        
        # Find shortest path for reference
        print(f"\nFinding path from GS {source} to GS {target}")
        print(f"Target weight factor: {target_weight_factor}")
        
        vlist, elist = shortest_path(self.graph, source_v, target_v, weights=self.distance)
        shortest_path_list = [self.graph.vertex_index[v] for v in vlist]
        shortest_dist = sum(self.distance[e] for e in elist)
        target_dist = shortest_dist * target_weight_factor
        
        print(f"\nShortest path distance: {shortest_dist:.2f}")
        print(f"Target distance: {target_dist:.2f}")
        print(f"Initial satellite hop: {self.vertex_map[source]} -> {int(vlist[1])}")
        
        # Get edges to exclude (from shortest path)
        excluded_edges = set((int(e.source()), int(e.target())) for e in elist[1:-1])
        # Create reverse edges in a new set first
        reverse_edges = set((v2, v1) for v1, v2 in excluded_edges)
        excluded_edges.update(reverse_edges)  # Now update with reverse edges
        
        print("\nExcluded edges from shortest path:")
        for e1, e2 in excluded_edges:
            print(f"  {e1} -> {e2}")
        
        # Initialize collections for recursive search
        paths_found = []
        initial_dist = self.distance[elist[0]]  # Distance to first satellite
        initial_path = [int(v) for v in vlist[:2]]  # Source and first satellite
        
        # Start recursive search
        self._find_paths_recursive(
            current_node=vlist[1],
            target=target_v,
            path_so_far=initial_path,
            dist_so_far=initial_dist,
            target_dist=target_dist,
            excluded_edges=excluded_edges,
            paths_found=paths_found,
            visited_edges=set(),
            max_depth=3,
            weight_ceiling=target_dist * 1.5
        )
        
        if paths_found:
            # Sort by how close the distance is to target_dist
            paths_found.sort(key=lambda x: abs(x[1] - target_dist))
            
            # Convert vertex indices back to original IDs
            reverse_map = {v: k for k, v in self.vertex_map.items()}
            converted_paths = []
            for path, dist in paths_found[:4]:  # Keep top 4 paths
                converted_path = [reverse_map[v] for v in path]
                converted_paths.append((converted_path, dist))
            
            # Print results
            print(f"\nFound {len(paths_found)} valid paths")
            best_path, best_dist = converted_paths[0]
            print(f"\nSelected best path:")
            print(f"Path distance: {best_dist:.2f} (target: {target_dist:.2f}, shortest: {shortest_dist:.2f})")
            print(f"Distance increase: {((best_dist/shortest_dist) - 1) * 100:.1f}%")
            
            if len(converted_paths) > 1:
                print("\nNext best alternatives:")
                for path, dist in converted_paths[1:]:
                    print(f"Distance: {dist:.2f}, Difference from target: {abs(dist - target_dist):.2f}")
            
            # return [path for path, _ in converted_paths]
            return shortest_path_list, best_path
            
        print("\nNo valid paths found")
        return []

    def _find_paths_recursive(self, current_node, target, path_so_far, dist_so_far, 
                        target_dist, excluded_edges, paths_found, visited_edges,
                        max_depth, weight_ceiling, current_depth=0):
        print_indent = "  " * current_depth
        print(f"\n{print_indent}At node {int(current_node)} (depth {current_depth})")
    
        if current_depth >= max_depth:
            print(f"{print_indent}Max depth reached, backtracking...")
            return
        if dist_so_far > weight_ceiling:
            print(f"{print_indent}Distance ceiling exceeded, backtracking...")
            return

        # Try routing to destination if we've already hit some spare segments
        if current_depth > 0:
            try:
                vlist, elist = shortest_path(self.graph, current_node, target, weights=self.distance)
                path_edges = set((int(e.source()), int(e.target())) for e in elist)
                if not (path_edges & excluded_edges):
                    exit_dist = sum(self.distance[e] for e in elist)
                    total_dist = dist_so_far + exit_dist
                    print(f"{print_indent}Found potential path to destination: {total_dist:.2f}")

                    if total_dist >= target_dist:
                        complete_path = path_so_far + [int(v) for v in vlist[1:]]
                        paths_found.append((complete_path, total_dist))
                        print(f"{print_indent}✓ Path accepted")
            except ValueError:
                pass
    
        # Find all nodes that are endpoints of spare edges
        spare_endpoints = set()
        for e in self.graph.edges():
            if self.is_spare[e]:
                spare_endpoints.add(int(e.source()))
                spare_endpoints.add(int(e.target()))

        # print(list(dict.fromkeys(spare_endpoints)))
    
        print(f"{print_indent}Found {len(spare_endpoints)} nodes involved in spare edges")
    
        # For each spare endpoint, try to find a path to it
        candidates = []
        for endpoint in spare_endpoints:
            if endpoint == int(current_node):
                continue

            try:
                vlist, elist = shortest_path(self.graph, current_node, 
                                           self.graph.vertex(endpoint), 
                                           weights=self.distance)

                # Check if path uses excluded edges
                path_edges = set((int(e.source()), int(e.target())) for e in elist)
                if not (path_edges & excluded_edges):
                    path_dist = sum(self.distance[e] for e in elist)
                    candidates.append((endpoint, path_dist, vlist, elist))

            except ValueError:
                continue
    
        # Sort by distance and try routing through closest candidates
        candidates.sort(key=lambda x: x[1])
        print(f"{print_indent}Found {len(candidates)} reachable spare endpoints")
    
        # Try a limited number of closest candidates
        for endpoint, path_dist, vlist, elist in candidates[:5]:
            print(f"{print_indent}Trying to route through spare endpoint {endpoint}")

            # Avoid revisiting endpoints
            if endpoint in [int(v) for v in path_so_far]:
                continue

            new_path = path_so_far + [int(v) for v in vlist[1:]]
            new_dist = dist_so_far + path_dist

            if new_dist > weight_ceiling:
                continue

            self._find_paths_recursive(
                current_node=self.graph.vertex(endpoint),
                target=target,
                path_so_far=new_path,
                dist_so_far=new_dist,
                target_dist=target_dist,
                excluded_edges=excluded_edges,
                paths_found=paths_found,
                visited_edges=visited_edges | {endpoint},
                max_depth=max_depth,
                weight_ceiling=weight_ceiling,
                current_depth=current_depth + 1
            )