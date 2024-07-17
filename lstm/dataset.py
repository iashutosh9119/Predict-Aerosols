import ee
import pandas as pd
import datetime

# Initialize the Earth Engine API
ee.Initialize()

# Constants
g = 9.82  # m/s^2
m_H2O = 0.01801528  # kg/mol
m_dry_air = 0.0289644  # kg/mol

def get_co_data(start_date, end_date, region, scale):
    try:
        # Define the Sentinel-5P CO dataset
        filtered_collection = ee.ImageCollection('COPERNICUS/S5P/OFFL/L3_CO') \
        .filterBounds(region) \
        .filterDate(start_date, end_date) \
        .select(['CO_column_number_density', 'H2O_column_number_density'])

        surface_pressure_collection = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR") \
        .filterBounds(region) \
        .filterDate(start_date, end_date) \
        .select('surface_pressure')

        # Check if the collections are empty
        if filtered_collection.size().getInfo() == 0 or surface_pressure_collection.size().getInfo() == 0:
            return None

        # Calculate the mean over the collection for CO, H2O, and surface pressure
        CO_mean_month = filtered_collection.select('CO_column_number_density').mean().clip(region)
        H2O_mean_month = filtered_collection.select('H2O_column_number_density').mean().clip(region)
        surface_pressure_mean_month = surface_pressure_collection.mean().clip(region)

        # Calculate TC_dry_air for the month
        TC_dry_air_month = surface_pressure_mean_month.divide(g * m_dry_air).subtract(H2O_mean_month.multiply(m_H2O / m_dry_air))

        # Calculate XCO for the month
        XCO_month = CO_mean_month.divide(TC_dry_air_month).rename('XCO')
        XCO_ppb_month = XCO_month.multiply(1e9).rename('XCO_ppb')

        # Calculate the mean CO concentration for the month
        mean_value = XCO_ppb_month.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=1000
        ).getInfo()
        # Convert XCO to ppb
        co_value = mean_value.get('XCO_ppb')

        if co_value is None:
            raise ValueError(f"No data available for date range: {start_date} to {end_date}")
        return co_value

    except Exception as e:
        print(f"Error retrieving data for {start_date} to {end_date}: {e}")
        return None

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

    for i in range(len(dates) - 1):
        start_date = dates[i]
        end_date = dates[i + 1]
        try:
            co_conc = get_co_data(start_date, end_date, region, scale)
            if co_conc is not None:
                data.append([start_date, co_conc * 1e9])  # Convert from mol/m^2 to ppb
            else:
                data.append([start_date, None])
            print(f"Downloaded data for {start_date} to {end_date}")
        except Exception as e:
            print(f"Error on {start_date} to {end_date}: {e}")
            data.append([start_date, None])

    # Handle the last date separately if needed
    last_date = dates[-1]
    try:
        co_conc = get_co_data(last_date, last_date, region, scale)
        if co_conc is not None:
            data.append([last_date, co_conc * 1e9])
        else:
            data.append([last_date, None])
        print(f"Downloaded data for {last_date}")
    except Exception as e:
        print(f"Error on {last_date}: {e}")
        data.append([last_date, None])

    df = pd.DataFrame(data, columns=['Date', 'CO_conc_ppb'])
    df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d').dt.strftime('%d%m%Y')
    df.to_csv('dataset/historical_co_density.csv', index=False)
    print("Data saved to historical_co_density.csv")

if __name__ == '__main__':
    # Example coordinates for the region of interest
    lat = 29.7604  # Houston latitude
    lon = -95.3698  # Houston longitude

    # Download CO data for 10 years
    download_co_data(lat, lon, 2014, 2023)
