import requests
import itertools
import streamlit as st
import folium
from streamlit_folium import st_folium
import os
import math

# intitailising API keys
TOMTOM_API_KEY = "TOMTOM_API_KEY" # enter your TomTom API key here
HERE_API_KEY = "HERE_API_KEY" # enter your HERE API key here

st.set_page_config(page_title="FedEx Route Planner", page_icon="images/icon.png", layout="wide")

if "stops" not in st.session_state:
    st.session_state.stops = []
if "optimal_route" not in st.session_state:
    st.session_state.optimal_route = None

st.logo("images/logo.svg",size="large")

# route calculation parameters for TOMTOM
st.sidebar.header("Route Calculation Parameters")
traffic = st.sidebar.radio(
    "Use Traffic Data",
    ["true", "false"]
)

# emission data
EMISSION_FACTORS = {
    "Car": {
        "Small":{
            "<800 CC":{
                "Petrol": 0.103,
                "CNG": 0.063,
                "LPG": 0.138
            }
        },
        "Hatchback":{
            "<1000 CC":{
                "Diesel": 0.105,
                "Petrol": 0.117
            },
            "<1500 CC":{
                "Diesel":0.126,
                "Petrol":0.14
            }
        },
        "Sedan":{
            "<1500 CC":{
                "Diesel":0.126,
                "Petrol":0.142
            },
            "<2000 CC":{
                "Diesel":0.156,
                "Petrol":0.170
            },
            "<2500 CC":{
                "Diesel":0.151,
                "Petrol":0.163
            },
            "<3000 CC":{
                "Diesel":0.23,
                "Petrol":0.194
            },
            ">3000 CC":{
                "Diesel":0.25,
                "Petrol":0.25
            }
        },
        "SUV":{
            "<2000 CC":{
                "Diesel":0.176,
                "Petrol":0.193
            },
            "<2500 CC":{
                "Diesel":0.195,
                "Petrol":0.199
            },
            "<3000 CC":{
                "Diesel":0.212,
                "Petrol":0.227
            },
            ">3000 CC":{
                "Diesel":0.269,
                "Petrol":0.267
            }
        },
        "Electric":0.0
    },
    "Freight-vehicle": {
        "LDV (<3.5T)":0.3070,
        "MDV (<12T)":0.5928,
        "HDV (>12T)":0.7375
    },
    "Three-wheeler": {
        "petrol": 0.1135,
        "diesel": 0.1322,
        "CNG": 0.10768,
    },
    "Two-wheeler": {
        "scooter": 0.0334 , 
        "motorcycle": {
            "<100 CC":0.0325,
            "<200 CC":0.0417,
            "<300 CC":0.0540,
            "<500 CC":0.0542
        }, 
        "electric": 0.0
    },
    "Bicycle": {"any": 0.0},  
    "Pedestrian": {"any": 0.0},  
}

# vehicle details
travel_mode = st.sidebar.selectbox("Travel Mode", ["Car", "Freight-vehicle", "Three-wheeler", "Two-wheeler", "Bicycle", "Pedestrian"])
if travel_mode == "Car":
    car_type = st.sidebar.selectbox("Select Car Type", ["Small", "Hatchback", "Sedan", "SUV", "Electric"])
    if car_type == "Electric":
        fuel_type = None
    elif car_type== "Small":
        engine_size="<800 CC"
        fuel_type = st.sidebar.selectbox("Select Fuel Type", ["Petrol", "CNG", "LPG"])
    elif car_type== "Hatchback":
        engine_size = st.sidebar.selectbox("Select Engine Size", ["<1000 CC", "<1500 CC"])
        fuel_type = st.sidebar.selectbox("Select Fuel Type", ["Diesel", "Petrol"])
    elif car_type== "Sedan":
        engine_size = st.sidebar.selectbox("Select Engine Size", ["<1500 CC", "<2000 CC", "<2500 CC", "<3000 CC", ">3000 CC"])
        fuel_type = st.sidebar.selectbox("Select Fuel Type", ["Diesel", "Petrol"])
    elif car_type== "SUV":
        engine_size = st.sidebar.selectbox("Select Engine Size", ["<2000 CC", "<2500 CC", "<3000 CC", ">3000 CC"])
        fuel_type = st.sidebar.selectbox("Select Fuel Type", ["Diesel", "Petrol"])
elif travel_mode == "Freight-vehicle":
    car_type = None
    engine_size = st.sidebar.selectbox("Select Freight Vehicle Type", ["LDV (<3.5T)", "MDV (<12T)", "HDV (>12T)"])
    fuel_type = None
