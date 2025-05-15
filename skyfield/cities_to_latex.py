import csv
import re

def escape_latex(text):
    """Escape special LaTeX characters in a string."""
    if not isinstance(text, str):
        return str(text)
    
    # Define LaTeX special characters and their escaped versions
    special_chars = {
        '\\': '\\textbackslash{}',
        '~': '\\textasciitilde{}',
        '^': '\\textasciicircum{}',
        '&': '\\&',
        '%': '\\%',
        '$': '\\$',
        '#': '\\#',
        '_': '\\_',
        '{': '\\{',
        '}': '\\}'
    }
    
    # Replace each special character with its escaped version
    for char, escaped in special_chars.items():
        text = text.replace(char, escaped)
    
    return text

def format_city_name(name):
    """Format city names by replacing hyphens with spaces."""
    return name.replace('-', ' ')

def csv_to_latex(input_file, output_file, include_id=False):
    """Convert CSV data to a LaTeX table.
    
    Args:
        input_file (str): Path to input CSV file
        output_file (str): Path to output LaTeX file
        include_id (bool): Whether to include the ID column (default: False)
    """
    with open(input_file, 'r', encoding='utf-8') as csvfile:
        # Read CSV data
        reader = csv.DictReader(csvfile)
        data = list(reader)
    
    with open(output_file, 'w', encoding='utf-8') as texfile:
        # Write LaTeX table preamble
        texfile.write("% Required packages for this table\n")
        texfile.write("% \\usepackage{longtable}\n")
        texfile.write("% \\usepackage{booktabs}\n")
        texfile.write("% \\usepackage{array}\n\n")
        
        texfile.write("% Table formatting settings (optional)\n")
        texfile.write("% \\setlength{\\tabcolsep}{8pt}        % Horizontal spacing between columns\n")
        texfile.write("% \\renewcommand{\\arraystretch}{1.1}  % Vertical spacing between rows\n\n")
        
        # Determine the number of columns based on whether to include ID
        if include_id:
            columns = "lrrc"  # ID, City, Lat, Long, Pop
            header = "\\textbf{ID} & \\textbf{City} & \\textbf{Latitude} & \\textbf{Longitude} & \\textbf{Population (thousands)} \\\\"
        else:
            columns = "lrrc"  # City, Lat, Long, Pop
            header = "\\textbf{City} & \\textbf{Latitude} & \\textbf{Longitude} & \\textbf{Population (thousands)} \\\\"
        
        # Begin the longtable environment
        texfile.write("\\begin{longtable}{" + columns + "}\n")
        texfile.write("\\caption{List of World Cities with Geographic Coordinates and Population} \\label{tab:world-cities} \\\\\n")
        texfile.write("\\toprule\n")
        texfile.write(header + "\n")
        texfile.write("\\midrule\n")
        texfile.write("\\endhead\n\n")
        
        texfile.write("\\midrule\n")
        texfile.write("\\multicolumn{" + str(4 if not include_id else 5) + "}{r}{\\footnotesize\\textit{Continued on next page}} \\\\\n")
        texfile.write("\\endfoot\n\n")
        
        texfile.write("\\bottomrule\n")
        texfile.write("\\endlastfoot\n\n")
        
        # Write each row
        for row in data:
            city_name = escape_latex(format_city_name(row['name']))
            latitude = float(row['latitude'])
            longitude = float(row['longitude'])
            population = float(row['population'])
            
            # Format the row based on whether to include ID
            if include_id:
                row_text = f"{row['id']} & {city_name} & {latitude:.4f} & {longitude:.4f} & {population:.1f} \\\\"
            else:
                row_text = f"{city_name} & {latitude:.4f} & {longitude:.4f} & {population:.1f} \\\\"
            
            texfile.write(row_text + "\n")
        
        # End the longtable environment
        texfile.write("\\end{longtable}\n")

# Example usage
if __name__ == "__main__":
    input_file = "cities.csv"  # Replace with your CSV file path
    output_file = "cities_table.tex"
    include_id = False  # Set to True if you want to include the ID column
    
    csv_to_latex(input_file, output_file, include_id)
    print(f"LaTeX table has been written to {output_file}")