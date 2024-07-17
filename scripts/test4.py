from flask import Flask, jsonify, render_template, request
import ee
import os
from google.oauth2 import service_account
import google.auth.transport.requests

app = Flask(__name__)

# Path to your GCP service account key JSON file
SERVICE_ACCOUNT_FILE = '/home/ashutosh/Workspace/Predict-Aerosols/config/creds2.json'

# Authenticate to GEE using the service account
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)
ee.Initialize(credentials)

@app.route('/api/get-co-density')
def get_co_density():
    # Get latitude and longitude from query parameters
    lat = float(request.args.get('lat', 29.7604))  # Default is Houston
    lon = float(request.args.get('lon', -95.3698))  # Default is Houston

    # Define the region of interest based on latitude and longitude
    delta = 0.1  # Degree span for the area of interest
    region = ee.Geometry.Rectangle([lon - delta, lat - delta, lon + delta, lat + delta])

    # Load the Sentinel-5P CO data
    dataset = ee.ImageCollection('COPERNICUS/S5P/NRTI/L3_CO') \
                .select('CO_column_number_density') \
                .filterDate('2024-01-01', '2024-12-31') \
                .filterBounds(region)

    # Calculate the mean CO density over the specified time period
    meanCO = dataset.mean().clip(region)

    # Generate a visualization URL
    vis_params = {
        'min': 0,
        'max': 0.05,
        'palette': ['blue', 'green', 'red']
    }
    map_id = meanCO.getMapId(vis_params)
    tile_url = map_id['tile_fetcher'].url_format

    return jsonify({'tile_url': tile_url})

@app.route('/')
def index():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
