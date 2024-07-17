import matplotlib.pyplot as plt

# Data for the months and CO concentrations
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
true_values = [94.462, 96.16, 102.613, 107.591, 116.25, 91.43, 87.506, 0, 0, 0, 0, 0]
predicted_values = [100.16, 102.67, 108.47, 100.66, 123.71, 89.88, 89.27, 85.71, 93.62, 96.77, 96.17, 99.19]

# Plotting the data
plt.figure(figsize=(10, 6))
plt.plot(months, predicted_values, label='Predicted CO Concentration (ppb)', marker='o', linestyle='-', color='b')
plt.plot(months, true_values, label='True CO Concentration (ppb)', marker='o', linestyle='--', color='g')

# Adding titles and labels
plt.title('CO Concentration in ppb (Jan to Dec 2024)')
plt.xlabel('Months')
plt.ylabel('CO Concentration (ppb)')
plt.legend()

# Adding grid for better readability
plt.grid(True)

# Annotating the points with values
for i, month in enumerate(months):
    plt.text(month, predicted_values[i], str(predicted_values[i]), fontsize=9, ha='right', color='blue')
    plt.text(month, true_values[i], str(true_values[i]), fontsize=9, ha='left', color='green')

# Display the plot
plt.show()
