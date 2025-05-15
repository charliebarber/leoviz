import pandas as pd
import numpy as np
import argparse
from pathlib import Path
import math
import matplotlib.pyplot as plt
import seaborn as sns
import re
import sys
from typing import Dict, Tuple, Optional, List

# Add skyfield directory to path to import TLEParser
# Assumes the script is run from the root directory or the analysis directory
script_dir = Path(__file__).parent.resolve()
skyfield_dir = script_dir.parent / 'skyfield'
if str(skyfield_dir) not in sys.path:
    sys.path.append(str(skyfield_dir))

try:
    from tle_parser import TLEParser
except ImportError:
    print(f"Error: Could not import TLEParser. Ensure '{skyfield_dir}' is accessible and contains tle_parser.py.")
    sys.exit(1)

# Function to calculate 3D Euclidean distance
def calculate_3d_distance(pos1: Dict, pos2: Dict) -> float:
    """Calculates the 3D Euclidean distance between two points given their ECEF coordinates."""
    if not all(k in pos1 for k in ['x_km', 'y_km', 'z_km']) or \
       not all(k in pos2 for k in ['x_km', 'y_km', 'z_km']):
        # This should not happen if get_position_snapshot works correctly
        raise ValueError("Position dictionaries must contain 'x_km', 'y_km', 'z_km'")
    dist_sq = (pos1['x_km'] - pos2['x_km'])**2 + \
              (pos1['y_km'] - pos2['y_km'])**2 + \
              (pos1['z_km'] - pos2['z_km'])**2
    return math.sqrt(dist_sq)

# Function to get satellite positions
def get_satellite_positions(tle_filepath: str, timestamp: float) -> List[Dict]:
    """Loads TLEs and returns a list of satellite position dicts, ordered by TLEParser's internal ID (assumed 0-based index)."""
    print(f"Loading TLEs from: {tle_filepath}")
    parser = TLEParser(tle_filepath)
    print("Creating satellite objects from TLEs...")
    # Note: create_satellites can be time-consuming for large TLE sets
    parser.create_satellites()
    print(f"Getting position snapshot for timestamp: {timestamp}")
    positions_list: List[Dict] = parser.get_position_snapshot(timestamp)
    # Optional sanity check: Ensure IDs match list indices
    # for i, pos in enumerate(positions_list):
    #     if int(pos['id']) != i:
    #         print(f"Warning: Position list index mismatch. Expected ID {i}, got {pos['id']}")
    print(f"Loaded positions for {len(positions_list)} satellites.")
    return positions_list

# Function to extract timestamp from filename
def extract_timestamp_from_filename(filename: str) -> Optional[int]:
    """Extracts Unix timestamp from filenames like routing_effectiveness_1234567890.csv"""
    # Match underscores followed by 10 or more digits, right before .csv
    match = re.search(r'_(\d{10,})\.csv$', filename)
    if match:
        return int(match.group(1))
    print(f"Warning: Could not extract timestamp from filename '{filename}'. Expected format like 'routing_effectiveness_1234567890.csv'.")
    return None

