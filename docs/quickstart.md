# Quickstart

## 1. Create a config file

All settings for a measurement are stored in one INI file. Copy the example
file `isx3_api/tests/config_example.ini` and adjust at least the serial port:

```ini
[Connection]
port = COM4
baudrate = 115200
```

All sections and keys are described in {doc}`configuration`.

## 2. Start a measurement

```python
from isx3_api import Measurement

measurement = Measurement()
measurement.measurement("config.ini")
```

If no path is given, a file dialog asks for the config file:

```python
Measurement().measurement()
```

## 3. What happens during the measurement

1. A new HDF5 file is created in the folder `measurements/`.
2. The device is connected and the config file is saved in the HDF5 file.
3. The options are sent to the device and the frequency points are created
   from the config file.
4. For every frequency point the device is configured, the measurement is
   started, the live plot is updated and the results are saved.
5. If `continuous_measurement = True`, step 4 is repeated.

:::{tip}
Press **`e`** to stop the measurement manually. Results that were already
received stay saved in the HDF5 file.
:::

After the measurement the plot stays open until you close it.

## 4. Read the results

```python
import h5py

with h5py.File("measurements/measurement_results_20260801-120000.h5") as f:
    for name, group in f.items():
        print(name, list(group.keys()))
```

The structure of the file is described in {doc}`data_format`.
