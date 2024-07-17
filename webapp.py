from flask import Flask, jsonify, render_template, request
import ee
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account

app = Flask(__name__)

# Path to your GCP service account key JSON file
SERVICE_ACCOUNT_FILE = 'config/creds2.json'


# Constants
g = 9.82  # m/s^2
m_H2O = 0.01801528  # kg/mol
m_dry_air = 0.0289644  # kg/mol

# Authenticate to GEE using the service account
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)
ee.Initialize(credentials)


@app.route('/about/')
def about():
    return render_template('about_us.html')

@app.route('/contact/')
def contact():
    return render_template('contact_us.html')


@app.route('/api/get-co-density', methods=['GET'])
def get_co_density():

    city_lat = float(request.args.get('lat'))
    city_lon = float(request.args.get('lon'))
    buffer = request.args.get('buffer', default=25000, type=int) 

    start_date = request.args.get('start_date', '2024-01-01')
    end_date = request.args.get('end_date', '2024-05-31')

    # print(city_lat, city_lon, type(city_lat), type(city_lon))
    
    if not city_lat or not city_lon or not buffer:
        return jsonify({'error': 'Latitude, longitude and buffer are required parameters.'}), 400

    # Define a buffer around the point to cover an area around Hyderabad (25 kilometers)
    buffer_radius = buffer  # 25 kilometers in meters
    buffered_city_geometry = ee.Geometry.Point(city_lon, city_lat).buffer(buffer_radius)

        # Filter the collections for the given month
    filtered_collection = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_CO') \
        .filterBounds(buffered_city_geometry) \
        .filterDate(start_date, end_date) \
        .select(['CO_column_number_density', 'H2O_column_number_density'])

    surface_pressure_collection = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR") \
        .filterBounds(buffered_city_geometry) \
        .filterDate(start_date, end_date) \
        .select('surface_pressure')

    # Check if the collections are empty
    if filtered_collection.size().getInfo() == 0 or surface_pressure_collection.size().getInfo() == 0:
        return None

    # Calculate the mean over the collection for CO, H2O, and surface pressure
    CO_mean_month = filtered_collection.select('CO_column_number_density').mean().clip(buffered_city_geometry)
    H2O_mean_month = filtered_collection.select('H2O_column_number_density').mean().clip(buffered_city_geometry)
    surface_pressure_mean_month = surface_pressure_collection.mean().clip(buffered_city_geometry)

    # Calculate TC_dry_air for the month
    TC_dry_air_month = surface_pressure_mean_month.divide(g * m_dry_air).subtract(H2O_mean_month.multiply(m_H2O / m_dry_air))

    # Calculate XCO for the month
    XCO_month = CO_mean_month.divide(TC_dry_air_month).rename('XCO')

    # Convert XCO to ppb
    XCO_ppb_month = XCO_month.multiply(1e9).rename('XCO_ppb')

    # dataset = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CO') \
    #             .select('CO_column_number_density') \
    #             .filterDate(start_date, end_date) \
    #             .filterBounds(buffered_city_geometry)

    # # Calculate the mean CO density over the specified time period
    # meanCO = dataset.mean().clip(buffered_city_geometry)

    meanCO = XCO_ppb_month

    min_max = meanCO.reduceRegion(
    reducer=ee.Reducer.minMax(),
    geometry=buffered_city_geometry,
    scale=1000,
    bestEffort=True
    ).getInfo()


    min_value = round(min_max.get('XCO_ppb_min', 0), 2)
    max_value = round(min_max.get('XCO_ppb_max', 0), 2)


    vis_params = {
        'min': min_value,
        'max': max_value,
        'palette': ['blue', 'cyan', 'green', 'yellow', 'red']
    }
    map_id = meanCO.getMapId(vis_params)
    tile_url = map_id['tile_fetcher'].url_format

    return jsonify({'tile_url': tile_url,'min': min_value,'max': max_value})

@app.route('/')
def index():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)

