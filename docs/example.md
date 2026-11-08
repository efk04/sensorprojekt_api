# Example

In order to use the isx3_api, you first have to install the package and then import it in your code. The installation is documented in its own chapter under *Getting Started*.

We then start by importing the main function *Measurement* into our code.
```python
from isx3_api import Measurement
```

When calling the *Measurement* function, we have the option to give it a relative filepath to our desired *config.ini*. There we configure all options for our measurement. If no filepath is given, the function will open a file dialog to ask for a config.

For this example, we will mostly use the standard configuration as given in *tests/config_example.ini*.

We want to see the measured values in a Bode plot, and we only want to measure once (no continuous measurement). Both can be configured under *[ApiSettings]*.
```text
[ApiSettings]
plot_type = bode
continuous_measurement = False
```

Depending on your PC, you may have to change the *port* setting under *[Connection]*. On Windows, you can check which port is used in the Device Manager. The baud rate is fixed by the ISX device at *115200*.
```text
[Connection]
interface_type = COM
port = COM4
baudrate = 115200
```

For the *FrequencySetup*, we are setting up the *auto* mode. It takes a start and a stop frequency as well as a count for how many frequency points lie in between. It generates a frequency list from these values. The list can use linear or logarithmic scaling.
```text
[FrequencySetup]
mode = auto

frequency_hz = 1000.0, 5000.0
precision = 1.0

start_frequency_hz = 100.0
stop_frequency_hz = 100000.0
count = 10
scale = logarithmic
```

Now we can start measuring.