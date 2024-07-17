import ee
import pandas as pd
import datetime
from google.oauth2 import service_account


SERVICE_ACCOUNT_FILE = 'config/creds2.json'

# Authenticate to GEE using the service account
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)
ee.Initialize(credentials)


def get_co_data(start_date, end_date, region, scale):
    # Define the Sentinel-5P CO dataset
    dataset = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_CO') \
                .filterDate(start_date, end_date) \
                .select('CO_column_number_density')

    # Calculate the mean CO concentration for the specified date range and region
    mean_co = dataset.mean().reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=scale,
        bestEffort=True
    )

    return mean_co.getInfo()['CO_column_number_density']

def generate_dates(start_year, end_year):
    dates = []
    start_date = datetime.date(start_year, 1, 1)
    end_date = datetime.date(end_year, 12, 31)
    delta = datetime.timedelta(days=1)
    
    while start_date <= end_date:
        dates.append(start_date.strftime('%Y-%m-%d'))
        start_date += delta
    
    return dates

def download_co_data(lat, lon, start_year, end_year, scale=1000):
    region = ee.Geometry.Point(lon, lat).buffer(25000)  # 25 km buffer radius
    dates = generate_dates(start_year, end_year)
    
    data = []

    for date in dates:
        try:
            co_conc = get_co_data(date, date, region, scale)
            data.append([date, co_conc * 1e9])  # Convert from mol/m^2 to ppb
            print(f"Downloaded data for {date}")
        except Exception as e:
            print(f"Error on {date}: {e}")
            data.append([date, None])

    df = pd.DataFrame(data, columns=['Date', 'CO_conc_ppb'])
    df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d').dt.strftime('%d%m%Y')
    df.to_csv('dataset/historical_co_density.csv', index=False)
    print("Data saved to historical_co_density.csv")

if __name__ == '__main__':
    # Example coordinates for the region of interest
    lat = 29.7604  # Houston latitude
    lon = -95.3698  # Houston longitude

    # Download CO data for 10 years
    download_co_data(lat, lon, 2011, 2023)
