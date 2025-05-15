import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
import json # Import json

def load_coverage_data(base_dir: Path) -> pd.DataFrame:
    """
    Loads all gs_delays_*.csv files from timestamp subdirectories into a single DataFrame.

    Args:
        base_dir (Path): The base directory containing timestamp subdirectories
                         (e.g., ../positions/starlink_550_traffic_scaled/).

    Returns:
        pd.DataFrame: DataFrame containing columns ['timestamp', 'gs_id', 'delay_ms'].
                      Returns an empty DataFrame if no data is found.
    """
    all_data = []
    timestamp_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.isdigit()],
                           key=lambda x: int(x.name))

    if not timestamp_dirs:
        print(f"Error: No timestamp directories found in {base_dir}")
        return pd.DataFrame(columns=['timestamp', 'gs_id', 'delay_ms'])

    print(f"Found {len(timestamp_dirs)} timestamp directories.")

    for ts_dir in tqdm(timestamp_dirs, desc="Loading coverage data"):
        timestamp = int(ts_dir.name)
        coverage_dir = ts_dir / "coverage_data"
        csv_file = coverage_dir / f"gs_delays_{timestamp}.csv"

        if csv_file.exists():
            try:
                df = pd.read_csv(csv_file)
                df['timestamp'] = timestamp
                # Replace inf with NaN for easier processing
                df.replace([np.inf, -np.inf], np.nan, inplace=True)
                all_data.append(df[['timestamp', 'gs_id', 'delay_ms']])
            except pd.errors.EmptyDataError:
                print(f"Warning: Skipping empty file {csv_file}")
            except Exception as e:
                print(f"Warning: Error reading {csv_file}: {e}")
        else:
            print(f"Warning: File not found {csv_file}")

    if not all_data:
        print("Error: No coverage data loaded.")
        return pd.DataFrame(columns=['timestamp', 'gs_id', 'delay_ms'])

    return pd.concat(all_data, ignore_index=True)

def load_timing_data(base_dir: Path) -> pd.DataFrame:
    """
    Loads all coverage_timing_*.txt files from timestamp subdirectories.

    Args:
        base_dir (Path): The base directory containing timestamp subdirectories.

    Returns:
        pd.DataFrame: DataFrame containing columns ['timestamp', 'duration_s'].
                      Returns an empty DataFrame if no data is found.
    """
    all_timing_data = []
    timestamp_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.isdigit()],
                           key=lambda x: int(x.name))

    if not timestamp_dirs:
        print(f"Error: No timestamp directories found in {base_dir} for timing data.")
        return pd.DataFrame(columns=['timestamp', 'duration_s'])

    print(f"Searching for timing data in {len(timestamp_dirs)} timestamp directories.")

    for ts_dir in tqdm(timestamp_dirs, desc="Loading timing data"):
        timestamp = int(ts_dir.name)
        coverage_dir = ts_dir / "coverage_data"
        timing_file = coverage_dir / f"coverage_timing_{timestamp}.txt"

        if timing_file.exists():
            try:
                with open(timing_file, 'r') as f:
                    duration_s = float(f.readline().strip())
                    all_timing_data.append({'timestamp': timestamp, 'duration_s': duration_s})
            except Exception as e:
                print(f"Warning: Error reading timing file {timing_file}: {e}")
        # else: # Optional: Warn if timing file is missing
            # print(f"Warning: Timing file not found {timing_file}")

    if not all_timing_data:
        print("Warning: No timing data loaded.")
        return pd.DataFrame(columns=['timestamp', 'duration_s'])

    return pd.DataFrame(all_timing_data)

def load_contiguity_data(base_dir: Path) -> pd.DataFrame:
    """
    Loads all spare_contiguity_*.json files from timestamp subdirectories.

    Args:
        base_dir (Path): The base directory containing timestamp subdirectories.

    Returns:
        pd.DataFrame: DataFrame containing contiguity statistics per timestamp.
                      Returns an empty DataFrame if no data is found.
    """
    all_contiguity_data = []
    timestamp_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.isdigit()],
                           key=lambda x: int(x.name))

    if not timestamp_dirs:
        print(f"Error: No timestamp directories found in {base_dir} for contiguity data.")
        return pd.DataFrame() # Return empty DF

    print(f"Searching for contiguity data in {len(timestamp_dirs)} timestamp directories.")

    for ts_dir in tqdm(timestamp_dirs, desc="Loading contiguity data"):
        timestamp = int(ts_dir.name)
        coverage_dir = ts_dir / "coverage_data"
        contiguity_file = coverage_dir / f"spare_contiguity_{timestamp}.json"

        if contiguity_file.exists():
            try:
                with open(contiguity_file, 'r') as f:
                    stats = json.load(f)
                    all_contiguity_data.append(stats)
            except Exception as e:
                print(f"Warning: Error reading contiguity file {contiguity_file}: {e}")
        # else: # Optional: Warn if contiguity file is missing
            # print(f"Warning: Contiguity file not found {contiguity_file}")

    if not all_contiguity_data:
        print("Warning: No contiguity data loaded.")
        return pd.DataFrame() # Return empty DF

    # Set timestamp as index for easier joining later if needed
    contiguity_df = pd.DataFrame(all_contiguity_data)
    if 'timestamp' in contiguity_df.columns:
         contiguity_df.set_index('timestamp', inplace=True)
    return contiguity_df

