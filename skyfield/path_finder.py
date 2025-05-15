from dataclasses import dataclass
from typing import Set, List, Tuple, Optional, Dict
from dataclasses import dataclass
from typing import Set, List, Tuple, Optional, Dict
from graph_tool import Vertex, Edge, Graph, GraphView
from graph_tool.topology import shortest_path, shortest_distance
from scipy.spatial import KDTree # Import KDTree
import numpy as np
import logging
import os
import time
import csv # Import csv for compact stats
from math import radians, cos, sin
from pathlib import Path # Import Path

@dataclass
class PathCandidate:
    """Represents a candidate path segment to explore"""
    endpoint: int
    delay: float  # Changed from distance to delay
    distance: float  # Added to track distance
    vertex_list: List[Vertex]
    edge_list: List[Edge]
    path_edges: Set[Tuple[int, int]]

class PathFinder:
    """Handles path finding logic separate from the main SatelliteNetwork class"""
    def __init__(self, network, output_dir):
        self.network = network
        self.logger = logging.getLogger(__name__)

        self.output_dir = output_dir

        self.spare_edges = None
        self.distances_to_target = None
        self.excluded_edges = None
        self.target_delay = None
        self.delay_ceiling = None
        self.paths_found = None
        self.target_vertex = None
        self.spare_endpoint_kdtree = None
        self.spare_endpoint_indices = None
        self.spare_endpoint_edges = None

    def _get_ecef_coords(self, vertex: Vertex) -> Optional[np.ndarray]:
        """Convert lat/lon/alt of a vertex to ECEF coordinates."""
        R_EARTH = 6371000.0 # Approx mean radius in meters
        try:
            lat = radians(self.network.latitude[vertex])
            lon = radians(self.network.longitude[vertex])
            # Ensure height is accessed correctly and converted to meters
            alt = self.network.height[vertex] * 1000.0 # height is stored in km

            x = (R_EARTH + alt) * cos(lat) * cos(lon)
            y = (R_EARTH + alt) * cos(lat) * sin(lon)
            z = (R_EARTH + alt) * sin(lat)
            return np.array([x, y, z])
        except Exception as e:
            self.logger.error(f"Error getting ECEF coords for vertex {int(vertex)}: {e}")
            return None

    def _create_edge_set(self, edges: List[Edge]) -> Set[Tuple[int, int]]:
        """Create a set of edges including both directions"""
        path_edges = set((int(e.source()), int(e.target())) for e in edges)
        path_edges.update((int(e.target()), int(e.source())) for e in edges)
        return path_edges

    def _is_valid_satellite_path(self, vertex_list: List[Vertex], exclude_last: bool = True) -> bool:
        """Check if path only contains satellite nodes"""
        check_vertices = vertex_list[:-1] if exclude_last else vertex_list
        return all(self.network.vertex_type[v] != 'ground_station' for v in check_vertices)

    def _find_spare_endpoints(self) -> Set[int]:
        """Find all satellite nodes that are endpoints of spare edges"""
        spare_endpoints = set()
        for e in self.network.graph.edges():
            if self.network.is_spare[e]:
                src = self.network.graph.vertex(int(e.source()))
                dst = self.network.graph.vertex(int(e.target()))
                if (self.network.vertex_type[src] != 'ground_station' and 
                    self.network.vertex_type[dst] != 'ground_station'):
                    spare_endpoints.add(int(e.source()))
                    spare_endpoints.add(int(e.target()))
        return spare_endpoints
    
    def _calculate_distances_to_target(self, target: Vertex) -> Dict[int, float]:
        """Pre-calculate shortest path delays from all nodes to target"""
        distances = {}
        for v in self.network.graph.vertices():
            try:
                _, elist = shortest_path(self.network.graph, v, target, 
                                    weights=self.network.delay)
                distances[int(v)] = sum(self.network.delay[e] for e in elist)
            except ValueError:
                distances[int(v)] = float('inf')
        return distances

    def _find_nearest_spare_edges(self, current_node: Vertex, max_candidates: int = 20) -> List[Tuple[Edge, Vertex, Vertex]]:
        """Find the nearest spare edges using KD-Tree for initial filtering.

        Args:
            current_node: The current node to find nearest spare edges for.
            max_candidates: Maximum number of final candidates to return, sorted by delay.

        Returns:
            List of (edge, src, dst) tuples for the nearest spare edges, sorted by delay.
        """
        current_node_id = int(current_node)
        edge_distances = [] # Stores (delay, edge, src, dst)
        current_pos_ecef = self._get_ecef_coords(current_node)

        # Check if KD-Tree is available AND we could get ECEF for current node
        if self.spare_endpoint_kdtree is None or current_pos_ecef is None:
            # Fallback if KD-Tree wasn't built or current node position is invalid
            if self.spare_endpoint_kdtree is None:
                 self.logger.warning("KD-Tree not built, falling back to slower nearest edge search.")
            if current_pos_ecef is None:
                 self.logger.warning(f"Could not get ECEF coordinates for current node {current_node_id}, falling back.")

            # --- Fallback Method ---
            for edge, src, dst in self.spare_edges:
                src_id = int(src)
                dst_id = int(dst)
                if current_node_id in (src_id, dst_id):
                    edge_distances.append((0, edge, src, dst))
                    continue
                try:
                    self.network.graph.clear_filters()
                    dist_map = shortest_distance(self.network.graph, source=current_node, weights=self.network.delay)
                    delay = min(dist_map[src], dist_map[dst])
                    if delay != float('inf'):
                        edge_distances.append((delay, edge, src, dst))
                except ValueError:
                    continue
            edge_distances.sort(key=lambda x: x[0])
            nearest_edges = [(edge, src, dst) for _, edge, src, dst in edge_distances[:max_candidates]]
            # --- End Fallback ---

        else:
            # --- KD-Tree Method ---
            # Use ECEF coordinates calculated earlier
            k_neighbors = min(len(self.spare_endpoint_indices), max(max_candidates * 5, 50)) # Query more neighbors initially

            try:
                # Query KD-Tree using ECEF coordinates
                distances, indices = self.spare_endpoint_kdtree.query(current_pos_ecef, k=k_neighbors)
            except ValueError as e:
                 self.logger.error(f"KD-Tree query failed for node {current_node_id} with ECEF {current_pos_ecef}: {e}. Falling back.")
                 # --- Fallback (similar to above, simplified) ---
                 for edge, src, dst in self.spare_edges:
                     try:
                         self.network.graph.clear_filters()
                         dist_map = shortest_distance(self.network.graph, source=current_node, weights=self.network.delay)
                         delay = min(dist_map[src], dist_map[dst])
                         if delay != float('inf'):
                             edge_distances.append((delay, edge, src, dst))
                     except ValueError: continue
                 edge_distances.sort(key=lambda x: x[0])
                 nearest_edges = [(edge, src, dst) for _, edge, src, dst in edge_distances[:max_candidates]]
                 # Reapply filter if needed and return
                 if hasattr(self, 'edge_filter'): self.network.graph.set_edge_filter(self.edge_filter)
                 return nearest_edges


            # Get the unique set of candidate spare edges connected to these neighbors
            candidate_edges = set()
            neighbor_indices = set() # Keep track of neighbors we've processed

            # Handle cases where query returns single value or array
            if isinstance(indices, (int, np.integer)): # Single neighbor found
                 indices = [indices]
            elif indices is None: # Should not happen, but safeguard
                 indices = []

            for idx in indices:
                 # indices from KDTree correspond to the order in self.spare_endpoint_indices
                 if idx < len(self.spare_endpoint_indices):
                     endpoint_vertex_index = self.spare_endpoint_indices[idx]
                     neighbor_indices.add(endpoint_vertex_index)
                     # Add edges connected to this endpoint
                     if endpoint_vertex_index in self.spare_endpoint_edges:
                         for edge_info in self.spare_endpoint_edges[endpoint_vertex_index]:
                             candidate_edges.add(edge_info) # edge_info is (edge, src_v, dst_v)

            # Calculate actual graph delay for these candidate edges
            # self.logger.debug(f"KD-Tree found {len(neighbor_indices)} neighbors, evaluating {len(candidate_edges)} candidate edges.")
            for edge, src, dst in candidate_edges:
                src_id = int(src)
                dst_id = int(dst)

                # Skip if current node is one of the endpoints
                if current_node_id in (src_id, dst_id):
                    edge_distances.append((0, edge, src, dst))
                    continue

                # Calculate shortest distance (delay) from current_node to src OR dst
                try:
                    # Use unfiltered graph for distance calculation
                    self.network.graph.clear_filters()
                    dist_map = shortest_distance(
                        self.network.graph,
                        source=current_node,
                        weights=self.network.delay
                    )
                    # Find the minimum delay to reach either endpoint of the spare edge
                    delay_to_src = dist_map[src]
                    delay_to_dst = dist_map[dst]
                    min_delay_to_edge = min(delay_to_src, delay_to_dst)

                    if min_delay_to_edge != float('inf'):
                        edge_distances.append((min_delay_to_edge, edge, src, dst))

                except ValueError:
                    # Cannot reach either endpoint from current_node
                    continue

            # Sort the evaluated candidates by actual delay
            edge_distances.sort(key=lambda x: x[0])
            # Select the top max_candidates based on delay
            nearest_edges = [(edge, src, dst) for _, edge, src, dst in edge_distances[:max_candidates]]
            # --- End KD-Tree Method ---

        # Reapply our base filter (excluding shortest path ISLs) if it exists
        if hasattr(self, 'edge_filter') and self.edge_filter is not None:
            self.network.graph.set_edge_filter(self.edge_filter)
            
        return nearest_edges

    def _get_path_candidates(self, current_node: Vertex, 
                   visited_edges: Set[Tuple[int, int]], 
                   max_candidates: int) -> List[PathCandidate]:
        """Find path candidates to spare edges"""
        candidates = []
        current_node_id = int(current_node)

        nearest_spare_edges = self._find_nearest_spare_edges(current_node, max_candidates=20)
        
        for edge, src, dst in nearest_spare_edges:
            src_id = int(src)
            dst_id = int(dst)

            # Skip edges that would create a cycle
            edge_tuple = (src_id, dst_id)
            reverse_edge = (dst_id, src_id)
            if edge_tuple in visited_edges or reverse_edge in visited_edges:
                continue
                
            # Skip edges in the excluded set (from shortest path)
            if edge_tuple in self.excluded_edges or reverse_edge in self.excluded_edges:
                continue
            
            # Case 1: We're at src, route directly to dst through the spare edge
            if src_id == current_node_id:
                edge_delay = self.network.delay[edge]
                edge_dist = self.network.distance[edge]
                
                # Create path (just the edge)
                vlist = [current_node, dst]
                elist = [edge]
                path_edges = {edge_tuple, reverse_edge}
                
                candidates.append(PathCandidate(
                    endpoint=dst_id,
                    delay=edge_delay,
                    distance=edge_dist,
                    vertex_list=vlist,
                    edge_list=elist,
                    path_edges=path_edges
                ))
                
            # Case 2: We're at dst, route directly to src through the spare edge
            elif dst_id == current_node_id:
                edge_delay = self.network.delay[edge]
                edge_dist = self.network.distance[edge]
                
                # Create path (just the edge)
                vlist = [current_node, src]
                elist = [edge]
                path_edges = {edge_tuple, reverse_edge}
                
                candidates.append(PathCandidate(
                    endpoint=src_id,
                    delay=edge_delay,
                    distance=edge_dist,
                    vertex_list=vlist,
                    edge_list=elist,
                    path_edges=path_edges
                ))
                
            # Case 3: We need to route to either src or dst
            else:
                # --- Create a combined filter for this specific search ---
                # Start with the base filter (excludes shortest path ISLs)
                combined_filter_map = self.edge_filter.copy()
                # Also exclude edges already visited in this specific path candidate branch
                for edge_tuple in visited_edges:
                    try:
                        u, v = edge_tuple
                        # Check both directions as visited_edges might store only one
                        edge_obj_fwd = self.network.graph.edge(u, v)
                        edge_obj_rev = self.network.graph.edge(v, u)
                        if edge_obj_fwd is not None:
                            combined_filter_map[edge_obj_fwd] = False
                        if edge_obj_rev is not None:
                            combined_filter_map[edge_obj_rev] = False
                    except ValueError: # Should not happen if edge exists
                        pass

                # Create a temporary GraphView with the combined filter
                # No vertex filter needed here as _is_valid_satellite_path checks later
                temp_view = GraphView(self.network.graph, efilt=combined_filter_map)
                # --- End combined filter setup ---

                # Try routing to src first, then through the spare edge to dst
                try:
                    # Find path using the temporary filtered view
                    # Ensure the source vertex exists in the view before calling shortest_path
                    if temp_view.vertex(current_node) is None:
                         raise ValueError(f"Current node {current_node} not in temporary view.")
                    if temp_view.vertex(src) is None:
                         raise ValueError(f"Source spare endpoint {src} not in temporary view.")

                    vlist_to_src, elist_to_src = shortest_path(
                        temp_view, # Use the filtered view
                        current_node,
                        src,
                        weights=temp_view.edge_properties['delay'] # Use view's weights
                    )

                    # Check path validity (using original graph properties)
                    if not self._is_valid_satellite_path([self.network.graph.vertex(v) for v in vlist_to_src]):
                        raise ValueError("Path contains non-satellite nodes")

                    # Create edge set for this path
                    src_path_edges = self._create_edge_set(elist_to_src)

                    # Calculate path metrics
                    src_path_delay = sum(self.network.delay[e] for e in elist_to_src)
                    src_path_dist = sum(self.network.distance[e] for e in elist_to_src)

                    # Add the spare edge to complete the path
                    total_delay = src_path_delay + self.network.delay[edge]
                    total_dist = src_path_dist + self.network.distance[edge]

                    # Build full path including both src and dst of the spare edge
                    full_vlist = list(vlist_to_src) + [dst]
                    full_elist = list(elist_to_src) + [edge]
                    full_path_edges = src_path_edges | {edge_tuple, reverse_edge}

                    candidates.append(PathCandidate(
                        endpoint=dst_id,  # We end at dst of the spare edge
                        delay=total_delay,
                        distance=total_dist,
                        vertex_list=full_vlist,
                        edge_list=full_elist,
                        path_edges=full_path_edges
                    ))

                except ValueError:
                    # No path to src or path invalid
                    pass
                # No finally block needed to clear filters, as temp_view is local

                # Try routing to dst first, then through the spare edge to src
                # Use the same temporary view created earlier
                try:
                    # Find path using the temporary filtered view
                    # Ensure the source vertex exists in the view before calling shortest_path
                    if temp_view.vertex(current_node) is None:
                         raise ValueError(f"Current node {current_node} not in temporary view.")
                    if temp_view.vertex(dst) is None:
                         raise ValueError(f"Destination spare endpoint {dst} not in temporary view.")

                    vlist_to_dst, elist_to_dst = shortest_path(
                        temp_view, # Use the filtered view
                        current_node,
                        dst,
                        weights=temp_view.edge_properties['delay'] # Use view's weights
                    )

                    # Check path validity (using original graph properties)
                    if not self._is_valid_satellite_path([self.network.graph.vertex(v) for v in vlist_to_dst]):
                        raise ValueError("Path contains non-satellite nodes")

                    # Create edge set for this path
                    dst_path_edges = self._create_edge_set(elist_to_dst)

                    # Calculate path metrics
                    dst_path_delay = sum(self.network.delay[e] for e in elist_to_dst)
                    dst_path_dist = sum(self.network.distance[e] for e in elist_to_dst)

                    # Add the spare edge to complete the path
                    total_delay = dst_path_delay + self.network.delay[edge]
                    total_dist = dst_path_dist + self.network.distance[edge]

                    # Build full path including both dst and src of the spare edge
                    full_vlist = list(vlist_to_dst) + [src]
                    full_elist = list(elist_to_dst) + [edge]
                    full_path_edges = dst_path_edges | {edge_tuple, reverse_edge}

                    candidates.append(PathCandidate(
                        endpoint=src_id,  # We end at src of the spare edge
                        delay=total_delay,
                        distance=total_dist,
                        vertex_list=full_vlist,
                        edge_list=full_elist,
                        path_edges=full_path_edges
                    ))

                except ValueError:
                    # No path to dst or path invalid
                    pass
                # No finally block needed to clear filters, as temp_view is local

        # Sort candidates by distance to target
        # No need to clear filters here as we used a local GraphView
        return sorted(candidates, key=lambda x: self.distances_to_target[x.endpoint])[:max_candidates]

    def _count_edge_types(self, path: List[int]) -> Tuple[int, int]:
        """Count the number of spare and normal edges in a path"""
        spare_count = 0
        normal_count = 0
        
        for i in range(len(path) - 1):
            v1 = self.network.graph.vertex(path[i])
            v2 = self.network.graph.vertex(path[i + 1])
            
            # Find the edge between these vertices
            for e in v1.out_edges():
                if e.target() == v2:
                    if self.network.is_spare[e]:
                        spare_count += 1
                    else:
                        normal_count += 1
                    break
                    
        return spare_count, normal_count

    def _find_satellite_constrained_path(self, source_v: Vertex, target_v: Vertex, 
                               excluded_edges: Set[Tuple[int, int]] = None,
                               visited_edges: Set[Tuple[int, int]] = None) -> Optional[Tuple[List[Vertex], List[Edge]]]:
        """Find a path between nodes with satellite-only constraint in the middle segment.
        
        Args:
            source_v: Source vertex
            target_v: Target vertex
            excluded_edges: Set of edges to exclude from path
            visited_edges: Set of already visited edges to exclude from path
            
        Returns:
            Tuple of (vertex_list, edge_list) for the path, or None if no path found
        """
        if excluded_edges is None:
            excluded_edges = set()
        if visited_edges is None:
            visited_edges = set()
        
        # Handle special case: if source or target is a satellite
        is_source_satellite = self.network.vertex_type[source_v] == 'satellite'
        is_target_satellite = self.network.vertex_type[target_v] == 'satellite'
        
        # Step 1: Get all visible satellites from source (if source is a ground station)
        source_satellites = []
        source_edges = {}
        
        if not is_source_satellite:
            for e in source_v.all_edges():
                other_v = e.target() if e.source() == source_v else e.source()
                if (self.network.edge_type[e] == 'visibility' and 
                    self.network.vertex_type[other_v] == 'satellite'):
                    source_satellites.append(other_v)
                    source_edges[int(other_v)] = e
        else:
            # Source is already a satellite
            source_satellites = [source_v]
            source_edges = {int(source_v): None}
        
        # Step 2: Get all visible satellites from target (if target is a ground station)
        target_satellites = []
        target_edges = {}
        
        if not is_target_satellite:
            for e in target_v.all_edges():
                other_v = e.target() if e.source() == target_v else e.source()
                if (self.network.edge_type[e] == 'visibility' and 
                    self.network.vertex_type[other_v] == 'satellite'):
                    target_satellites.append(other_v)
                    target_edges[int(other_v)] = e
        else:
            # Target is already a satellite
            target_satellites = [target_v]
            target_edges = {int(target_v): None}
        
        # Check for direct path through a single satellite
        if not is_source_satellite and not is_target_satellite:
            for src_sat in source_satellites:
                for dst_sat in target_satellites:
                    # If source and target connect to the same satellite, this is a direct path
                    if int(src_sat) == int(dst_sat):
                        source_edge = source_edges[int(src_sat)]
                        target_edge = target_edges[int(dst_sat)]
                        total_delay = self.network.delay[source_edge] + self.network.delay[target_edge]
                        complete_vlist = [source_v, src_sat, target_v]
                        complete_elist = [source_edge, target_edge]
                        return complete_vlist, complete_elist
        
        # Step 3: For each pair of source-target satellites, find satellite-only path
        best_path = None
        best_delay = float('inf')
        best_src_sat = None
        best_dst_sat = None

        # --- Optimization: Precompute SSSP from source satellites ---
        # Create base satellite and ISL filters (incorporating excluded/visited)
        satellite_filter = self.network.graph.new_vertex_property("bool")
        isl_filter = self.network.graph.new_edge_property("bool")
        combined_excluded = (excluded_edges or set()) | (visited_edges or set())

        for v in self.network.graph.vertices():
            satellite_filter[v] = self.network.vertex_type[v] == 'satellite'
        for e in self.network.graph.edges():
            is_isl = self.network.edge_type[e] == 'ISL'
            e_tuple = (int(e.source()), int(e.target()))
            e_reverse = (int(e.target()), int(e.source()))
            is_excluded = e_tuple in combined_excluded or e_reverse in combined_excluded
            isl_filter[e] = is_isl and not is_excluded

        # Create GraphView for satellite-only paths
        sat_view = GraphView(self.network.graph, vfilt=satellite_filter, efilt=isl_filter)

        source_sat_delays = {} # Store delay maps from each source satellite
        for src_sat in source_satellites:
            # Ensure src_sat is actually in the view (it should be if it's a satellite)
            if satellite_filter[src_sat]:
                try:
                    # Calculate distances from this src_sat to all others in the filtered view
                    # Pass the original vertex object as source
                    # Use the delay property map from the sat_view
                    dist_map = shortest_distance(sat_view, source=src_sat, weights=sat_view.edge_properties['delay'])
                    source_sat_delays[int(src_sat)] = dist_map # Store the property map
                except ValueError as e_dist:
                    # Log specific error during shortest_distance calculation
                    src_sat_id_str = self.network.index_map.get(int(src_sat), f"Unknown_Index_{int(src_sat)}")
                    self.logger.error(f"ValueError during shortest_distance from {src_sat_id_str} in sat_view: {e_dist}", exc_info=True)
                    source_sat_delays[int(src_sat)] = None # Mark as failed
                except Exception as e_generic:
                    # Catch other potential errors
                    src_sat_id_str = self.network.index_map.get(int(src_sat), f"Unknown_Index_{int(src_sat)}")
                    self.logger.error(f"Unexpected error during shortest_distance from {src_sat_id_str} in sat_view: {e_generic}", exc_info=True)
                    source_sat_delays[int(src_sat)] = None # Mark as failed
            else:
                 source_sat_delays[int(src_sat)] = None # Source satellite itself is filtered out?

        # --- Find best pair using precomputed delays ---
        for dst_sat in target_satellites:
            # Ensure dst_sat is in the view
            if not satellite_filter[dst_sat]:
                continue

            dst_sat_id = int(dst_sat)
            target_edge = target_edges.get(dst_sat_id) # Get target GSL edge
            target_gsl_delay = self.network.delay[target_edge] if target_edge else 0.0

            for src_sat in source_satellites:
                src_sat_id = int(src_sat)
                source_edge = source_edges.get(src_sat_id) # Get source GSL edge
                source_gsl_delay = self.network.delay[source_edge] if source_edge else 0.0

                dist_map = source_sat_delays.get(src_sat_id)
                if dist_map is not None:
                    # Look up precomputed delay from src_sat to dst_sat
                    # Need the vertex object 'dst_sat' for the lookup in the dist_map
                    # The dist_map is indexed by vertices *from the view*
                    # We need to find the view vertex corresponding to the original dst_sat
                    # Note: shortest_distance returns a map keyed by original graph vertices if source is original
                    sat_path_delay = dist_map[dst_sat]

                    if sat_path_delay != float('inf'):
                        total_delay = source_gsl_delay + sat_path_delay + target_gsl_delay

                        if total_delay < best_delay:
                            best_delay = total_delay
                            best_src_sat = src_sat
                            best_dst_sat = dst_sat

        # --- Reconstruct the best path found ---
        if best_src_sat is not None and best_dst_sat is not None:
            # Use the sat_view created earlier which has the correct filters
            try:
                # Find the single shortest path for the best pair using the view
                # Pass original vertices as source/target
                sat_vlist_indices, sat_elist_edges = shortest_path(
                    sat_view, # Use the filtered view
                    best_src_sat,
                    best_dst_sat,
                    weights=sat_view.edge_properties['delay'] # Use view's weights property map
                )

                # sat_vlist_indices contains indices relative to the original graph
                # sat_elist_edges contains Edge objects from the original graph (via the view)
                sat_vlist = [self.network.graph.vertex(idx) for idx in sat_vlist_indices]
                sat_elist = sat_elist_edges # Already Edge objects

                # Construct the full path including GSLs if necessary
                complete_vlist = list(sat_vlist)
                complete_elist = list(sat_elist)

                if not is_source_satellite:
                    source_edge = source_edges[int(best_src_sat)] # GSL edge lookup is correct
                    complete_vlist.insert(0, source_v)
                    complete_elist.insert(0, source_edge)

                if not is_target_satellite:
                    target_edge = target_edges[int(best_dst_sat)]
                    complete_vlist.append(target_v)
                    complete_elist.append(target_edge)

                best_path = (complete_vlist, complete_elist)

            except ValueError as e_path: # Capture the exception object here
                 # Handle specific ValueError during shortest_path reconstruction
                 best_src_id_str = self.network.index_map.get(int(best_src_sat), f"Unknown_{int(best_src_sat)}")
                 best_dst_id_str = self.network.index_map.get(int(best_dst_sat), f"Unknown_{int(best_dst_sat)}")
                 self.logger.error(f"ValueError during shortest_path reconstruction between {best_src_id_str} and {best_dst_id_str} in sat_view: {e_path}", exc_info=True)
                 best_path = None
            except Exception as e_generic_path:
                 # Catch other potential errors during reconstruction
                 best_src_id_str = self.network.index_map.get(int(best_src_sat), f"Unknown_{int(best_src_sat)}")
                 best_dst_id_str = self.network.index_map.get(int(best_dst_sat), f"Unknown_{int(best_dst_sat)}")
                 self.logger.error(f"Unexpected error during shortest_path reconstruction between {best_src_id_str} and {best_dst_id_str} in sat_view: {e_generic_path}", exc_info=True)
                 best_path = None
            # No finally block needed to clear filters as we used the view
        else:
             # No path found between any pair (best_src_sat or best_dst_sat is None)
             best_path = None

        return best_path

    def _find_shortest_path(self, source_v: Vertex, target_v: Vertex) -> Tuple[List[Vertex], List[Edge]]:
        """Find shortest path with constraint that GSLs can only be used at start and end"""
        path_result = self._find_satellite_constrained_path(source_v, target_v)
        
        if path_result:
            return path_result
        else:
            raise ValueError(f"No valid constrained path found between {source_v} and {target_v}")

    def _get_path_to_target(self, current_node: Vertex, target: Vertex,
                        visited_edges: Set[Tuple[int, int]],
                        excluded_edges: Set[Tuple[int, int]]) -> Optional[Tuple[List[Vertex], List[Edge]]]:
        """Attempt to find a path to the target with satellite-only constraint, reusing base filters."""
        # Note: _find_satellite_constrained_path now handles combining excluded_edges and visited_edges
        # We don't need to create a temporary filter here anymore.
        # It will use the combined set when creating its internal GraphView or filters.
        try:
            path_result = self._find_satellite_constrained_path(
                current_node, target, excluded_edges, visited_edges)
            return path_result
        except Exception as e:
            # Log the error more informatively if possible
            self.logger.error(f"Error finding path from {self.network.index_map.get(int(current_node), 'Unknown')} "
                              f"to target {self.network.index_map.get(int(target), 'Unknown')}: {e}", exc_info=True)
            return None
        # No finally block needed as _find_satellite_constrained_path cleans up its own filters.

    def _find_spare_edges(self) -> List[Tuple[Edge, Vertex, Vertex]]:
        """Find all spare edges in the network (satellite-to-satellite only)"""
        spare_edges = []
        for e in self.network.graph.edges():
            if self.network.is_spare[e]:
                src = self.network.graph.vertex(int(e.source()))
                dst = self.network.graph.vertex(int(e.target()))
                if (self.network.vertex_type[src] != 'ground_station' and 
                    self.network.vertex_type[dst] != 'ground_station'):
                    spare_edges.append((e, src, dst))
        return spare_edges

    def find_paths_via_spare_edges(self, source: str, target: str, 
                             target_weight_factor: float = 1.25,
                             max_depth: int = 3,
                             max_candidates: int = 5) -> Dict:
        """
        Main entry point for finding paths via spare edges.
        Handles both Ground Station and Satellite endpoints.

        Returns:
            Dict: Containing path finding results:
                  'source': source_id,
                  'target': target_id,
                  'shortest_path_delay': float,
                  'shortest_path_dist': float,
                  'shortest_path_nodes': List[str],
                  'target_delay': float,
                  'spare_path_found': bool,
                  'spare_path_delay': Optional[float],
                  'spare_path_dist': Optional[float],
                  'spare_path_nodes': Optional[List[str]],
                  'spare_edges_count': Optional[int],
                  'normal_edges_count': Optional[int],
                  'duration_s': Optional[float] # Add duration field
        """
        start_route_time = time.perf_counter() # Start timer

        print(f"\nFinding path from {source} to {target}")
        print(f"Target weight factor: {target_weight_factor}")

        results = {
            'source': source,
            'target': target,
            'shortest_path_delay': None,
            'shortest_path_dist': None,
            'shortest_path_nodes': None,
            'target_delay': None,
            'spare_path_found': False,
            'spare_path_delay': None,
            'spare_path_dist': None,
            'spare_path_nodes': None,
            'spare_edges_count': None,
            'normal_edges_count': None,
            'duration_s': None # Initialize duration
        }

        try:
            # Check if source/target exist in the map
            if source not in self.network.vertex_map:
                 raise ValueError(f"Source node '{source}' not found in network.")
            if target not in self.network.vertex_map:
                 raise ValueError(f"Target node '{target}' not found in network.")
                 
            source_v = self.network.graph.vertex(self.network.vertex_map[source])
            target_v = self.network.graph.vertex(self.network.vertex_map[target])
            self.target_vertex = target_v

            # Pre-calculate distances to target (stored as class member)
            self.distances_to_target = self._calculate_distances_to_target(target_v)

            # Pre-compute all spare edges once (stored as class member)
            self.spare_edges = self._find_spare_edges() # List of (Edge, Vertex, Vertex)
            print(f"Found {len(self.spare_edges)} spare edges in network")

            # --- Build KD-Tree for spare endpoints (if positions available) ---
            self.spare_endpoint_kdtree = None
            self.spare_endpoint_kdtree = None
            self.spare_endpoint_indices = []
            self.spare_endpoint_edges = {}
            # Check for necessary properties (lat, lon, height) instead of 'position'
            if (hasattr(self.network, 'latitude') and
                hasattr(self.network, 'longitude') and
                hasattr(self.network, 'height') and self.spare_edges):

                spare_endpoints_ecef = [] # Store ECEF coordinates
                endpoint_indices_for_kdtree = [] # Store corresponding vertex indices
                unique_endpoint_indices = set()
                temp_endpoint_edges = {} # Temp map: index -> list of (Edge, src_v, dst_v)

                for edge, src_v, dst_v in self.spare_edges:
                    src_idx = int(src_v)
                    dst_idx = int(dst_v)
                    edge_info = (edge, src_v, dst_v) # Store the full tuple

                    # Add endpoints to set for position lookup
                    unique_endpoint_indices.add(src_idx)
                    unique_endpoint_indices.add(dst_idx)

                    # Map index to edges
                    temp_endpoint_edges.setdefault(src_idx, []).append(edge_info)
                    temp_endpoint_edges.setdefault(dst_idx, []).append(edge_info)

                # Get ECEF coordinates for unique endpoints
                for idx in unique_endpoint_indices:
                    vertex = self.network.graph.vertex(idx)
                    ecef_coords = self._get_ecef_coords(vertex)
                    if ecef_coords is not None:
                        spare_endpoints_ecef.append(ecef_coords)
                        endpoint_indices_for_kdtree.append(idx) # Keep track of the index for this position
                    else:
                        self.logger.warning(f"Could not get ECEF for spare endpoint {idx}, skipping for KD-Tree.")

                # Build KD-Tree if we have valid coordinates
                if spare_endpoints_ecef:
                    try:
                        self.spare_endpoint_kdtree = KDTree(spare_endpoints_ecef)
                        self.spare_endpoint_indices = endpoint_indices_for_kdtree # Store indices in the same order as ECEF coords
                        self.spare_endpoint_edges = temp_endpoint_edges # Store the final map
                        print(f"Built KD-Tree for {len(self.spare_endpoint_indices)} unique spare endpoints.")
                    except Exception as kdtree_err:
                         print(f"Warning: Failed to build KD-Tree from ECEF coordinates: {kdtree_err}. Proceeding without KD-Tree optimization.")
                         self.spare_endpoint_kdtree = None # Ensure it's None on error
                else:
                    print("Warning: No valid ECEF coordinates found for spare endpoints. KD-Tree not built.")
            else:
                 print("Warning: Missing latitude/longitude/height properties or no spare edges. KD-Tree not built.")
                 self.spare_endpoint_kdtree = None # Ensure it's None on error <-- Corrected Indentation
            # --- End KD-Tree Build ---

            # Use constrained shortest path calculation
            try:
                vlist, elist = self._find_shortest_path(source_v, target_v)
                
                # Rest of processing remains the same
                shortest_path_nodes_list = [str(self.network.index_map[int(v)]) for v in vlist] # Use int()
                shortest_delay = sum(self.network.delay[e] for e in elist)
                shortest_dist = sum(self.network.distance[e] for e in elist)
                
                results['shortest_path_delay'] = shortest_delay
                results['shortest_path_dist'] = shortest_dist
                results['shortest_path_nodes'] = shortest_path_nodes_list
                
                self.target_delay = shortest_delay * target_weight_factor
                results['target_delay'] = self.target_delay
                self.delay_ceiling = self.target_delay * 2.0 # Keep delay ceiling calculation

                # Get ISL edges from the shortest path to exclude
                self.excluded_edges = set()
                for i, e in enumerate(elist):
                    # Check if the edge connects two satellites (is an ISL)
                    v_source = vlist[i]
                    v_target = vlist[i+1]
                    if (self.network.vertex_type[v_source] == 'satellite' and
                        self.network.vertex_type[v_target] == 'satellite'):
                        # Add both directions to the exclusion set using vertex indices from vlist
                        # This avoids potential issues with the edge descriptor 'e' itself
                        u_idx = int(v_source) # v_source is vlist[i]
                        v_idx = int(v_target) # v_target is vlist[i+1]
                        self.excluded_edges.add((u_idx, v_idx))
                        self.excluded_edges.add((v_idx, u_idx))
                print(f"Excluding {len(self.excluded_edges) // 2} ISL edges from the shortest path.")

                # Create a base edge filter property map - OPTIMIZATION
                # This map will be used and potentially copied/modified during the search
                self.edge_filter = self.network.graph.new_edge_property("bool")
                for e in self.network.graph.edges():
                    self.edge_filter[e] = True  # Default to allowing all edges
                    
                    # Exclude edges from the excluded set
                    e_tuple = (int(e.source()), int(e.target()))
                    e_reverse = (int(e.target()), int(e.source()))
                    if e_tuple in self.excluded_edges or e_reverse in self.excluded_edges:
                        self.edge_filter[e] = False
                
                # We'll apply this filter when needed in the path finding methods

                # Initialize search
                self.paths_found = []
                
                # Start with first satellite after source ground station
                initial_path = [int(vlist[1])]
                
                self._find_paths_recursive(
                    current_node=vlist[1],
                    path_so_far=initial_path,
                    delay_so_far=0,
                    dist_so_far=0,
                    visited_edges=set(),
                    max_depth=max_depth,
                    current_depth=0,
                    max_candidates=max_candidates
                )

                # Process found paths and update results dictionary
                self._update_results_with_best_path(
                    results, # Pass the results dict to be updated
                    self.paths_found,
                    self.target_delay,
                    source,
                    target,
                    shortest_path_nodes_list,
                    shortest_delay,
                    shortest_dist
                )
                
                # REMOVED: return results # Let execution continue to finally block

            except ValueError as e:
                # Log the error more specifically before returning partial results
                self.logger.error(f"ValueError in _find_shortest_path for {source}-{target}: {e}", exc_info=True)
                # REMOVED: return results # Let execution continue to finally block
            except Exception as e_outer:
                 # Catch any other unexpected error during the main pathfinding logic
                 self.logger.error(f"Unexpected error during pathfinding for {source}-{target} after shortest path calculation: {e_outer}", exc_info=True)
                 results['error'] = f"Unexpected error: {e_outer}"
                 # Duration calculation moved to the outer finally block
                 # REMOVED: return results # Let execution continue to finally block
            finally:
                # --- Calculate and store duration here ---
                end_route_time = time.perf_counter()
                results['duration_s'] = end_route_time - start_route_time
                # -----------------------------------------
                # Ensure we clean up the filter if it exists, regardless of errors above
                if hasattr(self, 'edge_filter'):
                    # Clear any applied filters
                    self.network.graph.clear_filters()
                    # Delete the filter attribute
                    delattr(self, 'edge_filter')
        except Exception as e:
            print(f"Error in find_paths_via_spare_edges for {source}-{target}: {str(e)}")
            results['error'] = str(e) # Store error in results
            # --- Calculate and store duration here too for early errors ---
            end_route_time = time.perf_counter()
            results['duration_s'] = end_route_time - start_route_time
            # -------------------------------------------------------------
            return results # Return potentially partial results

        # Duration calculation is now handled in the finally block above

        # --- Write compact stats AFTER duration is calculated ---
        stats_dir = f"{self.output_dir}/paths/path_{source}_{target}"
        self._write_compact_stats(results, stats_dir, target_weight_factor) # Pass the factor
        # ---

        return results # Return final results including duration

    def _write_compact_stats(self, results: Dict, stats_dir: str, factor: float):
        """Writes a compact CSV summary of the pathfinding results."""
        # Include factor in filename, replacing '.' with '_'
        factor_str = str(factor).replace('.', '_')
        compact_file = Path(stats_dir) / f"compact_stats_{factor_str}.csv"
        file_exists = compact_file.is_file()
        fieldnames = [
            'source', 'target', 'shortest_path_delay', 'shortest_path_dist',
            'target_delay', 'spare_path_found', 'spare_path_delay',
            'spare_path_dist', 'spare_edges_count', 'normal_edges_count',
            'duration_s', 'error'
        ]

        # Prepare data row, ensuring all keys exist with default None
        data_row = {field: results.get(field) for field in fieldnames}

        try:
            with open(compact_file, 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader() # Write header only if file is new
                writer.writerow(data_row)
        except Exception as e:
            self.logger.error(f"Failed to write compact stats to {compact_file}: {e}")


    def _find_paths_recursive(self, current_node: Vertex,
                            path_so_far: List[int], delay_so_far: float,
                            dist_so_far: float, visited_edges: Set[Tuple[int, int]],
                            max_depth: int, current_depth: int = 0,
                            max_candidates: int = 5):
        """Recursive path finding implementation"""
        if current_depth >= max_depth:
            # print(f"Stopping: reached max depth {max_depth}")
            return
        if delay_so_far > self.delay_ceiling:
            # print(f"Stopping: delay {delay_so_far} exceeds ceiling {self.delay_ceiling}")
            return

        # Try routing to destination if we've hit some spare segments
        if current_depth > 0:
            # print("Attempting to find path to target...")
            path_result = self._get_path_to_target(current_node, self.target_vertex, 
                                                visited_edges, self.excluded_edges)
            if path_result:
                # print("Found path to target")
                vlist, elist = path_result
                total_delay = delay_so_far + sum(self.network.delay[e] for e in elist)
                total_dist = dist_so_far + sum(self.network.distance[e] for e in elist)
                if total_delay < self.delay_ceiling:
                    complete_path = path_so_far + [int(v) for v in vlist[1:]]
                    self.paths_found.append((complete_path, total_delay, total_dist))
            # else:
                # print("No path to target found")

        # Find and process candidates
        spare_endpoints = self._find_spare_endpoints()
        candidates = self._get_path_candidates(current_node, 
                                            visited_edges, max_candidates)

        # Explore candidates
        for candidate in candidates[:max_candidates]:
            if candidate.endpoint in path_so_far:
                continue

            new_path = path_so_far + [int(v) for v in candidate.vertex_list[1:]]
            new_delay = delay_so_far + candidate.delay
            new_dist = dist_so_far + candidate.distance

            if new_delay > self.delay_ceiling:
                continue

            new_visited = visited_edges | candidate.path_edges

            self._find_paths_recursive(
                current_node=self.network.graph.vertex(candidate.endpoint),
                path_so_far=new_path,
                delay_so_far=new_delay,
                dist_so_far=new_dist,
                visited_edges=new_visited,
                max_depth=max_depth,
                current_depth=current_depth + 1,
                max_candidates=max_candidates
            )

    def _update_results_with_best_path(self, results: Dict,
                                    paths_found: List[Tuple[List[int], float, float]],
                                    target_delay: float, source: str, target: str,
                                    shortest_path_nodes_list: List[str],
                                    shortest_delay: float, shortest_dist: float):
        """Finds the best spare path, logs stats, and updates the results dictionary."""
        # Get the factor from the target_delay and shortest_delay
        factor = target_delay / shortest_delay if shortest_delay > 0 else 0.0
        if not paths_found:
             print("No alternative paths found using spare edges.") # Corrected indentation
             return # Results dict remains with spare_path_found=False # Corrected indentation

        # Filter out paths that are shorter than shortest_path (shouldn't happen often with delay ceiling)
        valid_paths = [(path, delay, dist) for path, delay, dist in paths_found

                       if delay > shortest_delay]

        if not valid_paths:
            print("All found spare paths were faster than the shortest path (unexpected).")
            return # Results dict remains with spare_path_found=False

        # Calculate metrics for each path
        path_metrics = []
        for path_data, delay, dist in valid_paths:
            # Calculate delay metric (how close to target_delay)
            delay_metric = abs(delay - target_delay) / target_delay
            
            # Calculate spare edge percentage
            spare_edges, normal_edges = self._count_edge_types(path_data)
            total_edges = spare_edges + normal_edges
            spare_percentage = spare_edges / total_edges if total_edges > 0 else 0
            
            # Combined score - lower is better
            # Weight factors can be adjusted to prioritize delay vs spare usage
            delay_weight = 1.0  # 60% weight on delay
            spare_weight = 0  # 40% weight on spare edge usage
            
            # Delay metric: lower is better, spare percentage: higher is better
            combined_score = (delay_weight * delay_metric) - (spare_weight * spare_percentage)
            
            path_metrics.append((path_data, delay, dist, spare_edges, normal_edges, combined_score))
        # Sort by combined score (lower is better)
        path_metrics.sort(key=lambda x: x[5])

        best_path_data, best_delay, best_dist, spare_edges, normal_edges, _ = path_metrics[0]
        total_edges = spare_edges + normal_edges

        # Get node names from reverse mapping
        reverse_map = {int(v): k for k, v in self.network.vertex_map.items()} # Use int(v)
        best_path_nodes_list = [reverse_map[v] for v in best_path_data]
        
        # Add source node if it's not already the first node (e.g., for Sat-Sat paths)
        if best_path_nodes_list[0] != source:
             best_path_nodes_list.insert(0, source)
             
        # Update results dictionary
        results['spare_path_found'] = True
        results['spare_path_delay'] = best_delay
        results['spare_path_dist'] = best_dist
        results['spare_path_nodes'] = best_path_nodes_list
        results['spare_edges_count'] = spare_edges
        results['normal_edges_count'] = normal_edges

        # Log path statistics (can be kept for debugging/info)
        print(f"\nPath Statistics for {source} -> {target}:")
        print(f"Shortest path delay: {shortest_delay:.6f} seconds")
        print(f"Shortest path distance: {shortest_dist:.2f} meters")
        print(f"Target delay: {target_delay:.6f} seconds")
        print(f"Best spare path delay: {best_delay:.6f} seconds")
        print(f"Best spare path distance: {best_dist:.2f} meters")
        print(f"Delay increase: {((best_delay/shortest_delay) - 1) * 100:.1f}%")
        print(f"Distance increase: {((best_dist/shortest_dist) - 1) * 100:.1f}%")
        
        print(f"\nEdge Type Statistics:")
        print(f"Total edges: {total_edges}")
        print(f"Spare edges: {spare_edges} ({(spare_edges/total_edges)*100:.1f}%)")
        print(f"Normal edges: {normal_edges} ({(normal_edges/total_edges)*100:.1f}%)")
        
        # Print alternative paths if available
        if len(path_metrics) > 1:
            print("\nAlternative path statistics:")
            for path_data, delay, dist, spare_count, normal_count, _ in path_metrics[1:4]:  # Show up to 3 alternatives
                total = spare_count + normal_count
                print(f"Delay: {delay:.6f}s (+{((delay/shortest_delay) - 1) * 100:.1f}%), "
                    f"Distance: {dist:.2f}m (+{((dist/shortest_dist) - 1) * 100:.1f}%), "
                    f"Spare edges: {spare_count}/{total} ({(spare_count/total)*100:.1f}%)")
            
        self.write_path_stats(
            source, target, 
            shortest_path_nodes_list, shortest_delay, shortest_dist, # Use correct variable name
            best_path_nodes_list, best_delay, best_dist, # Use correct variable name
            spare_edges, normal_edges,
            target_delay,
            path_metrics[1:4] if len(path_metrics) > 1 else None
        ) # Pass factor here


        # --- Compact stats writing moved to the end of find_paths_via_spare_edges ---

        # No return needed, results dict is updated directly

    def write_path_stats(self, src: str, dst: str,
                   shortest_path_nodes_list: List[str], shortest_delay: float, shortest_dist: float,
                   best_path_nodes_list: List[str], best_delay: float, best_dist: float,
                   spare_edges: int, normal_edges: int,
                   target_delay: float,
                   alternative_paths: List[Tuple] = None,
                   factor: float = 0.0): # Add factor parameter
        stats_dir = f"{self.output_dir}/paths/path_{src}_{dst}"
        os.makedirs(stats_dir, exist_ok=True)

        # Include factor in filename, replacing '.' with '_'
        factor_str = str(factor).replace('.', '_')
        
        # Write statistics to the file
        with open(f"{stats_dir}/stats_{factor_str}.txt", 'w') as f:
            f.write(f"Path Statistics: {src} to {dst}\n")
            f.write(f"=============================================\n\n")
            f.write(f"Shortest Path:\n")

            f.write(f"  Delay: {shortest_delay:.6f} seconds\n")
            f.write(f"  Distance: {shortest_dist:.2f} meters\n")
            f.write(f"  Nodes: {' → '.join(shortest_path_nodes_list)}\n\n")

            f.write(f"Target delay: {target_delay:.6f} seconds\n\n")

            if best_path_nodes_list: # Check if a spare path was found
                total_edges = spare_edges + normal_edges
                f.write(f"Best Spare Path:\n")
                f.write(f"  Delay: {best_delay:.6f} seconds\n")
                f.write(f"  Distance: {best_dist:.2f} meters\n")
                f.write(f"  Delay increase: {((best_delay/shortest_delay) - 1) * 100:.1f}%\n")
                f.write(f"  Distance increase: {((best_dist/shortest_dist) - 1) * 100:.1f}%\n")
                f.write(f"  Total edges: {total_edges}\n")
                f.write(f"  Spare edges: {spare_edges} ({(spare_edges/total_edges)*100:.1f}%)\n")
                f.write(f"  Normal edges: {normal_edges} ({(normal_edges/total_edges)*100:.1f}%)\n")
                f.write(f"  Nodes: {' → '.join(best_path_nodes_list)}\n\n")
            else:
                f.write(f"No valid spare path found\n\n")
            # Include alternative paths if provided
            if alternative_paths and len(alternative_paths) > 0:
                f.write(f"Alternative Paths:\n")
                for i, (_, delay, dist, spare_count, normal_count, _) in enumerate(alternative_paths[:3], 1):
                    total = spare_count + normal_count
                    f.write(f"  Path {i}:\n")
                    f.write(f"    Delay: {delay:.6f}s (+{((delay/shortest_delay) - 1) * 100:.1f}%)\n")
                    f.write(f"    Distance: {dist:.2f}m (+{((dist/shortest_dist) - 1) * 100:.1f}%)\n")
                    f.write(f"    Spare edges: {spare_count}/{total} ({(spare_count/total)*100:.1f}%)\n\n")
