from flask import Flask, jsonify, render_template, request
import ee
from google.oauth2 import service_account
from datetime import datetime, timedelta

app = Flask(__name__)

SERVICE_ACCOUNT_FILE = 'config/creds2.json'

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

# Route for the home page
@app.route('/')
def index():
    return render_template('home.html')

# Route for the about page
@app.route('/about/')
def about():
    return render_template('about_us.html')

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

        # Process data based on the selected pollutant
        if pollutant == 'PM10':
            # Fetch the aerosol index data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_AER_AI') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('absorbing_aerosol_index')

            if filtered_collection.size().getInfo() == 0:
                return jsonify({'error': 'No PM10 data available for the specified parameters.'}), 404

            # Mask negative values in the aerosol index
            def mask_negative_values(image):
                return image.updateMask(image.gte(0))

            filtered_collection = filtered_collection.map(mask_negative_values)

            # Calculate the mean aerosol index
            aerosol_index_mean = filtered_collection.mean().clip(buffered_city_geometry)

            # Convert aerosol index to PM10 concentration
            PM10_mean = aerosol_index_mean.multiply(50).add(20)  # Adjust scaling factor and offset as needed
            pollutant_mean = PM10_mean.rename('PM10')

            # Calculate percentiles for visualization
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

        elif pollutant == 'PM2.5':
            # Fetch and process the PM2.5 data using the MODIS dataset
            filtered_collection = ee.ImageCollection('MODIS/061/MCD19A2_GRANULES') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('Optical_Depth_055')

            if filtered_collection.size().getInfo() == 0:
                return jsonify({'error': 'No PM2.5 data available for the specified parameters.'}), 404
            
            def mask_negative_values(image):
                return image.updateMask(image.gte(0))

            filtered_collection = filtered_collection.map(mask_negative_values)

            # Apply scaling factor and offset to convert to PM2.5 concentration
            PM2_5_mean = filtered_collection.mean().clip(buffered_city_geometry) \
                .multiply(206.91).add(41.181)
            pollutant_mean = PM2_5_mean.rename('PM2_5')

            # Calculate percentiles for visualization
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

        elif pollutant == 'NO2':
            # Fetch and process the NO2 data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_NO2') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('NO2_column_number_density')

            collection_size = filtered_collection.size().getInfo()
            print(f"NO2 collection size for the given parameters: {collection_size}")

            if collection_size == 0:
                return jsonify({'error': 'No NO2 data available for the specified parameters.'}), 404
            
            def mask_negative_values(image):
                return image.updateMask(image.gte(0))

            filtered_collection = filtered_collection.map(mask_negative_values)

            NO2_mean = filtered_collection.mean().clip(buffered_city_geometry)
            pollutant_mean = NO2_mean.rename('NO2')

            # Calculate percentiles for visualization
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

            min_value = round(min_value, 8)
            max_value = round(max_value, 8)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'NO2 data is too low or not available for visualization in this area/date range.'}), 404

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
                return jsonify({'error': 'No CO data available for the specified parameters.'}), 404
            
            def mask_negative_values(image):
                return image.updateMask(image.gte(0))

            filtered_collection = filtered_collection.map(mask_negative_values)

            # Calculate means of the required bands
            CO_mean = filtered_collection.select('CO_column_number_density').mean().clip(buffered_city_geometry)
            H2O_mean = filtered_collection.select('H2O_column_number_density').mean().clip(buffered_city_geometry)
            surface_pressure_mean = surface_pressure_collection.mean().clip(buffered_city_geometry)

            # Calculate total column of dry air
            TC_dry_air = surface_pressure_mean.divide(g * m_dry_air).subtract(H2O_mean.multiply(m_H2O / m_dry_air))

            # Calculate CO concentration in ppb
            XCO_ppb = CO_mean.divide(TC_dry_air).multiply(1e9).rename('XCO_ppb')
            pollutant_mean = XCO_ppb

            # Calculate percentiles for visualization
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

        elif pollutant == 'SO2':
            # Fetch and process the SO2 data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_SO2') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('SO2_column_number_density')

            if filtered_collection.size().getInfo() == 0:
                return jsonify({'error': 'No SO2 data available for the specified parameters.'}), 404
            
            def mask_negative_values(image):
                return image.updateMask(image.gte(0))

            filtered_collection = filtered_collection.map(mask_negative_values)

            SO2_mean = filtered_collection.mean().clip(buffered_city_geometry)
            pollutant_mean = SO2_mean.rename('SO2')

            # Calculate percentiles for visualization
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

            min_value = round(min_value, 8)
            max_value = round(max_value, 8)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'SO2 data is too low or not available for visualization in this area/date range.'}), 404

        elif pollutant == 'O3':
            # Fetch and process the O3 data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_O3') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('O3_column_number_density')

            if filtered_collection.size().getInfo() == 0:
                return jsonify({'error': 'No O3 data available for the specified parameters.'}), 404
            
            def mask_negative_values(image):
                return image.updateMask(image.gte(0))

            filtered_collection = filtered_collection.map(mask_negative_values)

            O3_mean = filtered_collection.mean().clip(buffered_city_geometry)
            pollutant_mean = O3_mean.rename('O3')

            # Calculate percentiles for visualization
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

            min_value = round(min_value, 8)
            max_value = round(max_value, 8)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'O3 data is too low or not available for visualization in this area/date range.'}), 404

        elif pollutant == 'HCHO':
            # Fetch and process the HCHO data from Sentinel-5P
            filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_HCHO') \
                .filterBounds(buffered_city_geometry) \
                .filterDate(start_date, end_date) \
                .select('tropospheric_HCHO_column_number_density')

            if filtered_collection.size().getInfo() == 0:
                return jsonify({'error': 'No HCHO data available for the specified parameters.'}), 404
            
            def mask_negative_values(image):
                return image.updateMask(image.gte(0))

            filtered_collection = filtered_collection.map(mask_negative_values)

            HCHO_mean = filtered_collection.mean().clip(buffered_city_geometry)
            pollutant_mean = HCHO_mean.rename('HCHO')

            # Calculate percentiles for visualization
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

            min_value = round(min_value, 8)
            max_value = round(max_value, 8)

            if min_value == 0 and max_value == 0:
                return jsonify({'error': 'HCHO data is too low or not available for visualization in this area/date range.'}), 404

        # elif pollutant == 'CH4':
        #     # Fetch and process the CH4 data from Sentinel-5P
        #     filtered_collection = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CH4') \
        #         .filterBounds(buffered_city_geometry) \
        #         .filterDate(start_date, end_date) \
        #         .select('CH4_column_volume_mixing_ratio_dry_air')

        #     if filtered_collection.size().getInfo() == 0:
        #         return jsonify({'error': 'No CH4 data available for the specified parameters.'}), 404
            
            # def mask_negative_values(image):
            #     return image.updateMask(image.gte(0))

            # filtered_collection = filtered_collection.map(mask_negative_values)

        #     CH4_mean = filtered_collection.mean().clip(buffered_city_geometry)
        #     pollutant_mean = CH4_mean.rename('CH4')

        #     # Calculate percentiles for visualization
        #     percentiles = pollutant_mean.reduceRegion(
        #         reducer=ee.Reducer.percentile([5, 95]),
        #         geometry=buffered_city_geometry,
        #         scale=1000,
        #         bestEffort=True
        #     ).getInfo()

        #     min_value = percentiles.get('CH4_p5', None)
        #     max_value = percentiles.get('CH4_p95', None)

        #     if min_value is None or max_value is None:
        #         return jsonify({'error': 'Could not calculate visualization parameters for CH4.'}), 500

        #     min_value = round(min_value, 2)
        #     max_value = round(max_value, 2)

        #     if min_value == 0 and max_value == 0:
        #         return jsonify({'error': 'CH4 data is too low or not available for visualization in this area/date range.'}), 404

        else:
            return jsonify({'error': f"Unsupported pollutant: {pollutant}"}), 400

        # Handle cases where min and max values are the same
        if min_value == max_value:
            min_value -= 0.1 * abs(min_value) or 0.1
            max_value += 0.1 * abs(max_value) or 0.1

        # Apply a buffer to ensure full utilization of the color palette
        buffer_range = abs(max_value - min_value) * 0.1
        vis_params = {
            'min': min_value - buffer_range,
            'max': max_value + buffer_range,
            'palette': ['blue', 'cyan', 'green', 'yellow', 'red']
        }

        # Generate map tiles for visualization
        map_id = pollutant_mean.getMapId(vis_params)
        tile_url = map_id['tile_fetcher'].url_format

        # Format values for the legend
        min_value_sci = f"{min_value:.2e}"
        max_value_sci = f"{max_value:.2e}"

        # Return the response as JSON
        return jsonify({
            'tile_url': tile_url,
            'min': min_value_sci,
            'max': max_value_sci,
            'min_raw': min_value,
            'max_raw': max_value
        })

    except Exception as e:
        # Handle any exceptions that occur during processing
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
