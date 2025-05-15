import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import os
from pathlib import Path

def generate_latex_table(data: pd.Series, caption: str, label: str) -> str:
    """Generates a LaTeX table string from a pandas Series."""
    
    # Start table environment
    latex_string = f"\\begin{{table}}[htbp]\n"
    latex_string += f"\\centering\n"
    latex_string += f"\\caption{{{caption}}}\n"
    latex_string += f"\\label{{{label}}}\n"
    
    # Start tabular environment (adjust columns as needed)
    latex_string += f"\\begin{{tabular}}{{cc}}\n"
    latex_string += f"\\toprule\n" # Use booktabs style
    
    # Header row
    header = data.index.name if data.index.name else "Delay Factor" # Use index name or default
    latex_string += f"{header} & Success Rate (\\%) \\\\\n"
    latex_string += f"\\midrule\n" # Use booktabs style
    
    # Data rows
    for index, value in data.items():
        latex_string += f"{index:.2f} & {value:.1f} \\\\\n" # Format factor and percentage
        
    # End tabular and table environments
    latex_string += f"\\bottomrule\n" # Use booktabs style
    latex_string += f"\\end{{tabular}}\n"
    latex_string += f"\\end{{table}}\n"
    
    return latex_string

def analyze_success(csv_filepath):
    """
    Analyzes the success rate of finding spare paths from routing effectiveness data.

    Args:
        csv_filepath (str): Path to the routing_effectiveness_{timestamp}.csv file.
    """
    filepath = Path(csv_filepath)
    if not filepath.is_file():
        print(f"Error: File not found at {filepath}")
        return

    print(f"Analyzing success rate from: {filepath}")
    df = pd.read_csv(filepath)

    # --- Overall Success Rate ---
    total_attempts = len(df)
    successful_runs = df['spare_path_found'].sum()
    overall_success_rate = (successful_runs / total_attempts) * 100 if total_attempts > 0 else 0
    print(f"\n--- Overall Success ---")
    print(f"Total runs: {total_attempts}")
    print(f"Successful spare paths found: {successful_runs}")
    print(f"Overall Success Rate: {overall_success_rate:.2f}%")

    # --- Success Rate per Delay Factor ---
    print(f"\n--- Success Rate per Delay Factor ---")
    success_by_factor = df.groupby('delay_factor')['spare_path_found'].mean() * 100
    print(success_by_factor)

    # Plotting Success Rate per Delay Factor
    plt.figure(figsize=(8, 5))
    sns.barplot(x=success_by_factor.index, y=success_by_factor.values)
    plt.title(f'Spare Path Success Rate vs. Delay Factor ({filepath.stem})')
    plt.xlabel('Target Delay Factor (Multiplier of Shortest Path)')
    plt.ylabel('Success Rate (%)')
    plt.ylim(0, 105) # Extend y-axis slightly above 100
    # Add text labels for percentages
    for index, value in enumerate(success_by_factor.values):
        plt.text(index, value + 1, f'{value:.1f}%', ha='center', va='bottom')

    plot_filename = filepath.parent / f"success_rate_vs_factor_{filepath.stem}.png"
    plt.savefig(plot_filename)
    print(f"Saved success rate plot to: {plot_filename}")
    # plt.show() # Uncomment to display plot immediately

    # --- Generate and Save LaTeX Table ---
    print(f"\n--- Generating LaTeX Table ---")
    table_caption = f"Spare Path Success Rate vs. Target Delay Factor ({filepath.stem.replace('_', ' ')})"
    table_label = f"tab:success_rate_{filepath.stem}"
    latex_code = generate_latex_table(success_by_factor, table_caption, table_label)
    
    latex_filename = filepath.parent / f"success_rate_table_{filepath.stem}.tex"
    try:
        with open(latex_filename, 'w') as f_tex:
            f_tex.write(latex_code)
        print(f"Saved LaTeX table code to: {latex_filename}")
    except Exception as e:
        print(f"Error saving LaTeX table: {e}")
    # ------------------------------------

    # --- Identify Consistently Failing Pairs ---
    print(f"\n--- Consistently Failing Pairs ---")
    # Group by source-target pair and check if 'spare_path_found' is ever True for that pair
    pair_success = df.groupby(['source', 'target'])['spare_path_found'].any()
    failing_pairs = pair_success[~pair_success].index.tolist()

    if failing_pairs:
        print(f"Found {len(failing_pairs)} pairs that failed for all tested delay factors:")
        # Print first few failing pairs for brevity
        for i, pair in enumerate(failing_pairs[:10]):
            print(f"  - {pair[0]} -> {pair[1]}")
        if len(failing_pairs) > 10:
            print(f"  ... and {len(failing_pairs) - 10} more.")
        # Optionally save all failing pairs to a file
        failing_pairs_file = filepath.parent / f"failing_pairs_{filepath.stem}.txt"
        with open(failing_pairs_file, 'w') as f:
            for src, tgt in failing_pairs:
                f.write(f"{src},{tgt}\n")
        print(f"Saved full list of failing pairs to: {failing_pairs_file}")
    else:
        print("No pairs failed for all tested delay factors.")

    print("\nAnalysis complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze spare path success rate from routing effectiveness CSV.')
    parser.add_argument('csv_file', type=str, help='Path to the routing_effectiveness_{timestamp}.csv file.')
    args = parser.parse_args()

    analyze_success(args.csv_file)
