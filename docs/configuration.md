# Config file

All settings of a measurement are stored in one INI file. Missing keys are
replaced by default values (see {class}`~isx3_api.config_handler.ConfigParser`).

An example file can be found at `isx3_api/tests/config_example.ini`.

The path to the configuration file is passed as an argument to the measurement function. If no path is specified, the function prompts for one via a file dialog.

## [ApiSettings]

Settings of the API itself. They are not sent to the device.

| Key | Default | Description |
|---|---|---|
| `plot_type` | `bode` | Live plot: `bode`, `nyquist` or `impedance_frequency` |
| `continuous_measurement` | `False` | Repeat the measurement until `e` is pressed |

## [Connection]

| Key | Default | Description |
|---|---|---|
| `interface_type` | `COM` | `COM` (serial / USB) or `TCP` (Ethernet) |
| `port` | `COM1` | Serial port, e.g. `COM4` or `/dev/ttyUSB0` |
| `baudrate` | `115200` | Baud rate of the serial connection |
| `ip_address` | `192.168.1.100` | IP address (TCP only) |
| `tcp_port` | `8888` | TCP port (TCP only) |
| `tcp_watchdog_interval_s` | `60` | TCP watchdog interval, 1 s to 600 s |

:::{note}
Currently only the serial connection (`COM`) is supported.
:::

## [Options]

Data frame options (commands `0x97` / `0x98`).

| Key | Default | Description |
|---|---|---|
| `timestamp_mode` | `0` | 0 = off, 1 = ms timestamp (uint32), 2 = µs timestamp (uint56) |
| `enable_current_range_output` | `0` | Send the current range in every data frame (0 / 1) |

## [Frontend]

Frontend settings (commands `0xB0` / `0xB1`).

| Key | Default | Values |
|---|---|---|
| `measurement_mode` | `1` | 1 = 2-point, 2 = 4-point, 3 = 3-point |
| `measurement_channel` | `1` | 1 = BNC port, 2 = extension port, 3 = extension port 2 |
| `current_range` | `0` | 0 = auto, 1 = ±10 mA, 2 = ±100 µA, 4 = ±1 µA, 6 = ±10 nA |
| `voltage_range` | `1` | 0 = auto, 1 = ±1 V, 2 = ±0.09 V |

## [ExtensionPort]

Channel selection of the extension port (commands `0xB2` / `0xB3`). The values
depend on the connected module (e.g. MuxModule).

| Key | Default |
|---|---|
| `counter_port` | `0` |
| `reference_port` | `0` |
| `working_sense_port` | `0` |
| `working_port` | `0` |

:::{note}
The extension port settings are not sent to the device yet.
:::

## [FrequencySetup]

Frequency setup (command `0xB6`).

| Key | Default | Description |
|---|---|---|
| `mode` | `auto` | `user_defined` (frequencies from `frequency_hz`) or `user_defined` |
| `frequency_hz` | `1000.0` | Comma separated list of frequencies in Hz (`single` mode) |
| `start_frequency_hz` | `100.0` | Start frequency in Hz (`auto` mode) |
| `stop_frequency_hz` | `100000.0` | Stop frequency in Hz (`auto` mode) |
| `count` | `10` | Number of frequency points (`auto` mode) |
| `scale` | `linear` | `linear` or `logarithmic` (`auto` mode) |
| `precision` | `1.0` | Measurement precision |
| `excitation_type` | `1` | 1 = voltage (0.0001 V to 1 V), 2 = current (1 µA to 10 mA) |
| `amplitude` | `0.01` | Excitation amplitude in V or A |
| `point_delay_us` | `0` | Delay between measurement points in µs |
| `phase_sync` | `0` | Phase synchronous switching (0 / 1) |

## [DCBias]

| Key | Default | Description |
|---|---|---|
| `dc_bias_enabled` | `0` | Enable the DC bias (0 / 1) |
| `bias_voltage_v` | `0.0` | Bias voltage in V, -1.0 V to +1.0 V |

## [SyncTime]

| Key | Default | Description |
|---|---|---|
| `sync_time_us` | `0` | Time between two spectrum measurements in µs (max. 180 s) |

## [Measurement]

| Key | Default | Description |
|---|---|---|
| `number_of_spectra` | `1` | Number of spectra per frequency point (0 = continuous) |
