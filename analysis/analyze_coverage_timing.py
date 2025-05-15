import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path
import re # For extracting timestamp

def generate_timing_latex_table(stats: pd.Series, caption: str, label: str) -> str:
    """Generates a LaTeX table string for timing summary statistics."""
    
    latex_string = f"\\begin{{table}}[htbp]\n"
    latex_string += f"\\centering\n"
    latex_string += f"\\caption{{{caption}}}\n"
    latex_string += f"\\label{{{label}}}\n"
    latex_string += f"\\begin{{tabular}}{{lr}}\n" # l for label, r for right-aligned number
    latex_string += f"\\toprule\n"
    latex_string += f"Statistic & Duration (s) \\\\\n"
    latex_string += f"\\midrule\n"
    
    # Map index names to more descriptive labels
    stat_labels = {
        'count': 'Number of Timestamps',
        'mean': 'Mean',
        'std': 'Std. Dev.',
        'min': 'Minimum',
        '25%': '25th Percentile',
        '50%': 'Median (50%)',
        '75%': '75th Percentile',
        'max': 'Maximum'
    }
    
    # Iterate through the stats Series
    for index, value in stats.items():
        label_name = stat_labels.get(index, index)
        if index == 'count':
            formatted_value = f"{int(value):,}"
        else:
            formatted_value = f"{value:.3f}" # Show more precision for seconds
        latex_string += f"{label_name} & {formatted_value} \\\\\n"
        
    latex_string += f"\\bottomrule\n"
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"
    
    return latex_string

def analyze_timing(base_dir: str):
    """
    Analyzes the computation time for spare capacity coverage calculation
    across multiple timestamps.

    Args:
        base_dir (str): The base directory containing timestamp subdirectories
                        (e.g., ../positions/starlink_550_traffic_scaled/).
    """
    base_path = Path(base_dir)
    if not base_path.is_dir():
        print(f"Error: Base directory not found at {base_path}")
        return

    print(f"Analyzing coverage timing data in: {base_path}")

    timing_files = list(base_path.rglob('coverage_data/coverage_timing_*.txt'))

    if not timing_files:
        print("Error: No 'coverage_timing_*.txt' files found in subdirectories.")
        return

    print(f"Found {len(timing_files)} timing files.")

    durations = []
    timestamps = []
    # Regex to extract timestamp from filename
    timestamp_pattern = re.compile(r'coverage_timing_(\d+)\.txt')

    for file in timing_files:
        match = timestamp_pattern.search(file.name)
        if match:
            timestamps.append(int(match.group(1)))
            try:
                with open(file, 'r') as f:
                    duration = float(f.readline().strip())
                    durations.append(duration)
            except Exception as e:
                print(f"Warning: Could not read or parse file {file}: {e}")
        else:
            print(f"Warning: Could not extract timestamp from filename {file.name}")


    if not durations:
        print("Error: No valid duration data could be read.")
        return

    # Create a DataFrame for easier analysis and plotting
    df_timing = pd.DataFrame({'timestamp': timestamps, 'duration_s': durations})
    df_timing.sort_values('timestamp', inplace=True)

    print(f"\n--- Spare Capacity Calculation Timing Statistics (seconds) ---")
    timing_stats = df_timing['duration_s'].describe()
    print(timing_stats)

    # Define output directory (place results in the base analysis dir for aggregation)
    output_dir = base_path / "analysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Save Summary Stats to Text File ---
    summary_filename = output_dir / "coverage_timing_summary.txt"
    try:
        with open(summary_filename, 'w') as f_summary:
            f_summary.write("Spare Capacity Calculation Timing Summary\n")
            f_summary.write("=========================================\n\n")
            f_summary.write(f"Data sourced from: {base_path}\n")
            f_summary.write(f"Number of timestamps analyzed: {len(df_timing)}\n\n")
            f_summary.write("Timing Statistics (seconds):\n")
            f_summary.write(timing_stats.to_string())
        print(f"\nSaved timing summary to: {summary_filename}")
    except Exception as e:
        print(f"Error saving timing summary: {e}")
    # ---------------------------------------

    # --- Generate and Save LaTeX Table for Stats ---
    latex_table_filename = output_dir / "coverage_timing_table.tex"
    try:
        table_caption = f"Summary Statistics for Spare Capacity Calculation Time"
        table_label = f"tab:coverage_timing_summary"
        latex_code = generate_timing_latex_table(timing_stats, table_caption, table_label)
        with open(latex_table_filename, 'w') as f_tex:
            f_tex.write(latex_code)
        print(f"Saved LaTeX table for stats to: {latex_table_filename}")
    except Exception as e:
        print(f"Error saving LaTeX table: {e}")
    # ---------------------------------------------

    # --- Plot Distribution of Duration ---
    plt.figure(figsize=(10, 6))
    sns.histplot(df_timing['duration_s'], bins=20, kde=True)
    plt.title('Distribution of Spare Capacity Calculation Time')
    plt.xlabel('Duration (seconds)')
    plt.ylabel('Frequency (Number of Timestamps)')
    plt.grid(axis='y', alpha=0.5)

    plot_filename_hist = output_dir / "coverage_timing_hist.png"
    plt.savefig(plot_filename_hist)
    print(f"Saved duration histogram to: {plot_filename_hist}")
    # plt.show()

    # --- Plot Duration over Time (Optional) ---
    # plt.figure(figsize=(12, 6))
    # plt.plot(pd.to_datetime(df_timing['timestamp'], unit='s'), df_timing['duration_s'], marker='o', linestyle='-')
    # plt.title('Spare Capacity Calculation Time over Timestamps')
    # plt.xlabel('Timestamp')
    # plt.ylabel('Duration (seconds)')
    # plt.grid(True)
    # plt.xticks(rotation=45)
    # plt.tight_layout()
    # plot_filename_ts = output_dir / "coverage_timing_timeseries.png"
    # plt.savefig(plot_filename_ts)
    # print(f"Saved duration time series plot to: {plot_filename_ts}")
    # plt.show()

    print("\nAnalysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze spare capacity calculation timing across multiple timestamps.')
    parser.add_argument('base_directory', type=str,
                        help='Base directory containing timestamp subdirectories (e.g., ../positions/starlink_550_traffic_scaled/)')
    args = parser.parse_args()

    analyze_timing(args.base_directory)
