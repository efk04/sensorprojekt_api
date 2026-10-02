# Installation

## Requirements

- Python **3.13** or newer
- Windows or Linux
- Sciospec ISX-3 / ISX-3mini connected via USB

## Install the package

It is recommended to install the package in a virtual environment:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux
source .venv/bin/activate
```

Install `isx3_api` from GitHub:

```bash
pip install "git+https://github.com/efk04/sensorprojekt_api.git#egg=isx3_api&subdirectory=isx3_api"
```

## Install the dependencies

The dependencies are listed in `isx3_api/requirements.txt`:

```bash
pip install -r isx3_api/requirements.txt
```

The most important ones are:

| Package | Used for |
|---|---|
| `pyserial` | Serial communication with the device |
| `numpy` | Frequency sweeps |
| `matplotlib` | Live plot |
| `h5py` | Saving the results in HDF5 files |
| `keyboard` | Stopping a measurement with the `e` key |

:::{note}
On Linux the `keyboard` package needs root rights to read key presses.
:::

## Check the installation

```python
import isx3_api
print(isx3_api.__version__)
```
