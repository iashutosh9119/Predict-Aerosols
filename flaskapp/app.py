from flask import Flask, jsonify, render_template, request
import ee
from google.oauth2 import service_account
import os

app = Flask(__name__)

# SERVICE_ACCOUNT_FILE = '/home/ubuntu/ssta/config/creds2.json'
SERVICE_ACCOUNT_FILE = 'config/creds2.json'

# Load your Windy API key from an environment variable
WINDY_API_KEY = "DHnqHp6YzeueWA6uhkK3cxT8USF5QsuX"

# Constants for pollutant calculations
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

@app.route('/sample/')
def sample():
    return render_template('sample.html')

@app.route('/contact/')
def contact():
    return render_template('contact_us.html')

@app.route('/api/get-co-density', methods=['GET'])
def get_co_density():
    try:
        city_lat = float(request.args.get('lat'))
        city_lon = float(request.args.get('lon'))
        buffer = request.args.get('buffer', default=50000, type=int)

        start_date = request.args.get('start_date', '2024-01-01')
        end_date = request.args.get('end_date', '2024-05-31')

        pollutant = request.args.get('pollutant', 'CO')

        if not city_lat or not city_lon or not buffer:
            return jsonify({'error': 'Latitude, longitude, and buffer are required parameters.'}), 400

        # Define a buffer around the point
        buffer_radius = buffer  # in meters
        buffered_city_geometry = ee.Geometry.Point(city_lon, city_lat).buffer(buffer_radius)

        # Fetch and process the pollutant data
        if pollutant == 'CO':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CO') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select(['CO_column_number_density', 'H2O_column_number_density'])

            surface_pressure_collection = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR") \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('surface_pressure')

            # Check if the collections are empty
            if filtered_collection.size().getInfo() == 0 or surface_pressure_collection.size().getInfo() == 0:
                return jsonify({'error': 'No data available for the specified parameters.'}), 404

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

            return jsonify({'tile_url': tile_url, 'min': min_value, 'max': max_value})

        elif pollutant == 'NO2':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_NO2') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('NO2_column_number_density')

            # Log collection size for debugging
            collection_size = filtered_collection.size().getInfo()
            print(f"NO2 collection size for the given parameters: {collection_size}")

            if collection_size == 0:
                return jsonify({'error': 'No NO2 data available for the specified parameters.'}), 404

            # Calculate mean NO2 for the area
            NO2_mean_month = filtered_collection.mean().clip(buffered_city_geometry)

            # Set visualization parameters explicitly
            vis_params = {
                'min': 0,          # match your GEE example's min value
                'max': 0.0002,     # match your GEE example's max value
                'palette': ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']
            }

            # Use reduceRegion with a finer scale
            min_max = NO2_mean_month.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=500,  # Try a finer scale like 500m
                bestEffort=True
            ).getInfo()

            min_value = round(min_max.get('NO2_column_number_density_min', 0), 8)
            max_value = round(min_max.get('NO2_column_number_density_max', 0), 8)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'NO2 data is too low or not available for visualization in this area/date range.'}), 404

            # Generate map tiles
            map_id = NO2_mean_month.getMapId(vis_params)
            tile_url = map_id['tile_fetcher'].url_format

            return jsonify({'tile_url': tile_url, 'min': min_value, 'max': max_value})




        elif pollutant == 'PM2.5':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_AER_AI') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('absorbing_aerosol_index')

            if filtered_collection.size().getInfo() == 0:
                return jsonify({'error': 'No data available for the specified parameters.'}), 404

            PM2_5_mean_month = filtered_collection.mean().clip(buffered_city_geometry).multiply(0.7)

            min_max = PM2_5_mean_month.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = round(min_max.get('absorbing_aerosol_index_min', 0), 2)
            max_value = round(min_max.get('absorbing_aerosol_index_max', 0), 2)

            vis_params = {
                'min': min_value,
                'max': max_value,
                'palette': ['blue', 'cyan', 'green', 'yellow', 'red']
            }
            map_id = PM2_5_mean_month.getMapId(vis_params)
            tile_url = map_id['tile_fetcher'].url_format

            return jsonify({'tile_url': tile_url, 'min': min_value, 'max': max_value})

        elif pollutant == 'PM10':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_AER_AI') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('absorbing_aerosol_index')

            if filtered_collection.size().getInfo() == 0:
                return jsonify({'error': 'No data available for the specified parameters.'}), 404

            PM10_mean_month = filtered_collection.mean().clip(buffered_city_geometry).multiply(1.2)

            min_max = PM10_mean_month.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = round(min_max.get('absorbing_aerosol_index_min', 0), 2)
            max_value = round(min_max.get('absorbing_aerosol_index_max', 0), 2)

            vis_params = {
                'min': min_value,
                'max': max_value,
                'palette': ['blue', 'cyan', 'green', 'yellow', 'red']
            }
            map_id = PM10_mean_month.getMapId(vis_params)
            tile_url = map_id['tile_fetcher'].url_format

            return jsonify({'tile_url': tile_url, 'min': min_value, 'max': max_value})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-windy-api-key', methods=['GET'])
def get_windy_api_key():
    if WINDY_API_KEY:
        return jsonify({'api_key': WINDY_API_KEY})
    else:
        return jsonify({'error': 'Windy API key not configured.'}), 500

@app.route('/')
def index():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