# Main analysis function
def analyze_failure_distance(csv_filepath: str, tle_filepath: str):
    """Analyzes correlation between routing failure and satellite distance."""
    filepath = Path(csv_filepath).resolve()
    tle_path = Path(tle_filepath).resolve()
    output_dir = filepath.parent

    if not filepath.is_file():
        print(f"Error: CSV file not found at {filepath}")
        sys.exit(1)
    if not tle_path.is_file():
        print(f"Error: TLE file not found at {tle_path}")
        sys.exit(1)

    # 1. Parse timestamp
    timestamp = extract_timestamp_from_filename(filepath.name)
    if timestamp is None:
        sys.exit(1)
    print(f"Analyzing data for timestamp: {timestamp}")

    # 2. Load CSV
    print(f"Loading routing data from: {filepath}")
    try:
        df = pd.read_csv(filepath)
        # Ensure IDs are strings for lookup consistency
        df['source'] = df['source'].astype(str)
        df['target'] = df['target'].astype(str)
        print(f"Loaded {len(df)} rows.")

        # Filter for satellite pairs if 'pair_type' column exists
        if 'pair_type' in df.columns:
            initial_count = len(df)
            df = df[df['pair_type'] == 'random_sat'].copy()
            filtered_count = len(df)
            print(f"Filtered for 'random_sat' pairs. Kept {filtered_count} out of {initial_count} rows.")
            if filtered_count == 0:
                print("Error: No 'random_sat' pairs found in the CSV file.")
                sys.exit(1)
        else:
            print("Warning: 'pair_type' column not found. Assuming all rows are satellite pairs.")

    except Exception as e:
        print(f"Error loading CSV file: {e}")
        sys.exit(1)

    # 3. Get satellite positions (now returns a list)
    try:
        # sat_positions_list is ordered by TLEParser ID (0, 1, 2...)
        sat_positions_list = get_satellite_positions(str(tle_path), float(timestamp))
        num_sats_in_tle = len(sat_positions_list)
    except Exception as e:
        print(f"Error getting satellite positions: {e}")
        sys.exit(1)

    # 4. Calculate distances for all unique pairs present in the DataFrame
    print("Calculating distances between satellite pairs...")
    unique_pairs = df[['source', 'target']].drop_duplicates()
    pair_distances: Dict[Tuple[str, str], float] = {}
    calculation_errors = 0
    invalid_id_count = 0
    missing_coords_count = 0 # New counter for missing x,y,z keys

    for _, row in unique_pairs.iterrows():
        src_id_str, tgt_id_str = row['source'], row['target']
        # Use a consistent key order (e.g., sorted) for the pair distance lookup
        pair_key = tuple(sorted((src_id_str, tgt_id_str)))

        if pair_key not in pair_distances:
            pos1 = None
            pos2 = None
            try:
                # Assume network_id string can be converted to 0-based index
                src_idx = int(src_id_str)
                tgt_idx = int(tgt_id_str)

                # Check if indices are valid for the loaded positions list
                if 0 <= src_idx < num_sats_in_tle and 0 <= tgt_idx < num_sats_in_tle:
                    pos1 = sat_positions_list[src_idx]
                    pos2 = sat_positions_list[tgt_idx]
                else:
                    invalid_id_count += 1 # Count pairs with out-of-bounds IDs

            except ValueError:
                # Should not happen if we filtered for 'random_sat' and IDs are integers
                print(f"Warning: Could not convert satellite IDs to integers for pair ({src_id_str}, {tgt_id_str}). Skipping.")
                invalid_id_count += 1 # Count pairs with non-integer IDs

            # Check if positions were successfully retrieved AND contain necessary keys
            if pos1 and pos2:
                if all(k in pos1 for k in ['x_km', 'y_km', 'z_km']) and \
                   all(k in pos2 for k in ['x_km', 'y_km', 'z_km']):
                    try:
                        distance = calculate_3d_distance(pos1, pos2)
                        pair_distances[pair_key] = distance
                    except ValueError as e: # Should ideally not happen now, but keep as safeguard
                        print(f"Warning: Unexpected error calculating distance for pair ({src_id_str}, {tgt_id_str}): {e}")
                        pair_distances[pair_key] = np.nan
                        calculation_errors += 1
                else:
                    # Handle cases where position dicts are missing keys
                    # print(f"Debug: Missing keys for pair ({src_id_str}, {tgt_id_str}). Pos1 keys: {pos1.keys()}, Pos2 keys: {pos2.keys()}") # Optional debug print
                    missing_coords_count += 1
                    pair_distances[pair_key] = np.nan
            else:
                # This branch is taken if IDs were invalid/out-of-bounds or conversion failed
                pair_distances[pair_key] = np.nan

    # Report issues after the loop
    if invalid_id_count > 0:
         print(f"Warning: Skipped {invalid_id_count} unique pairs due to invalid or out-of-bounds source/target IDs (expected 0 to {num_sats_in_tle - 1}).")
    if calculation_errors > 0:
         print(f"Warning: Encountered {calculation_errors} errors during distance calculation.")
    if missing_coords_count > 0:
         print(f"Warning: Skipped {missing_coords_count} unique pairs because position data was missing 'x_km', 'y_km', or 'z_km' keys.")
    calculated_count = len(pair_distances) - sum(1 for d in pair_distances.values() if np.isnan(d))
    print(f"Successfully calculated distances for {calculated_count} unique pairs.")

    # 5. Add distance column to DataFrame
    def get_pair_distance(row):
        pair_key = tuple(sorted((row['source'], row['target'])))
        return pair_distances.get(pair_key, np.nan)

    df['distance_km'] = df.apply(get_pair_distance, axis=1)
    initial_rows = len(df)
    df.dropna(subset=['distance_km'], inplace=True) # Remove rows where distance couldn't be calculated
    removed_rows = initial_rows - len(df)
    if removed_rows > 0:
        print(f"Removed {removed_rows} rows from DataFrame due to missing distances.")
    if df.empty:
        print("Error: No data remaining after calculating distances. Check TLE file, timestamp, and CSV content.")
        sys.exit(1)

    # 6. Identify failing/successful groups
    df_all_125 = df[df['delay_factor'] == 1.25].copy()
    if df_all_125.empty:
        print("Warning: No data found for delay_factor = 1.25. Cannot perform comparison.")
        # Optionally exit or skip analysis parts
    df_fail_125 = df_all_125[df_all_125['spare_path_found'] == False].copy()
    df_success_125 = df_all_125[df_all_125['spare_path_found'] == True].copy()

    # Identify consistently failing pairs (fail for ALL factors present for that pair)
    # Group by pair and check if 'spare_path_found' is never True
    pair_success_summary = df.groupby(['source', 'target'])['spare_path_found'].any()
    consistently_failing_pairs_indices = pair_success_summary[~pair_success_summary].index
    print(f"Found {len(consistently_failing_pairs_indices)} consistently failing pairs (failed for all factors).")

    # Get the data for consistently failing pairs (we only need distance, so factor 1.25 rows are fine)
    # Create a multi-index from the pairs to filter df_all_125 efficiently
    if not consistently_failing_pairs_indices.empty:
        df_consistently_fail = df_all_125[df_all_125.set_index(['source', 'target']).index.isin(consistently_failing_pairs_indices)].copy()
    else:
        df_consistently_fail = pd.DataFrame(columns=df_all_125.columns) # Empty dataframe if none consistently fail

    # 7. Calculate & print stats
    print("\n--- Distance Statistics (km) ---")
    stats = {}
    if not df_all_125.empty:
        stats['All Pairs (Factor 1.25)'] = df_all_125['distance_km'].describe()
    if not df_success_125.empty:
        stats['Successful Pairs (Factor 1.25)'] = df_success_125['distance_km'].describe()
    if not df_fail_125.empty:
        stats['Failing Pairs (Factor 1.25)'] = df_fail_125['distance_km'].describe()
    if not df_consistently_fail.empty:
        stats['Consistently Failing Pairs'] = df_consistently_fail['distance_km'].describe()

    if stats:
        stats_df = pd.DataFrame(stats).T # Transpose for better readability
        print(stats_df.to_string(float_format="%.2f"))

        # Save stats to file
        stats_filename = output_dir / f"failure_distance_stats_{timestamp}.csv"
        try:
            stats_df.to_csv(stats_filename, float_format='%.2f')
            print(f"\nSaved distance statistics to: {stats_filename}")
        except Exception as e:
            print(f"Error saving statistics: {e}")
    else:
        print("No valid data groups found to calculate statistics.")

    # 8. Generate & save plots (only if data exists)
    if not df_all_125.empty:
        print("\nGenerating plots...")
        plt.style.use('seaborn-v0_8-deep') # Use a nice style

        # Prepare data for boxplot: add a category column
        plot_data_list = []
        if not df_success_125.empty: plot_data_list.append(df_success_125.assign(category='Success (1.25)'))
        if not df_fail_125.empty: plot_data_list.append(df_fail_125.assign(category='Fail (1.25)'))
        if not df_consistently_fail.empty: plot_data_list.append(df_consistently_fail.assign(category='Consistently Fail'))

        if plot_data_list:
            df_plot = pd.concat(plot_data_list, ignore_index=True)

            # Histogram comparison
            plt.figure(figsize=(12, 7))
            if not df_success_125.empty: sns.histplot(data=df_success_125, x='distance_km', color='green', label='Success (Factor 1.25)', kde=True, stat='density', element='step', fill=False)
            if not df_fail_125.empty: sns.histplot(data=df_fail_125, x='distance_km', color='red', label='Fail (Factor 1.25)', kde=True, stat='density', element='step', fill=False)
            if not df_consistently_fail.empty: sns.histplot(data=df_consistently_fail, x='distance_km', color='orange', label='Consistently Fail', kde=True, stat='density', element='step', fill=False, linestyle='--')
            plt.title(f'Distribution of Satellite Pair Distances (Timestamp: {timestamp})')
            plt.xlabel('Straight-Line Distance (km)')
            plt.ylabel('Density')
            plt.legend()
            plt.tight_layout()
            hist_filename = output_dir / f"failure_distance_histogram_{timestamp}.png"
            plt.savefig(hist_filename)
            print(f"Saved histogram plot to: {hist_filename}")
            plt.close() # Close the figure

            # Box plot comparison
            plt.figure(figsize=(8, 6))
            category_order = [cat['category'].iloc[0] for cat in plot_data_list if not cat.empty] # Maintain order
            palette = {'Success (1.25)': 'green', 'Fail (1.25)': 'red', 'Consistently Fail': 'orange'}
            sns.boxplot(data=df_plot, x='category', y='distance_km', order=category_order, palette=palette)
            plt.title(f'Satellite Pair Distances by Success Status (Timestamp: {timestamp})')
            plt.xlabel('Path Finding Outcome')
            plt.ylabel('Straight-Line Distance (km)')
            plt.xticks(rotation=15, ha='right')
            plt.tight_layout()
            box_filename = output_dir / f"failure_distance_boxplot_{timestamp}.png"
            plt.savefig(box_filename)
            print(f"Saved box plot to: {box_filename}")
            plt.close() # Close the figure
        else:
            print("No data available for plotting.")
    else:
        print("Skipping plot generation as no data for factor 1.25 was found.")

    print("\nAnalysis complete.")


# Argparse and main execution block
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Analyze correlation between routing failure and satellite distance using 3D ECEF coordinates.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('csv_file', type=str, help='Path to the routing_effectiveness_{timestamp}.csv file.')
    # Provide a default relative path assuming a standard project structure
    default_tle_path = Path(__file__).parent.parent / 'constellations' / 'starlink_550' / 'tles.txt'
    parser.add_argument('--tle-file', type=str, default=str(default_tle_path),
                        help='Path to the TLE file.')
    args = parser.parse_args()

    # Ensure the default TLE path exists if used
    if args.tle_file == str(default_tle_path) and not default_tle_path.exists():
        print(f"Warning: Default TLE file not found at {default_tle_path}. Please specify the correct path using --tle-file.")
        # Optionally exit if TLE is critical
        # sys.exit(1)

    analyze_failure_distance(args.csv_file, args.tle_file)
