from flask import Flask, jsonify, render_template
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



@app.route('/api/get-co-density')
def get_co_density():
    # Define the region of interest (Houston)
    # houston = ee.Geometry.Rectangle([-95.797, 29.523, -95.014, 30.110])

    # Load the Sentinel-5P CO data
    city_lat = 29.7601
    city_lon = -95.3701


    # Define a buffer around the point to cover an area around Hyderabad (25 kilometers)
    buffer_radius = 50000  # 25 kilometers in meters
    buffered_city_geometry = ee.Geometry.Point(city_lon, city_lat).buffer(buffer_radius)

    dataset = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CO') \
                .select('CO_column_number_density') \
                .filterDate('2019-06-01', '2019-06-11') \
                .filterBounds(buffered_city_geometry)

    # Calculate the mean CO density over the specified time period
    meanCO = dataset.mean().clip(buffered_city_geometry)

    # print(meanCO)

    vis_params = {
        'min': 0,
        'max': 0.05,
        'palette': ['black', 'blue', 'purple', 'cyan', 'green', 'yellow', 'red']
    }
    map_id = meanCO.getMapId(vis_params)
    tile_url = map_id['tile_fetcher'].url_format

    return jsonify({'tile_url': tile_url})

    # co_feature_collection = meanCO.reduceToVectors(
    #     geometry=houston,
    #     scale=1000,
    #     geometryType='polygon',
    #     reducer=ee.Reducer.mean(),
    #     maxPixels=1e8
    # )
    # # Get the data as a URL
    # # url = meanCO.getThumbURL({
    # #     'min': 0,
    # #     'max': 0.05,
    # #     'palette': ['blue', 'green', 'red'],
    # #     'region': houston
    # # })

    # geojson = co_feature_collection.getInfo()
    
    # # return jsonify({'url': url})
    # return jsonify(geojson)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
