import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path
import re # For extracting timestamp

# --- LaTeX Table Generation (Adapted from analyze_contiguity.py) ---

def generate_summary_latex_table(stats: pd.Series, caption: str, label: str, column_name: str) -> str:
    """Generates a LaTeX table string for summary statistics (describe output)."""

    latex_string = f"\\begin{{table}}[htbp]\n"
    latex_string += f"\\centering\n"
    latex_string += f"\\caption{{{caption}}}\n"
    latex_string += f"\\label{{{label}}}\n"
    latex_string += f"\\begin{{tabular}}{{lr}}\n" # l for label, r for right-aligned number
    latex_string += f"\\toprule\n"
    latex_string += f"Statistic & {column_name} \\\\\n"
    latex_string += f"\\midrule\n"

    # Map index names to more descriptive labels
    stat_labels = {
        'count': 'Count',
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
        # Format numbers appropriately
        if index == 'count':
            formatted_value = f"{int(value):,}"
        else:
            # Assuming delay values in ms
            formatted_value = f"{value:.4f}" # Increase precision for potential timing values too
        latex_string += f"{label_name} & {formatted_value} \\\\\n"

    latex_string += f"\\bottomrule\n"
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"

    return latex_string

def generate_worst_gs_latex_table(df_worst: pd.DataFrame, caption: str, label: str, metric_col: str, unit: str) -> str:
    """Generates a LaTeX table for worst-performing GSes."""
    latex_string = f"\\begin{{table}}[htbp]\n"
    latex_string += f"\\centering\n"
    latex_string += f"\\caption{{{caption}}}\n"
    latex_string += f"\\label{{{label}}}\n"
    # Adjust columns based on DataFrame: GS ID, Mean Delay, Max Delay
    latex_string += f"\\begin{{tabular}}{{lrr}}\n" # GS ID, Mean Value, Max Value
    latex_string += f"\\toprule\n"
    latex_string += f"Ground Station ID & Mean {metric_col} ({unit}) & Max {metric_col} ({unit}) \\\\\n"
    latex_string += f"\\midrule\n"

    for index, row in df_worst.iterrows():
        gs_id = index
        mean_delay = row['mean']
        max_delay = row['max']
        # Use more precision for timing if needed
        latex_string += f"{gs_id} & {mean_delay:.4f} & {max_delay:.4f} \\\\\n"

    latex_string += f"\\bottomrule\n"
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"
    return latex_string

# --- Main Analysis Function ---

def analyze_gs_delay(base_dir: str):
    """
    Analyzes the minimum delay and calculation time from Ground Stations (GS)
    to the nearest spare node.

    Args:
        base_dir (str): The base directory containing timestamp subdirectories
                        (e.g., ../positions/starlink_550_traffic_scaled/).
    """
    base_path = Path(base_dir)
    if not base_path.is_dir():
        print(f"Error: Base directory not found at {base_path}")
        return

    print(f"Analyzing GS delay data in: {base_path}")

    # Find all gs_delays CSV files
    delay_files = list(base_path.rglob('coverage_data/gs_delays_*.csv'))

    if not delay_files:
        print("Error: No 'gs_delays_*.csv' files found in coverage_data subdirectories.")
        return

    print(f"Found {len(delay_files)} GS delay files.")

    all_dfs = []
    # Regex to extract timestamp from filename
    timestamp_regex = re.compile(r'gs_delays_(\d+)\.csv')

    for file in delay_files:
        match = timestamp_regex.search(file.name)
        if match:
            timestamp = int(match.group(1))
            try:
                df_ts = pd.read_csv(file)
                # Check if 'calc_time_ms' column exists, add if not for backward compatibility
                if 'calc_time_ms' not in df_ts.columns:
                    print(f"Warning: 'calc_time_ms' column not found in {file}. Adding NaN column.")
                    df_ts['calc_time_ms'] = np.nan
                df_ts['timestamp'] = timestamp
                all_dfs.append(df_ts)
            except Exception as e:
                print(f"Warning: Could not read or parse file {file}: {e}")
        else:
            print(f"Warning: Could not extract timestamp from filename {file.name}")

    if not all_dfs:
        print("Error: No valid GS delay data could be read.")
        return

    # Concatenate all data
    df_all = pd.concat(all_dfs, ignore_index=True)
    num_timestamps = df_all['timestamp'].nunique()
    num_gs = df_all['gs_id'].nunique()
    print(f"Data loaded for {num_gs} ground stations across {num_timestamps} timestamps.")

    # Define output directory
    output_dir = base_path / "analysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Per-Timestamp Analysis ---
    print("\n--- Analyzing Metrics Per Timestamp ---")
    df_ts_delay_stats = df_all.groupby('timestamp')['delay_ms'].describe()
    df_ts_time_stats = df_all.groupby('timestamp')['calc_time_ms'].describe()
    print("Summary statistics of delays across all GS per timestamp:")
    print(df_ts_delay_stats[['mean', '50%', 'min', 'max']].head()) # Show head for brevity
    print("\nSummary statistics of calculation times across all GS per timestamp:")
    print(df_ts_time_stats[['mean', '50%', 'min', 'max']].head()) # Show head for brevity


    # --- 2. Per-GS Analysis ---
    print("\n--- Analyzing Metrics Per Ground Station (Across Time) ---")
    df_gs_delay_stats = df_all.groupby('gs_id')['delay_ms'].describe()
    df_gs_time_stats = df_all.groupby('gs_id')['calc_time_ms'].describe()
    print("Summary statistics of delays for each GS across all timestamps:")
    print(df_gs_delay_stats.head()) # Show head for brevity
    print("\nSummary statistics of calculation times for each GS across all timestamps:")
    print(df_gs_time_stats.head()) # Show head for brevity

    # --- Overall Stats (based on per-GS averages) ---
    print("\nOverall statistics of the average delay per GS:")
    overall_gs_avg_delay_stats = df_gs_delay_stats['mean'].describe()
    print(overall_gs_avg_delay_stats)

    # Also calculate overall stats for the maximum delay experienced by each GS
    print("\nOverall statistics of the maximum delay per GS:")
    overall_gs_max_delay_stats = df_gs_delay_stats['max'].describe()
    print(overall_gs_max_delay_stats)

    print("\nOverall statistics of the average calculation time per GS:")
    overall_gs_avg_time_stats = df_gs_time_stats['mean'].describe()
    print(overall_gs_avg_time_stats)

    print("\nOverall statistics of the maximum calculation time per GS:")
    overall_gs_max_time_stats = df_gs_time_stats['max'].describe()
    print(overall_gs_max_time_stats)

    # --- Identify Worst Performers ---
    n_worst = 5 # Number of worst performers to show
    # Delay
    worst_avg_delay_gs = df_gs_delay_stats.nlargest(n_worst, 'mean')
    worst_max_delay_gs = df_gs_delay_stats.nlargest(n_worst, 'max')
    worst_delay_combined_ids = worst_avg_delay_gs.index.union(worst_max_delay_gs.index)
    df_worst_delay_combined = df_gs_delay_stats.loc[worst_delay_combined_ids]
    # Timing
    worst_avg_time_gs = df_gs_time_stats.nlargest(n_worst, 'mean')
    worst_max_time_gs = df_gs_time_stats.nlargest(n_worst, 'max')
    worst_time_combined_ids = worst_avg_time_gs.index.union(worst_max_time_gs.index)
    df_worst_time_combined = df_gs_time_stats.loc[worst_time_combined_ids]

    print(f"\n--- Top {n_worst} GSes with Highest Average Delay ---")
    print(worst_avg_delay_gs[['mean', 'std', 'min', 'max']])
    print(f"\n--- Top {n_worst} GSes with Highest Maximum Delay ---")
    print(worst_max_delay_gs[['mean', 'std', 'min', 'max']])
    print(f"\n--- Top {n_worst} GSes with Highest Average Calculation Time ---")
    print(worst_avg_time_gs[['mean', 'std', 'min', 'max']])
    print(f"\n--- Top {n_worst} GSes with Highest Maximum Calculation Time ---")
    print(worst_max_time_gs[['mean', 'std', 'min', 'max']])

    # --- 3. Save LaTeX Tables ---
    print("\n--- Generating LaTeX Tables ---")
    try:
        # Table for overall stats of the AVERAGE delay per GS
        caption = f"Overall Statistics for Average GS Delay to Nearest Spare Node (ms) across {num_gs} GS and {num_timestamps} timestamps"
        label = "tab:gs_delay_overall_avg_per_gs"
        latex_code = generate_summary_latex_table(overall_gs_avg_delay_stats, caption, label, "Delay (ms)")
        with open(output_dir / "gs_delay_overall_avg_per_gs_table.tex", 'w') as f:
            f.write(latex_code)
        print(f"Saved LaTeX table to: {output_dir / 'gs_delay_overall_avg_per_gs_table.tex'}")

        # Table for overall stats of the MAXIMUM delay per GS
        caption = f"Overall Statistics for Maximum GS Delay to Nearest Spare Node (ms) across {num_gs} GS and {num_timestamps} timestamps"
        label = "tab:gs_delay_overall_max_per_gs"
        latex_code = generate_summary_latex_table(overall_gs_max_delay_stats, caption, label, "Delay (ms)")
        with open(output_dir / "gs_delay_overall_max_per_gs_table.tex", 'w') as f:
            f.write(latex_code)
        print(f"Saved LaTeX table to: {output_dir / 'gs_delay_overall_max_per_gs_table.tex'}")

        # Table for worst performing GSes (Delay)
        caption = f"Worst Performing Ground Stations based on Mean and Maximum Delay to Spare Network (ms) across {num_timestamps} timestamps"
        label = "tab:gs_delay_worst_performers"
        latex_code = generate_worst_gs_latex_table(df_worst_delay_combined, caption, label, "Delay", "ms")
        with open(output_dir / "gs_delay_worst_performers_table.tex", 'w') as f:
            f.write(latex_code)
        print(f"Saved LaTeX table to: {output_dir / 'gs_delay_worst_performers_table.tex'}")

        # Table for overall stats of the AVERAGE calculation time per GS
        caption = f"Overall Statistics for Average GS Calculation Time to Find Nearest Spare Node (ms) across {num_gs} GS and {num_timestamps} timestamps"
        label = "tab:gs_timing_overall_avg_per_gs"
        latex_code = generate_summary_latex_table(overall_gs_avg_time_stats, caption, label, "Calc. Time (ms)")
        with open(output_dir / "gs_timing_overall_avg_per_gs_table.tex", 'w') as f:
            f.write(latex_code)
        print(f"Saved LaTeX table to: {output_dir / 'gs_timing_overall_avg_per_gs_table.tex'}")

        # Table for worst performing GSes (Timing)
        caption = f"Worst Performing Ground Stations based on Mean and Maximum Calculation Time to Find Nearest Spare Node (ms) across {num_timestamps} timestamps"
        label = "tab:gs_timing_worst_performers"
        latex_code = generate_worst_gs_latex_table(df_worst_time_combined, caption, label, "Calc. Time", "ms")
        with open(output_dir / "gs_timing_worst_performers_table.tex", 'w') as f:
            f.write(latex_code)
        print(f"Saved LaTeX table to: {output_dir / 'gs_delay_worst_performers_table.tex'}")

    except Exception as e:
        print(f"Error generating LaTeX tables: {e}")

    # --- 4. Generate Plots ---
    print("\n--- Generating Plots ---")
    sns.set_theme(style="ticks", palette="pastel")

    try:
        # Histogram of average delays per GS
        plt.figure(figsize=(10, 6))
        sns.histplot(df_gs_delay_stats['mean'], bins=30, kde=True)
        plt.xlabel("Average Delay to Nearest Spare Node (ms)")
        plt.ylabel("Number of Ground Stations")
        plt.title(f"Distribution of Average Delays per GS across {num_timestamps} Timestamps")
        plt.grid(axis='y', alpha=0.5)
        plt.tight_layout()
        hist_filename = output_dir / "gs_delay_avg_per_gs_hist.png"
        hist_filename_pdf = output_dir / "gs_delay_avg_per_gs_hist.pdf"
        plt.savefig(hist_filename)
        plt.savefig(hist_filename_pdf, format='pdf')
        print(f"Saved histogram of average GS delays to: {hist_filename_pdf} (and .png)")
        plt.close()

        # Box plot of average delays per GS
        plt.figure(figsize=(8, 6))
        sns.boxplot(y=df_gs_delay_stats['mean'])
        plt.ylabel("Average Delay to Nearest Spare Node (ms)")
        plt.title(f"Distribution of Average Delays per GS across {num_timestamps} Timestamps")
        plt.grid(axis='y', alpha=0.5)
        plt.tight_layout()
        box_filename = output_dir / "gs_delay_avg_per_gs_boxplot.png"
        box_filename_pdf = output_dir / "gs_delay_avg_per_gs_boxplot.pdf"
        plt.savefig(box_filename)
        plt.savefig(box_filename_pdf, format='pdf')
        print(f"Saved boxplot of average GS delays to: {box_filename_pdf} (and .png)")
        plt.close()

        # Histogram of average calculation times per GS
        plt.figure(figsize=(10, 6))
        sns.histplot(df_gs_time_stats['mean'], bins=30, kde=True)
        plt.xlabel("Average Calculation Time to Find Nearest Spare Node (ms)")
        plt.ylabel("Number of Ground Stations")
        plt.title(f"Distribution of Average Calculation Times per GS across {num_timestamps} Timestamps")
        plt.grid(axis='y', alpha=0.5)
        plt.tight_layout()
        hist_filename = output_dir / "gs_timing_avg_per_gs_hist.png"
        hist_filename_pdf = output_dir / "gs_timing_avg_per_gs_hist.pdf"
        plt.savefig(hist_filename)
        plt.savefig(hist_filename_pdf, format='pdf')
        print(f"Saved histogram of average GS calculation times to: {hist_filename_pdf} (and .png)")
        plt.close()

        # Box plot of average calculation times per GS
        plt.figure(figsize=(8, 6))
        sns.boxplot(y=df_gs_time_stats['mean'])
        plt.ylabel("Average Calculation Time to Find Nearest Spare Node (ms)")
        plt.title(f"Distribution of Average Calculation Times per GS across {num_timestamps} Timestamps")
        plt.grid(axis='y', alpha=0.5)
        plt.tight_layout()
        box_filename = output_dir / "gs_timing_avg_per_gs_boxplot.png"
        box_filename_pdf = output_dir / "gs_timing_avg_per_gs_boxplot.pdf"
        plt.savefig(box_filename)
        plt.savefig(box_filename_pdf, format='pdf')
        print(f"Saved boxplot of average GS calculation times to: {box_filename_pdf} (and .png)")
        plt.close()

        # CDF plot for average calculation times per GS
        plt.figure(figsize=(10, 6)) # Standard figure size
        sns.ecdfplot(data=df_gs_time_stats, x="mean")
        plt.xlabel("Average Calculation Time per GS (ms)")
        plt.ylabel("Cumulative Probability (CDF)")
        # Title removed as per request
        plt.grid(True, alpha=0.5)
        plt.tight_layout()

        avg_cdf_filename_png = output_dir / "gs_timing_avg_per_gs_cdf.png"
        avg_cdf_filename_pdf = output_dir / "gs_timing_avg_per_gs_cdf.pdf"
        
        plt.savefig(avg_cdf_filename_png, bbox_inches='tight')
        plt.savefig(avg_cdf_filename_pdf, format='pdf', bbox_inches='tight')
        print(f"Saved CDF plot of average GS calculation times to: {avg_cdf_filename_pdf} (and .png)")
        plt.close()

        # CDF plot for maximum calculation times per GS
        plt.figure(figsize=(10, 6)) # Standard figure size
        sns.ecdfplot(data=df_gs_time_stats, x="max")
        plt.xlabel("Maximum Calculation Time per GS (ms)")
        plt.ylabel("Cumulative Probability (CDF)")
        # Title removed as per request
        plt.grid(True, alpha=0.5)
        plt.tight_layout()

        max_cdf_filename_png = output_dir / "gs_timing_max_per_gs_cdf.png"
        max_cdf_filename_pdf = output_dir / "gs_timing_max_per_gs_cdf.pdf"
        
        plt.savefig(max_cdf_filename_png, bbox_inches='tight')
        plt.savefig(max_cdf_filename_pdf, format='pdf', bbox_inches='tight')
        print(f"Saved CDF plot of maximum GS calculation times to: {max_cdf_filename_pdf} (and .png)")
        plt.close()


    except Exception as e:
        print(f"Error generating plots: {e}")

    print("\nAnalysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze Ground Station delay and calculation time to the nearest spare network node.')
    parser.add_argument('base_directory', type=str,
                        help='Base directory containing timestamp subdirectories with coverage_data folders (e.g., ../positions/starlink_550_traffic_scaled/)')
    args = parser.parse_args()

    analyze_gs_delay(args.base_directory)
