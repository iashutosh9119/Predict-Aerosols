import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.callbacks import ModelCheckpoint
import datetime

# Load the historical CO density data
data = pd.read_csv('dataset/historical_co_density.csv')

# Ensure the Date column is in the correct datetime format
data['Date'] = pd.to_datetime(data['Date'], format='%d%m%Y')

# Sort data by date
data = data.sort_values('Date')

# Prepare the data for LSTM
# Set the date column as index
data.set_index('Date', inplace=True)

# Normalize the data
scaler = MinMaxScaler(feature_range=(0, 1))
scaled_data = scaler.fit_transform(data[['CO_conc_ppb']])

# Create sequences of time steps
def create_sequences(data, seq_length):
    xs, ys = [], []
    for i in range(len(data) - seq_length):
        x = data[i:i + seq_length]
        y = data[i + seq_length]
        xs.append(x)
        ys.append(y)
    return np.array(xs), np.array(ys)

seq_length = 30  # Number of time steps to look back
X, y = create_sequences(scaled_data, seq_length)

# Split the data into training and test sets
split = int(0.8 * len(X))
X_train, y_train = X[:split], y[:split]
X_test, y_test = X[split:], y[split:]

# Build the LSTM model
model = Sequential()
model.add(LSTM(50, return_sequences=True, input_shape=(seq_length, 1)))
model.add(LSTM(50, return_sequences=False))
model.add(Dense(25))
model.add(Dense(1))

# Compile the model
model.compile(optimizer='adam', loss='mean_squared_error')

# Define a checkpoint to save the best model
checkpoint = ModelCheckpoint('model/co_lstm_model.h5', save_best_only=True, monitor='val_loss', mode='min')

# Train the model
model.fit(X_train, y_train, validation_data=(X_test, y_test), epochs=10, batch_size=1, callbacks=[checkpoint])

print("Model training completed and saved to 'model/co_lstm_model.h5'")
