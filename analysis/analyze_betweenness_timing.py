import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path

# --- LaTeX Table Generation ---

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
            # Assuming time values in seconds
            formatted_value = f"{value:.6f}" # High precision for seconds
        latex_string += f"{label_name} & {formatted_value} \\\\\n"

    latex_string += f"\\bottomrule\n"
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"

    return latex_string

# --- Main Analysis Function ---

def analyze_betweenness_timing(base_dir: str, timestamp: int):
    """
    Analyzes the per-pair calculation time for edge betweenness for a specific timestamp.

    Args:
        base_dir (str): The base directory containing timestamp subdirectories
                        (e.g., ../positions/starlink_550_traffic_scaled/).
        timestamp (int): The specific timestamp to analyze.
    """
    base_path = Path(base_dir)
    timestamp_dir = base_path / str(timestamp)
    timing_dir = timestamp_dir / "timing_data"
    timing_csv_file = timing_dir / f"betweenness_timing_per_pair_{timestamp}.csv"

    if not timing_csv_file.is_file():
        print(f"Error: Timing file not found at {timing_csv_file}")
        return

    print(f"Analyzing betweenness per-pair timing data from: {timing_csv_file}")

    try:
        df_timing = pd.read_csv(timing_csv_file)
    except Exception as e:
        print(f"Error reading CSV file {timing_csv_file}: {e}")
        return

    if 'time_s' not in df_timing.columns:
        print(f"Error: 'time_s' column not found in {timing_csv_file}")
        return

    # Define output directory
    output_dir = timestamp_dir / "analysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Calculate and Print Statistics ---
    print("\n--- Overall Statistics for Per-Pair Calculation Time (seconds) ---")
    timing_stats = df_timing['time_s'].describe()
    print(timing_stats)

    # Identify worst performers
    n_worst = 10 # Number of worst performers to show
    worst_pairs = df_timing.nlargest(n_worst, 'time_s')

    print(f"\n--- Top {n_worst} GS Pairs with Highest Calculation Time ---")
    print(worst_pairs[['gs1', 'gs2', 'demand', 'path_found', 'time_s']])

    # --- Save LaTeX Table ---
    print("\n--- Generating LaTeX Table ---")
    try:
        caption = f"Overall Statistics for Per-Pair Edge Betweenness Calculation Time (seconds) for Timestamp {timestamp}"
        label = f"tab:betweenness_timing_stats_{timestamp}"
        latex_code = generate_summary_latex_table(timing_stats, caption, label, "Time (s)")
        table_filename = output_dir / f"betweenness_timing_stats_{timestamp}.tex"
        with open(table_filename, 'w') as f:
            f.write(latex_code)
        print(f"Saved LaTeX table to: {table_filename}")
    except Exception as e:
        print(f"Error generating LaTeX table: {e}")

    # --- Generate Plots ---
    print("\n--- Generating Plots ---")
    sns.set_theme(style="ticks", palette="pastel")

    try:
        # Histogram of per-pair times
        plt.figure(figsize=(10, 6))
        sns.histplot(df_timing['time_s'], bins=50, kde=False) # Use more bins, KDE might be slow/misleading
        plt.xlabel("Per-Pair Calculation Time (seconds)")
        plt.ylabel("Number of GS Pairs")
        # plt.title(f"Distribution of Per-Pair Betweenness Calculation Times (Timestamp {timestamp})") # Title removed for paper
        plt.grid(axis='y', alpha=0.5)
        # Consider log scale if distribution is highly skewed
        # plt.yscale('log')
        plt.tight_layout()
        hist_filename = output_dir / f"betweenness_timing_hist_{timestamp}.png"
        hist_filename_pdf = output_dir / f"betweenness_timing_hist_{timestamp}.pdf"
        plt.savefig(hist_filename)
        plt.savefig(hist_filename_pdf, format='pdf', bbox_inches='tight')
        print(f"Saved histogram of per-pair times to: {hist_filename_pdf} (and .png)")
        plt.close()

        # CDF plot of per-pair times
        plt.figure(figsize=(10, 6))
        sns.ecdfplot(data=df_timing, x="time_s")
        plt.xlabel("Per-Pair Calculation Time (seconds)")
        plt.ylabel("Cumulative Probability (CDF)")
        # plt.title(f"CDF of Per-Pair Betweenness Calculation Times (Timestamp {timestamp})") # Title removed for paper
        plt.grid(True, alpha=0.5)
        plt.tight_layout() # Use tight layout here, bbox_inches might be too slow for many points
        cdf_filename = output_dir / f"betweenness_timing_cdf_{timestamp}.png"
        cdf_filename_pdf = output_dir / f"betweenness_timing_cdf_{timestamp}.pdf"
        plt.savefig(cdf_filename)
        plt.savefig(cdf_filename_pdf, format='pdf') # Save PDF without bbox_inches first
        print(f"Saved CDF plot of per-pair times to: {cdf_filename_pdf} (and .png)")
        plt.close()

    except Exception as e:
        print(f"Error generating plots: {e}")

    print("\nAnalysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze per-pair edge betweenness calculation timing for a specific timestamp.')
    parser.add_argument('base_directory', type=str,
                        help='Base directory containing timestamp subdirectories (e.g., ../positions/starlink_550_traffic_scaled/)')
    parser.add_argument('timestamp', type=int,
                        help='The specific Unix timestamp to analyze.')
    args = parser.parse_args()

    analyze_betweenness_timing(args.base_directory, args.timestamp)

