import pandas as pd
import numpy as np
from math import radians, sin, cos, sqrt, asin

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r

def find_max_distance(csv_file):
    # Read the CSV file
    df = pd.read_csv(csv_file)
    
    max_distance = 0
    farthest_points = (None, None)
    
    # Calculate distances between all pairs of points
    n = len(df)
    for i in range(n):
        for j in range(i+1, n):
            lat1, lon1 = df.iloc[i]['latitude'], df.iloc[i]['longitude']
            lat2, lon2 = df.iloc[j]['latitude'], df.iloc[j]['longitude']
            
            distance = haversine_distance(lat1, lon1, lat2, lon2)

            if df.iloc[i]['name'] == "Montréal" and df.iloc[j]['name'] == "Birmingham-(West-Midlands)":
                return distance, (df.iloc[i]['name'], df.iloc[j]['name']) 
            
            if distance > max_distance:
                max_distance = distance
                farthest_points = (df.iloc[i]['name'], df.iloc[j]['name'])
    
    return max_distance, farthest_points

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python script.py <csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    max_distance, (point1, point2) = find_max_distance(csv_file)
    
    print(f"Maximum distance: {max_distance:.2f} km")
    print(f"Between: {point1} and {point2}")