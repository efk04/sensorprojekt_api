# Measuring & Execution Modes

This section explains how frequency sweeps, single-point lists, multi-block configurations, and multi-sensor MUX campaigns are executed on the ISX-3.

## Frequency Execution Modes (`[FrequencySetup] mode`)

In the `[FrequencySetup]` section of the `.ini` file, `mode` determines how the frequency points are transmitted to and executed on the device:

| Mode | Protocol Command | Behavior & Use Case |
|---|---|---|
| `sweep` | `0xB6 Sub 0x03` | **Hardware Block Sweep (Default & Fastest):** Transmits each block from `[FrequencyBlocks]` once as a 22-byte configuration frame. The ISX-3 DSP executes the entire sweep autonomously without per-point USB handshakes. |
| `point_list` | `0xB6 Sub 0x02` | **Python Point-by-Point List:** Expands all `[FrequencyBlocks]` into discrete frequencies in Python and transmits each point individually as a 13-byte setup command (`0xB6 Sub 0x02`). Ideal for USB communication overhead and timing benchmarks. |
| `single` | `0xB6 Sub 0x02` | **Discrete Single Frequencies:** Measures one or more comma-separated frequencies defined in `frequency_hz` (for example `frequency_hz = 100.0, 1000.0, 10000.0`). |

## Multi-Block Frequency Sweeps (`[FrequencyBlocks]`)

When multiple blocks (`block_1_*`, `block_2_*`, ...) are defined in `[FrequencyBlocks]`, they are processed sequentially block-by-block. This allows switching excitation types (`Current` vs. `Voltage`), amplitudes, scaling (`logarithmic` vs. `linear`), or precision levels across different frequency decades within a single sweep.

## Multi-Sensor Multiplexer Execution (`[MUX]`)

When `[MUX] enabled = True`, `isx3_api` iterates sequentially over all active sensors defined in `active_sensors`:

1. Configures the multiplexer relay routing for the current sensor (`ISX3.route_mux_sensor`) and waits for `switch_delay_s` to let relays settle.
2. Applies the frontend configuration (`0xB0` 15-byte frame for `medical`; 4-byte `0xB0` + `0xB2` extension command for `standard`).
3. Runs the configured frequency sweep (`number_of_spectra` repetitions) and writes the results under `Sensor_<idx>/` in the HDF5 file before switching to the next sensor.

## Repeated & Continuous Measurements (`number_of_spectra`)

In `[Measurement]`, `number_of_spectra` controls how many times the configured spectrum is acquired per sensor:
- **`number_of_spectra >= 1`:** Acquires the exact number of repeated sweeps (enabling $\pm 1\sigma$ repeatability statistics in `auswertung_visualisierung.py`).
- **`number_of_spectra = 0`:** Starts continuous acquisition until stopped manually via **`Ctrl+C`** in the terminal.