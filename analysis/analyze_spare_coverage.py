import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import argparse
from pathlib import Path
import numpy as np

def analyze_coverage(delay_csv_filepath: str, cities_csv_filepath: str = 'skyfield/cities.csv'):
    """
    Analyzes and visualizes the geographic coverage of spare capacity based on GS delays.

    Args:
        delay_csv_filepath (str): Path to the gs_delays_{timestamp}.csv file.
        cities_csv_filepath (str): Path to the cities.csv file containing GS locations.
    """
    delay_file = Path(delay_csv_filepath)
    cities_file = Path(cities_csv_filepath)

    if not delay_file.is_file():
        print(f"Error: Delay file not found at {delay_file}")
        return
    if not cities_file.is_file():
        print(f"Error: Cities file not found at {cities_file}")
        return

    print(f"Analyzing spare coverage from: {delay_file}")
    print(f"Using city locations from: {cities_file}")

    # Load data
    df_delays = pd.read_csv(delay_file)
    df_cities = pd.read_csv(cities_file)

    # Prepare data for merging
    # Ensure gs_id in delays is string, id in cities is int/string compatible
    df_delays['gs_id'] = df_delays['gs_id'].astype(str)
    df_cities['id'] = df_cities['id'].astype(str) # Assuming city IDs match GS IDs used in delays

    # Merge delay data with city locations
    df_merged = pd.merge(df_delays, df_cities, left_on='gs_id', right_on='id', how='left')

    # Separate reachable and unreachable stations
    df_merged['delay_ms'] = df_merged['delay_ms'].replace([np.inf, -np.inf], np.nan) # Replace inf with NaN for processing
    df_reachable = df_merged.dropna(subset=['delay_ms'])
    df_unreachable = df_merged[df_merged['delay_ms'].isna()]

    print(f"\n--- Coverage Summary ---")
    print(f"Total Ground Stations Analyzed: {len(df_merged)}")
    print(f"Reachable Stations: {len(df_reachable)}")
    print(f"Unreachable Stations: {len(df_unreachable)}")

    if not df_reachable.empty:
        print(f"\n--- Reachable Stations Delay Statistics (ms) ---")
        delay_stats = df_reachable['delay_ms'].describe() # Capture stats
        print(delay_stats)

        # Identify best and worst covered stations
        min_delay = delay_stats['min'] # Use stats Series
        max_delay = df_reachable['delay_ms'].max()
        best_stations = df_reachable[df_reachable['delay_ms'] == min_delay][['name', 'gs_id', 'delay_ms']]
        worst_stations = df_reachable[df_reachable['delay_ms'] == max_delay][['name', 'gs_id', 'delay_ms']]

        print("\nBest Covered Stations (Minimum Delay):")
        best_stations_str = best_stations.to_string(index=False)
        print(best_stations_str)
        print("\nWorst Covered Stations (Maximum Delay):")
        worst_stations_str = worst_stations.to_string(index=False)
        print(worst_stations_str)

        # --- Save Summary Stats and Best/Worst to Text File ---
        summary_filename = delay_file.parent / f"spare_coverage_summary_{delay_file.stem}.txt"
        try:
            with open(summary_filename, 'w') as f_summary:
                f_summary.write("Spare Capacity Coverage Summary\n")
                f_summary.write("===============================\n\n")
                f_summary.write(f"Total Ground Stations Analyzed: {len(df_merged)}\n")
                f_summary.write(f"Reachable Stations: {len(df_reachable)}\n")
                f_summary.write(f"Unreachable Stations: {len(df_unreachable)}\n\n")
                f_summary.write("Reachable Stations Delay Statistics (ms):\n")
                f_summary.write(delay_stats.to_string())
                f_summary.write("\n\nBest Covered Stations (Minimum Delay):\n")
                f_summary.write(best_stations_str)
                f_summary.write("\n\nWorst Covered Stations (Maximum Delay):\n")
                f_summary.write(worst_stations_str)
            print(f"\nSaved coverage summary to: {summary_filename}")
        except Exception as e:
            print(f"Error saving coverage summary: {e}")
        # -------------------------------------------------------

        # --- Generate and Save LaTeX Table for Stats ---
        latex_table_filename = delay_file.parent / f"spare_coverage_table_{delay_file.stem}.tex"
        try:
            table_caption = f"Summary Statistics for Delay (ms) to Nearest Spare Node ({delay_file.stem.replace('_', ' ')})"
            table_label = f"tab:coverage_stats_{delay_file.stem}"
            latex_code = generate_coverage_latex_table(delay_stats, table_caption, table_label)
            with open(latex_table_filename, 'w') as f_tex:
                f_tex.write(latex_code)
            print(f"Saved LaTeX table for stats to: {latex_table_filename}")
        except Exception as e:
            print(f"Error saving LaTeX table: {e}")
        # ---------------------------------------------

        # --- Create Geographic Plot ---
        print("\nGenerating geographic coverage map...")
        plt.figure(figsize=(15, 8))
        ax = plt.axes(projection=ccrs.PlateCarree()) # Use PlateCarree for lat/lon data
        ax.stock_img()
        ax.add_feature(cfeature.COASTLINE)
        ax.add_feature(cfeature.BORDERS, linestyle=':')
        ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False)

        # Define colormap and normalization for reachable stations
        # Use a logarithmic scale if delays vary widely, otherwise linear
        if max_delay / min_delay > 100: # Heuristic for large range
            norm = mcolors.LogNorm(vmin=min_delay, vmax=max_delay)
            cmap_label = 'Delay to Nearest Spare Node (ms) [Log Scale]'
        else:
            norm = mcolors.Normalize(vmin=min_delay, vmax=max_delay)
            cmap_label = 'Delay to Nearest Spare Node (ms)'
        cmap = plt.get_cmap('viridis_r') # Reversed viridis (yellow=low delay, purple=high)

        # Plot reachable stations
        scatter = ax.scatter(df_reachable['longitude'], df_reachable['latitude'],
                             c=df_reachable['delay_ms'],
                             cmap=cmap,
                             norm=norm,
                             s=50, # Adjust size as needed
                             transform=ccrs.Geodetic(), # Important for lat/lon data
                             label='Reachable GS',
                             zorder=10) # Ensure points are on top

        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax, orientation='vertical', pad=0.05, shrink=0.7)
        cbar.set_label(cmap_label)

        # Plot unreachable stations
        if not df_unreachable.empty:
            ax.scatter(df_unreachable['longitude'], df_unreachable['latitude'],
                       color='red',
                       marker='x', # Use 'x' marker
                       s=60, # Adjust size
                       transform=ccrs.Geodetic(),
                       label='Unreachable GS',
                       zorder=11) # Ensure these are also on top

        # Add legend
        ax.legend(loc='lower left')

        plt.title(f'Spare Capacity Coverage: Delay to Nearest Spare Node ({delay_file.stem})')

        plot_filename = delay_file.parent / f"spare_coverage_map_{delay_file.stem}.png"
        plt.savefig(plot_filename, bbox_inches='tight')
        print(f"Saved coverage map to: {plot_filename}")
        # plt.show()

    else:
        print("\nNo reachable ground stations found. Skipping map generation.")

    print("\nAnalysis complete.")

