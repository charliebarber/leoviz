from dataclasses import dataclass
from typing import Set, List, Tuple, Optional
from graph_tool import Vertex, Edge, Graph
from graph_tool.topology import shortest_path
import logging

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
    def __init__(self, network):
        self.network = network
        self.logger = logging.getLogger(__name__)

    def _create_edge_set(self, edges: List[Edge]) -> Set[Tuple[int, int]]:
        """Create a set of edges including both directions"""
        path_edges = set((int(e.source()), int(e.target())) for e in edges)
        path_edges.update((int(e.target()), int(e.source())) for e in edges)
        return path_edges

    def _is_valid_satellite_path(self, vertex_list: List[Vertex], exclude_last: bool = True) -> bool:
        """Check if path only contains satellite nodes"""
        check_vertices = vertex_list[:-1] if exclude_last else vertex_list
        return all(self.network.vertex_type[v] != 'ground_station' for v in check_vertices)

    def _get_path_to_target(self, current_node: Vertex, target: Vertex, 
                           visited_edges: Set[Tuple[int, int]], 
                           excluded_edges: Set[Tuple[int, int]]) -> Optional[Tuple[List[Vertex], List[Edge]]]:
        """Attempt to find a path to the target"""
        try:
            # Changed to use delay for weights instead of distance
            vlist, elist = shortest_path(self.network.graph, current_node, target, 
                                       weights=self.network.delay)
            
            if not self._is_valid_satellite_path(vlist):
                return None
                
            path_edges = self._create_edge_set(elist)
            if path_edges & (excluded_edges | visited_edges):
                return None
                
            return vlist, elist
        except ValueError:
            return None

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

    def _get_path_candidates(self, current_node: Vertex, spare_endpoints: Set[int],
                           visited_edges: Set[Tuple[int, int]], 
                           excluded_edges: Set[Tuple[int, int]]) -> List[PathCandidate]:
        """Find and sort valid path candidates to spare endpoints"""
        candidates = []
        
        for endpoint in spare_endpoints:
            if endpoint == int(current_node):
                continue

            try:
                vlist, elist = shortest_path(self.network.graph, current_node,
                                           self.network.graph.vertex(endpoint),
                                           weights=self.network.delay)  # Changed to delay
                
                if not self._is_valid_satellite_path(vlist):
                    continue

                path_edges = self._create_edge_set(elist)
                if path_edges & (excluded_edges | visited_edges):
                    continue

                path_delay = sum(self.network.delay[e] for e in elist)
                path_dist = sum(self.network.distance[e] for e in elist)
                candidates.append(PathCandidate(endpoint, path_delay, path_dist, vlist, elist, path_edges))

            except ValueError:
                continue

        return sorted(candidates, key=lambda x: x.delay)  # Sort by delay instead of distance


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

            # Get shortest path based on delay
            vlist, elist = shortest_path(self.network.graph, source_v, target_v, 
                                       weights=self.network.delay)
            shortest_path_list = [str(self.network.index_map[v]) for v in vlist]
            shortest_delay = sum(self.network.delay[e] for e in elist)
            shortest_dist = sum(self.network.distance[e] for e in elist)
            target_delay = shortest_delay * target_weight_factor
            delay_ceiling = target_delay * 2.0 # Double the delay to allow more path options

            # Get edges to exclude (from shortest path)
            excluded_edges = self._create_edge_set(elist[1:-1])

            # Initialize search
            paths_found = []
            initial_path = [int(vlist[1])]  # Start with first satellite
            
            self._find_paths_recursive(
                current_node=vlist[1],
                target=target_v,
                path_so_far=initial_path,
                delay_so_far=0,
                dist_so_far=0,
                target_delay=target_delay,
                excluded_edges=excluded_edges,
                paths_found=paths_found,
                visited_edges=set(),
                max_depth=max_depth,
                delay_ceiling=delay_ceiling,
                max_candidates=max_candidates
            )

            return shortest_path_list, self._get_best_path(paths_found, target_delay, source, shortest_delay, shortest_dist)
        except ValueError:
            print(f"No path found between {source} and {target}")
            return [], []

    def _find_paths_recursive(self, current_node: Vertex, target: Vertex,
                            path_so_far: List[int], delay_so_far: float,
                            dist_so_far: float, target_delay: float, 
                            excluded_edges: Set[Tuple[int, int]],
                            paths_found: List[Tuple[List[int], float, float]],  # Added distance
                            visited_edges: Set[Tuple[int, int]],
                            max_depth: int, delay_ceiling: float,
                            current_depth: int = 0,
                            max_candidates: int = 5):
        """Recursive path finding implementation"""
        if current_depth >= max_depth or delay_so_far > delay_ceiling:
            return

        # Try routing to destination if we've hit some spare segments
        if current_depth > 0:
            path_result = self._get_path_to_target(current_node, target, 
                                                 visited_edges, excluded_edges)
            if path_result:
                vlist, elist = path_result
                total_delay = delay_so_far + sum(self.network.delay[e] for e in elist)
                total_dist = dist_so_far + sum(self.network.distance[e] for e in elist)
                if total_delay >= target_delay:
                    complete_path = path_so_far + [int(v) for v in vlist[1:]]
                    paths_found.append((complete_path, total_delay, total_dist))

        # Find and process candidates
        spare_endpoints = self._find_spare_endpoints()
        candidates = self._get_path_candidates(current_node, spare_endpoints, 
                                            visited_edges, excluded_edges)

        # Explore candidates
        for candidate in candidates[:max_candidates]:
            if candidate.endpoint in path_so_far:
                continue

            new_path = path_so_far + [int(v) for v in candidate.vertex_list[1:]]
            new_delay = delay_so_far + candidate.delay
            new_dist = dist_so_far + candidate.distance

            if new_delay > delay_ceiling:
                continue

            new_visited = visited_edges | candidate.path_edges

            self._find_paths_recursive(
                current_node=self.network.graph.vertex(candidate.endpoint),
                target=target,
                path_so_far=new_path,
                delay_so_far=new_delay,
                dist_so_far=new_dist,
                target_delay=target_delay,
                excluded_edges=excluded_edges,
                paths_found=paths_found,
                visited_edges=new_visited,
                max_depth=max_depth,
                delay_ceiling=delay_ceiling,
                current_depth=current_depth + 1,
                max_candidates=max_candidates
            )

    def _get_best_path(self, paths_found: List[Tuple[List[int], float, float]], 
                           target_delay: float, source: str, 
                           shortest_delay: float, shortest_dist: float) -> List[str]:
        """Get the best path from the found paths and log path statistics"""
        if not paths_found:
            return []

        paths_found.sort(key=lambda x: abs(x[1] - target_delay))
        best_path_data, best_delay, best_dist = paths_found[0]
        reverse_map = {v: k for k, v in self.network.vertex_map.items()}
        
        # Count edge types in the path
        spare_edges, normal_edges = self._count_edge_types(best_path_data)
        total_edges = spare_edges + normal_edges
        
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
        
        if len(paths_found) > 1:
            print("\nAlternative path statistics:")
            for path_data, delay, dist in paths_found[1:4]:  # Show up to 3 alternatives
                spare_count, normal_count = self._count_edge_types(path_data)
                total = spare_count + normal_count
                print(f"Delay: {delay:.6f}s (+{((delay/shortest_delay) - 1) * 100:.1f}%), "
                      f"Distance: {dist:.2f}m (+{((dist/shortest_dist) - 1) * 100:.1f}%), "
                      f"Spare edges: {spare_count}/{total} ({(spare_count/total)*100:.1f}%)")
            
        return best_path