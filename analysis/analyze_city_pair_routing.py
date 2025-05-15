import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import argparse
from pathlib import Path
import re # For extracting timestamp

# --- LaTeX Table Generation ---

def generate_latex_table_generic(df_table_data: pd.DataFrame, caption: str, label: str, metric_name: str, unit: str = "") -> str:
    """Generates a LaTeX table string for city pair summary data (Success Rate or Delay)."""

    # df_table_data has MultiIndex columns, index is standard RangeIndex
    # Identify actual data columns (those not under 'Pair' if it existed, or just not Source/Dest)
    data_cols = [col for col in df_table_data.columns if col[0] not in ['Source', 'Destination']]
    num_data_cols = len(data_cols)
    n_levels = df_table_data.columns.nlevels

    col_format = 'll' + 'r' * num_data_cols # ll for Source/Dest, r for data cols

    latex_string = f"\\begin{{table}}[htbp]\n"
    latex_string += f"\\centering\n"
    latex_string += f"\\caption{{{caption}}}\n"
    latex_string += f"\\label{{{label}}}\n"
    latex_string += f"\\resizebox{{\\textwidth}}{{!}}{{\n" # Make table fit text width
    latex_string += f"\\begin{{tabular}}{{@{{}} {col_format} @{{}}}}\n" # Add @{} to remove extra space
    latex_string += f"\\toprule\n"

    # --- Multi-level Header ---
    # Top level header row (Parent Columns)
    # Get the unique top-level metric names from the data columns
    top_level_metrics = sorted(list(set(col[0] for col in data_cols)))
    header_level0 = ["Source", "Destination"] # Start with Pair columns
    col_spans = {} # Store span for cmidrule
    for metric in top_level_metrics:
        # Count how many sub-columns belong to this metric
        span = sum(1 for col in data_cols if col[0] == metric)
        header_level0.append(f"\\multicolumn{{{span}}}{{c}}{{{metric}}}")
        col_spans[metric] = span
    latex_string += " & ".join(header_level0) + " \\\\\n"

    # Add cmidrules under the top-level headers
    cmidrule_parts = []
    start_col_idx = 3 # Start after 'Source', 'Destination' columns (index 1, 2)
    for metric in top_level_metrics: # Iterate in the same order
        span = col_spans[metric]
        end_col_idx = start_col_idx + span - 1
        cmidrule_parts.append(f"\\cmidrule(lr){{{start_col_idx}-{end_col_idx}}}")
        start_col_idx = end_col_idx + 1
    latex_string += " ".join(cmidrule_parts) + "\n"

    # Second level header row (Sub-columns)
    header_level1 = ["", ""] # Placeholders for 'Source', 'Destination' headers
    header_level1.extend([col[1].replace('Factor ', '').replace('Within 5% ', '') for col in data_cols]) # Clean up sub-column names
    latex_string += " & ".join(header_level1) + " \\\\\n"
    latex_string += f"\\midrule\n"

    # Data rows - Use df_table_data here
    for index, row in df_table_data.iterrows(): # Use the correct DataFrame variable
        # Access Source and Destination columns directly
        # Access Source and Destination columns directly using the flattened names
        row_values = [str(row[('Source', 'Source')]), str(row[('Destination', 'Destination')])] # Start with Source/Dest
        # Iterate through the actual data columns (excluding Pair info which is now handled)
        # Iterate ONLY through the identified data columns
        for col_tuple in data_cols: # data_cols was defined earlier
            value = row[col_tuple]
            col_level0_name = col_tuple[0] # Parent column name

            # Format numeric values, handle potential errors or NaNs
            if pd.isna(value) or value == "N/A": # Check for explicit "N/A" too

                formatted_value = "N/A" # Handle potential NaNs
            else:
                try:
                    # Increase precision for Delta columns
                    formatted_value = f"{float(value):.1f}\\%" if 'Rate' in col_level0_name or 'Usage' in col_level0_name else f"{float(value):.4f}"
                except (ValueError, TypeError):
                    formatted_value = str(value) # Fallback if not numeric
            row_values.append(formatted_value)

        latex_string += " & ".join(row_values) + " \\\\\n"

    latex_string += f"\\bottomrule\n"
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"}}\n" # End resizebox
    latex_string += f"\\end{{table}}\n"

    return latex_string

