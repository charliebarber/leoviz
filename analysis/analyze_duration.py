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

def analyze_duration(csv_filepath):
    """
    Analyzes the pathfinding duration from routing effectiveness data.

    Args:
        csv_filepath (str): Path to the routing_effectiveness_{timestamp}.csv file.
    """
    filepath = Path(csv_filepath)
    output_dir = filepath.parent # Define output_dir based on the input file path
    if not filepath.is_file():
        print(f"Error: File not found at {filepath}")
        sys.exit(1)

    print(f"Analyzing pathfinding duration from: {filepath}")
    df = pd.read_csv(filepath)

    # Check if duration column exists and has data
    if 'duration_s' not in df.columns or df['duration_s'].isna().all():
        print("Error: 'duration_s' column not found or contains no data.")
        sys.exit(1)

    # Drop rows with missing duration for analysis
    df_duration = df.dropna(subset=['duration_s']).copy()

    if df_duration.empty:
        print("No valid duration data found.")
        sys.exit(0) # Exit gracefully if no data

    print(f"Analyzing duration for {len(df_duration)} runs.")

    print(f"\n--- Pathfinding Duration Statistics (seconds) ---")
    # Calculate overall statistics
    overall_stats = df_duration['duration_s'].describe()
    print("Overall:")
    print(overall_stats.to_string(float_format="%.3f"))

    # Calculate statistics grouped by delay_factor
    print("\nBy Delay Factor:")
    duration_stats_by_factor = df_duration.groupby('delay_factor')['duration_s'].describe()
    print(duration_stats_by_factor.to_string(float_format="%.3f"))

    # Save the grouped statistics table to a CSV file
    stats_filename = output_dir / f"duration_stats_by_factor_{filepath.stem}.csv"
    try:
        duration_stats_by_factor.to_csv(stats_filename, float_format='%.3f')
        print(f"\nSaved duration statistics by factor to: {stats_filename}")
    except Exception as e:
        print(f"Error saving duration statistics CSV: {e}")

    # --- Analyze Average Duration vs. Delay Factor ---
    avg_duration_by_factor = df_duration.groupby('delay_factor')['duration_s'].mean()
    print(f"\n--- Average Duration per Delay Factor ---")
    print(avg_duration_by_factor.to_string(float_format="%.3f"))
    # Removed bar plot generation

    # --- Generate Separate CDF Plots for Duration by Delay Factor ---
    print("\nGenerating separate CDF plots for pathfinding duration per factor...")
    plt.style.use('seaborn-v0_8-paper') # Use a style suitable for papers

    delay_factors = sorted(df_duration['delay_factor'].unique())

    for factor in delay_factors:
        df_factor = df_duration[df_duration['delay_factor'] == factor]

        if df_factor.empty:
            print(f"Skipping duration plot for factor {factor:.2f} as no data is available.")
            continue

        print(f"Generating duration CDF plot for delay factor {factor:.2f}...")
        plt.figure(figsize=(6, 4)) # Adjust size as needed for paper

        sns.ecdfplot(data=df_factor, x='duration_s', color='blue') # Use a single color

        # plt.title(f'CDF of Pathfinding Duration (Factor {factor:.2f})') # Removed title
        plt.xlabel('Pathfinding Duration (seconds)')
        plt.ylabel('Cumulative Probability (CDF)')
        plt.grid(True, which='both', linestyle='--', linewidth=0.5)
        # plt.legend() # No legend needed for single line plot
        plt.tight_layout()

        # Save the plot as PDF
        plot_filename = output_dir / f"cdf_duration_s_factor_{factor:.2f}_{filepath.stem}.pdf"
        plt.savefig(plot_filename, format='pdf', bbox_inches='tight')
        print(f"Saved CDF plot to: {plot_filename}")
        plt.close() # Close the figure to free memory

    print("\nAnalysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze pathfinding duration from routing effectiveness CSV.')
    parser.add_argument('csv_file', type=str, help='Path to the routing_effectiveness_{timestamp}.csv file.')
    args = parser.parse_args()

    analyze_duration(args.csv_file)
