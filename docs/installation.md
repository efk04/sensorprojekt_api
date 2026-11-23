# Installation

## Requirements

- Python **3.11** or newer (tested with Python 3.13)
- Windows or Linux
- Sciospec ISX-3 / ISX-3mini or Medical Research ISX-3 connected via USB

## Install the package

It is recommended to create and activate a virtual environment first:

```bash
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate
```

Install `isx3_api` from GitHub:

```bash
pip install "git+[https://github.com/efk04/sensorprojekt_api.git#egg=isx3_api&subdirectory=isx3_api](https://github.com/efk04/sensorprojekt_api.git#egg=isx3_api&subdirectory=isx3_api)"
```

## Install the dependencies

All required dependencies are listed in `isx3_api/requirements.txt`:

```bash
pip install -r isx3_api/requirements.txt
```

| Package | Used for |
|---|---|
| `pyserial` | Serial USB/COM communication with the ISX-3 |
| `numpy` | Frequency sweeps and numerical array processing |
| `h5py` | Saving configuration, impedance spectra, and metadata in HDF5 files |
| `matplotlib` | Live plotting and offline comparison visualization |
| `scipy` | Signal processing and statistical evaluation utilities |
| `pandas` | Structured data handling and export utilities |

## Check the installation

```python
from isx3_api import ISX3, Measurement, ConfigBuilder

print("isx3_api successfully imported!")
```