# import cProfile, pstats, io # Remove cProfile imports
import datetime
from pathlib import Path
from datetime import timezone
import argparse
import pandas as pd # For saving results
from satellite_network import SatelliteNetwork
from tle_parser import TLEParser
from ground_stations import GroundStations
import os
from tqdm import tqdm
import logging # For logging configuration

def main():
    # Configure basic logging
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    # --- cProfile removed ---

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Process satellite positions and connections, optionally evaluate routing.')
    parser.add_argument('--timestamp', type=float, required=True,
                        help='Unix timestamp to process')
    parser.add_argument('--num-eval-pairs', type=int, default=1000,
                        help='Number of random satellite pairs to evaluate routing for (default: 1000)')
    parser.add_argument('--delay-factors', type=str, default='1.25,1.5,2.0',
                        help='Comma-separated list of delay factors for routing evaluation (default: 1.25,1.5,2.0,4.0)')
    args = parser.parse_args()

    # Parse delay factors
    try:
        delay_factors = [float(f.strip()) for f in args.delay_factors.split(',')]
    except ValueError:
        print("Error: Invalid format for --delay-factors. Use comma-separated numbers (e.g., 1.25,1.5).")
        exit(1)

    # File paths
    tle_file = "../constellations/starlink_550/tles.txt"
    isls_file = "../constellations/starlink_550/isls.txt"
    cities_file = "./cities.csv"
    base_output_dir = Path(f"../positions/starlink_550_traffic_scaled/{str(int(args.timestamp))}/")

    # Create output directory if it doesn't exist
    base_output_dir.mkdir(parents=True, exist_ok=True)

    # --- cProfile removed ---

    # Initialize all components
    network = SatelliteNetwork(isls_file)
    parser = TLEParser(tle_file)
    ground_stations = GroundStations(cities_file)

    try:
        # Create satellite objects
        satellites = parser.create_satellites()

        # Configuration
        max_gsl_length_m = 1089686.4181956202  # Maximum GSL length in meters
        min_elevation_angle = 25.0  # Minimum elevation angle in degrees

        timestamp = args.timestamp  # Using the passed timestamp

        # Get satellite positions for this timestamp
        sat_positions = parser.get_position_snapshot(timestamp)
        
        # Get ground station positions (static)
        gs_positions = ground_stations.get_station_positions()
        
        # Update network with all positions
        network.update_node_positions(sat_positions, node_type='satellite')
        network.update_node_positions(gs_positions, node_type='ground_station')
        
        # Update ISL distances and visibility edges
        # network.update_isl_distances() # not needed as update_link_delays also calculates
        network.update_visibility_edges(max_gsl_length_m, min_elevation_angle)

        # Calculate and update link delays
        network.update_link_delays()
        
        # --- Calculate and Print ISL Delay Stats ---
        isl_delay_stats = network.calculate_isl_delay_stats_by_distance()
        print("\n--- ISL Delay Statistics (Approximated by Distance) ---")
        print(f"Threshold: {isl_delay_stats['distance_threshold_km']} km")
        print(f"Short ISLs (< threshold): Count={isl_delay_stats['short_isl_count']}, Avg Delay={isl_delay_stats['avg_short_isl_delay_ms']:.3f} ms")
        print(f"Long ISLs (>= threshold): Count={isl_delay_stats['long_isl_count']}, Avg Delay={isl_delay_stats['avg_long_isl_delay_ms']:.3f} ms")
        print("-------------------------------------------------------\n")
        # ------------------------------------------

        # Save satellite positions to CSV
        # output_file = base_output_dir / f"{int(timestamp)}.csv"
        # parser.save_positions_to_csv(sat_positions, output_file)
        
        # Save GSLs to file
        # gsls_file = base_output_dir / f"gsls_{int(timestamp)}.txt"
        # network.save_gsls(str(gsls_file))
        
        # Calculate and save edge betweenness
        betweenness_file = base_output_dir / f"betweenness_{int(timestamp)}.txt"
        # network.save_edge_betweenness(str(betweenness_file), args.timestamp, base_output_dir)

        # Load betweenness from file
        network.load_edge_betweenness(str(betweenness_file))
        print(network.get_edge_betweenness_stats())
        network.update_spare_edges()
        
        # --- Report and Save Spare Capacity Coverage ---
        # network.report_spare_capacity_coverage(args.timestamp, base_output_dir)
        # ---------------------------------------------
        
        # --- Analyze and Save Spare Contiguity ---
        # network.analyze_spare_contiguity(args.timestamp, base_output_dir)
        # -----------------------------------------

        # --- Find longest GS-GS spare path (hops) using the selected candidate pairs ---
        print("\n--- Searching for Longest Hop GS-GS Spare Path (Candidate Pairs) ---")
        
        # Parameters for candidate selection (can be argparse options)
        # Reduced for faster processing, and random sampling disabled
        top_k_candidate_metric = 3  # Select top 3 by lat diff, top 3 by lon diff
        num_random_candidate = 0    # Disable random sampling for this search

        candidate_gs_pairs = network.get_candidate_gs_pairs_for_long_paths(
            top_k_each=top_k_candidate_metric, 
            num_random=num_random_candidate
        )

        max_overall_hops = 0
        best_path_info = {} # To store info about the path with max hops

        if not candidate_gs_pairs:
            print("No candidate GS pairs selected for max hop search.")
        else:
            print(f"Evaluating {len(candidate_gs_pairs)} candidate GS pairs for max hops...")
            
            factors_for_max_hop_search = [float(f.strip()) for f in args.delay_factors.split(',')]

            with tqdm(total=len(candidate_gs_pairs) * len(factors_for_max_hop_search), desc="Max Hop Search") as pbar_mh:
                for src_id, dst_id in candidate_gs_pairs:
                    for factor in factors_for_max_hop_search:
                        try:
                            path_results = network.find_paths_via_spare_edges(src_id, dst_id, factor, base_output_dir)

                            if path_results.get('spare_path_found') and path_results.get('spare_path_nodes'):
                                current_hops = len(path_results['spare_path_nodes']) -1 # Hops = num_nodes - 1
                                if current_hops > max_overall_hops:
                                    max_overall_hops = current_hops
                                    best_path_info = {
                                        'source': src_id,
                                        'target': dst_id,
                                        'factor': factor,
                                        'hops': current_hops,
                                        'delay': path_results.get('spare_path_delay'),
                                        'nodes': path_results.get('spare_path_nodes')
                                    }
                                    # Optional: print immediate updates
                                    # print(f"New max hops: {max_overall_hops} for {src_id}-{dst_id} (factor {factor})")
                        except Exception as e:
                            print(f"Error during max hop search for {src_id}-{dst_id} (factor {factor}): {e}")
                        finally:
                            pbar_mh.update(1)

        if best_path_info:
            print(f"\nMaximum spare path hops found: {best_path_info['hops']}")
            print(f"  GS Pair: {best_path_info['source']} -> {best_path_info['target']}")
            print(f"  Achieved with factor: {best_path_info['factor']}")
            print(f"  Path Delay: {best_path_info['delay']:.6f} s" if best_path_info['delay'] is not None else "  Path Delay: N/A")
            # Path nodes can be very long, so commented out by default
            # print(f"  Path Nodes: {' -> '.join(best_path_info['nodes'])}")
        else:
            print("\nNo spare paths found for candidate GS pairs, or no candidates identified that yielded a spare path.")
        print("---------------------------------------------------------------------\n")

        # --- Routing Effectiveness Evaluation ---
        # Define specific city pairs and random satellite pairs
        # Pairs: (London, NYC), (Singapore, London), (Paris, Johannesburg), (Birmingham, Tokyo), (Goteborg, Perth), (Kansas City, Philadelphia)
        city_pairs = [("10028", "10010"), ("10064", "10028"), ("10025", "10035"), ("10179", "10001"), ("10883", "10255"), ("10300", "10065")]
        # city_pairs = [("10300", "10065")]
        random_sat_pairs = []
        if args.num_eval_pairs > 0:
            random_sat_pairs = network.get_random_satellite_pairs(args.num_eval_pairs)

        # Combine pairs, adding a type identifier
        all_eval_pairs = []
        for pair in city_pairs:
            all_eval_pairs.append({'pair': pair, 'type': 'city'})
        for pair in random_sat_pairs:
            all_eval_pairs.append({'pair': pair, 'type': 'random_sat'})

        if not all_eval_pairs:
            print("No pairs (city or random satellite) specified for routing evaluation.")
        else:
            print(f"\n--- Evaluating Routing Effectiveness for {len(city_pairs)} City Pairs and {len(random_sat_pairs)} Random Satellite Pairs ---")
            print(f"Delay Factors: {delay_factors}")

            # --- Save the combined pairs list ---
            pairs_file = base_output_dir / f"eval_pairs_{int(timestamp)}.txt"
            try:
                with open(pairs_file, 'w') as f_pairs:
                    for item in all_eval_pairs:
                        p1, p2 = item['pair']
                        pair_type = item['type']
                        f_pairs.write(f"{p1},{p2},{pair_type}\n")
                print(f"Saved {len(all_eval_pairs)} evaluation pairs to {pairs_file}")
            except Exception as e_save:
                print(f"Warning: Could not save evaluation pairs to {pairs_file}: {e_save}")
            # ------------------------------------

            routing_results = []
            total_evals = len(all_eval_pairs) * len(delay_factors)

            with tqdm(total=total_evals, desc="Evaluating Routing") as pbar_route:
                for item in all_eval_pairs:
                    (src, dst) = item['pair']
                    pair_type = item['type']

                    for factor in delay_factors:
                        try:
                            # Call the function which returns a dict
                            # PathFinder now saves detailed stats per pair/factor
                            path_result_dict = network.find_paths_via_spare_edges(src, dst, factor, base_output_dir)

                            # Add identifying info to the results
                            path_result_dict['pair_type'] = pair_type
                            path_result_dict['delay_factor'] = factor

                            # Calculate delay delta if path found
                            if path_result_dict.get('spare_path_found', False):
                                if path_result_dict.get('spare_path_delay') is not None and path_result_dict.get('target_delay') is not None:
                                    path_result_dict['delay_delta'] = path_result_dict['spare_path_delay'] - path_result_dict['target_delay']
                                else:
                                    path_result_dict['delay_delta'] = None
                            else:
                                path_result_dict['delay_delta'] = None

                            routing_results.append(path_result_dict)

                            # --- Save factor-specific path files ---
                            # Ensure directories exist
                            paths_dir = base_output_dir / 'paths'
                            pair_dir = paths_dir / f'path_{src}_{dst}'
                            pair_dir.mkdir(parents=True, exist_ok=True)

                            # Construct factor-specific filenames
                            factor_str = str(factor).replace('.', '_')
                            paths_txt_file = pair_dir / f"paths_{factor_str}.txt"
                            spare_yaml_file = pair_dir / f"spare_{factor_str}.yaml"
                            shortest_yaml_file = pair_dir / f"shortest_{factor_str}.yaml"

                            # Write paths (pass potentially empty lists)
                            shortest_path_nodes = path_result_dict.get('shortest_path_nodes', [])
                            spare_path_nodes = path_result_dict.get('spare_path_nodes', [])
                            network.write_paths_to_file(str(paths_txt_file), src, dst, shortest_path_nodes, spare_path_nodes)

                            # Write YAML only if paths exist and are not empty
                            if spare_path_nodes:
                                 network.write_path_yaml(str(spare_yaml_file), spare_path_nodes)
                            if shortest_path_nodes:
                                 network.write_path_yaml(str(shortest_yaml_file), shortest_path_nodes)
                            # --- End factor-specific path saving ---

                        except Exception as route_err:
                             print(f"Error evaluating routing for {src}-{dst} ({pair_type}) with factor {factor}: {route_err}")
                             # Append partial results or error indicator if needed
                             routing_results.append({
                                 'source': src, 'target': dst, 'pair_type': pair_type, 'delay_factor': factor,
                                 'error': str(route_err), 'spare_path_found': False
                             })
                        finally:
                             pbar_route.update(1)

            # Save combined results to CSV
            if routing_results:
                results_df = pd.DataFrame(routing_results)
                # Select and order columns for clarity
                cols_to_save = [
                    'source', 'target', 'pair_type', 'delay_factor', 'shortest_path_delay',
                    'target_delay', 'spare_path_found', 'spare_path_delay',
                    'delay_delta', 'spare_edges_count', 'normal_edges_count',
                    'shortest_path_dist', 'spare_path_dist', 'duration_s', # Add duration
                    'error' # Include error if present
                ]
                # Filter columns that actually exist in the dataframe
                existing_cols = [col for col in cols_to_save if col in results_df.columns]
                results_df = results_df[existing_cols]

                coverage_dir = base_output_dir / "coverage_data"
                coverage_dir.mkdir(parents=True, exist_ok=True)
                output_csv = coverage_dir / f"routing_effectiveness_{int(timestamp)}.csv"
                results_df.to_csv(output_csv, index=False, float_format='%.6f')
                print(f"Saved combined routing effectiveness results to {output_csv}")
            else:
                 print("No routing effectiveness results generated.")
            print("---------------------------------------------------\n")
        # --------------------------------------

        print(f"Successfully processed timestamp {timestamp} ({datetime.datetime.fromtimestamp(timestamp, tz=timezone.utc)})")

    except Exception as e:
        print(f"Error processing data: {str(e)}")
        raise  # Re-raise the exception to ensure non-zero exit status
    # --- cProfile finally block removed ---

if __name__ == "__main__":
    main()
