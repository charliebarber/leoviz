import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path
import json
import re # For extracting timestamp
from collections import Counter

def generate_contiguity_latex_table(stats: pd.Series, caption: str, label: str, column_name: str) -> str:
    """Generates a LaTeX table string for summary statistics."""
    
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
        elif 'fraction' in index or 'ratio' in index or 'coefficient' in index:
             formatted_value = f"{value:.4f}" # More precision for ratios/fractions
        elif 'edges' in column_name.lower() or 'components' in column_name.lower():
             formatted_value = f"{value:.1f}" # Fewer decimals for counts/sizes
        else:
            formatted_value = f"{value:.2f}"
        latex_string += f"{label_name} & {formatted_value} \\\\\n"
        
    latex_string += f"\\bottomrule\n"
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"
    
    return latex_string

def generate_structural_summary_latex(df_stats: pd.DataFrame, caption: str, label: str) -> str:
    """Generates a LaTeX table string for the structural summary (Mean, Std. Dev.)."""

    latex_string = f"\\begin{{table}}[htbp]\n"
    latex_string += f"\\centering\n"
    latex_string += f"\\caption{{{caption}}}\n"
    latex_string += f"\\label{{{label}}}\n"
    # Use 'lrr' for left-aligned metric name, right-aligned numbers
    latex_string += f"\\begin{{tabular}}{{lrr}}\n"
    latex_string += f"\\toprule\n"
    # Add specific headers for Mean and Std. Dev.
    latex_string += f"Metric & Mean & Std. Dev. \\\\\n"
    latex_string += f"\\midrule\n"

    # Iterate through the DataFrame rows (metrics)
    for index, row in df_stats.iterrows():
        metric_name = index # Assumes index contains descriptive names
        mean_val = row['Mean']
        std_val = row['Std. Dev.']

        # Format numbers appropriately (adjust precision as needed)
        formatted_mean = f"{mean_val:.1f}"
        formatted_std = f"{std_val:.1f}"

        latex_string += f"{metric_name} & {formatted_mean} & {formatted_std} \\\\\n"

    latex_string += f"\\bottomrule\n"
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"

    return latex_string


