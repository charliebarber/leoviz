from dataclasses import dataclass
from typing import Set, List, Tuple, Optional, Dict
from graph_tool import Vertex, Edge, Graph
from graph_tool.topology import shortest_path
import logging
import os

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
        """Find the nearest spare edges to the current node based on network distance.
        
        Args:
            current_node: The current node to find nearest spare edges for
            max_candidates: Maximum number of spare edges to return
            
        Returns:
            List of (edge, src, dst) tuples for the nearest spare edges
        """
        current_node_id = int(current_node)
        
        # Calculate distance from current node to all spare edge endpoints
        edge_distances = []
        
        for edge, src, dst in self.spare_edges:
            src_id = int(src)
            dst_id = int(dst)
            
            # Skip if current node is one of the endpoints (these will be handled separately)
            if current_node_id in (src_id, dst_id):
                edge_distances.append((0, edge, src, dst))
                continue
                
            # Try to find distance to source endpoint
            try:
                # Use unfiltered graph for distance calculation
                self.network.graph.clear_filters()
                
                _, elist_to_src = shortest_path(
                    self.network.graph,
                    current_node,
                    src,
                    weights=self.network.delay
                )
                src_distance = sum(self.network.delay[e] for e in elist_to_src)
                
                # Calculate direct distance (using position if available, otherwise topological)
                if hasattr(self.network, 'position'):
                    # Calculate Euclidean distance if positions are available
                    pos1 = self.network.position[current_node]
                    pos2 = self.network.position[src]
                    direct_distance = ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)**0.5
                else:
                    # Use topological distance as fallback
                    direct_distance = src_distance
                    
                edge_distances.append((direct_distance, edge, src, dst))
                
            except ValueError:
                # No path to src, try dst
                try:
                    _, elist_to_dst = shortest_path(
                        self.network.graph,
                        current_node,
                        dst,
                        weights=self.network.delay
                    )
                    dst_distance = sum(self.network.delay[e] for e in elist_to_dst)
                    
                    # Calculate direct distance
                    if hasattr(self.network, 'position'):
                        pos1 = self.network.position[current_node]
                        pos2 = self.network.position[dst]
                        direct_distance = ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2 + (pos1[2] - pos2[2])**2)**0.5
                    else:
                        direct_distance = dst_distance
                        
                    edge_distances.append((direct_distance, edge, src, dst))
                    
                except ValueError:
                    # No path to either endpoint
                    continue
        
        # Sort by distance and take the closest ones
        edge_distances.sort(key=lambda x: x[0])
        nearest_edges = [(edge, src, dst) for _, edge, src, dst in edge_distances[:max_candidates]]
        
        # Reapply our filter if needed
        if hasattr(self, 'edge_filter'):
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
                # Try routing to src first, then through the spare edge to dst
                try:
                    # Create a temporary filter that also excludes visited edges
                    temp_filter = self.edge_filter.copy()
                    
                    # Also exclude any visited edges
                    for e in self.network.graph.edges():
                        e_tuple = (int(e.source()), int(e.target()))
                        e_reverse = (int(e.target()), int(e.source()))
                        if e_tuple in visited_edges or e_reverse in visited_edges:
                            temp_filter[e] = False
                    
                    # Apply the filter
                    self.network.graph.set_edge_filter(temp_filter)
                    
                    try:
                        vlist_to_src, elist_to_src = shortest_path(
                            self.network.graph,
                            current_node,
                            src,
                            weights=self.network.delay
                        )
                        
                        # Check path validity
                        if not self._is_valid_satellite_path(vlist_to_src):
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
                    finally:
                        # Clear our temporary filter
                        self.network.graph.clear_filters()
                        
                except Exception as e:
                    print(f"Error finding path to src: {e}")
                    # Ensure filter is cleared in case of error
                    self.network.graph.clear_filters()
                    
                # Try routing to dst first, then through the spare edge to src
                try:
                    # Create a temporary filter that also excludes visited edges
                    temp_filter = self.edge_filter.copy()
                    
                    # Also exclude any visited edges
                    for e in self.network.graph.edges():
                        e_tuple = (int(e.source()), int(e.target()))
                        e_reverse = (int(e.target()), int(e.source()))
                        if e_tuple in visited_edges or e_reverse in visited_edges:
                            temp_filter[e] = False
                    
                    # Apply the filter
                    self.network.graph.set_edge_filter(temp_filter)
                    
                    try:
                        vlist_to_dst, elist_to_dst = shortest_path(
                            self.network.graph,
                            current_node,
                            dst,
                            weights=self.network.delay
                        )
                        
                        # Check path validity
                        if not self._is_valid_satellite_path(vlist_to_dst):
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
                    finally:
                        # Clear our temporary filter
                        self.network.graph.clear_filters()
                        
                except Exception as e:
                    print(f"Error finding path to dst: {e}")
                    # Ensure filter is cleared in case of error
                    self.network.graph.clear_filters()
        
        # Sort candidates by distance to target
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
        
        # DEBUG: Count filtered edges
        excluded_count = 0
        
        for src_sat in source_satellites:
            for dst_sat in target_satellites:
                # Skip if same satellite (already handled for ground stations)
                if int(src_sat) == int(dst_sat) and not is_source_satellite and not is_target_satellite:
                    continue
                    
                # Create a satellite-only filter
                satellite_filter = self.network.graph.new_vertex_property("bool")
                for v in self.network.graph.vertices():
                    satellite_filter[v] = self.network.vertex_type[v] == 'satellite'
                
                # Create an ISL-only filter
                isl_filter = self.network.graph.new_edge_property("bool")
                for e in self.network.graph.edges():
                    # Accept only ISL edges
                    isl_filter[e] = (self.network.edge_type[e] == 'ISL')
                    
                    # Also exclude any specified edges
                    if excluded_edges or visited_edges:
                        edge_tuple = (int(e.source()), int(e.target()))
                        reverse_tuple = (int(e.target()), int(e.source()))
                        
                        # DEBUG: Check if this edge would be excluded
                        was_excluded = False
                        
                        if ((edge_tuple in excluded_edges or reverse_tuple in excluded_edges) or
                            (edge_tuple in visited_edges or reverse_tuple in visited_edges)):
                            isl_filter[e] = False
                            was_excluded = True
                            excluded_count += 1
                
                
                # Set the filters on the graph
                self.network.graph.set_vertex_filter(satellite_filter)
                self.network.graph.set_edge_filter(isl_filter)
                
                try:
                    # Find path using the filtered graph
                    sat_vlist, sat_elist = shortest_path(
                        self.network.graph,
                        src_sat,
                        dst_sat,
                        weights=self.network.delay
                    )
                    
                    # DEBUG: Check if path contains any excluded edges
                    path_edges = set()
                    for i in range(len(sat_vlist) - 1):
                        u = int(sat_vlist[i])
                        v = int(sat_vlist[i + 1])
                        path_edges.add((u, v))
                        path_edges.add((v, u))
                    
                    overlap = path_edges.intersection(excluded_edges)
                    if overlap:
                        print(f"WARNING: Path contains {len(overlap)} excluded edges!")
                        print(f"First overlapping edge: {next(iter(overlap))}")
                    
                    # Calculate satellite path delay
                    sat_path_delay = sum(self.network.delay[e] for e in sat_elist)
                    
                    # Add source and target edges if needed
                    total_delay = sat_path_delay
                    complete_vlist = list(sat_vlist)
                    complete_elist = list(sat_elist)
                    
                    if not is_source_satellite:
                        source_edge = source_edges[int(src_sat)]
                        total_delay += self.network.delay[source_edge]
                        complete_vlist.insert(0, source_v)
                        complete_elist.insert(0, source_edge)
                    
                    if not is_target_satellite:
                        target_edge = target_edges[int(dst_sat)]
                        total_delay += self.network.delay[target_edge]
                        complete_vlist.append(target_v)
                        complete_elist.append(target_edge)
                    
                    if total_delay < best_delay:
                        best_path = (complete_vlist, complete_elist)
                        best_delay = total_delay
                        
                except ValueError:
                    # No path between these satellites
                    continue
                finally:
                    # Always clear the filters regardless of success/failure
                    self.network.graph.clear_filters()
        
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
        """Attempt to find a path to the target with satellite-only constraint"""
        try:
            # Create a temporary filter that combines our main filter with visited edges
            temp_filter = self.edge_filter.copy()
            
            # Also exclude any visited edges
            for e in self.network.graph.edges():
                e_tuple = (int(e.source()), int(e.target()))
                e_reverse = (int(e.target()), int(e.source()))
                if e_tuple in visited_edges or e_reverse in visited_edges:
                    temp_filter[e] = False
            
            # Apply the combined filter
            self.network.graph.set_edge_filter(temp_filter)
            
            # Find the path with the filter applied
            path_result = self._find_satellite_constrained_path(
                current_node, target, excluded_edges, visited_edges)
            
            return path_result
        
        except Exception as e:
            print(f"Error finding path to target: {e}")
            return None
        finally:
            # Always clear the temporary filter
            self.network.graph.clear_filters()

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
                             max_candidates: int = 5) -> Tuple[List[int], List[str]]:
        """Main entry point for finding paths via spare edges"""
        print(f"\nFinding path from GS {source} to GS {target}")
        print(f"Target weight factor: {target_weight_factor}")
        
        try:
            source_v = self.network.graph.vertex(self.network.vertex_map[source])
            target_v = self.network.graph.vertex(self.network.vertex_map[target])
            self.target_vertex = target_v

            # Pre-calculate distances to target (stored as class member)
            self.distances_to_target = self._calculate_distances_to_target(target_v)
            
            # Pre-compute all spare edges once (stored as class member)
            self.spare_edges = self._find_spare_edges()
            print(f"Found {len(self.spare_edges)} spare edges in network")

            # Use constrained shortest path calculation
            try:
                vlist, elist = self._find_shortest_path(source_v, target_v)
                
                # Rest of processing remains the same
                shortest_path_list = [str(self.network.index_map[v]) for v in vlist]
                shortest_delay = sum(self.network.delay[e] for e in elist)
                shortest_dist = sum(self.network.distance[e] for e in elist)
                self.target_delay = shortest_delay * target_weight_factor
                self.delay_ceiling = self.target_delay * 2.0

                # Get edges to exclude (from shortest path) - only middle edges as intended
                self.excluded_edges = self._create_edge_set(elist[1:-1])
                
                # Create a filtered graph view once - OPTIMIZATION
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

                return shortest_path_list, self._get_best_path(
                    self.paths_found, 
                    self.target_delay, 
                    source, 
                    target,
                    shortest_path_list,
                    shortest_delay, 
                    shortest_dist
                )
                
            except ValueError as e:
                print(f"Error finding constrained path: {str(e)}")
                return [], []
            finally:
                # Ensure we clean up the filter if it exists
                if hasattr(self, 'edge_filter'):
                    # Clear any applied filters
                    self.network.graph.clear_filters()
                    # Delete the filter attribute
                    delattr(self, 'edge_filter')
                
        except Exception as e:
            print(f"No path found between {source} and {target}: {str(e)}")
            return [], []

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

    def _get_best_path(self, paths_found: List[Tuple[List[int], float, float]], 
                    target_delay: float, source: str, target: str,
                    shortest_path_list: List[str],
                    shortest_delay: float, shortest_dist: float) -> List[str]:
        """Get the best path from the found paths and log path statistics"""
        if not paths_found:
            return []

        # Filter out paths that are shorter than shortest_path
        valid_paths = [(path, delay, dist) for path, delay, dist in paths_found 
                    if delay > shortest_delay]
        
        if not valid_paths:
            return []

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
            delay_weight = 0.6  # 60% weight on delay
            spare_weight = 0.4  # 40% weight on spare edge usage
            
            # Delay metric: lower is better, spare percentage: higher is better
            combined_score = (delay_weight * delay_metric) - (spare_weight * spare_percentage)
            
            path_metrics.append((path_data, delay, dist, spare_edges, normal_edges, combined_score))
        
        # Sort by combined score (lower is better)
        path_metrics.sort(key=lambda x: x[5])
        
        best_path_data, best_delay, best_dist, spare_edges, normal_edges, _ = path_metrics[0]
        total_edges = spare_edges + normal_edges
        
        # Get node names from reverse mapping
        reverse_map = {v: k for k, v in self.network.vertex_map.items()}
        best_path = [reverse_map[v] for v in best_path_data]
        best_path.insert(0, source)

        # Log path statistics
        print(f"\nPath Statistics:")
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
            shortest_path_list, shortest_delay, shortest_dist,
            best_path, best_delay, best_dist,
            spare_edges, normal_edges,
            target_delay,
            path_metrics[1:4] if len(path_metrics) > 1 else None  # Pass alternative paths
        )

        return best_path

    def write_path_stats(self, src: str, dst: str, 
                   shortest_path_list: List[str], shortest_delay: float, shortest_dist: float,
                   best_path: List[str], best_delay: float, best_dist: float,
                   spare_edges: int, normal_edges: int, 
                   target_delay: float,
                   alternative_paths: List[Tuple] = None):
        stats_dir = f"{self.output_dir}/paths/path_{src}_{dst}"
        os.makedirs(stats_dir, exist_ok=True)
        
        # Write statistics to the file
        with open(f"{stats_dir}/stats.txt", 'w') as f:
            f.write(f"Path Statistics: {src} to {dst}\n")
            f.write(f"=============================================\n\n")
            
            f.write(f"Shortest Path:\n")
            f.write(f"  Delay: {shortest_delay:.6f} seconds\n")
            f.write(f"  Distance: {shortest_dist:.2f} meters\n")
            f.write(f"  Nodes: {' → '.join(shortest_path_list)}\n\n")
            
            f.write(f"Target delay: {target_delay:.6f} seconds\n\n")
            
            if best_path:
                total_edges = spare_edges + normal_edges
                f.write(f"Best Spare Path:\n")
                f.write(f"  Delay: {best_delay:.6f} seconds\n")
                f.write(f"  Distance: {best_dist:.2f} meters\n")
                f.write(f"  Delay increase: {((best_delay/shortest_delay) - 1) * 100:.1f}%\n")
                f.write(f"  Distance increase: {((best_dist/shortest_dist) - 1) * 100:.1f}%\n")
                f.write(f"  Total edges: {total_edges}\n")
                f.write(f"  Spare edges: {spare_edges} ({(spare_edges/total_edges)*100:.1f}%)\n")
                f.write(f"  Normal edges: {normal_edges} ({(normal_edges/total_edges)*100:.1f}%)\n")
                f.write(f"  Nodes: {' → '.join(best_path)}\n\n")
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