def load_routing_effectiveness_data(base_dir: Path) -> pd.DataFrame:
    """
    Loads all routing_effectiveness_*.csv files from timestamp subdirectories.

    Args:
        base_dir (Path): The base directory containing timestamp subdirectories.

    Returns:
        pd.DataFrame: DataFrame containing routing effectiveness results.
                      Returns an empty DataFrame if no data is found.
    """
    all_routing_data = []
    timestamp_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.isdigit()],
                           key=lambda x: int(x.name))

    if not timestamp_dirs:
        print(f"Error: No timestamp directories found in {base_dir} for routing data.")
        return pd.DataFrame()

    print(f"Searching for routing effectiveness data in {len(timestamp_dirs)} timestamp directories.")

    for ts_dir in tqdm(timestamp_dirs, desc="Loading routing data"):
        timestamp = int(ts_dir.name)
        coverage_dir = ts_dir / "coverage_data"
        routing_file = coverage_dir / f"routing_effectiveness_{timestamp}.csv"

        if routing_file.exists():
            try:
                df_route = pd.read_csv(routing_file)
                df_route['timestamp'] = timestamp
                all_routing_data.append(df_route)
            except pd.errors.EmptyDataError:
                print(f"Warning: Skipping empty routing file {routing_file}")
            except Exception as e:
                print(f"Warning: Error reading routing file {routing_file}: {e}")
        # else: # Optional: Warn if routing file is missing
            # print(f"Warning: Routing file not found {routing_file}")

    if not all_routing_data:
        print("Warning: No routing effectiveness data loaded.")
        return pd.DataFrame()

    return pd.concat(all_routing_data, ignore_index=True)


