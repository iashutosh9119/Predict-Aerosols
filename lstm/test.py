import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import load_model
import datetime

def prepare_data(historical_data, seq_length):
    # Normalize the data
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(historical_data[['CO_conc_ppb']])
    
    # Create sequences of time steps
    def create_sequences(data, seq_length):
        xs = []
        for i in range(len(data) - seq_length):
            x = data[i:i + seq_length]
            xs.append(x)
        return np.array(xs)

    X = create_sequences(scaled_data, seq_length)
    return X, scaler

def predict_for_month(model, data, scaler, start_date, end_date, seq_length):
    # Generate sequences for the given date range
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    predictions = []

    for date in date_range:
        input_sequence = data[-seq_length:]
        input_sequence = input_sequence.reshape((1, seq_length, 1))
        
        predicted_value = model.predict(input_sequence)
        predicted_value = scaler.inverse_transform(predicted_value)
        
        # Append the predicted value and update the data with the new prediction
        predictions.append((date.strftime('%Y-%m-%d'), predicted_value[0][0]))
        new_data_point = scaler.transform([[predicted_value[0][0]]])
        data = np.append(data, new_data_point).reshape(-1, 1)

    return predictions

if __name__ == '__main__':
    # Load the historical CO density data
    historical_data = pd.read_csv('dataset/historical_co_density.csv')
    
    # Ensure the Date column is in the correct datetime format
    historical_data['Date'] = pd.to_datetime(historical_data['Date'], format='%d%m%Y')
    
    # Sort data by date
    historical_data = historical_data.sort_values('Date')
    
    # Set the date column as index
    historical_data.set_index('Date', inplace=True)
    
    # Define sequence length
    seq_length = 30
    
    # Prepare the data
    X, scaler = prepare_data(historical_data, seq_length)
    
    # Load the trained LSTM model
    model = load_model('model/co_lstm_model.h5')
    
    # Get the month and year from the user
    month = input('Enter the month (MM): ')
    year = input('Enter the year (YYYY): ')
    
    # Define the start and end date for the prediction
    start_date = f'{year}-{month}-01'
    end_date = (pd.to_datetime(start_date) + pd.DateOffset(months=1) - pd.DateOffset(days=1)).strftime('%Y-%m-%d')
    
    # Predict for the given month and year
    predictions = predict_for_month(model, X, scaler, start_date, end_date, seq_length)
    
    # Print the predictions
    print(f"CO Density Predictions for {month}-{year}:")
    for date, value in predictions:
        print(f"{date}: {value:.2f} ppb")
