import pandas as pd
import numpy as np
import argparse
from pathlib import Path
import re

def find_tolerance_example(base_dir: str, source_id: str, target_id: str):
    """
    Finds a timestamp where a city pair succeeds at factors 1.5 and 2.0,
    meets 5% tolerance at 1.5x, but fails 5% tolerance at 2.0x.

    Args:
        base_dir (str): Base directory with timestamp subdirs.
        source_id (str): Source ground station ID.
        target_id (str): Target ground station ID.
    """
    base_path = Path(base_dir)
    if not base_path.is_dir():
        print(f"Error: Base directory not found at {base_path}")
        return

    print(f"Searching for example in: {base_path}")
    print(f"Pair: {source_id} -> {target_id}")

    # Find all routing_effectiveness CSV files
    routing_files = sorted(list(base_path.rglob('coverage_data/routing_effectiveness_*.csv')))

    if not routing_files:
        print("Error: No 'routing_effectiveness_*.csv' files found.")
        return

    print(f"Found {len(routing_files)} routing effectiveness files.")

    timestamp_regex = re.compile(r'routing_effectiveness_(\d+)\.csv')
    tolerance = 0.05

    for file in routing_files:
        match = timestamp_regex.search(file.name)
        if not match:
            continue
        timestamp = int(match.group(1))

        try:
            df_ts = pd.read_csv(file)
            # Filter for the specific pair
            df_pair = df_ts[(df_ts['source'].astype(str) == source_id) &
                            (df_ts['target'].astype(str) == target_id)].copy()

            if len(df_pair) < 2: # Need results for at least 1.5 and 2.0
                continue

            # Get results for factor 1.5 and 2.0
            res_1_5 = df_pair[df_pair['delay_factor'] == 1.5].iloc[0] if 1.5 in df_pair['delay_factor'].values else None
            res_2_0 = df_pair[df_pair['delay_factor'] == 2.0].iloc[0] if 2.0 in df_pair['delay_factor'].values else None

            # Check if both succeeded
            if res_1_5 is None or res_2_0 is None or \
               not res_1_5['spare_path_found'] or not res_2_0['spare_path_found']:
                continue

            # Check tolerance for 1.5
            shortest_delay = res_1_5['shortest_path_delay']
            spare_delay_1_5 = res_1_5['spare_path_delay']
            lower_bound_1_5 = shortest_delay * (1.5 * (1 - tolerance))
            upper_bound_1_5 = shortest_delay * (1.5 * (1 + tolerance))
            met_tolerance_1_5 = (spare_delay_1_5 >= lower_bound_1_5) and (spare_delay_1_5 <= upper_bound_1_5)

            # Check tolerance for 2.0
            # Note: shortest_delay should be the same for both factors in the same timestamp
            spare_delay_2_0 = res_2_0['spare_path_delay']
            lower_bound_2_0 = shortest_delay * (2.0 * (1 - tolerance))
            upper_bound_2_0 = shortest_delay * (2.0 * (1 + tolerance))
            met_tolerance_2_0 = (spare_delay_2_0 >= lower_bound_2_0) and (spare_delay_2_0 <= upper_bound_2_0)

            # Found the desired example?
            if met_tolerance_1_5 and not met_tolerance_2_0:
                print(f"\n--- Found Example Timestamp: {timestamp} ---")
                print(f"Pair: {source_id} -> {target_id}")
                print(f"Shortest Path Delay: {shortest_delay*1000:.4f} ms")

                print("\nFactor 1.5 Results:")
                print(f"  Target Delay: {res_1_5['target_delay']*1000:.4f} ms")
                print(f"  Spare Path Delay: {spare_delay_1_5*1000:.4f} ms")
                print(f"  5% Tolerance Range: [{lower_bound_1_5*1000:.4f} ms, {upper_bound_1_5*1000:.4f} ms]")
                print(f"  Met 5% Tolerance: {met_tolerance_1_5}")

                print("\nFactor 2.0 Results:")
                print(f"  Target Delay: {res_2_0['target_delay']*1000:.4f} ms")
                print(f"  Spare Path Delay: {spare_delay_2_0*1000:.4f} ms")
                print(f"  5% Tolerance Range: [{lower_bound_2_0*1000:.4f} ms, {upper_bound_2_0*1000:.4f} ms]")
                print(f"  Met 5% Tolerance: {met_tolerance_2_0}")
                print("\nThis timestamp provides a good example for visualization.")
                return # Stop after finding the first example

        except Exception as e:
            print(f"Warning: Error processing file {file}: {e}")

    print(f"\nNo timestamp found matching the criteria for pair {source_id}-{target_id}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find a timestamp example demonstrating tolerance behavior.')
    parser.add_argument('base_directory', type=str, help='Base directory containing timestamp subdirectories')
    parser.add_argument('source_id', type=str, help='Source GS ID (e.g., 10025)')
    parser.add_argument('target_id', type=str, help='Target GS ID (e.g., 10035)')
    args = parser.parse_args()

    find_tolerance_example(args.base_directory, args.source_id, args.target_id)

