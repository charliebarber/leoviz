import pandas as pd
import numpy as np
import argparse
from pathlib import Path
import re

def calculate_spare_usage_perc(row):
    """Calculates spare usage percentage from a DataFrame row."""
    spare_count = row['spare_edges_count']
    normal_count = row['normal_edges_count']
    total_edges = spare_count + normal_count
    if total_edges > 0:
        return (spare_count / total_edges) * 100
    else:
        return 0.0 # Or np.nan if preferred for zero-edge paths

def find_spare_usage_example(base_dir: str, source_id: str, target_id: str, min_diff: float):
    """
    Finds a timestamp where a city pair succeeds at factors 1.25 and 2.0,
    and the spare link usage percentage decreases from 1.25x to 2.0x.

    Args:
        base_dir (str): Base directory with timestamp subdirs.
        source_id (str): Source ground station ID.
        target_id (str): Target ground station ID.
        min_diff (float): Minimum percentage point difference required (perc_1_25 - perc_2_0).
    """
    base_path = Path(base_dir)
    if not base_path.is_dir():
        print(f"Error: Base directory not found at {base_path}")
        return

    print(f"Searching for decreasing spare usage example in: {base_path}")
    print(f"Pair: {source_id} -> {target_id}")
    print(f"Minimum required decrease in usage: {min_diff:.1f}%")

    # Find all routing_effectiveness CSV files
    routing_files = sorted(list(base_path.rglob('coverage_data/routing_effectiveness_*.csv')))

    if not routing_files:
        print("Error: No 'routing_effectiveness_*.csv' files found.")
        return

    print(f"Found {len(routing_files)} routing effectiveness files.")

    timestamp_regex = re.compile(r'routing_effectiveness_(\d+)\.csv')

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

            if len(df_pair) < 2: # Need results for at least 1.25 and 2.0
                continue

            # Get results for factor 1.25 and 2.0
            res_1_25 = df_pair[df_pair['delay_factor'] == 1.25].iloc[0] if 1.25 in df_pair['delay_factor'].values else None
            res_2_0 = df_pair[df_pair['delay_factor'] == 2.0].iloc[0] if 2.0 in df_pair['delay_factor'].values else None

            # Check if both succeeded and have edge counts
            if res_1_25 is None or res_2_0 is None or \
               not res_1_25['spare_path_found'] or not res_2_0['spare_path_found'] or \
               pd.isna(res_1_25['spare_edges_count']) or pd.isna(res_1_25['normal_edges_count']) or \
               pd.isna(res_2_0['spare_edges_count']) or pd.isna(res_2_0['normal_edges_count']):
                continue

            # Calculate spare usage percentages
            perc_1_25 = calculate_spare_usage_perc(res_1_25)
            perc_2_0 = calculate_spare_usage_perc(res_2_0)

            # Found the desired example? (perc_1_25 - perc_2_0 >= min_diff)
            difference = perc_1_25 - perc_2_0
            if difference >= min_diff:
                print(f"\n--- Found Example Timestamp: {timestamp} ---")
                print(f"Pair: {source_id} -> {target_id}")
                shortest_delay = res_1_25['shortest_path_delay'] # Should be same for both
                print(f"Shortest Path Delay: {shortest_delay*1000:.4f} ms")

                print("\nFactor 1.25 Results:")
                print(f"  Spare Path Delay: {res_1_25['spare_path_delay']*1000:.4f} ms")
                print(f"  Spare Edges: {int(res_1_25['spare_edges_count'])}, Normal Edges: {int(res_1_25['normal_edges_count'])}")
                print(f"  Spare Usage: {perc_1_25:.1f}%")

                print("\nFactor 2.0 Results:")
                print(f"  Spare Path Delay: {res_2_0['spare_path_delay']*1000:.4f} ms")
                print(f"  Spare Edges: {int(res_2_0['spare_edges_count'])}, Normal Edges: {int(res_2_0['normal_edges_count'])}")
                print(f"  Spare Usage: {perc_2_0:.1f}%")
                print(f"\nUsage decreased by {difference:.1f} percentage points (>= {min_diff:.1f}% threshold).")
                print("This timestamp provides a good example for visualization.")
                return # Stop after finding the first example

        except Exception as e:
            print(f"Warning: Error processing file {file}: {e}")

    print(f"\nNo timestamp found matching the criteria for pair {source_id}-{target_id}.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find a timestamp example demonstrating decreasing spare usage.')
    parser.add_argument('base_directory', type=str, help='Base directory containing timestamp subdirectories')
    parser.add_argument('source_id', type=str, help='Source GS ID (e.g., 10025)')
    parser.add_argument('target_id', type=str, help='Target GS ID (e.g., 10035)')
    parser.add_argument('--min-diff', type=float, default=5.0,
                        help='Minimum required percentage point decrease in spare usage from 1.25x to 2.0x (default: 5.0)')
    args = parser.parse_args()

    find_spare_usage_example(args.base_directory, args.source_id, args.target_id, args.min_diff)
