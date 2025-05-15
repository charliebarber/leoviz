import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path
import sys

# Configure matplotlib for PDF output and publication quality
plt.rcParams['pdf.fonttype'] = 42 # Embed fonts for PDF compatibility
plt.rcParams['ps.fonttype'] = 42

def analyze_delay_delta_cdf(csv_filepath: str):
    """
    Analyzes and plots the Cumulative Distribution Function (CDF) of the delay delta
    (spare_path_delay - target_delay) for successful spare paths, grouped by delay factor.

    Args:
        csv_filepath (str): Path to the routing_effectiveness_{timestamp}.csv file.
    """
    filepath = Path(csv_filepath).resolve()
    output_dir = filepath.parent

    if not filepath.is_file():
        print(f"Error: CSV file not found at {filepath}")
        sys.exit(1)

    print(f"Analyzing delay delta CDF from: {filepath}")

    # Load the CSV
    try:
        df = pd.read_csv(filepath)
        print(f"Loaded {len(df)} rows.")
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        sys.exit(1)

    # Filter for successful runs where spare paths were found
    df_success = df[df['spare_path_found']].copy()

    if df_success.empty:
        print("No successful spare paths found in the data. Cannot generate CDF.")
        return

    print(f"Analyzing {len(df_success)} successful spare paths.")

    # Calculate delay_delta if it doesn't exist
    if 'delay_delta' not in df_success.columns:
        print("Calculating 'delay_delta' (spare_path_delay - target_delay)...")
        df_success['delay_delta'] = df_success['spare_path_delay'] - df_success['target_delay']

    # Convert delay_delta from seconds to milliseconds for better readability on the plot
    df_success['delay_delta_ms'] = df_success['delay_delta'] * 1000

    # Drop rows where delta couldn't be calculated (e.g., NaN delays)
    initial_rows = len(df_success)
    df_success.dropna(subset=['delay_delta_ms'], inplace=True)
    removed_rows = initial_rows - len(df_success)
    if removed_rows > 0:
        print(f"Removed {removed_rows} rows due to missing delay delta values.")

    if df_success.empty:
        print("No valid delay delta data remaining after filtering.")
        return

    # --- Calculate and Print Statistics ---
    print("\n--- Delay Delta Statistics (milliseconds) by Delay Factor ---")
    # Calculate descriptive statistics grouped by delay_factor
    delay_delta_stats = df_success.groupby('delay_factor')['delay_delta_ms'].describe()

    # Print the statistics table to the console
    print(delay_delta_stats.to_string(float_format="%.3f"))

    # Save the statistics table to a CSV file
    stats_filename = output_dir / f"delay_delta_stats_{filepath.stem}.csv"
    try:
        delay_delta_stats.to_csv(stats_filename, float_format='%.3f')
        print(f"\nSaved delay delta statistics to: {stats_filename}")
    except Exception as e:
        print(f"Error saving statistics CSV: {e}")
    # ------------------------------------

    # --- Generate Separate CDF Plots for Each Delay Factor ---
    print("\nGenerating separate CDF plots for delay delta per factor...")
    plt.style.use('seaborn-v0_8-paper') # Use a style suitable for papers

    delay_factors = sorted(df_success['delay_factor'].unique())

    for factor in delay_factors:
        df_factor = df_success[df_success['delay_factor'] == factor]

        if df_factor.empty:
            print(f"Skipping plot for factor {factor:.2f} as no data is available.")
            continue

        print(f"Generating CDF plot for delay factor {factor:.2f}...")
        plt.figure(figsize=(6, 4)) # Adjust size as needed for paper

        sns.ecdfplot(data=df_factor, x='delay_delta_ms', color='blue') # Use a single color

        # plt.title(f'CDF of Delay Delta (Factor {factor:.2f})') # Removed title
        plt.xlabel('Delay Delta (ms)')
        plt.ylabel('Cumulative Probability (CDF)')
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        plt.axvline(0, color='red', linestyle='--', linewidth=1, label='Target Met (Delta=0)')
        # plt.legend() # No legend needed for single line plot
        plt.tight_layout()

        # Save the plot as PDF
        plot_filename = output_dir / f"cdf_delay_delta_ms_factor_{factor:.2f}_{filepath.stem}.pdf"
        plt.savefig(plot_filename, format='pdf', bbox_inches='tight')
        print(f"Saved CDF plot to: {plot_filename}")
        plt.close() # Close the figure to free memory

    print("\nAnalysis complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Generate CDF plots for spare path delay delta grouped by delay factor.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('csv_file', type=str, help='Path to the routing_effectiveness_{timestamp}.csv file.')
    args = parser.parse_args()

    analyze_delay_delta_cdf(args.csv_file)
