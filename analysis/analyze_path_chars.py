import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path

def analyze_characteristics(csv_filepath):
    """
    Analyzes the characteristics (spare edge usage) of spare paths.

    Args:
        csv_filepath (str): Path to the routing_effectiveness_{timestamp}.csv file.
    """
    filepath = Path(csv_filepath)
    if not filepath.is_file():
        print(f"Error: File not found at {filepath}")
        return

    print(f"Analyzing path characteristics from: {filepath}")
    df = pd.read_csv(filepath)

    # Filter for successful runs where spare paths were found and counts exist
    df_success = df[
        df['spare_path_found'] &
        df['spare_edges_count'].notna() &
        df['normal_edges_count'].notna()
    ].copy()

    if df_success.empty:
        print("No successful spare paths with edge counts found. Cannot analyze characteristics.")
        return

    print(f"Analyzing {len(df_success)} successful spare paths with edge counts.")

    # --- Calculate Spare Edge Percentage ---
    df_success['total_edges'] = df_success['spare_edges_count'] + df_success['normal_edges_count']
    df_success['spare_edge_percentage'] = df_success.apply(
        lambda row: (row['spare_edges_count'] / row['total_edges']) * 100 if row['total_edges'] > 0 else 0, axis=1
    )

    print(f"\n--- Spare Edge Usage Statistics ---")
    print("Spare Edge Percentage:")
    print(df_success['spare_edge_percentage'].describe())

    # --- Plot Distribution of Spare Edge Percentage ---
    plt.figure(figsize=(8, 5))
    sns.histplot(df_success['spare_edge_percentage'], bins=20, kde=False) # Use bins=20 or adjust as needed
    plt.title(f'Distribution of Spare Edge Usage ({filepath.stem})')
    plt.xlabel('Percentage of Spare Edges in Path (%)')
    plt.ylabel('Frequency')
    plt.xlim(0, 101)

    plot_filename_hist = filepath.parent / f"spare_usage_hist_{filepath.stem}.png"
    plt.savefig(plot_filename_hist)
    print(f"\nSaved spare usage histogram to: {plot_filename_hist}")
    # plt.show()

    # --- Analyze Spare Percentage vs. Delay Factor ---
    plt.figure(figsize=(10, 6))
    sns.boxplot(x='delay_factor', y='spare_edge_percentage', data=df_success)
    plt.title(f'Spare Edge Percentage vs. Target Delay Factor ({filepath.stem})')
    plt.xlabel('Target Delay Factor')
    plt.ylabel('Spare Edge Percentage (%)')
    plt.ylim(0, 105)

    plot_filename_box = filepath.parent / f"spare_usage_vs_factor_box_{filepath.stem}.png"
    plt.savefig(plot_filename_box)
    print(f"Saved spare usage vs factor box plot to: {plot_filename_box}")
    # plt.show()

    print("\nAnalysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze spare path characteristics (edge usage) from routing effectiveness CSV.')
    parser.add_argument('csv_file', type=str, help='Path to the routing_effectiveness_{timestamp}.csv file.')
    args = parser.parse_args()

    analyze_characteristics(args.csv_file)
