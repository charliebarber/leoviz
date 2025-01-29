from ground_stations import GroundStations
import math
import csv

def haversine_distance(gs1, gs2):
    # Radius of the Earth in kilometers
    R = 6371.0

    # Convert degrees to radians
    lat1 = math.radians(gs1['latitude'])
    lon1 = math.radians(gs1['longitude'])
    lat2 = math.radians(gs2['latitude'])
    lon2 = math.radians(gs2['longitude'])

    # Differences in coordinates
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in kilometers
    distance = R * c
    return distance

ground_stations = GroundStations("./cities.csv")

# gs_pairs = [(gs1, gs2) for i, gs1 in enumerate(ground_stations) 
# #                    for gs2 in ground_stations[i+1:]]

# print(gs_pairs)
gs_pos = ground_stations.get_station_positions()

gs_pairs = [(gs1, gs2) for i, gs1 in enumerate(gs_pos) for gs2 in gs_pos[i+1:]]

max_pop_product = gs_pos[0]['population'] * gs_pos[1]['population']
max_dist = max([haversine_distance(gs1, gs2) for i, gs1 in enumerate(gs_pos) for gs2 in gs_pos[i+1:]])
# print(max_pop_product)
# print(max_dist)

data = [["gs1", "gs1_name", "gs2", "gs2_name", "scaled_pop_product", "scaled_dist", "distance_weight", "traffic_demand"]]

for gs1, gs2 in gs_pairs:
  pop_product = gs1['population'] * gs2['population']
  scaled_pop_product = pop_product / max_pop_product
  dist = haversine_distance(gs1, gs2)
  scaled_dist = dist / max_dist
  distance_weight = math.exp((-1 * scaled_dist))
  traffic_demand = scaled_pop_product * distance_weight

  # print(f"{gs1['name']} {gs2['name']} {scaled_pop_product} {scaled_dist} {distance_weight}")
  data.append([gs1['id'], gs1['name'], gs2['id'], gs2['name'], scaled_pop_product, scaled_dist, distance_weight, traffic_demand])

with open('cities_scaled.csv', mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerows(data)
    