def analyze_coverage(df: pd.DataFrame, timing_df: pd.DataFrame, contiguity_df: pd.DataFrame, routing_df: pd.DataFrame, output_dir: Path):
    """
    Analyzes the loaded coverage, timing, contiguity, and routing data, generates reports and plots.

    Args:
        df (pd.DataFrame): DataFrame with columns ['timestamp', 'gs_id', 'delay_ms'].
        timing_df (pd.DataFrame): DataFrame with columns ['timestamp', 'duration_s'].
        contiguity_df (pd.DataFrame): DataFrame with contiguity statistics indexed by timestamp.
        routing_df (pd.DataFrame): DataFrame with routing effectiveness results.
        output_dir (Path): Directory to save analysis results.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_results_file = output_dir / "coverage_analysis_summary.txt"
    
    # --- Coverage Analysis ---
    if not df.empty:
        print("\n--- Analyzing Coverage Delay ---")
        # Exclude NaN values (unreachable GS) for statistical calculations
        df_valid = df.dropna(subset=['delay_ms'])
        
        stats_per_timestamp = df_valid.groupby('timestamp')['delay_ms'].agg(
            ['mean', 'median', 'min', 'max', 'count', lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
        ).rename(columns={'<lambda_0>': 'q25', '<lambda_1>': 'q75'})

        # Count unreachable GS per timestamp
        unreachable_counts = df[df['delay_ms'].isna()].groupby('timestamp').size().rename('unreachable_count')
        total_counts = df.groupby('timestamp').size().rename('total_gs')
        stats_per_timestamp = stats_per_timestamp.join(unreachable_counts, how='left').fillna(0)
        stats_per_timestamp = stats_per_timestamp.join(total_counts, how='left')
        stats_per_timestamp['reachable_count'] = stats_per_timestamp['total_gs'] - stats_per_timestamp['unreachable_count']

        print("\n--- Statistics per Timestamp (Coverage Delay) ---")
        print(stats_per_timestamp.head())
        stats_per_timestamp.to_csv(output_dir / "coverage_stats_per_timestamp.csv")

        # --- Overall Statistics ---
        overall_avg_delay = df_valid['delay_ms'].mean()
        overall_median_delay = df_valid['delay_ms'].median()
        overall_min_delay = df_valid['delay_ms'].min()
        overall_max_delay = df_valid['delay_ms'].max()
        
        # Find GS with best/worst average delay
        avg_delay_per_gs = df_valid.groupby('gs_id')['delay_ms'].mean().sort_values()
        best_gs_avg = avg_delay_per_gs.index[0]
        worst_gs_avg = avg_delay_per_gs.index[-1]
        best_avg_delay = avg_delay_per_gs.iloc[0]
        worst_avg_delay = avg_delay_per_gs.iloc[-1]

        # Find GS with overall min/max delay instances
        min_delay_row = df_valid.loc[df_valid['delay_ms'].idxmin()]
        max_delay_row = df_valid.loc[df_valid['delay_ms'].idxmax()]
        best_gs_min = min_delay_row['gs_id']
        worst_gs_max = max_delay_row['gs_id']
        min_delay_ts = min_delay_row['timestamp']
        max_delay_ts = max_delay_row['timestamp']

        print("\n--- Overall Coverage Summary ---")
        print(f"Overall Average Delay (reachable): {overall_avg_delay:.2f} ms")
        print(f"Overall Median Delay (reachable): {overall_median_delay:.2f} ms")
        print(f"Overall Minimum Delay: {overall_min_delay:.2f} ms (GS: {best_gs_min} at timestamp {min_delay_ts})")
        print(f"Overall Maximum Delay: {overall_max_delay:.2f} ms (GS: {worst_gs_max} at timestamp {max_delay_ts})")
        print(f"Best Average Coverage GS: {best_gs_avg} ({best_avg_delay:.2f} ms avg)")
        print(f"Worst Average Coverage GS: {worst_gs_avg} ({worst_avg_delay:.2f} ms avg)")

        # Save summary to file (overwrite or create)
        with open(analysis_results_file, 'w') as f:
            f.write("--- Overall Spare Capacity Coverage Analysis ---\n\n")
            f.write(f"Overall Average Delay (reachable): {overall_avg_delay:.2f} ms\n")
            f.write(f"Overall Median Delay (reachable): {overall_median_delay:.2f} ms\n")
            f.write(f"Overall Minimum Delay: {overall_min_delay:.2f} ms (GS: {best_gs_min} at timestamp {min_delay_ts})\n")
            f.write(f"Overall Maximum Delay: {overall_max_delay:.2f} ms (GS: {worst_gs_max} at timestamp {max_delay_ts})\n")
            f.write(f"Best Average Coverage GS: {best_gs_avg} ({best_avg_delay:.2f} ms avg)\n")
            f.write(f"Worst Average Coverage GS: {worst_gs_avg} ({worst_avg_delay:.2f} ms avg)\n\n")
            f.write("--- Statistics per Timestamp (Coverage Delay) ---\n")
            f.write(stats_per_timestamp.to_string())
            f.write("\n\n")
        
        # --- Plotting Coverage ---
        sns.set_theme(style="darkgrid")
        plt.figure(figsize=(12, 6))
        
        # Plot average and median delay over time
        plt.plot(stats_per_timestamp.index, stats_per_timestamp['mean'], label='Mean Delay (ms)', marker='o', linestyle='-')
        plt.plot(stats_per_timestamp.index, stats_per_timestamp['median'], label='Median Delay (ms)', marker='x', linestyle='--')
        
        # Add shaded area for min/max or quantiles
        plt.fill_between(stats_per_timestamp.index, stats_per_timestamp['min'], stats_per_timestamp['max'], color='b', alpha=0.1, label='Min-Max Range')
        # Or use quantiles:
        # plt.fill_between(stats_per_timestamp.index, stats_per_timestamp['q25'], stats_per_timestamp['q75'], color='g', alpha=0.2, label='IQR')

        plt.title('Ground Station Delay to Nearest Spare Node Over Time')
        plt.xlabel('Timestamp')
        plt.ylabel('Delay (ms)')
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        plot_file = output_dir / "coverage_delay_over_time.png"
        plt.savefig(plot_file)
        print(f"Coverage plot saved to {plot_file}")
        plt.close()

        # Plot number of reachable/unreachable GS over time
        plt.figure(figsize=(12, 6))
        plt.plot(stats_per_timestamp.index, stats_per_timestamp['reachable_count'], label='Reachable GS', marker='o', linestyle='-')
        plt.plot(stats_per_timestamp.index, stats_per_timestamp['unreachable_count'], label='Unreachable GS', marker='x', linestyle='--')
        plt.plot(stats_per_timestamp.index, stats_per_timestamp['total_gs'], label='Total GS', marker='.', linestyle=':', color='gray')

        plt.title('Ground Station Reachability to Spare Nodes Over Time')
        plt.xlabel('Timestamp')
        plt.ylabel('Number of Ground Stations')
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        reach_plot_file = output_dir / "coverage_reachability_over_time.png"
        plt.savefig(reach_plot_file)
        print(f"Reachability plot saved to {reach_plot_file}")
        plt.close()
        
    else:
         print("Coverage delay analysis skipped: Input DataFrame is empty.")
         # Create empty file if no coverage data, so append works later
         with open(analysis_results_file, 'w') as f:
              f.write("--- Coverage Delay Analysis Skipped (No Data) ---\n\n")
         return # Correct indentation

    output_dir.mkdir(parents=True, exist_ok=True)
    analysis_results_file = output_dir / "coverage_analysis_summary.txt"
    
    # --- Basic Statistics per Timestamp ---
    # Exclude NaN values (unreachable GS) for statistical calculations
    df_valid = df.dropna(subset=['delay_ms'])
    
    stats_per_timestamp = df_valid.groupby('timestamp')['delay_ms'].agg(
        ['mean', 'median', 'min', 'max', 'count', lambda x: x.quantile(0.25), lambda x: x.quantile(0.75)]
    ).rename(columns={'<lambda_0>': 'q25', '<lambda_1>': 'q75'})

    # Count unreachable GS per timestamp
    unreachable_counts = df[df['delay_ms'].isna()].groupby('timestamp').size().rename('unreachable_count')
    total_counts = df.groupby('timestamp').size().rename('total_gs')
    stats_per_timestamp = stats_per_timestamp.join(unreachable_counts, how='left').fillna(0)
    stats_per_timestamp = stats_per_timestamp.join(total_counts, how='left')
    stats_per_timestamp['reachable_count'] = stats_per_timestamp['total_gs'] - stats_per_timestamp['unreachable_count']

    print("\n--- Statistics per Timestamp ---")
    print(stats_per_timestamp.head())
    stats_per_timestamp.to_csv(output_dir / "coverage_stats_per_timestamp.csv")

    # --- Overall Statistics ---
    overall_avg_delay = df_valid['delay_ms'].mean()
    overall_median_delay = df_valid['delay_ms'].median()
    overall_min_delay = df_valid['delay_ms'].min()
    overall_max_delay = df_valid['delay_ms'].max()
    
    # Find GS with best/worst average delay
    avg_delay_per_gs = df_valid.groupby('gs_id')['delay_ms'].mean().sort_values()
    best_gs_avg = avg_delay_per_gs.index[0]
    worst_gs_avg = avg_delay_per_gs.index[-1]
    best_avg_delay = avg_delay_per_gs.iloc[0]
    worst_avg_delay = avg_delay_per_gs.iloc[-1]

    # Find GS with overall min/max delay instances
    min_delay_row = df_valid.loc[df_valid['delay_ms'].idxmin()]
    max_delay_row = df_valid.loc[df_valid['delay_ms'].idxmax()]
    best_gs_min = min_delay_row['gs_id']
    worst_gs_max = max_delay_row['gs_id']
    min_delay_ts = min_delay_row['timestamp']
    max_delay_ts = max_delay_row['timestamp']

    print("\n--- Overall Summary ---")
    print(f"Overall Average Delay (reachable): {overall_avg_delay:.2f} ms")
    print(f"Overall Median Delay (reachable): {overall_median_delay:.2f} ms")
    print(f"Overall Minimum Delay: {overall_min_delay:.2f} ms (GS: {best_gs_min} at timestamp {min_delay_ts})")
    print(f"Overall Maximum Delay: {overall_max_delay:.2f} ms (GS: {worst_gs_max} at timestamp {max_delay_ts})")
    print(f"Best Average Coverage GS: {best_gs_avg} ({best_avg_delay:.2f} ms avg)")
    print(f"Worst Average Coverage GS: {worst_gs_avg} ({worst_avg_delay:.2f} ms avg)")

    # Save summary to file
    with open(analysis_results_file, 'w') as f:
        f.write("--- Overall Spare Capacity Coverage Analysis ---\n\n")
        f.write(f"Overall Average Delay (reachable): {overall_avg_delay:.2f} ms\n")
        f.write(f"Overall Median Delay (reachable): {overall_median_delay:.2f} ms\n")
        f.write(f"Overall Minimum Delay: {overall_min_delay:.2f} ms (GS: {best_gs_min} at timestamp {min_delay_ts})\n")
        f.write(f"Overall Maximum Delay: {overall_max_delay:.2f} ms (GS: {worst_gs_max} at timestamp {max_delay_ts})\n")
        f.write(f"Best Average Coverage GS: {best_gs_avg} ({best_avg_delay:.2f} ms avg)\n")
        f.write(f"Worst Average Coverage GS: {worst_gs_avg} ({worst_avg_delay:.2f} ms avg)\n\n")
        f.write("--- Statistics per Timestamp (Coverage Delay) ---\n")
        f.write(stats_per_timestamp.to_string())
        f.write("\n\n")

    # --- Timing Analysis ---
    if not timing_df.empty:
        print("\n--- Analyzing Calculation Timing ---")
        min_time = timing_df['duration_s'].min()
        max_time = timing_df['duration_s'].max()
        mean_time = timing_df['duration_s'].mean()
        median_time = timing_df['duration_s'].median()
        total_time = timing_df['duration_s'].sum()

        timing_stats_text = "" # Initialize the variable
        timing_stats_text += "--- Calculation Timing Summary ---\n"
        timing_stats_text += f"Minimum Calculation Time: {min_time:.2f} s\n"
        timing_stats_text += f"Maximum Calculation Time: {max_time:.2f} s\n"
        timing_stats_text += f"Average Calculation Time: {mean_time:.2f} s\n"
        timing_stats_text += f"Median Calculation Time: {median_time:.2f} s\n"
        timing_stats_text += f"Total Calculation Time (across all timestamps): {total_time:.2f} s\n"
        timing_stats_text = "--- Calculation Timing Summary ---\n"
        timing_stats_text += f"Minimum Calculation Time: {min_time:.2f} s\n"
        timing_stats_text += f"Maximum Calculation Time: {max_time:.2f} s\n"
        timing_stats_text += f"Average Calculation Time: {mean_time:.2f} s\n"
        timing_stats_text += f"Median Calculation Time: {median_time:.2f} s\n"
        timing_stats_text += f"Total Calculation Time (across all timestamps): {total_time:.2f} s\n"
        print(timing_stats_text)

        # Append timing stats to summary file
        with open(analysis_results_file, 'a') as f:
             f.write("\n" + timing_stats_text) # Add newline before appending

        # Plot timing data
        plt.figure(figsize=(12, 6))
        plt.plot(timing_df['timestamp'], timing_df['duration_s'], label='Calculation Time (s)', marker='o', linestyle='-')
        plt.title('Spare Capacity Calculation Time Over Time')
        plt.xlabel('Timestamp')
        plt.ylabel('Duration (s)')
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        timing_plot_file = output_dir / "coverage_timing_over_time.png"
        plt.savefig(timing_plot_file)
        print(f"Timing plot saved to {timing_plot_file}")
        plt.close()
    else:
        print("Timing analysis skipped: No timing data loaded.")

    # --- Contiguity Analysis ---
    if not contiguity_df.empty:
        print("\n--- Analyzing Spare Contiguity ---")
        # Calculate overall averages/medians etc.
        avg_components = contiguity_df['num_spare_components'].mean()
        median_components = contiguity_df['num_spare_components'].median()
        avg_largest_comp_edges = contiguity_df['largest_component_edges'].mean()
        median_largest_comp_edges = contiguity_df['largest_component_edges'].median()
        avg_largest_comp_frac = contiguity_df['largest_component_fraction'].mean()
        median_largest_comp_frac = contiguity_df['largest_component_fraction'].median()
        avg_frag_ratio = contiguity_df['fragmentation_ratio'].mean()
        median_frag_ratio = contiguity_df['fragmentation_ratio'].median()
        # Add clustering coefficient stats
        avg_clust_coeff = contiguity_df['global_clustering_coefficient'].mean()
        median_clust_coeff = contiguity_df['global_clustering_coefficient'].median()


        contiguity_stats_text = "" # Initialize the variable
        contiguity_stats_text += "\n--- Spare Contiguity Summary (Averages) ---\n"
        contiguity_stats_text += f"Average Number of Spare Components: {avg_components:.1f}\n"
        contiguity_stats_text += f"Median Number of Spare Components: {median_components:.1f}\n"
        contiguity_stats_text += f"Average Largest Component Size (Edges): {avg_largest_comp_edges:.1f}\n"
        contiguity_stats_text += f"Median Largest Component Size (Edges): {median_largest_comp_edges:.1f}\n"
        contiguity_stats_text += f"Average Largest Component Fraction: {avg_largest_comp_frac*100:.1f}%\n"
        contiguity_stats_text += f"Median Largest Component Fraction: {median_largest_comp_frac*100:.1f}%\n"
        contiguity_stats_text += f"Average Fragmentation Ratio: {avg_frag_ratio:.4f}\n"
        contiguity_stats_text += f"Median Fragmentation Ratio: {median_frag_ratio:.4f}\n"
        contiguity_stats_text += f"Average Global Clustering Coefficient: {avg_clust_coeff:.4f}\n" # Add clustering
        contiguity_stats_text += f"Median Global Clustering Coefficient: {median_clust_coeff:.4f}\n" # Add clustering
        contiguity_stats_text = "\n--- Spare Contiguity Summary (Averages) ---\n"
        contiguity_stats_text += f"Average Number of Spare Components: {avg_components:.1f}\n"
        contiguity_stats_text += f"Median Number of Spare Components: {median_components:.1f}\n"
        contiguity_stats_text += f"Average Largest Component Size (Edges): {avg_largest_comp_edges:.1f}\n"
        contiguity_stats_text += f"Median Largest Component Size (Edges): {median_largest_comp_edges:.1f}\n"
        contiguity_stats_text += f"Average Largest Component Fraction: {avg_largest_comp_frac*100:.1f}%\n"
        contiguity_stats_text += f"Median Largest Component Fraction: {median_largest_comp_frac*100:.1f}%\n"
        contiguity_stats_text += f"Average Fragmentation Ratio: {avg_frag_ratio:.4f}\n"
        contiguity_stats_text += f"Median Fragmentation Ratio: {median_frag_ratio:.4f}\n"
        contiguity_stats_text += f"Average Global Clustering Coefficient: {avg_clust_coeff:.4f}\n" # Add clustering
        contiguity_stats_text += f"Median Global Clustering Coefficient: {median_clust_coeff:.4f}\n" # Add clustering
        print(contiguity_stats_text)

        # Append contiguity stats to summary file
        with open(analysis_results_file, 'a') as f:
             f.write("\n" + contiguity_stats_text) # Add newline
             f.write("\n--- Statistics per Timestamp (Contiguity) ---\n")
             f.write(contiguity_df.to_string()) # Save per-timestamp data too

        # Save contiguity data per timestamp to CSV
        contiguity_df.to_csv(output_dir / "contiguity_stats_per_timestamp.csv")
        print(f"Per-timestamp contiguity stats saved to {output_dir / 'contiguity_stats_per_timestamp.csv'}")

        # Plot contiguity data
        fig, axes = plt.subplots(4, 1, figsize=(12, 18), sharex=True) # Increased figure height for 4 plots
        sns.set_theme(style="darkgrid")

        # Plot 1: Number of components
        axes[0].plot(contiguity_df.index, contiguity_df['num_spare_components'], label='Number of Spare Components', marker='o')
        axes[0].set_ylabel('Count')
        axes[0].set_title('Number of Spare Components Over Time')
        axes[0].legend()
        axes[0].grid(True)

        # Plot 2: Largest component size (absolute and relative)
        ax2b = axes[1].twinx() # instantiate a second axes that shares the same x-axis
        line1, = axes[1].plot(contiguity_df.index, contiguity_df['largest_component_edges'], label='Largest Component Size (Edges)', marker='s', color='tab:blue')
        line2, = ax2b.plot(contiguity_df.index, contiguity_df['largest_component_fraction'] * 100, label='Largest Component Fraction (%)', marker='^', linestyle='--', color='tab:red')
        axes[1].set_ylabel('Number of Edges', color='tab:blue')
        ax2b.set_ylabel('Fraction of Total Spare Edges (%)', color='tab:red')
        axes[1].tick_params(axis='y', labelcolor='tab:blue')
        ax2b.tick_params(axis='y', labelcolor='tab:red')
        axes[1].set_title('Largest Spare Component Size Over Time')
        # Add combined legend
        lines = [line1, line2]
        axes[1].legend(lines, [l.get_label() for l in lines])
        axes[1].grid(True)


        # Plot 3: Fragmentation Ratio
        axes[2].plot(contiguity_df.index, contiguity_df['fragmentation_ratio'], label='Fragmentation Ratio', marker='x', color='tab:green')
        axes[2].set_ylabel('Components / Spare Edge')
        axes[2].set_title('Spare Area Fragmentation Over Time')
        axes[2].legend()
        axes[2].grid(True)

        # Plot 4: Global Clustering Coefficient
        axes[3].plot(contiguity_df.index, contiguity_df['global_clustering_coefficient'], label='Global Clustering Coefficient', marker='p', color='tab:purple')
        axes[3].set_ylabel('Coefficient')
        axes[3].set_title('Spare Area Clustering Over Time')
        axes[3].legend()
        axes[3].grid(True)


        plt.xlabel('Timestamp')
        plt.xticks(rotation=45)
        fig.tight_layout() # adjust subplot parameters for a tight layout
        contiguity_plot_file = output_dir / "spare_contiguity_over_time.png"
        plt.savefig(contiguity_plot_file)
        print(f"Contiguity plot saved to {contiguity_plot_file}")
        plt.close(fig)

    else:
        print("Contiguity analysis skipped: No contiguity data loaded.")


    print(f"\nAnalysis summary saved to {analysis_results_file}")
    # Print paths to all generated CSVs
    if not df.empty:
         print(f"Per-timestamp coverage stats saved to {output_dir / 'coverage_stats_per_timestamp.csv'}")
    if not contiguity_df.empty:
         print(f"Per-timestamp contiguity stats saved to {output_dir / 'contiguity_stats_per_timestamp.csv'}")

    # --- Routing Effectiveness Analysis ---
    if not routing_df.empty:
        print("\n--- Analyzing Routing Effectiveness ---")
        
        # Calculate success rate per delay factor
        success_rate = routing_df.groupby('delay_factor')['spare_path_found'].mean() * 100
        print("\nSpare Path Success Rate (%):")
        print(success_rate)

        # Analyze delay delta for successful paths
        successful_routes = routing_df[routing_df['spare_path_found']].copy()
        successful_routes['delay_delta_ms'] = successful_routes['delay_delta'] * 1000 # Convert to ms

        delta_stats = successful_routes.groupby('delay_factor')['delay_delta_ms'].agg(
            ['mean', 'median', 'min', 'max', 'std', 'count']
        )
        print("\nDelay Delta Statistics (Actual - Target) for Successful Paths (ms):")
        print(delta_stats)

        # Analyze routing duration
        duration_stats = routing_df.groupby('delay_factor')['duration_s'].agg(
            ['mean', 'median', 'min', 'max', 'std', 'count']
        )
        print("\nRouting Calculation Duration Statistics (s):")
        print(duration_stats)

        # Save stats to summary file
        routing_stats_text = "\n--- Routing Effectiveness Summary ---\n"
        routing_stats_text += "Spare Path Success Rate (%):\n"
        routing_stats_text += success_rate.to_string() + "\n\n"
        routing_stats_text += "Delay Delta Statistics (Actual - Target) for Successful Paths (ms):\n"
        routing_stats_text += delta_stats.to_string() + "\n\n"
        routing_stats_text += "Routing Calculation Duration Statistics (s):\n" # Add duration stats
        routing_stats_text += duration_stats.to_string() + "\n"

        with open(analysis_results_file, 'a') as f:
            f.write("\n" + routing_stats_text)

        # Save detailed routing stats (including duration) per factor to CSV
        routing_summary_csv = output_dir / "routing_effectiveness_summary.csv"
        summary_df = success_rate.reset_index().rename(columns={'spare_path_found': 'success_rate_percent'})
        summary_df = pd.merge(summary_df, delta_stats.reset_index(), on='delay_factor', how='left')
        summary_df = pd.merge(summary_df, duration_stats.reset_index().add_suffix('_duration'), on='delay_factor_duration', how='left') # Add duration stats
        # Clean up merged column name if needed
        if 'delay_factor_duration' in summary_df.columns:
             summary_df.drop(columns=['delay_factor_duration'], inplace=True)
             
        summary_df.to_csv(routing_summary_csv, index=False, float_format='%.4f') # Use more precision for duration
        print(f"Routing effectiveness summary saved to {routing_summary_csv}")

        # Plotting Routing Effectiveness
        # Plot 1: Success Rate
        plt.figure(figsize=(10, 5))
        sns.barplot(x=success_rate.index, y=success_rate.values)
        plt.title('Spare Path Finding Success Rate vs. Delay Factor')
        plt.xlabel('Target Delay Factor (Shortest Path * Factor)')
        plt.ylabel('Success Rate (%)')
        plt.ylim(0, 105)
        plt.grid(axis='y')
        success_plot_file = output_dir / "routing_success_rate.png"
        plt.savefig(success_plot_file)
        print(f"Routing success rate plot saved to {success_plot_file}")
        plt.close()

        # Plot 2: Delay Delta Distribution (Box Plot or Violin Plot)
        plt.figure(figsize=(12, 7))
        # Ensure delay_factor is treated as categorical for plotting
        successful_routes['delay_factor_cat'] = successful_routes['delay_factor'].astype(str)
        sns.boxplot(data=successful_routes, x='delay_factor_cat', y='delay_delta_ms', showfliers=False)
        # sns.violinplot(data=successful_routes, x='delay_factor_cat', y='delay_delta_ms')
        plt.title('Distribution of Delay Delta (Actual - Target) for Successful Spare Paths')
        plt.xlabel('Target Delay Factor')
        plt.ylabel('Delay Delta (ms)')
        plt.axhline(0, color='r', linestyle='--', label='Target Delay')
        plt.legend()
        plt.grid(axis='y')
        delta_plot_file = output_dir / "routing_delay_delta_distribution.png"
        plt.savefig(delta_plot_file)
        print(f"Routing delay delta plot saved to {delta_plot_file}")
        plt.close()

        # Plot 3: Routing Duration Distribution
        plt.figure(figsize=(12, 7))
        routing_df['delay_factor_cat'] = routing_df['delay_factor'].astype(str) # Ensure categorical
        sns.boxplot(data=routing_df, x='delay_factor_cat', y='duration_s', showfliers=False)
        plt.title('Distribution of Routing Calculation Duration')
        plt.xlabel('Target Delay Factor')
        plt.ylabel('Duration (s)')
        plt.grid(axis='y')
        duration_plot_file = output_dir / "routing_duration_distribution.png"
        plt.savefig(duration_plot_file)
        print(f"Routing duration plot saved to {duration_plot_file}")
        plt.close()

    else:
        print("Routing effectiveness analysis skipped: No routing data loaded.")

    # --- Plotting ---
    sns.set_theme(style="darkgrid")
    plt.figure(figsize=(12, 6))
    
    # Plot average and median delay over time
    plt.plot(stats_per_timestamp.index, stats_per_timestamp['mean'], label='Mean Delay (ms)', marker='o', linestyle='-')
    plt.plot(stats_per_timestamp.index, stats_per_timestamp['median'], label='Median Delay (ms)', marker='x', linestyle='--')
    
    # Add shaded area for min/max or quantiles
    plt.fill_between(stats_per_timestamp.index, stats_per_timestamp['min'], stats_per_timestamp['max'], color='b', alpha=0.1, label='Min-Max Range')
    # Or use quantiles:
    # plt.fill_between(stats_per_timestamp.index, stats_per_timestamp['q25'], stats_per_timestamp['q75'], color='g', alpha=0.2, label='IQR')

    plt.title('Ground Station Delay to Nearest Spare Node Over Time')
    plt.xlabel('Timestamp')
    plt.ylabel('Delay (ms)')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plot_file = output_dir / "coverage_delay_over_time.png"
    plt.savefig(plot_file)
    print(f"Plot saved to {plot_file}")
    plt.close()

    # Plot number of reachable/unreachable GS over time
    plt.figure(figsize=(12, 6))
    plt.plot(stats_per_timestamp.index, stats_per_timestamp['reachable_count'], label='Reachable GS', marker='o', linestyle='-')
    plt.plot(stats_per_timestamp.index, stats_per_timestamp['unreachable_count'], label='Unreachable GS', marker='x', linestyle='--')
    plt.plot(stats_per_timestamp.index, stats_per_timestamp['total_gs'], label='Total GS', marker='.', linestyle=':', color='gray')

    plt.title('Ground Station Reachability to Spare Nodes Over Time')
    plt.xlabel('Timestamp')
    plt.ylabel('Number of Ground Stations')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    reach_plot_file = output_dir / "coverage_reachability_over_time.png"
    plt.savefig(reach_plot_file)
    print(f"Reachability plot saved to {reach_plot_file}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Analyze spare capacity coverage over time.')
    parser.add_argument('base_dir', type=str,
                        help='Base directory containing timestamp results (e.g., ../positions/starlink_550_traffic_scaled/)')
    parser.add_argument('--output-dir', type=str, default='analysis_results',
                        help='Directory to save analysis results and plots')
    args = parser.parse_args()

    base_results_dir = Path(args.base_dir)
    analysis_output_dir = Path(args.output_dir)

    if not base_results_dir.is_dir():
        print(f"Error: Base directory not found: {base_results_dir}")
        return

    print(f"Loading coverage data from: {base_results_dir}")
    coverage_df = load_coverage_data(base_results_dir)
    print(f"Loading timing data from: {base_results_dir}")
    timing_df = load_timing_data(base_results_dir)
    print(f"Loading contiguity data from: {base_results_dir}")
    contiguity_df = load_contiguity_data(base_results_dir)
    print(f"Loading routing effectiveness data from: {base_results_dir}")
    routing_df = load_routing_effectiveness_data(base_results_dir)

    if not coverage_df.empty or not timing_df.empty or not contiguity_df.empty or not routing_df.empty:
        if not coverage_df.empty:
             print(f"Loaded {len(coverage_df)} coverage records.")
        if not timing_df.empty:
             print(f"Loaded {len(timing_df)} timing records.")
        if not contiguity_df.empty:
             print(f"Loaded {len(contiguity_df)} contiguity records.")
        if not routing_df.empty:
             print(f"Loaded {len(routing_df)} routing effectiveness records.")
             
        print("Starting analysis...")
        # Pass all dataframes to the analysis function
        analyze_coverage(coverage_df, timing_df, contiguity_df, routing_df, analysis_output_dir)
        print("Analysis complete.")
    else:
        print("No coverage, timing, contiguity, or routing data loaded, exiting analysis.")

if __name__ == "__main__":
    main()