elif travel_mode == "Three-wheeler":
    car_type = None
    engine_size = None
    fuel_type = st.sidebar.selectbox("Select Fuel Type", ["petrol", "diesel", "CNG"])
elif travel_mode == "Two-wheeler":
    car_type = None
    sub_type = st.sidebar.selectbox("Select Two-Wheeler Type", ["scooter", "motorcycle"])
    if sub_type == "motorcycle":
        engine_size = st.sidebar.selectbox("Select Engine Size", ["<100 CC", "<200 CC", "<300 CC", "<500 CC"])
    else:
        engine_size = None
    fuel_type = None
else:
    car_type = None
    engine_size = None
    fuel_type = None

st.sidebar.divider()

# input mode
st.sidebar.header("Plan Route")
input_mode = st.sidebar.radio("Input Mode", ["Coordinates", "Search for Destination"])

# fetch coordinates using HERE API
def fetch_coordinates(location_name):
    url = "https://geocode.search.hereapi.com/v1/geocode"
    params = {
        "q": location_name,
        "apiKey": HERE_API_KEY,
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data["items"]:
            coords = data["items"][0]["position"]
            return f"{coords['lat']},{coords['lng']}"
        else:
            st.error("Location not found.")
            return None
    else:
        st.error(f"Error connecting to HERE API: {response.status_code}")
        st.write("Response:", response.text)
        return None

# starting location input
start_location_name = None  

if input_mode == "Coordinates":
    start_location = st.sidebar.text_input("Enter Starting Location (Latitude,Longitude)", "e.g., 52.50931,13.42936")
    start_location_name = "Start Location"  
else:
    start_location_name = st.sidebar.text_input("Search Starting Location")  
    if start_location_name:
        start_location_coords = fetch_coordinates(start_location_name)
        if start_location_coords:
            start_location = start_location_coords
            st.sidebar.success(f"Selected Coordinates: {start_location}")
        else:
            st.sidebar.error("Location not found.")

# Add stop
if input_mode == "Coordinates":
    stop_name = "Stop"
    new_stop = st.sidebar.text_input("Add a Stop (Latitude,Longitude)", "e.g., 52.5206,13.3862")
else:
    stop_name = st.sidebar.text_input("Search Stop Location")
    if stop_name:
        stop_location_coords = fetch_coordinates(stop_name)
        if stop_location_coords:
            new_stop = stop_location_coords
            st.sidebar.success(f"Stop Coordinates: {new_stop}")
        else:
            st.sidebar.error("Stop location not found.")

if st.sidebar.button("Add Stop", type='secondary'):
    if new_stop and stop_name:
        st.session_state.stops.append({"name": stop_name, "coordinates": new_stop})
        st.sidebar.success(f"Added Stop: {stop_name}")
    else:
        st.sidebar.error("Please enter a valid stop.")
fixed_stop_coords = None
fixed_stop = None

# Input for ending location
if input_mode == "Coordinates":
    fixed_stop_name = "Ending Location"
    fixed_stop = st.sidebar.text_input("Ending Location (leave empty if flexible)", "e.g., 52.50931,13.42936")
else:
    fixed_stop_name = st.sidebar.text_input("Search Ending Location (leave empty if flexible)")
    if fixed_stop_name:
        fixed_stop_coords = fetch_coordinates(fixed_stop_name)
        if fixed_stop_coords:
            fixed_stop = fixed_stop_coords
            st.sidebar.success(f"Selected Ending Coordinates: {fixed_stop}")
        else:
            st.sidebar.error("Ending location not found.")

# Display stops in formatted style
st.sidebar.subheader("Stops in the Route:")
if st.session_state.stops:
    for i, stop in enumerate(st.session_state.stops, start=1):
        st.sidebar.write(f"{i}. {stop['name']}: {stop['coordinates']}")
    if st.sidebar.button("Clear All Stops", type='secondary'):
        st.session_state.stops = []
        st.sidebar.info("Cleared all stops.")
else:
    st.sidebar.write("No stops added yet.")

def get_tomtom_travel_mode(travel_mode):
    mode_mapping = {
        "Freight-vehicle": "truck",
        "Car": "car",
        "Three-wheeler": "car", 
        "Two-wheeler": "motorcycle",
        "Bicycle": "bicycle",
        "Pedestrian": "pedestrian"
    }
    return mode_mapping.get(travel_mode, "car")  # default to carr if not found

# Calculate route using TomTom API 
def calculate_route_tomtom(start, stops, specific_end=None):
    stops = [stop["coordinates"] if isinstance(stop, dict) else stop for stop in stops]
    waypoints = ":".join(stops) if stops else ""
    route = f"{start}:{waypoints}:{specific_end}" if specific_end else f"{start}:{waypoints}"
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{route}/json"
    tomtom_travel_mode = get_tomtom_travel_mode(travel_mode)
    params = {
        "key": TOMTOM_API_KEY,
        "routeType": "fastest",
        "traffic": traffic,
        "travelMode": tomtom_travel_mode
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        try:
            route_geometry = [
                (point["latitude"], point["longitude"])
                for leg in data["routes"][0]["legs"]
                for point in leg["points"]
            ]
            # converting to longitude,latitude for folium
            route_geometry = [(lng, lat) for lat, lng in route_geometry]

            travel_time = data["routes"][0]["summary"]["travelTimeInSeconds"]
            total_distance = data["routes"][0]["summary"]["lengthInMeters"]
            return travel_time, total_distance, route_geometry
        except KeyError as e:
            st.error(f"Unexpected response structure: Missing key {e}")
            return None, None, None
    else:
        st.error(f"Error fetching route: {response.status_code} - {response.text}")
        return None, None, None

# solving travelling salesman problem using TomTom API and heldkarp alg
def solve_tsp_path_with_details(start, stops, fixed_stop=None):
    all_locations = [start] + [stop["coordinates"] if isinstance(stop, dict) else stop for stop in stops]
    if fixed_stop:
        all_locations.append(fixed_stop)
    n = len(all_locations)

    distance_matrix = [[0] * n for _ in range(n)]
    time_matrix = [[0] * n for _ in range(n)]
    route_geometries = [[[] for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                travel_time, distance, geometry = calculate_route_tomtom(all_locations[i], [all_locations[j]])
                distance_matrix[i][j] = distance
                time_matrix[i][j] = travel_time
                route_geometries[i][j] = geometry

    dp = [[math.inf] * n for _ in range(1 << n)]
    dp[1][0] = 0
    parent = [[-1] * n for _ in range(1 << n)]

    for mask in range(1 << n):
        for i in range(n):
            if mask & (1 << i):
                for j in range(n):
                    if not mask & (1 << j):
                        next_mask = mask | (1 << j)
                        new_cost = dp[mask][i] + distance_matrix[i][j]
                        if new_cost < dp[next_mask][j]:
                            dp[next_mask][j] = new_cost
                            parent[next_mask][j] = i

    min_cost = math.inf
    last_city = -1
    endpoint = n - 1 if fixed_stop else None

    if fixed_stop:
        min_cost = dp[(1 << n) - 1][endpoint]
        last_city = endpoint
    else:
        for i in range(1, n):
            if dp[(1 << n) - 1][i] < min_cost:
                min_cost = dp[(1 << n) - 1][i]
                last_city = i

    mask = (1 << n) - 1
    optimal_route = []
    while last_city != -1:
        optimal_route.append(last_city)
        next_city = parent[mask][last_city]
        mask ^= (1 << last_city)
        last_city = next_city

    optimal_route.reverse()
    optimal_sequence = [all_locations[idx] for idx in optimal_route]

    total_distance = 0
    total_travel_time = 0
    full_route_geometry = []
    for i in range(len(optimal_route) - 1):
        total_distance += distance_matrix[optimal_route[i]][optimal_route[i + 1]]
        total_travel_time += time_matrix[optimal_route[i]][optimal_route[i + 1]]
        full_route_geometry.extend(route_geometries[optimal_route[i]][optimal_route[i + 1]])

    return optimal_sequence, total_distance, total_travel_time, full_route_geometry

# Align stop names according to the generated optimal sequence
def align_names_with_sequence(optimal_sequence, stops, start_location_name, fixed_stop_name):
    names_in_order = []
    for coord in optimal_sequence:
        if coord == start_location:
            names_in_order.append(start_location_name)  
        elif coord == fixed_stop:
            names_in_order.append(fixed_stop_name)  
        else:
            if input_mode == "Coordinates":
                names_in_order.append(coord)
            else:
                matched_stop = next((stop["name"] for stop in stops if stop["coordinates"] == coord), None)
                if matched_stop:
                    names_in_order.append(matched_stop)
    return names_in_order

# generating gmaps url
def generate_google_maps_url(sequence):
    origin = sequence[0]
    destination = sequence[-1]
    waypoints = "|".join(sequence[1:-1])  #all stops except origin and destination
    return f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&waypoints={waypoints}"

# calculating emissions based on the provided vehicle details and emissions data
def calculate_emissions(distance_km, travel_mode, car_type=None, engine_size=None, fuel_type=None, vehicle_type=None):
    try:
        if travel_mode == "Car":
            if car_type and engine_size and fuel_type:
                return distance_km * EMISSION_FACTORS[travel_mode][car_type][engine_size][fuel_type]
            elif car_type == "Electric":
                return 0.0
        elif travel_mode == "Freight-vehicle":
            if engine_size:
                return distance_km * EMISSION_FACTORS[travel_mode][engine_size]
        elif travel_mode == "Three-wheeler":
            if fuel_type:
                return distance_km * EMISSION_FACTORS[travel_mode].get(fuel_type, 0.0)
        elif travel_mode == "Two-wheeler":
            if sub_type == "motorcycle" and engine_size:
                return distance_km * EMISSION_FACTORS[travel_mode][sub_type].get(engine_size, 0.0)
            elif sub_type == "scooter":
                return distance_km * EMISSION_FACTORS[travel_mode].get(sub_type, 0.0)
        else:
            return 0.0
    except KeyError:
        st.error("Emission factor not found for the selected options.")
        return 0.0



if st.sidebar.button("Calculate Optimal Route", type="primary"):
    if not start_location:
        st.sidebar.error("Please provide a starting location.")
    elif not st.session_state.stops:
        st.sidebar.error("Please add at least one stop.")
    else:
        optimal_sequence, total_distance, travel_time, route_geometry = solve_tsp_path_with_details(
            start=start_location, stops=st.session_state.stops, fixed_stop=fixed_stop
        )
        if optimal_sequence:
            st.session_state.optimal_route = {
                "sequence": optimal_sequence,
                "distance": total_distance,
                "time": travel_time,
                "coordinates": route_geometry,
            }

def format_travel_time(travel_time_seconds):
    """Converts travel time from seconds to hours and minutes."""
    hours = travel_time_seconds // 3600
    minutes = (travel_time_seconds % 3600) // 60
    return f"{hours} hours, {minutes} minutes" if hours > 0 else f"{minutes} minutes"

# displaying on the main screen
if st.session_state.optimal_route:
    route_data = st.session_state.optimal_route

    stop_names_in_order = align_names_with_sequence(
        optimal_sequence=route_data["sequence"],
        stops=st.session_state.stops,
        start_location_name=start_location_name,
        fixed_stop_name=fixed_stop_name
    )
    col1, col2 = st.columns([0.55,0.45], border=True)
    col1.markdown("##### \U0001F6A6 Optimal Sequence:")
    for idx, stop_name in enumerate(stop_names_in_order, start=1):
        col1.write(f"{idx}. {stop_name}")
    formatted_travel_time = format_travel_time(route_data['time'])
    total_emissions = calculate_emissions(route_data['distance'] / 1000, travel_mode, car_type, engine_size, fuel_type)
    col2.markdown(f"##### \U0001F552 Total Travel Time: {formatted_travel_time}")
    col2.markdown(f"##### \U0001F6E3 Total Distance: {route_data['distance'] / 1000:.2f} km")
    col2.markdown(f"##### \U0001F30F Estimated Emissions: {total_emissions:.2f} kg CO₂")

    #button for gmap link
    google_maps_url = generate_google_maps_url(route_data["sequence"])
    
    st.markdown(
        f"""
        <a href="{google_maps_url}" target="_blank">
            <button style="
                background-color: #4d158d;
                color: white;
                border: none;
                padding: 10px 20px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 16px;
                margin: 10px 2px;
                border-radius: 8px;
                cursor: pointer;
            ">
                Open in Google Maps
            </button>
        </a>
        """,
        unsafe_allow_html=True)

    # map visualization
    route_map = folium.Map(location=[float(route_data["sequence"][0].split(",")[0]), float(route_data["sequence"][0].split(",")[1])], zoom_start=12)
    folium.PolyLine(locations=[coord[::-1] for coord in route_data["coordinates"]], color="blue", weight=5).add_to(route_map)

    # adding markers for start, waypoints, and end 
    for idx, location in enumerate(route_data["sequence"]):
        lat, lon = map(float, location.split(","))
        if idx == 0:
            label = "Start"
            icon_color = "green"
        elif idx == len(route_data["sequence"]) - 1:
            label = "End"
            icon_color = "red"
        else:
            label = f"Waypoint {idx}"
            icon_color = "blue"
        folium.Marker(location=[lat, lon], popup=label, icon=folium.Icon(color=icon_color)).add_to(route_map)

    st_folium(route_map, width=1000, height=560)

