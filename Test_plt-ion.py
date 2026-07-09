import matplotlib.pyplot as plt
import numpy as np

plt.ion()  # Turn on interactive mode

x = np.linspace(0, 10, 100)
y = np.sin(x)

for i in range(10):
    plt.plot(x, y * (i + 1))
    plt.draw()
    plt.pause(0.5)  # Pause to update the plot

plt.ioff()  # Turn off interactive mode
plt.show()  # Display the final plot