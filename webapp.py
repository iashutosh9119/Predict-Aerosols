from flask import Flask, jsonify, render_template, request
import ee
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import service_account

app = Flask(__name__)

# Path to your GCP service account key JSON file
SERVICE_ACCOUNT_FILE = 'config/creds2.json'


# Authenticate to GEE using the service account
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)
ee.Initialize(credentials)



@app.route('/api/get-co-density', methods=['GET'])
def get_co_density():

    city_lat = float(request.args.get('lat'))
    city_lon = float(request.args.get('lon'))
    buffer = request.args.get('buffer', default=50000, type=int) 

    # print(city_lat, city_lon, type(city_lat), type(city_lon))
    
    if not city_lat or not city_lon or not buffer:
        return jsonify({'error': 'Latitude, longitude and buffer are required parameters.'}), 400

    # Define a buffer around the point to cover an area around Hyderabad (25 kilometers)
    buffer_radius = buffer  # 25 kilometers in meters
    buffered_city_geometry = ee.Geometry.Point(city_lon, city_lat).buffer(buffer_radius)

    dataset = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CO') \
                .select('CO_column_number_density') \
                .filterDate('2019-06-01', '2019-06-11') \
                .filterBounds(buffered_city_geometry)

    # Calculate the mean CO density over the specified time period
    meanCO = dataset.mean().clip(buffered_city_geometry)

    vis_params = {
        'min': 0,
        'max': 0.05,
        'palette': ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']
    }
    map_id = meanCO.getMapId(vis_params)
    tile_url = map_id['tile_fetcher'].url_format

    return jsonify({'tile_url': tile_url})

@app.route('/')
def index():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
