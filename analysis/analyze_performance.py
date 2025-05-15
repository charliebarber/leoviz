import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path

def generate_latex_table(data: pd.Series, caption: str, label: str, value_col_name: str) -> str:
    """Generates a LaTeX table string from a pandas Series."""
    
    latex_string = f"\\begin{{table}}[htbp]\n"
    latex_string += f"\\centering\n"
    latex_string += f"\\caption{{{caption}}}\n"
    latex_string += f"\\label{{{label}}}\n"
    
    # Start tabular environment (adjust columns as needed)
    latex_string += f"\\begin{{tabular}}{{cc}}\n"
    latex_string += f"\\toprule\n" # Use booktabs style
    
    # Header row
    header = data.index.name if data.index.name else "Delay Factor" # Use index name or default
    latex_string += f"{header} & {value_col_name} \\\\\n"
    latex_string += f"\\midrule\n" # Use booktabs style
    
    # Data rows
    for index, value in data.items():
        # Format factor and the value (e.g., delay delta in ms)
        latex_string += f"{index:.2f} & {value:.3f} \\\\\n" 
        
    # End tabular and table environments
    latex_string += f"\\bottomrule\n" # Use booktabs style
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"
    
    return latex_string

def analyze_performance(csv_filepath):
    """
    Analyzes the performance trade-offs (delay, distance) of spare paths.

    Args:
        csv_filepath (str): Path to the routing_effectiveness_{timestamp}.csv file.
    """
    filepath = Path(csv_filepath)
    if not filepath.is_file():
        print(f"Error: File not found at {filepath}")
        return

    print(f"Analyzing performance from: {filepath}")
    df = pd.read_csv(filepath)

    # Filter for successful runs where spare paths were found
    df_success = df[df['spare_path_found']].copy()

    if df_success.empty:
        print("No successful spare paths found in the data. Cannot analyze performance.")
        return

    print(f"Analyzing {len(df_success)} successful spare paths.")

    # --- Calculate Actual Increase Ratios ---
    # Avoid division by zero if shortest path delay/dist is somehow zero
    df_success['actual_delay_increase_ratio'] = df_success.apply(
        lambda row: row['spare_path_delay'] / row['shortest_path_delay'] if row['shortest_path_delay'] > 0 else np.nan, axis=1
    )
    df_success['actual_distance_increase_ratio'] = df_success.apply(
        lambda row: row['spare_path_dist'] / row['shortest_path_dist'] if row['shortest_path_dist'] > 0 else np.nan, axis=1
    )
    # Convert ratios to percentages for easier interpretation if desired
    df_success['actual_delay_increase_pct'] = (df_success['actual_delay_increase_ratio'] - 1) * 100
    df_success['actual_distance_increase_pct'] = (df_success['actual_distance_increase_ratio'] - 1) * 100

    # Drop rows where calculation failed (e.g., due to NaN or zero shortest path)
    df_success.dropna(subset=['actual_delay_increase_ratio', 'actual_distance_increase_ratio'], inplace=True)

    if df_success.empty:
        print("No valid data remaining after calculating increase ratios.")
        return

    print(f"\n--- Performance Increase Statistics (Ratio: Spare/Shortest) ---")
    print("Delay Increase Ratio:")
    print(df_success['actual_delay_increase_ratio'].describe())
    print("\nDistance Increase Ratio:")
    print(df_success['actual_distance_increase_ratio'].describe())

    # --- Plot Distributions of Increases ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    sns.histplot(df_success['actual_delay_increase_ratio'], bins=30, kde=True, ax=axes[0])
    axes[0].set_title(f'Distribution of Actual Delay Increase Ratio ({filepath.stem})')
    axes[0].set_xlabel('Spare Path Delay / Shortest Path Delay')
    axes[0].set_ylabel('Frequency')

    sns.histplot(df_success['actual_distance_increase_ratio'], bins=30, kde=True, ax=axes[1])
    axes[1].set_title(f'Distribution of Actual Distance Increase Ratio ({filepath.stem})')
    axes[1].set_xlabel('Spare Path Distance / Shortest Path Distance')
    axes[1].set_ylabel('Frequency')

    plt.tight_layout()
    plot_filename_hist = filepath.parent / f"performance_increase_hist_{filepath.stem}.png"
    plt.savefig(plot_filename_hist)
    print(f"\nSaved performance increase histograms to: {plot_filename_hist}")
    # plt.show()

    # --- Plot Increase vs. Delay Factor ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    sns.boxplot(x='delay_factor', y='actual_delay_increase_ratio', data=df_success, ax=axes[0])
    axes[0].set_title(f'Actual Delay Increase Ratio vs. Target Factor ({filepath.stem})')
    axes[0].set_xlabel('Target Delay Factor')
    axes[0].set_ylabel('Actual Delay Ratio (Spare/Shortest)')

    sns.boxplot(x='delay_factor', y='actual_distance_increase_ratio', data=df_success, ax=axes[1])
    axes[1].set_title(f'Actual Distance Increase Ratio vs. Target Factor ({filepath.stem})')
    axes[1].set_xlabel('Target Delay Factor')
    axes[1].set_ylabel('Actual Distance Ratio (Spare/Shortest)')

    plt.tight_layout()
    plot_filename_box = filepath.parent / f"performance_vs_factor_box_{filepath.stem}.png"
    plt.savefig(plot_filename_box)
    print(f"Saved performance vs factor box plots to: {plot_filename_box}")
    # plt.show()

    # --- Scatter Plots: Shortest vs. Spare ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Delay Scatter
    max_delay = max(df_success['shortest_path_delay'].max(), df_success['spare_path_delay'].max()) * 1.05
    sns.scatterplot(x='shortest_path_delay', y='spare_path_delay', data=df_success, alpha=0.5, ax=axes[0])
    axes[0].plot([0, max_delay], [0, max_delay], color='red', linestyle='--', label='y=x (Shortest = Spare)') # y=x line
    axes[0].set_title(f'Spare Path Delay vs. Shortest Path Delay ({filepath.stem})')
    axes[0].set_xlabel('Shortest Path Delay (s)')
    axes[0].set_ylabel('Spare Path Delay (s)')
    axes[0].set_xlim(0, max_delay)
    axes[0].set_ylim(0, max_delay)
    axes[0].legend()
    axes[0].grid(True)

    # Distance Scatter
    max_dist = max(df_success['shortest_path_dist'].max(), df_success['spare_path_dist'].max()) * 1.05
    sns.scatterplot(x='shortest_path_dist', y='spare_path_dist', data=df_success, alpha=0.5, ax=axes[1])
    axes[1].plot([0, max_dist], [0, max_dist], color='red', linestyle='--', label='y=x (Shortest = Spare)') # y=x line
    axes[1].set_title(f'Spare Path Distance vs. Shortest Path Distance ({filepath.stem})')
    axes[1].set_xlabel('Shortest Path Distance (m)')
    axes[1].set_ylabel('Spare Path Distance (m)')
    axes[1].ticklabel_format(style='sci', axis='both', scilimits=(0,0)) # Use scientific notation
    axes[1].set_xlim(0, max_dist)
    axes[1].set_ylim(0, max_dist)
    axes[1].legend()
    axes[1].grid(True)

    plt.tight_layout()
    plot_filename_scatter = filepath.parent / f"performance_scatter_{filepath.stem}.png"
    plt.savefig(plot_filename_scatter)
    print(f"Saved performance scatter plots to: {plot_filename_scatter}")
    # plt.show()

    # --- Analyze Delay Delta ---
    print(f"\n--- Delay Delta Analysis (spare_path_delay - target_delay) ---")
    # Ensure 'delay_delta' column exists and is calculated correctly
    if 'delay_delta' not in df_success.columns:
        # Calculate if missing (might happen if script was run before delta was added)
        df_success['delay_delta'] = df_success['spare_path_delay'] - df_success['target_delay']

    # Drop rows where delta couldn't be calculated
    df_delta_valid = df_success.dropna(subset=['delay_delta'])

    if df_delta_valid.empty:
        print("No valid delay delta data found.")
    else:
        print("Delay Delta Statistics (seconds):")
        print(df_delta_valid['delay_delta'].describe())

        # Calculate average delay delta per factor
        avg_delay_delta_by_factor = df_delta_valid.groupby('delay_factor')['delay_delta'].mean()
        print("\nAverage Delay Delta per Delay Factor (seconds):")
        print(avg_delay_delta_by_factor)

        # --- Generate and Save LaTeX Table for Average Delay Delta ---
        latex_table_filename = filepath.parent / f"average_delay_delta_table_{filepath.stem}.tex"
        try:
            table_caption = f"Average Delay Delta (Spare Path Delay - Target Delay) vs. Target Delay Factor ({filepath.stem.replace('_', ' ')})"
            table_label = f"tab:avg_delay_delta_{filepath.stem}"
            # Convert seconds to milliseconds for the table for readability
            latex_code = generate_latex_table(avg_delay_delta_by_factor * 1000, table_caption, table_label, "Avg. Delay Delta (ms)")
            with open(latex_table_filename, 'w') as f_tex:
                f_tex.write(latex_code)
            print(f"\nSaved LaTeX table for average delay delta to: {latex_table_filename}")
        except Exception as e:
            print(f"Error saving average delay delta LaTeX table: {e}")
        # ----------------------------------------------------------

    print("\nAnalysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze spare path performance trade-offs from routing effectiveness CSV.')
    parser.add_argument('csv_file', type=str, help='Path to the routing_effectiveness_{timestamp}.csv file.')
    args = parser.parse_args()

    analyze_performance(args.csv_file)
