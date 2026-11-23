# Config file

All settings of a measurement campaign are stored in one `.ini` profile (editable via `config_gui.py`, the console wizard in `main.py`, or any text editor). Missing keys are automatically replaced by default values (see {class}`~isx3_api.config_handler.ConfigParser`).

SI prefixes and physical units (such as `100u`, `100uA`, `10k`, `1.5MHz`, `100mVpp`) are parsed automatically.

The path to the configuration file is passed to `Measurement().measurement(config_path=...)`. If no path is specified, a file dialog prompts you to select one.

## [Connection]

Serial USB / Virtual COM Port settings and hardware protocol selection.

| Key | Default | Description |
|---|---|---|
| `device_version` | `standard` | `standard` (ISX-3 / ISX-3mini: 4-byte `0xB0` + `0xB2`, Peak `A`/`V`) or `medical` (Medical Research ISX-3: 15-byte `0xB0`, `App`/`Vpp` halved internally) |
| `port` | `COM12` | Serial COM port (e.g. `COM12` on Windows or `/dev/ttyUSB0` on Linux) |
| `baudrate` | `115200` | Baud rate of the serial connection (default `115200`) |

## [MUX]

Multiplexer routing settings (`MUX32` / `MUX64`).

| Key | Default | Description |
|---|---|---|
| `enabled` | `False` | `True` = route through multiplexer, `False` = measure via Main Front-BNC port |
| `mode` | `4` | `2` = 2-wire routing, `4` = 4-wire Kelvin routing |
| `channel` | `2` | `2` = External MUX (`0x02`), `3` = Internal Medical MUX (`0x03`, Medical version only) |
| `active_sensors` | `1-8` | Sensor range (`1-8`), comma list (`1,3,5`), or custom 4-pin tuples (`1: 2,5,8,6; 2: 22,22,23,23`) |
| `switch_delay_s` | `0.10` | Settling delay in seconds after switching multiplexer relays |

:::{note}
Simultaneous multi-pin electrode ganging (`CE:1,5,9`) is blocked by default until the manufacturer releases the register-based firmware update (`ISX3.configure_multipin_registers`).
:::

## [Frontend]

Analog frontend settings (command `0xB0`).

| Key | Default | Description |
|---|---|---|
| `measurement_mode` | `2` | `1` = 2-point, `2` = 4-point Kelvin, `3` = 3-point |
| `measurement_channel` | `1` | `1` = Main BNC port, `2` = External MUX port, `3` = Internal Medical MUX port |
| `current_range` | `2` | `0` = Autoranging, `1` = ±10 mA (100 Ω), `2` = ±100 µA (10 kΩ), `4` = ±1 µA (1 MΩ), `6` = ±10 nA (100 MΩ) |
| `voltage_range` | `1` | `1` = ±1.0 Vp (±2.0 Vpp Default), `2` = ±0.09 Vp (±180 mVpp High Gain) |

## [FrequencySetup]

Global frequency execution mode and timing parameters (command `0xB6`).

| Key | Default | Description |
|---|---|---|
| `mode` | `sweep` | `sweep` (Hardware block sweep `0xB6 Sub 0x03`), `point_list` (Python point-by-point `0xB6 Sub 0x02`), or `single` (discrete `frequency_hz`) |
| `frequency_hz` | `1000.0` | Single frequency or comma-separated list in Hz (used when `mode = single`) |
| `start_frequency_hz` | `100.0` | Fallback start frequency in Hz if `[FrequencyBlocks]` is omitted |
| `stop_frequency_hz` | `10000000.0` | Fallback stop frequency in Hz if `[FrequencyBlocks]` is omitted |
| `count` | `101` | Fallback number of frequency points if `[FrequencyBlocks]` is omitted |
| `scale` | `logarithmic` | `logarithmic` or `linear` |
| `precision` | `1.0` | Measurement precision (`0.0` = low/fastest, `1.0` = medium, `2.0` = high, `3.0` = very high) |
| `excitation_type` | `2` | `1` = Voltage (`V Peak` or `Vpp`), `2` = Current (`A Peak` or `App`) |
| `amplitude` | `0.0001` | Excitation amplitude in `A`/`V` (`Peak` in Standard, `App`/`Vpp` in Medical) |
| `point_delay_ms` | `20.0` | Settling delay before each frequency point in milliseconds (converted to `point_delay_us` for EOP `0x01`) |
| `phase_sync` | `False` | Enable phase-synchronous switching (`True` / `False`, active for $f \ge 100\,\text{kHz}$) |

## [FrequencyBlocks]

Defines one or more sequential frequency sweep blocks (`<n>` = `1, 2, ...`). Used in `sweep` and `point_list` modes.

| Key | Default | Description |
|---|---|---|
| `block_<n>_start` | `100.0` | Start frequency of block `<n>` in Hz |
| `block_<n>_stop` | `10000000.0` | Stop frequency of block `<n>` in Hz |
| `block_<n>_steps` | `101` | Number of frequency points in block `<n>` |
| `block_<n>_scale` | `logarithmic` | `logarithmic` or `linear` |
| `block_<n>_precision` | `1.0` | Measurement precision (`0.0` to `3.0`) |
| `block_<n>_exc_type` | `2` | `1` = Voltage, `2` = Current |
| `block_<n>_amplitude` | `0.0001` | Excitation amplitude for block `<n>` |

## [Options]

Optional data frame extensions (command `0x97`).

| Key | Default | Description |
|---|---|---|
| `timestamp_mode` | `0` | `0` = off, `1` = milliseconds (4-byte `uint32`), `2` = microseconds (5-byte `uint40`) |
| `enable_current_range_output` | `False` | Include the active current range byte in every `0xB8` measurement frame (`True` / `False`) |

## [DCBias] & [SyncTime]

| Section / Key | Default | Description |
|---|---|---|
| `[DCBias] dc_bias_enabled` | `False` | Enable DC bias voltage on Standard ISX-3 (`True` / `False`) |
| `[DCBias] bias_voltage_v` | `0.0` | DC bias voltage in V (`-1.0 V` to `+1.0 V`) |
| `[SyncTime] sync_time_us` | `0` | Inter-sweep synchronization delay in µs via command `0xB9` |

## [Measurement] & [ApiSettings]

| Section / Key | Default | Description |
|---|---|---|
| `[Measurement] number_of_spectra` | `3` | Number of repeated spectrum sweeps (`0` = continuous until `Ctrl+C`) |
| `[ApiSettings] plot_type` | `bode` | Live plot template: `bode`, `bode_lin`, `nyquist`, or `impedance_frequency` |
| `[ApiSettings] live_plot_enabled` | `True` | Enable or disable real-time plotting during acquisition |
| `[ApiSettings] live_plot_mode` | `point` | `point` (update plot after each frequency point) or `sweep` (update after each full sweep) |
| `[ApiSettings] continuous_measurement` | `False` | Legacy continuous flag (use `number_of_spectra = 0` for continuous runs) |