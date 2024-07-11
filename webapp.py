from flask import Flask, jsonify, render_template
import requests
import os

app = Flask(__name__)

SERVICE_ACCOUNT_FILE = 'config/creds.json'

GEE_API_KEY = os.getenv('GEE_API_KEY')

@app.route('/api/get-co-density')
def get_co_density():
    url = 'YOUR_GEE_API_ENDPOINT'  # Replace with the actual GEE API endpoint
    headers = {
        'Authorization': f'Bearer {GEE_API_KEY}'
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    return jsonify(data)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
