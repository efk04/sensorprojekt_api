# isx3_api

Python API for controlling the **Sciospec ISX-3 / ISX-3mini** impedance analyzer.

With `isx3_api` you can:

- connect to the ISX-3 via USB (serial port),
- set all measurement parameters in one config file,
- run single or continuous impedance measurements,
- watch the results in a live plot (Bode, Nyquist or impedance over frequency),
- save the config and all results in an HDF5 file.

```python
from isx3_api import Measurement

Measurement().measurement("config.ini")
```

## Package structure

| Module | Purpose |
|---|---|
| {mod}`isx3_api.measurement` | Runs the whole measurement: main loop, HDF5 storage, live plot |
| {mod}`isx3_api.commands` | Low-level communication with the device (frames, ACKs, data frames) |
| {mod}`isx3_api.config_handler` | Reads the config file and creates the measurement setups |
| {mod}`isx3_api.plot_templates` | Plot templates for the live plot |

```{toctree}
:maxdepth: 2
:caption: Getting started

installation
quickstart
```

```{toctree}
:maxdepth: 2
:caption: User guide

configuration
data_format
```

```{toctree}
:maxdepth: 2
:caption: API reference

api/index
```
