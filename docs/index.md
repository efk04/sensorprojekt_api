# isx3_api

Python API and measurement framework for controlling the **Sciospec ISX-3 / ISX-3mini** and **Medical Research ISX-3** impedance analyzers.

With `isx3_api` you can:

- connect to the ISX-3 via USB (Virtual COM Port),
- configure all parameters via **GUI**, **interactive CLI wizard**, or **INI profile**,
- run fast hardware block sweeps (`0xB6 Sub 0x03`), point-by-point sweeps (`0xB6 Sub 0x02`), or discrete frequency measurements,
- control **MUX32 / MUX64** multiplexers in 2-wire or 4-wire mode with automatic or custom pin assignments,
- monitor measurements in a live plot (Bode, Nyquist, or Real/Imag over frequency),
- save configuration, impedance spectra, hardware timestamps, and timing metrics in HDF5 files,
- evaluate and compare `.h5`, `.scio5`, and `.spec` files using `auswertung_visualisierung.py`.

```python
from isx3_api import Measurement

Measurement().measurement("config/config.ini")
```

## Package structure

| Module | Purpose |
|---|---|
| {mod}`isx3_api.measurement` | Measurement campaign orchestrator, MUX sensor loop, live plotting, and HDF5 storage |
| {mod}`isx3_api.commands` | Low-level binary protocol driver (`0xB0`, `0xB2`, `0xB6`, `0xB8`, `0x97`, `0xB9`), Standard vs. Medical handling, baseline drift check |
| {mod}`isx3_api.config_handler` | INI parser, SI prefix converter (`100u`, `1M`), and sequential measurement queue builder |
| {mod}`isx3_api.config_gui` | Tkinter GUI for profile management, unit switching (`Peak` vs. `Vpp/App`), frequency blocks, and diagnostics |
| {mod}`isx3_api.plot_templates` | Live visualization templates (Bode log/linear, Nyquist, Real/Imag) |
| `main.py` | Interactive entry point (GUI, INI file loader, or step-by-step console wizard) |
| `auswertung_visualisierung.py` | Post-processing, timing benchmark, component estimation ($R/C/L$), and multi-file comparison tool |

```{toctree}
:maxdepth: 2
:caption: Getting started

installation
quickstart
example
```

```{toctree}
:maxdepth: 2
:caption: Content

configuration
measuring
data_format
evaluation
api/index
```