# Quickstart

## 1. Launch the Measurement Framework (`main.py`)

The easiest way to get started is running `main.py`, which offers three interactive entry options:

```bash
python main.py
```

1. **Graphical User Interface (GUI):** Opens the Tkinter configuration manager (`config_gui.py`) with dynamic unit switching (`Peak` vs. `Vpp/App`), frequency block tables, profile management, and the system baseline drift check.
2. **Load existing INI file:** Directly starts a measurement campaign from a saved `.ini` profile.
3. **Interactive console wizard:** Guides you step-by-step through creating a profile in the terminal (ideal for headless setups without a display).

## 2. Start a Measurement Directly in Python

```python
from isx3_api import Measurement

measurement = Measurement()
measurement.measurement("config/config.ini")
```

If no path is passed, a file dialog prompts you to select an `.ini` file:

```python
Measurement().measurement()
```

## 3. What Happens During a Measurement

1. A new HDF5 file is created in `measurements/` (`measurement_MAIN_<YYYYmmdd-HHMMSS>.h5` or `measurement_MUX_<YYYYmmdd-HHMMSS>.h5`).
2. The device is connected via USB and the complete INI configuration is saved in the HDF5 `Configuration/` group.
3. If `[MUX]` is enabled, active sensors are routed sequentially via `0xB0` (15-byte Medical) or `0xB0` + `0xB2` (Standard).
4. Depending on `mode`, frequencies are executed via hardware block sweep (`0xB6 Sub 0x03`), Python point list (`0xB6 Sub 0x02`), or discrete single points (`0xB6 Sub 0x02`), while updating the live plot and writing results to HDF5.

:::{tip}
Press **`Ctrl+C`** in the terminal to stop a running or continuous measurement cleanly. The serial port is closed safely and all already received data remains saved in the HDF5 file.
:::

## 4. Read and Evaluate the Results

You can inspect the HDF5 structure directly with `h5py`:

```python
import h5py

with h5py.File("measurements/measurement_MAIN_20261123-120000.h5", "r") as f:
    for name, group in f.items():
        print(name, list(group.keys()))
```

Or launch the interactive evaluation and comparison tool:

```bash
python auswertung_visualisierung.py
```

See {doc}`evaluation` and {doc}`data_format` for further details.