def generate_coverage_latex_table(stats: pd.Series, caption: str, label: str) -> str:
    """Generates a LaTeX table string for summary statistics."""
    
    latex_string = f"\\begin{{table}}[htbp]\n"
    latex_string += f"\\centering\n"
    latex_string += f"\\caption{{{caption}}}\n"
    latex_string += f"\\label{{{label}}}\n"
    latex_string += f"\\begin{{tabular}}{{lr}}\n" # l for label, r for right-aligned number
    latex_string += f"\\toprule\n"
    latex_string += f"Statistic & Delay (ms) \\\\\n"
    latex_string += f"\\midrule\n"
    
    # Map index names to more descriptive labels if needed
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
        label_name = stat_labels.get(index, index) # Use descriptive label or index name
        # Format numbers appropriately (e.g., count as integer, others float)
        if index == 'count':
            formatted_value = f"{int(value):,}" # Integer with comma separator
        else:
            formatted_value = f"{value:.2f}" # Float with 2 decimal places
        latex_string += f"{label_name} & {formatted_value} \\\\\n"
        
    latex_string += f"\\bottomrule\n"
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"
    
    return latex_string

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze and visualize geographic spare capacity coverage.')
    parser.add_argument('delay_csv', type=str, help='Path to the gs_delays_{timestamp}.csv file.')
    parser.add_argument('--cities_csv', type=str, default='skyfield/cities.csv',
                        help='Path to the cities CSV file for GS locations (default: skyfield/cities.csv).')
    args = parser.parse_args()

    analyze_coverage(args.delay_csv, args.cities_csv)