def analyze_contiguity(base_dir: str):
    """
    Analyzes the contiguity of spare areas across multiple timestamps.

    Args:
        base_dir (str): The base directory containing timestamp subdirectories
                        (e.g., ../positions/starlink_550_traffic_scaled/).
    """
    base_path = Path(base_dir)
    if not base_path.is_dir():
        print(f"Error: Base directory not found at {base_path}")
        return

    print(f"Analyzing spare contiguity data in: {base_path}")

    contiguity_files = list(base_path.rglob('coverage_data/spare_contiguity_*.json'))

    if not contiguity_files:
        print("Error: No 'spare_contiguity_*.json' files found in subdirectories.")
        return

    print(f"Found {len(contiguity_files)} contiguity files.")

    all_data = []
    all_component_distributions = [] # Store list of sizes for each timestamp
    first_timestamp_distribution = None
    first_timestamp_id = None

    for file in contiguity_files:
        try:
           with open(file, 'r') as f:
                data = json.load(f)
                # Calculate per-timestamp stats BEFORE appending
                if 'component_edge_distribution' in data and data['component_edge_distribution']:
                    component_sizes_ts = data['component_edge_distribution']
                    all_component_distributions.append(component_sizes_ts) # Store the list
                    if first_timestamp_distribution is None: # Capture the first one
                        first_timestamp_distribution = component_sizes_ts
                        first_timestamp_id = data.get('timestamp', 'Unknown')

                    # Calculate per-timestamp stats
                    s_ts = pd.Series(component_sizes_ts)
                    data['mean_comp_size_ts'] = s_ts.mean()
                    data['median_comp_size_ts'] = s_ts.median()
                    data['std_comp_size_ts'] = s_ts.std()
                    data['min_comp_size_ts'] = s_ts.min()
                    data['max_comp_size_ts'] = s_ts.max()
                else:
                    # Add NaN if no distribution data for this timestamp
                    data['mean_comp_size_ts'] = np.nan
                    data['median_comp_size_ts'] = np.nan
                    data['std_comp_size_ts'] = np.nan
                    data['min_comp_size_ts'] = np.nan
                    data['max_comp_size_ts'] = np.nan

                all_data.append(data) # Append modified data dict
        except Exception as e:
            print(f"Warning: Could not read or parse file {file}: {e}")

    if not all_data:
        print("Error: No valid contiguity data could be read.")
        return

    # Create DataFrame for overall metrics per timestamp
    df_contiguity = pd.DataFrame(all_data)
    df_contiguity.sort_values('timestamp', inplace=True)

    # Define output directory
    output_dir = base_path / "analysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Analyze Average Per-Timestamp Component Size Statistics ---
    print(f"\n--- Average Per-Timestamp Spare Component Statistics ---")
    avg_comp_stats = {}
    # Select metrics relevant to the revised table: Median Size, Max Size, and Number of Components
    avg_metric_cols = {
        'num_spare_components': 'avg_num_components', # Average number of components per timestamp
        'median_comp_size_ts': 'avg_median_size', # Average of the median size per timestamp
        'max_comp_size_ts': 'avg_max_size'       # Average of the max size per timestamp
    }
    for source_col, target_key in avg_metric_cols.items():
        if source_col in df_contiguity.columns and df_contiguity[source_col].notna().any():
            avg_comp_stats[target_key] = df_contiguity[source_col].mean() # Calculate mean across timestamps
        else:
            avg_comp_stats[target_key] = np.nan
    avg_component_stats_series = pd.Series(avg_comp_stats)
    if avg_component_stats_series.notna().any():
        print(avg_component_stats_series)
    else:
        print("No per-timestamp component size statistics could be calculated.")

    # --- Plot Average Proportion Histogram and Single Timestamp Histogram ---
    print(f"\n--- Plotting Component Size Histograms ---") # Corrected indentation
    if not all_component_distributions: # Corrected indentation
        print("No component size distributions found for histograms.") # Corrected indentation
    else: # Corrected indentation
        # Determine overall max size for consistent binning
        # --- Aggregate all component sizes from all timestamps ---
        all_sizes_flat = [size for sublist in all_component_distributions for size in sublist]
        if not all_sizes_flat:
            print("Warning: No component sizes found in the distributions.")
            return # Or handle appropriately
        component_series_agg = pd.Series(all_sizes_flat)

        # --- Plot Histogram of Pooled Component Sizes with Custom Bins ---
        plt.figure(figsize=(12, 7)) # Adjusted figure size

        min_val = component_series_agg.min() # Should be 1 usually
        max_val = component_series_agg.max()

        # Define custom bins: fine at low end, coarser (log-like) at high end
        bins = []
        fine_bin_max = 10 # Create individual bins up to this value
        if min_val <= fine_bin_max:
            # Bins for 1, 2, ..., fine_bin_max (or max_val if smaller)
            bins.extend(list(np.arange(min_val, min(fine_bin_max + 1, max_val + 1))))

        # Add logarithmic-like bins for larger values
        current_max_bin = bins[-1] if bins else 0 # Upper edge of the last fine bin
        if max_val > current_max_bin:
            # Start log bins from the next integer after the last fine bin edge
            log_start = max(fine_bin_max + 1, current_max_bin)
            # Ensure log_start is at least 1 for log10
            log_start = max(1, log_start)
            # Define ~15 bins logarithmically spaced up to max_val
            # Use max(log_start, 1) to avoid log10(0) or negative
            log_bins = np.logspace(np.log10(log_start), np.log10(max_val + 1), num=15)
            # Combine, remove duplicates, round to integers, ensure uniqueness
            custom_bins = np.unique(np.round(np.concatenate((bins, log_bins))).astype(int))
            # Ensure the exact max value is included as an upper edge if necessary
            if custom_bins[-1] < max_val + 1:
                 custom_bins = np.append(custom_bins, max_val + 1)
        else:
            custom_bins = np.array(bins) # Only fine bins needed

        # Ensure bins are unique, sorted, and start from the actual minimum value
        custom_bins = np.unique(custom_bins[custom_bins >= min_val])

        # ***** ADDED THIS LINE *****
        plt.hist(component_series_agg, bins=custom_bins, edgecolor='black') # Added edgecolor for clarity

        plt.title('Distribution of Pooled Spare Component Sizes (Edges) Across All Timestamps')
        plt.xlabel('Number of Edges in Component (Custom Bins)')
        plt.grid(axis='y', alpha=0.5)
        # Consider log scale for y-axis if frequencies vary greatly
        plt.yscale('log')
        plt.ylabel('Frequency (Number of Components) [Log Scale]')


        # Adjust x-axis ticks for readability if many bins
        if len(custom_bins) > 25:
            # Select a subset of ticks for clarity or use rotation
            tick_indices = np.linspace(0, len(custom_bins) - 1, 15, dtype=int) # Show ~15 ticks
            plt.xticks(ticks=custom_bins[tick_indices], rotation=45, ha='right')
        elif len(custom_bins) > 1:
             # Show all bin edges if fewer bins, rotate for clarity
             plt.xticks(ticks=custom_bins, rotation=45, ha='right')
        # Handle case with only one data point or one bin
        elif len(custom_bins) == 1:
             plt.xticks(ticks=[custom_bins[0]])

        plt.tight_layout() # Adjust layout

        plot_filename_hist = output_dir / "contiguity_component_size_hist_custom_logbins.png" # New filename reflecting bin strategy
        plt.savefig(plot_filename_hist)
        print(f"\nSaved component size histogram (custom log-like bins) to: {plot_filename_hist}")
        plt.close() # Close the figure to free memory
        # --- End Histogram Plot ---

        # --- Plot Histogram for the First Timestamp Only ---
        if first_timestamp_distribution and first_timestamp_id:
            print(f"\n--- Plotting Component Size Histogram for First Timestamp ({first_timestamp_id}) ---")
            # Apply Seaborn styling for better aesthetics
            sns.set_theme(style="ticks", palette="pastel") # Example theme, can be adjusted

            plt.figure(figsize=(10, 6))
            component_counts = Counter(first_timestamp_distribution)
            # Ensure all sizes up to cutoff are considered, even if frequency is 0
            sizes = sorted(component_counts.keys())
            frequencies = [component_counts[s] for s in sizes]

            max_size_first_ts = max(sizes) if sizes else 0
            cutoff = 20 # Show individual bars up to this size

            # Prepare data for plotting: x-coordinates, frequencies, and labels
            x_coords = []
            plot_freqs = []
            tick_positions = []
            tick_labels = []

            # Add bars and ticks for sizes 1 to cutoff
            for size in range(1, cutoff + 1):
                freq = component_counts.get(size, 0)
                x_coords.append(size)
                plot_freqs.append(freq)
                tick_positions.append(size)
                tick_labels.append(str(size))

            # Handle the max size bar separately if it's beyond the cutoff
            if max_size_first_ts > cutoff:
                max_freq = component_counts.get(max_size_first_ts, 0)
                if max_freq > 0: # Only add if it exists
                    # Place it at an x-coordinate offset from the cutoff to create a visual gap
                    max_bar_x_coord = cutoff + 2
                    x_coords.append(max_bar_x_coord)
                    plot_freqs.append(max_freq) # Use the calculated max_freq
                    # Add tick for the max bar
                    tick_positions.append(max_bar_x_coord)
                    tick_labels.append(str(max_size_first_ts)) # Use the actual max size for the label

            # Create the bar plot
            # Use calculated x_coords for bar positions. Width=0.8 for slight spacing.
            plt.bar(x_coords, plot_freqs, width=0.8, edgecolor='black')

            # Add '...' between cutoff and max value if needed
            # Add '...' break symbol on the x-axis if there's a gap
            if max_size_first_ts > cutoff + 1: # Check if there's a gap
                 # Add a tick mark and label for the break symbol in the gap
                 break_tick_pos = cutoff + 1 # Position for the '...' symbol
                 tick_positions.append(break_tick_pos)
                 tick_labels.append('...')
                 # Sort ticks for correct placement
                 sorted_indices = np.argsort(tick_positions)
                 tick_positions = np.array(tick_positions)[sorted_indices]
                 tick_labels = np.array(tick_labels)[sorted_indices]

            plt.xticks(ticks=tick_positions, labels=tick_labels, rotation=0)

            # Ensure y-axis ticks are integers
            ax = plt.gca()
            ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))

            # Removed title as per request for paper figures
            plt.xlabel('Number of Edges in Component')
            plt.ylabel('Frequency (Number of Components)')
            plt.grid(axis='y', alpha=0.5)
            plt.tight_layout()


            plot_filename_first_ts = output_dir / f"contiguity_component_size_hist_ts_{first_timestamp_id}.png"
            plot_filename_first_ts_pdf = output_dir / f"contiguity_component_size_hist_ts_{first_timestamp_id}.pdf"

            plt.savefig(plot_filename_first_ts)
            plt.savefig(plot_filename_first_ts_pdf, format='pdf') # Save as PDF
            print(f"Saved first timestamp histogram to: {plot_filename_first_ts_pdf} (and .png)")

            plt.close()
        else:
            print("\nCould not plot first timestamp histogram: Data not available.")
        # --- End First Timestamp Histogram ---


    # --- Analyze Overall Metrics per Timestamp ---
    print(f"\n--- Analysis of Overall Contiguity Metrics Across Timestamps ---")
    metrics_to_analyze = [
        'num_spare_components',
        'largest_component_fraction',
        'fragmentation_ratio',
        'global_clustering_coefficient'
    ]
    overall_stats = {}
    for metric in metrics_to_analyze:
        if metric in df_contiguity.columns and df_contiguity[metric].notna().any():
            print(f"\nStatistics for '{metric}':")
            stats = df_contiguity[metric].describe()
            print(stats)
            overall_stats[metric] = stats
        else:
            print(f"\nMetric '{metric}' not found or has no data.")

    # --- Prepare Data for Structural Summary Table ---
    structural_summary_data = {}
    if 'num_spare_components' in overall_stats:
        structural_summary_data['Number of Components'] = {
            'Mean': overall_stats['num_spare_components']['mean'],
            'Std. Dev.': overall_stats['num_spare_components']['std']
        }
    # Need describe() stats for max and median component sizes
    if 'max_comp_size_ts' in df_contiguity.columns and df_contiguity['max_comp_size_ts'].notna().any():
        max_stats = df_contiguity['max_comp_size_ts'].describe()
        structural_summary_data['Largest Component Size (Edges)'] = {
            'Mean': max_stats['mean'],
            'Std. Dev.': max_stats['std']
        }
    if 'median_comp_size_ts' in df_contiguity.columns and df_contiguity['median_comp_size_ts'].notna().any():
        median_stats = df_contiguity['median_comp_size_ts'].describe()
        structural_summary_data['Median Component Size (Edges)'] = {
            'Mean': median_stats['mean'],
            'Std. Dev.': median_stats['std']
        }
    if 'min_comp_size_ts' in df_contiguity.columns and df_contiguity['min_comp_size_ts'].notna().any():
        min_stats = df_contiguity['min_comp_size_ts'].describe()
        structural_summary_data['Smallest Component Size (Edges)'] = {
            'Mean': min_stats['mean'],
            'Std. Dev.': min_stats['std']
        }

    df_structural_summary = pd.DataFrame.from_dict(structural_summary_data, orient='index')
    # Add timestamp count
    num_timestamps = df_contiguity['timestamp'].nunique()

    # --- Save Summary Stats to Text File ---
    summary_filename = output_dir / "contiguity_summary.txt"
    try:
        with open(summary_filename, 'w') as f_summary:
            f_summary.write("Spare Area Contiguity Summary\n")
            f_summary.write("=============================\n\n")
            f_summary.write(f"Data sourced from: {base_path}\n")
            f_summary.write(f"Number of timestamps analyzed: {num_timestamps}\n\n")

            f_summary.write("Average Per-Timestamp Spare Component Size (Edges) Statistics:\n")
            if avg_component_stats_series.notna().any():
                f_summary.write(avg_component_stats_series.to_string())
            else:
                 f_summary.write("No component size data available.\n")
            f_summary.write("\n\n")

            f_summary.write("Structural Summary Statistics (Across Timestamps):\n")
            if not df_structural_summary.empty:
                f_summary.write(df_structural_summary.to_string(float_format="%.1f"))
            else:
                f_summary.write("Structural summary data not available.\n")
            f_summary.write("\n\n")
            f_summary.write("Overall Contiguity Metrics Statistics (per Timestamp):\n")
            for metric, stats in overall_stats.items():
                f_summary.write(f"\n--- {metric} ---\n")
                f_summary.write(stats.to_string())
                f_summary.write("\n")

        print(f"\nSaved contiguity summary to: {summary_filename}")
    except Exception as e:
        print(f"Error saving contiguity summary: {e}")
    # ---------------------------------------

   # --- Generate and Save LaTeX Tables ---
   # Table for Average Component Size Stats
    if avg_component_stats_series.notna().any():
        latex_comp_filename = output_dir / "contiguity_component_size_table.tex"
        try:
            caption = "Average Per-Timestamp Statistics for Spare Network Components"
            label = "tab:contiguity_component_size"
            # Need to rename the index for the LaTeX function labels
            stats_for_latex = avg_component_stats_series.rename(index={
                'avg_num_components': 'mean', # Treat avg count like a mean for table mapping ('Mean Component Count')
                'avg_median_size': '50%',     # Treat avg median like a median for table mapping ('Median Component Size')
                'avg_max_size': 'max'         # Treat avg max like a max for table mapping ('Maximum Component Size')
            })
            # Add a count row manually (number of timestamps with valid data)
            valid_timestamps_count = df_contiguity['timestamp'].nunique() # Count unique timestamps analyzed
            stats_for_latex['count'] = valid_timestamps_count
            stats_for_latex = stats_for_latex.reindex(['count', 'mean', '50%', 'max']) # Reorder for the new structure

            latex_code = generate_contiguity_latex_table(stats_for_latex.dropna(), caption, label, "Average Value") # Use a general column name
            with open(latex_comp_filename, 'w') as f_tex:
                f_tex.write(latex_code)
            print(f"Saved LaTeX table for component sizes to: {latex_comp_filename}")
        except Exception as e:
            print(f"Error saving component size LaTeX table: {e}")

    # Tables for Overall Metrics
    for metric, stats in overall_stats.items():
        latex_metric_filename = output_dir / f"contiguity_{metric}_table.tex"
        try:
            caption = f"Summary Statistics for {metric.replace('_', ' ').title()} per Timestamp"
            label = f"tab:contiguity_{metric}"
            # Determine appropriate column name for table header
            col_name = metric.replace('_', ' ').title()
            if 'fraction' in metric or 'ratio' in metric:
                 col_name += " Ratio"
            elif 'coefficient' in metric:
                 col_name += " Coefficient"

            latex_code = generate_contiguity_latex_table(stats, caption, label, col_name)
            with open(latex_metric_filename, 'w') as f_tex:
                f_tex.write(latex_code)
            print(f"Saved LaTeX table for {metric} to: {latex_metric_filename}")
        except Exception as e:
            print(f"Error saving {metric} LaTeX table: {e}")
    # ------------------------------------

    # --- Generate and Save Structural Summary LaTeX Table ---
    if not df_structural_summary.empty:
        latex_structural_filename = output_dir / "contiguity_structural_summary_table.tex"
        try:
            caption = f"Structural Summary of Spare Network Components Across {num_timestamps} Timestamps"
            label = "tab:contiguity_structural_summary"
            latex_code = generate_structural_summary_latex(df_structural_summary, caption, label)
            with open(latex_structural_filename, 'w') as f_tex:
                f_tex.write(latex_code)
            print(f"Saved LaTeX table for structural summary to: {latex_structural_filename}")
        except Exception as e:
            print(f"Error saving structural summary LaTeX table: {e}")
    # ------------------------------------------------------

    # --- Optional: Plot metrics over time ---
    # Example for fragmentation ratio
    # if 'fragmentation_ratio' in df_contiguity.columns:
    #     plt.figure(figsize=(12, 6))
    #     plt.plot(pd.to_datetime(df_contiguity['timestamp'], unit='s'), df_contiguity['fragmentation_ratio'], marker='.', linestyle='-')
    #     plt.title('Spare Network Fragmentation Ratio over Time')
    #     plt.xlabel('Timestamp')
    #     plt.ylabel('Fragmentation Ratio (Components/Spare Edge)')
    #     plt.grid(True)
    #     plt.xticks(rotation=45)
    #     plt.tight_layout()
    #     plot_filename_ts = output_dir / "contiguity_fragmentation_timeseries.png"
    #     plt.savefig(plot_filename_ts)
    #     print(f"\nSaved fragmentation ratio time series plot to: {plot_filename_ts}")
    #     # plt.show()

    print("\nAnalysis complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze spare area contiguity across multiple timestamps.')
    parser.add_argument('base_directory', type=str,
                        help='Base directory containing timestamp subdirectories (e.g., ../positions/starlink_550_traffic_scaled/)')
    args = parser.parse_args()

    analyze_contiguity(args.base_directory)
