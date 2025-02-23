import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.ticker import LogLocator, LogFormatter

# Load the CSV file
df = pd.read_csv("./costs.csv")

sns.set_style('white')
sns.set_context("paper", font_scale = 2)

# Create the plot with adjusted figure size ratio
plt.figure(figsize=(12, 8))

# Scatter plot with Seaborn
sns.scatterplot(data=df, x="First launch date", y="$k/kg", hue="System", palette="tab20", legend=None, s=100, edgecolor='black', linewidth=0.5)

# Filter data for different periods
df_after_2010 = df[df['First launch date'] >= 2010]
df_1970_2000 = df[(df['First launch date'] >= 1970) & (df['First launch date'] <= 2000)]
df_pre_1970 = df[df['First launch date'] < 1970]

# Add regression lines using log-transformed data
for data, color in [(df_after_2010, 'red'), 
                    (df_1970_2000, 'blue'), 
                    (df_pre_1970, 'green')]:
    if not data.empty:
        # Create log-transformed data for regression
        x = data['First launch date']
        y = np.log10(data['$k/kg'])
        
        # Calculate regression line
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        
        # Generate points for the line
        x_range = np.linspace(x.min(), x.max(), 100)
        y_range = 10 ** p(x_range)  # Transform back to original scale
        
        plt.plot(x_range, y_range, color=color, lw=2)

# Points to label
label_points = {
    "Vanguard": (1957, 894.7),
    "Falcon 9": (2010, 2.7),
    "Falcon Heavy": (2018, 1.4),
    "Space Shuttle": (1981, 61.7),
    "Saturn V": (1968, 5.2)
}

# Add labels to these points
for system, (x, y) in label_points.items():
    plt.annotate(system,
                (x, y),
                fontsize=12,
                ha='right',
                color='black',
                weight='bold',
                xytext=(20, -15),
                textcoords='offset points')

# Customize the plot
plt.xlabel("First Launch Date")
plt.ylabel("Launch Cost (thousands USD/kg)")
# Set custom x-axis ticks at decades
decades = np.arange(1960, 2021, 10)  # Creates array [1960, 1970, 1980, 1990, 2000, 2010, 2020]
plt.xticks(decades, rotation=45)

# Set the y-axis to a logarithmic scale
ax = plt.gca()
ax.set_yscale('log')

# Set custom y-axis ticks to show exactly 1, 10, 100, 1000
ax.set_yticks([1, 10, 100, 1000])
ax.set_yticklabels(['1', '10', '100', '1000'])
ax.yaxis.set_minor_locator(plt.NullLocator())  # Remove minor ticks

# Adjust the y-limits
plt.ylim(1, 1000)

# Add grid for major ticks only
plt.grid(True, which='major', linestyle='-', alpha=0.2)
plt.grid(False, which='minor')  # Turn off minor grid

plt.tight_layout()

sns.despine(right = True)

plt.savefig('launch_costs.png', dpi=300, bbox_inches='tight')
plt.savefig('launch_costs.pdf', bbox_inches='tight')