# Examples: Main Port & MUX32 Control

`isx3_api` can be controlled via `.ini` configuration files or directly in Python. Below are two complete examples covering **Main Port (Front-BNC)** measurements and **MUX32 multiplexer** multi-sensor sweeps.

---

## Example 1: Main Port Measurement (Multi-Block Front-BNC Sweep)

### 1. Configuration File (`config/example_main.ini`)

This example configures a **Standard ISX-3** on `COM12` to run a 2-block hardware sweep (`0xB6 Sub 0x03`) over the Front-BNC port in 4-point Kelvin mode (`measurement_mode = 2`):
- **Block 1 (`100 Hz` – `10 kHz`):** Current excitation (`excitation_type = 2`) with `100 µA Peak` (`0.0001`).
- **Block 2 (`10 kHz` – `1 MHz`):** Voltage excitation (`excitation_type = 1`) with `100 mV Peak` (`0.1`).

```ini
[Connection]
device_version = standard
port = COM12
baudrate = 115200

[MUX]
enabled = False

[Frontend]
measurement_mode = 2
measurement_channel = 1
current_range = 2
voltage_range = 1

[FrequencySetup]
mode = sweep
point_delay_ms = 20.0
phase_sync = False

[FrequencyBlocks]
block_1_start = 100.0
block_1_stop = 10000.0
block_1_steps = 11
block_1_scale = logarithmic
block_1_precision = 1.0
block_1_exc_type = 2
block_1_amplitude = 0.0001

block_2_start = 10000.0
block_2_stop = 1000000.0
block_2_steps = 11
block_2_scale = logarithmic
block_2_precision = 1.0
block_2_exc_type = 1
block_2_amplitude = 0.1

[Options]
timestamp_mode = 1
enable_current_range_output = False

[Measurement]
number_of_spectra = 3

[ApiSettings]
plot_type = bode
live_plot_enabled = True
live_plot_mode = point
```

### 2. Python Execution

```python
from isx3_api import Measurement

meas = Measurement()
h5_file = meas.measurement(config_path="config/example_main.ini")
print(f"Results saved to: {h5_file}")
```

---

## Example 2: MUX32 Multiplexer Control (Multi-Sensor & Custom Pins)

When `[MUX]` is enabled, `isx3_api` routes each active sensor sequentially before executing the configured frequency sweep:
- **`device_version = medical`**: Uses the 15-byte `0xB0` protocol (internal MUX port `3` or external MUX port `2`) and automatically halves Peak-to-Peak inputs (`App` / `Vpp`) for the firmware.
- **`device_version = standard`**: Uses the 4-byte `0xB0` protocol + separate `0xB2` routing command (external MUX port `2`) with 1:1 Peak inputs (`A` / `V`).
- **`active_sensors`**:
  - Automatic numbering: `1-4` (4-wire: Sensor 1 $\rightarrow$ pins `1,2,3,4`; Sensor 2 $\rightarrow$ `5,6,7,8`, etc.).
  - Custom pin routing (`CE, RE, WS, WE`): `1: 1,1,2,2; 2: 22,22,23,23` (e.g., Sensor 1 on pins 1/2 and the internal $2\,\text{k}\Omega$ reference resistor on pins 22/23).

### 1. Configuration File (`config/example_mux.ini`)

```ini
[Connection]
device_version = medical
port = COM12
baudrate = 115200

[MUX]
enabled = True
mode = 4
channel = 3
active_sensors = 1: 1,1,2,2; 2: 22,22,23,23
switch_delay_s = 0.10

[Frontend]
measurement_mode = 2
measurement_channel = 3
current_range = 2
voltage_range = 1

[FrequencySetup]
mode = sweep
point_delay_ms = 20.0
phase_sync = False

[FrequencyBlocks]
block_1_start = 100.0
block_1_stop = 1000000.0
block_1_steps = 21
block_1_scale = logarithmic
block_1_precision = 1.0
block_1_exc_type = 2
block_1_amplitude = 0.0001

[Options]
timestamp_mode = 1
enable_current_range_output = False

[Measurement]
number_of_spectra = 3

[ApiSettings]
plot_type = bode
live_plot_enabled = True
live_plot_mode = sweep
```

### 2. Python Execution with Pre-Measurement Drift Check

```python
from isx3_api import ISX3, Measurement

# Verify thermal stability on the internal 2 kOhm reference (pins 22,22,23,23 on MUX port 3)
diag = ISX3()
report = diag.run_baseline_drift_check(port="COM12", baudrate=115200, mux_channel=3)

if report["stable"]:
    Measurement().measurement(config_path="config/example_mux.ini")
else:
    print(f"Drift too high ({report['drift_pct']:.3f} %) - let device warm up first.")
```