# --- Main Analysis Function ---

def analyze_city_pair_routing(base_dir: str):
    """
    Analyzes routing effectiveness specifically for city pairs across multiple timestamps.

    Args:
        base_dir (str): The base directory containing timestamp subdirectories
                        (e.g., ../positions/starlink_550_traffic_scaled/).
    """
    base_path = Path(base_dir)
    if not base_path.is_dir():
        print(f"Error: Base directory not found at {base_path}")
        return

    print(f"Analyzing city pair routing data in: {base_path}")

    # Find all routing_effectiveness CSV files
    routing_files = list(base_path.rglob('coverage_data/routing_effectiveness_*.csv'))

    if not routing_files:
        print("Error: No 'routing_effectiveness_*.csv' files found in coverage_data subdirectories.")
        return

    print(f"Found {len(routing_files)} routing effectiveness files.")

    all_dfs = []
    timestamp_regex = re.compile(r'routing_effectiveness_(\d+)\.csv')

    for file in routing_files:
        match = timestamp_regex.search(file.name)
        if match:
            timestamp = int(match.group(1))
            try:
                df_ts = pd.read_csv(file)
                if 'pair_type' not in df_ts.columns:
                    print(f"Warning: 'pair_type' column not found in {file}. Assuming all are city pairs for this file.")
                    # Handle older files potentially? Or skip? For now, assume city type if column missing.
                    df_ts['pair_type'] = 'city' # Or skip based on requirements
                df_ts['timestamp'] = timestamp
                all_dfs.append(df_ts)
            except Exception as e:
                print(f"Warning: Could not read or parse file {file}: {e}")
        else:
            print(f"Warning: Could not extract timestamp from filename {file.name}")

    if not all_dfs:
        print("Error: No valid routing effectiveness data could be read.")
        return

    # Concatenate all data
    df_all = pd.concat(all_dfs, ignore_index=True)
    num_timestamps = df_all['timestamp'].nunique()
    print(f"Data loaded across {num_timestamps} timestamps.")

    # Filter for city pairs
    df_cities = df_all[df_all['pair_type'] == 'city'].copy()
    if df_cities.empty:
        print("Error: No data found for 'city' pair type.")
        return

    print(f"Analyzing {len(df_cities)} total runs for city pairs.")

    # Define output directory
    output_dir = base_path / "analysis_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Analysis per City Pair ---
    print("\n--- Analyzing Performance Per City Pair ---")
    grouped_pairs = df_cities.groupby(['source', 'target'])

    summary_results = []

    for name, group in grouped_pairs:
        source_id = name[0]
        target_id = name[1]
        pair_results = {} # Use tuples as keys for multi-index later

        # Overall Success Rate
        overall_success = group['spare_path_found'].mean() * 100 if not group.empty else 0.0
        pair_results[('Success Rate (%)', 'Overall')] = overall_success

        # Analysis per Factor
        delay_factors = sorted(group['delay_factor'].unique())
        for factor in delay_factors:
            group_factor = group[group['delay_factor'] == factor]

            # Success Rate for this factor
            success_rate_factor = group_factor['spare_path_found'].mean() * 100 if not group_factor.empty else 0.0
            pair_results[('Success Rate (%)', f'Factor {factor}')] = success_rate_factor

            # Delay Delta and Met Target Analysis (for successful paths at this factor)
            successful_factor_runs = group_factor[group_factor['spare_path_found'] & group_factor['delay_delta'].notna()]
            if not successful_factor_runs.empty:
                avg_delta_factor = successful_factor_runs['delay_delta'].mean()
                std_dev_delta_factor = successful_factor_runs['delay_delta'].std()

                # Define "Met Target" as spare_path_delay within +/- 5% of the target factor * shortest_path_delay
                # Requires shortest_path_delay which might not be in successful_factor_runs if loaded from old CSVs
                # Let's merge it back if needed, or assume it's present from df_cities/group_factor
                # Assuming 'shortest_path_delay' is available in successful_factor_runs
                tolerance = 0.05
                lower_bound = successful_factor_runs['shortest_path_delay'] * (factor * (1 - tolerance))
                upper_bound = successful_factor_runs['shortest_path_delay'] * (factor * (1 + tolerance))
                met_target_condition = (successful_factor_runs['spare_path_delay'] >= lower_bound) & \
                                       (successful_factor_runs['spare_path_delay'] <= upper_bound)
                met_target_factor = met_target_condition.mean() * 100

                # Calculate Spare Link Usage Percentage for successful runs
                total_edges = successful_factor_runs['spare_edges_count'] + successful_factor_runs['normal_edges_count']
                # Avoid division by zero for paths with 0 edges (shouldn't happen)
                spare_usage_perc = (successful_factor_runs['spare_edges_count'] / total_edges.replace(0, np.nan)) * 100
                avg_spare_usage_factor = spare_usage_perc.mean() # Average percentage

                # Store Avg Delta, Std Dev Delta, Within 5% Rate, and Avg Spare Usage
                pair_results[('Avg Delay Delta (ms)', f'Factor {factor}')] = avg_delta_factor
                pair_results[('Std Dev Delay Delta (ms)', f'Factor {factor}')] = std_dev_delta_factor if pd.notna(std_dev_delta_factor) else 0.0 # Store Std Dev, handle NaN
                pair_results[('Within 5% Target Rate (%)', f'Factor {factor}')] = met_target_factor # Use new name
                pair_results[('Avg Spare Link Usage (%)', f'Factor {factor}')] = avg_spare_usage_factor if pd.notna(avg_spare_usage_factor) else np.nan
                # Calculate Avg Duration for successful runs at this factor
                avg_duration_factor = successful_factor_runs['duration_s'].mean()
                pair_results[('Avg Duration (s)', f'Factor {factor}')] = avg_duration_factor if pd.notna(avg_duration_factor) else np.nan

            else:
                pair_results[('Avg Delay Delta (ms)', f'Factor {factor}')] = np.nan
                pair_results[('Std Dev Delay Delta (ms)', f'Factor {factor}')] = np.nan # Std Dev is NaN if no success
                pair_results[('Within 5% Target Rate (%)', f'Factor {factor}')] = 0.0 # Use new name
                pair_results[('Avg Spare Link Usage (%)', f'Factor {factor}')] = np.nan # Usage is NaN if no success
                pair_results[('Avg Duration (s)', f'Factor {factor}')] = np.nan # Duration is NaN if no success
        summary_results.append(pair_results)

    # Create DataFrame with MultiIndex columns directly
    df_summary = pd.DataFrame(summary_results, index=[f"{name[0]}-{name[1]}" for name, group in grouped_pairs])
    df_summary.index.name = 'Pair'
    # Ensure columns are MultiIndex and name levels
    df_summary.columns = pd.MultiIndex.from_tuples(df_summary.columns, names=['Metric', 'Factor'])

    # Add Source and Destination columns from index
    df_summary[('Pair', 'Source')] = df_summary.index.map(lambda x: x.split('-')[0])
    df_summary[('Pair', 'Destination')] = df_summary.index.map(lambda x: x.split('-')[1])

    # Sort columns for a logical order (add Duration)
    # And sort factors within each metric
    df_summary = df_summary.sort_index(axis=1, level=['Metric', 'Factor'])

    # --- Prepare DataFrames for Separate Tables ---
    df_success = df_summary[[('Pair', 'Source'), ('Pair', 'Destination'), ('Success Rate (%)', 'Overall')] +
                            [(('Success Rate (%)', f'Factor {f}')) for f in delay_factors]]
    # Include Std Dev and use new "Within 5% Target Rate" in the delay performance table
    df_delay = df_summary[[('Pair', 'Source'), ('Pair', 'Destination')] +
                          [(('Within 5% Target Rate (%)', f'Factor {f}')) for f in delay_factors] + # Use new name
                          [(('Avg Delay Delta (ms)', f'Factor {f}')) for f in delay_factors] +
                          [(('Std Dev Delay Delta (ms)', f'Factor {f}')) for f in delay_factors]] # Add Std Dev here
    df_usage = df_summary[[('Pair', 'Source'), ('Pair', 'Destination')] +
                          [(('Avg Spare Link Usage (%)', f'Factor {f}')) for f in delay_factors]]
    df_duration = df_summary[[('Pair', 'Source'), ('Pair', 'Destination')] +
                             [(('Avg Duration (s)', f'Factor {f}')) for f in delay_factors]]

    # Rename columns for simpler table generation (remove 'Pair' level)
    df_success.columns = pd.MultiIndex.from_tuples([(c[1] if c[0]=='Pair' else c[0], c[1]) for c in df_success.columns])
    df_delay.columns = pd.MultiIndex.from_tuples([(c[1] if c[0]=='Pair' else c[0], c[1]) for c in df_delay.columns])
    df_duration.columns = pd.MultiIndex.from_tuples([(c[1] if c[0]=='Pair' else c[0], c[1]) for c in df_duration.columns])
    df_usage.columns = pd.MultiIndex.from_tuples([(c[1] if c[0]=='Pair' else c[0], c[1]) for c in df_usage.columns])

    df_delay = df_delay.sort_index(axis=1, level=[0, 1]) # Sort delay table columns: Avg, Met Target, Std Dev

    print("\nCity Pair Routing Summary:")
    print("\n--- Success Rate ---")
    print(df_success.to_string(float_format="%.2f"))
    print("\n--- Delay Performance ---")
    print(df_delay.to_string(float_format="%.2f"))
    print("\n--- Spare Link Usage ---")
    print(df_usage.to_string(float_format="%.1f")) # Print usage with 1 decimal place
    print("\n--- Pathfinding Duration ---")
    print(df_duration.to_string(float_format="%.4f")) # Print duration with 4 decimal places

    # --- Save LaTeX Table ---
    print("\n--- Generating LaTeX Table ---")
    try:
        # Table 1: Success Rate
        caption1 = f"Spare Path Success Rate Summary for City Pairs across {num_timestamps} Timestamps"
        label1 = "tab:city_pair_success_summary"
        latex_code1 = generate_latex_table_generic(df_success, caption1, label1, "Success Rate (%)")
        table_filename1 = output_dir / "city_pair_success_summary.tex"
        with open(table_filename1, 'w') as f: # Use table_filename1
            f.write(latex_code1) # Use latex_code1
        print(f"Saved LaTeX table to: {table_filename1}")
    except Exception as e:
        print(f"Error generating LaTeX table: {e}")

    # Table 2: Delay Performance (Unindent this block)
    try:
        caption2 = f"Spare Path Delay Performance Summary for City Pairs across {num_timestamps} Timestamps"
        label2 = "tab:city_pair_delay_summary"
        latex_code2 = generate_latex_table_generic(df_delay, caption2, label2, "Delay Metrics") # Generic metric name
        table_filename2 = output_dir / "city_pair_delay_summary.tex"
        with open(table_filename2, 'w') as f:
            f.write(latex_code2)
        print(f"Saved LaTeX table to: {table_filename2}")
    except Exception as e:
        print(f"Error generating LaTeX table: {e}")

    # Table 3: Spare Usage
    try:
        caption3 = f"Average Spare Link Usage (%%) for Successful Paths between City Pairs across {num_timestamps} Timestamps" # Escape % for LaTeX
        label3 = "tab:city_pair_usage_summary"
        latex_code3 = generate_latex_table_generic(df_usage, caption3, label3, "Avg Spare Link Usage (%)")
        table_filename3 = output_dir / "city_pair_usage_summary.tex"
        with open(table_filename3, 'w') as f:
            f.write(latex_code3)
        print(f"Saved LaTeX table to: {table_filename3}")
    except Exception as e:
        print(f"Error generating LaTeX table: {e}")

    # Table 4: Duration
    try:
        caption4 = f"Average Pathfinding Duration (s) for Successful Paths between City Pairs across {num_timestamps} Timestamps"
        label4 = "tab:city_pair_duration_summary"
        latex_code4 = generate_latex_table_generic(df_duration, caption4, label4, "Avg Duration (s)")
        table_filename4 = output_dir / "city_pair_duration_summary.tex"
        with open(table_filename4, 'w') as f:
            f.write(latex_code4)
        print(f"Saved LaTeX table to: {table_filename4}")
    except Exception as e:
        print(f"Error generating LaTeX table: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze routing effectiveness for specific city pairs.')

    parser.add_argument('base_directory', type=str,
                        help='Base directory containing timestamp subdirectories with coverage_data folders (e.g., ../positions/starlink_550_traffic_scaled/)')
    args = parser.parse_args()

    analyze_city_pair_routing(args.base_directory)
