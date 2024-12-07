import os
from flask import Flask, jsonify, render_template, request
import ee
from google.oauth2 import service_account
from datetime import datetime, timedelta
import math  # Import math module for logarithmic calculations

app = Flask(__name__)

# Define the file paths
file_path = "/home/ubuntu/ssta/config/creds2.json"
default_path = "config/creds2.json"

# Check if the file exists and assign the appropriate value to the variable
SERVICE_ACCOUNT_FILE = file_path if os.path.exists(file_path) else default_path

# Load your Windy API key
WINDY_API_KEY = "DHnqHp6YzeueWA6uhkK3cxT8USF5QsuX"

# Constants for pollutant calculations
g = 9.82           # Acceleration due to gravity (m/s^2)
m_H2O = 0.01801528  # Molar mass of water vapor (kg/mol)
m_dry_air = 0.0289644  # Molar mass of dry air (kg/mol)

# Authenticate to Google Earth Engine using the service account
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)
ee.Initialize(credentials)

# Function to adjust units based on data range
def adjust_units(min_value, max_value, base_unit):
    prefixes = {
        -12: 'p',
        -9: 'n',
        -6: 'μ',
        -3: 'm',
        0: '',
        3: 'k',
        6: 'M',
        9: 'G',
        12: 'T'
    }

    abs_max = max(abs(min_value), abs(max_value))
    if abs_max == 0:
        exponent = 0
    else:
        exponent = int(math.floor(math.log10(abs_max)))
        exponent = (exponent // 3) * 3  # Round to nearest lower multiple of 3
        exponent = min(max(exponent, -12), 12)  # Limit exponent between -12 and 12

    scaling_factor = 10 ** (-exponent)
    prefix = prefixes.get(exponent, '')
    adjusted_unit = f"{prefix}{base_unit}"
    return scaling_factor, adjusted_unit

def interpolate_data_if_empty(pollutant, city_lat, city_lon, start_date, end_date, original_buffer):
    # If no data is available at the given buffer, we try larger buffers
    # This is a simple interpolation approach by expanding the search area until we find data.
    # We do not change any other logic, just attempt to find data in a larger radius and return mean.
    multipliers = [2, 5, 10]  # Try larger and larger radii
    for m in multipliers:
        new_buffer = original_buffer * m
        buffered_city_geometry = ee.Geometry.Point(city_lon, city_lat).buffer(new_buffer)
        if pollutant == 'PM10':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_AER_AI') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('absorbing_aerosol_index')
        elif pollutant == 'PM2.5':
            filtered_collection = ee.ImageCollection('MODIS/061/MCD19A2_GRANULES') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('Optical_Depth_055')
        elif pollutant == 'NO2':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_NO2') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('NO2_column_number_density')
        elif pollutant == 'CO':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CO') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select(['CO_column_number_density', 'H2O_column_number_density'])
        elif pollutant == 'SO2':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_SO2') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('SO2_column_number_density')
        elif pollutant == 'O3':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_O3') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('O3_column_number_density')
        elif pollutant == 'HCHO':
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_HCHO') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('tropospheric_HCHO_column_number_density')
        else:
            filtered_collection = None

        if filtered_collection and filtered_collection.size().getInfo() > 0:
            # We found data in a larger area. Take the mean and return it.
            def mask_negative_values(image):
                return image.updateMask(image.gte(0))
            filtered_collection = filtered_collection.map(mask_negative_values)
            mean_image = filtered_collection.mean().clip(buffered_city_geometry)
            # Return this mean image as "interpolated" data
            return mean_image, buffered_city_geometry
    # If no data found in any expanded search, return None
    return None, None

# Route for the home page
@app.route('/')
def index():
    return render_template('home.html')

# Route for the about page
@app.route('/about/')
def about():
    return render_template('about.html')

# Route for the sample page
@app.route('/sample/')
def sample():
    return render_template('sample.html')

# Route for the contact page
@app.route('/contact/')
def contact():
    return render_template('contact_us.html')

# API route to fetch pollutant data
@app.route('/api/get-pollutant', methods=['GET'])
def get_pollutant():
    try:
        # Retrieve parameters from the request
        city_lat = float(request.args.get('lat'))
        city_lon = float(request.args.get('lon'))
        buffer = request.args.get('buffer', default=50000, type=int)
        hml = request.args.get('hml', 'false').lower() == 'true'


        # Set default start and end dates (last 7 days)
        current_date = datetime.utcnow()
        default_end_date = current_date.strftime('%Y-%m-%dT%H:%M:%S')
        default_start_date = (current_date - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')

        start_date = request.args.get('start_date', default_start_date)
        end_date = request.args.get('end_date', default_end_date)

        pollutant = request.args.get('pollutant', 'PM2.5')  # Default to PM2.5 if not specified

        if not city_lat or not city_lon:
            return jsonify({'error': 'Latitude and longitude are required parameters.'}), 400

        # Define a buffer around the specified point
        buffer_radius = buffer  # in meters
        buffered_city_geometry = ee.Geometry.Point(city_lon, city_lat).buffer(buffer_radius)

        if pollutant == 'PM10':
            # Fetch the aerosol index data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_AER_AI') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('absorbing_aerosol_index')

            if filtered_collection.size().getInfo() == 0:
                # Try interpolation
                mean_image, new_geom = interpolate_data_if_empty('PM10', city_lat, city_lon, start_date, end_date, buffer_radius)
                if mean_image is None:
                    return jsonify({'error': 'No PM10 data available for the specified parameters.'}), 404
                else:
                    aerosol_index_mean = mean_image
                    buffered_city_geometry = new_geom
            else:
                def mask_negative_values(image):
                    return image.updateMask(image.gte(0))
                filtered_collection = filtered_collection.map(mask_negative_values)
                aerosol_index_mean = filtered_collection.mean().clip(buffered_city_geometry)

            # Convert aerosol index to PM10 concentration
            PM10_mean = aerosol_index_mean.multiply(50).add(20)  # Adjust scaling factor and offset as needed
            pollutant_mean = PM10_mean.rename('PM10')

            stats = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = stats.get('PM10_min', None)
            max_value = stats.get('PM10_max', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate data range for PM10.'}), 500

            base_unit = 'µg/m³'
            scaling_factor, adjusted_unit = adjust_units(min_value, max_value, base_unit)

            pollutant_mean = pollutant_mean.multiply(scaling_factor)

            percentiles = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.percentile([5, 95]),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = percentiles.get('PM10_p5', None)
            max_value = percentiles.get('PM10_p95', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate visualization parameters for PM10.'}), 500

            min_value = round(min_value, 2)
            max_value = round(max_value, 2)
            unit = adjusted_unit

        elif pollutant == 'PM2.5':
            # Fetch and process the PM2.5 data using the MODIS dataset
            filtered_collection = ee.ImageCollection('MODIS/061/MCD19A2_GRANULES') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('Optical_Depth_055')

            if filtered_collection.size().getInfo() == 0:
                # Try interpolation
                mean_image, new_geom = interpolate_data_if_empty('PM2.5', city_lat, city_lon, start_date, end_date, buffer_radius)
                if mean_image is None:
                    return jsonify({'error': 'No PM2.5 data available for the specified parameters.'}), 404
                else:
                    PM2_5_mean = mean_image.multiply(206.91).add(41.181)
                    buffered_city_geometry = new_geom
            else:
                def mask_negative_values(image):
                    return image.updateMask(image.gte(0))
                filtered_collection = filtered_collection.map(mask_negative_values)
                PM2_5_mean = filtered_collection.mean().clip(buffered_city_geometry) \
                    .multiply(206.91).add(41.181)

            pollutant_mean = PM2_5_mean.rename('PM2_5')

            stats = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = stats.get('PM2_5_min', None)
            max_value = stats.get('PM2_5_max', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate data range for PM2.5.'}), 500

            base_unit = 'µg/m³'
            scaling_factor, adjusted_unit = adjust_units(min_value, max_value, base_unit)

            pollutant_mean = pollutant_mean.multiply(scaling_factor)

            percentiles = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.percentile([5, 95]),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = percentiles.get('PM2_5_p5', None)
            max_value = percentiles.get('PM2_5_p95', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate visualization parameters for PM2.5.'}), 500

            min_value = round(min_value, 2)
            max_value = round(max_value, 2)
            unit = adjusted_unit

        elif pollutant == 'NO2':
            # Fetch and process the NO2 data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_NO2') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('NO2_column_number_density')

            collection_size = filtered_collection.size().getInfo()
            print(f"NO2 collection size for the given parameters: {collection_size}")

            if collection_size == 0:
                # Try interpolation
                mean_image, new_geom = interpolate_data_if_empty('NO2', city_lat, city_lon, start_date, end_date, buffer_radius)
                if mean_image is None:
                    return jsonify({'error': 'No NO2 data available for the specified parameters.'}), 404
                else:
                    NO2_mean = mean_image
                    buffered_city_geometry = new_geom
            else:
                def mask_negative_values(image):
                    return image.updateMask(image.gte(0))
                filtered_collection = filtered_collection.map(mask_negative_values)
                NO2_mean = filtered_collection.mean().clip(buffered_city_geometry)

            pollutant_mean = NO2_mean.rename('NO2')

            stats = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=500,
                bestEffort=True
            ).getInfo()

            min_value = stats.get('NO2_min', None)
            max_value = stats.get('NO2_max', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate data range for NO2.'}), 500

            base_unit = 'mol/m²'
            scaling_factor, adjusted_unit = adjust_units(min_value, max_value, base_unit)

            pollutant_mean = pollutant_mean.multiply(scaling_factor)

            percentiles = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.percentile([5, 95]),
                geometry=buffered_city_geometry,
                scale=500,
                bestEffort=True
            ).getInfo()

            min_value = percentiles.get('NO2_p5', None)
            max_value = percentiles.get('NO2_p95', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate visualization parameters for NO2.'}), 500

            min_value = round(min_value, 2)
            max_value = round(max_value, 2)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'NO2 data is too low or not available for visualization in this area/date range.'}), 404

            unit = adjusted_unit

        elif pollutant == 'CO':
            # Fetch and process the CO data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CO') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select(['CO_column_number_density', 'H2O_column_number_density'])

            surface_pressure_collection = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR") \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('surface_pressure')

            if filtered_collection.size().getInfo() == 0 or surface_pressure_collection.size().getInfo() == 0:
                # Try interpolation
                mean_image, new_geom = interpolate_data_if_empty('CO', city_lat, city_lon, start_date, end_date, buffer_radius)
                if mean_image is None:
                    return jsonify({'error': 'No CO data available for the specified parameters.'}), 404
                else:
                    # We need H2O for CO calculation, try a larger approach for H2O too
                    filtered_collection_h2o = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CO') \
                        .filterBounds(new_geom) \
                        .filterDate(start_date, end_date) \
                        .select(['H2O_column_number_density'])
                    if filtered_collection_h2o.size().getInfo() == 0:
                        return jsonify({'error': 'No CO data available for the specified parameters (H2O missing).'}), 404
                    def mask_negative_values(image):
                        return image.updateMask(image.gte(0))
                    filtered_collection_h2o = filtered_collection_h2o.map(mask_negative_values)
                    H2O_mean = filtered_collection_h2o.mean().clip(new_geom)

                    surface_pressure_collection_alt = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR") \
                        .filterBounds(new_geom) \
                        .filterDate(start_date, end_date) \
                        .select('surface_pressure')

                    if surface_pressure_collection_alt.size().getInfo() == 0:
                        return jsonify({'error': 'No CO data available for the specified parameters (Surface pressure missing).'}), 404
                    surface_pressure_mean = surface_pressure_collection_alt.mean().clip(new_geom)

                    CO_mean = mean_image
                    buffered_city_geometry = new_geom
                    # Calculate total column of dry air
                    TC_dry_air = surface_pressure_mean.divide(g * m_dry_air).subtract(H2O_mean.multiply(m_H2O / m_dry_air))
                    XCO_ppb = CO_mean.divide(TC_dry_air).multiply(1e9).rename('XCO_ppb')
                    pollutant_mean = XCO_ppb
                # end interpolation block
            else:
                def mask_negative_values(image):
                    return image.updateMask(image.gte(0))
                filtered_collection = filtered_collection.map(mask_negative_values)

                CO_mean = filtered_collection.select('CO_column_number_density').mean().clip(buffered_city_geometry)
                H2O_mean = filtered_collection.select('H2O_column_number_density').mean().clip(buffered_city_geometry)
                surface_pressure_mean = surface_pressure_collection.mean().clip(buffered_city_geometry)

                TC_dry_air = surface_pressure_mean.divide(g * m_dry_air).subtract(H2O_mean.multiply(m_H2O / m_dry_air))

                XCO_ppb = CO_mean.divide(TC_dry_air).multiply(1e9).rename('XCO_ppb')
                pollutant_mean = XCO_ppb

            stats = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = stats.get('XCO_ppb_min', None)
            max_value = stats.get('XCO_ppb_max', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate data range for CO.'}), 500

            base_unit = 'ppb'
            scaling_factor, adjusted_unit = adjust_units(min_value, max_value, base_unit)

            pollutant_mean = pollutant_mean.multiply(scaling_factor)

            percentiles = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.percentile([5, 95]),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = percentiles.get('XCO_ppb_p5', None)
            max_value = percentiles.get('XCO_ppb_p95', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate visualization parameters for CO.'}), 500

            min_value = round(min_value, 2)
            max_value = round(max_value, 2)
            unit = adjusted_unit

        elif pollutant == 'SO2':
            # Fetch and process the SO2 data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_SO2') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('SO2_column_number_density')

            if filtered_collection.size().getInfo() == 0:
                # Try interpolation
                mean_image, new_geom = interpolate_data_if_empty('SO2', city_lat, city_lon, start_date, end_date, buffer_radius)
                if mean_image is None:
                    return jsonify({'error': 'No SO2 data available for the specified parameters.'}), 404
                else:
                    SO2_mean = mean_image
                    buffered_city_geometry = new_geom
            else:
                def mask_negative_values(image):
                    return image.updateMask(image.gte(0))
                filtered_collection = filtered_collection.map(mask_negative_values)
                SO2_mean = filtered_collection.mean().clip(buffered_city_geometry)

            pollutant_mean = SO2_mean.rename('SO2')

            stats = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = stats.get('SO2_min', None)
            max_value = stats.get('SO2_max', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate data range for SO2.'}), 500

            base_unit = 'mol/m²'
            scaling_factor, adjusted_unit = adjust_units(min_value, max_value, base_unit)

            pollutant_mean = pollutant_mean.multiply(scaling_factor)

            percentiles = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.percentile([5, 95]),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = percentiles.get('SO2_p5', None)
            max_value = percentiles.get('SO2_p95', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate visualization parameters for SO2.'}), 500

            min_value = round(min_value, 2)
            max_value = round(max_value, 2)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'SO2 data is too low or not available for visualization in this area/date range.'}), 404

            unit = adjusted_unit

        elif pollutant == 'O3':
            # Fetch and process the O3 data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_O3') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('O3_column_number_density')

            if filtered_collection.size().getInfo() == 0:
                # Try interpolation
                mean_image, new_geom = interpolate_data_if_empty('O3', city_lat, city_lon, start_date, end_date, buffer_radius)
                if mean_image is None:
                    return jsonify({'error': 'No O3 data available for the specified parameters.'}), 404
                else:
                    O3_mean = mean_image
                    buffered_city_geometry = new_geom
            else:
                def mask_negative_values(image):
                    return image.updateMask(image.gte(0))
                filtered_collection = filtered_collection.map(mask_negative_values)
                O3_mean = filtered_collection.mean().clip(buffered_city_geometry)

            pollutant_mean = O3_mean.rename('O3')

            stats = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = stats.get('O3_min', None)
            max_value = stats.get('O3_max', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate data range for O3.'}), 500

            base_unit = 'mol/m²'
            scaling_factor, adjusted_unit = adjust_units(min_value, max_value, base_unit)

            pollutant_mean = pollutant_mean.multiply(scaling_factor)

            percentiles = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.percentile([5, 95]),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = percentiles.get('O3_p5', None)
            max_value = percentiles.get('O3_p95', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate visualization parameters for O3.'}), 500

            min_value = round(min_value, 2)
            max_value = round(max_value, 2)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'O3 data is too low or not available for visualization in this area/date range.'}), 404

            unit = adjusted_unit

        elif pollutant == 'HCHO':
            # Fetch and process the HCHO data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_HCHO') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('tropospheric_HCHO_column_number_density')

            if filtered_collection.size().getInfo() == 0:
                # Try interpolation
                mean_image, new_geom = interpolate_data_if_empty('HCHO', city_lat, city_lon, start_date, end_date, buffer_radius)
                if mean_image is None:
                    return jsonify({'error': 'No HCHO data available for the specified parameters.'}), 404
                else:
                    HCHO_mean = mean_image
                    buffered_city_geometry = new_geom
            else:
                def mask_negative_values(image):
                    return image.updateMask(image.gte(0))
                filtered_collection = filtered_collection.map(mask_negative_values)
                HCHO_mean = filtered_collection.mean().clip(buffered_city_geometry)

            pollutant_mean = HCHO_mean.rename('HCHO')

            stats = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.minMax(),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = stats.get('HCHO_min', None)
            max_value = stats.get('HCHO_max', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate data range for HCHO.'}), 500

            base_unit = 'mol/m²'
            scaling_factor, adjusted_unit = adjust_units(min_value, max_value, base_unit)

            pollutant_mean = pollutant_mean.multiply(scaling_factor)

            percentiles = pollutant_mean.reduceRegion(
                reducer=ee.Reducer.percentile([5, 95]),
                geometry=buffered_city_geometry,
                scale=1000,
                bestEffort=True
            ).getInfo()

            min_value = percentiles.get('HCHO_p5', None)
            max_value = percentiles.get('HCHO_p95', None)

            if min_value is None or max_value is None:
                return jsonify({'error': 'Could not calculate visualization parameters for HCHO.'}), 500

            min_value = round(min_value, 2)
            max_value = round(max_value, 2)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'HCHO data is too low or not available for visualization in this area/date range.'}), 404

            unit = adjusted_unit

        else:
            return jsonify({'error': f"Unsupported pollutant: {pollutant}"}), 400

        if min_value == max_value:
            min_value -= 0.1 * abs(min_value) or 0.1
            max_value += 0.1 * abs(max_value) or 0.1

        buffer_range = abs(max_value - min_value) * 0.1
        if hml:
            vis_params = {
                'min': min_value,
                'max': max_value,
                'palette': ['blue', 'yellow', 'red'],
            }
            legend_labels = ['Low', 'Medium', 'High']
        else:
            buffer_range = abs(max_value - min_value) * 0.1
            vis_params = {
                'min': min_value - buffer_range,
                'max': max_value + buffer_range,
                'palette': ['blue', 'cyan', 'green', 'yellow', 'red']
            }
            legend_labels = None

        map_id = pollutant_mean.getMapId(vis_params)
        tile_url = map_id['tile_fetcher'].url_format

        min_value_sci = f"{min_value:.2e}"
        max_value_sci = f"{max_value:.2e}"

        return jsonify({
                        'tile_url': tile_url,
                        'min': min_value_sci,
                        'max': max_value_sci,
                        'min_raw': min_value,
                        'max_raw': max_value,
                        'unit': unit,
                        'legend_labels': legend_labels
                    })


    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API route to get the Windy API key
@app.route('/api/get-windy-api-key', methods=['GET'])
def get_windy_api_key():
    if WINDY_API_KEY:
        return jsonify({'api_key': WINDY_API_KEY})
    else:
        return jsonify({'error': 'Windy API key not configured.'}), 500

if __name__ == '__main__':
    app.run(debug=True)
