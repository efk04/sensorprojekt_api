# HDF5 Output Format

Every measurement campaign creates one self-contained HDF5 file inside the `measurements/` directory[cite: 6]:

```text
measurements/measurement_<MAIN|MUX>_<YYYYmmdd-HHMMSS>.h5
```

- `measurement_MAIN_<timestamp>.h5` is created when measuring via the Main Front-BNC port (`[MUX] enabled = False`)[cite: 6].
- `measurement_MUX_<timestamp>.h5` is created when multiplexer routing is active (`[MUX] enabled = True`)[cite: 6].

## File Structure

### 1. MUX Mode (`[MUX] enabled = True`)

```text
measurement_MUX_20261123-120000.h5
├── Configuration/                  (group: attrs: source_file, measurement_type, device_version)
│   ├── Connection/                 (group: one string attribute per INI key)
│   ├── MUX/
│   ├── Frontend/
│   ├── FrequencySetup/
│   ├── FrequencyBlocks/
│   └── ...
├── Sensor_1/                       (group: attrs: measurement_duration_ms, execution_mode)
│   ├── Measurement_1.1/            (group: attrs: created)
│   │   ├── timestamp               (scalar float: PC Unix timestamp in seconds)
│   │   ├── frequency               (scalar float: frequency in Hz)
│   │   ├── frequency_id            (1D int array: device frame ID per spectrum)
│   │   ├── real_part               (1D float array: Z_real in Ω per spectrum)
│   │   ├── imaginary_part          (1D float array: Z_imag in Ω per spectrum)
│   │   ├── hw_timestamp            (optional 1D int array: ms or µs from 0x97, attr: unit)
│   │   └── current_range           (optional 1D int array: active range code from 0x97)
│   ├── Measurement_1.2/
│   └── ...
├── Sensor_2/
└── ...
```

### 2. Main Port Mode (`[MUX] enabled = False`)

In Main-Port mode without MUX, `Measurement_1.<id>` groups are written directly at the root level alongside a `Measurement/` metadata group holding `measurement_duration_ms` and `execution_mode`[cite: 6]:

```text
measurement_MAIN_20261123-120000.h5
├── Configuration/
├── Measurement/                    (group: attrs: measurement_duration_ms, execution_mode)
├── Measurement_1.1/
├── Measurement_1.2/
└── ...
```

## Configuration Group

Before connecting to the hardware, the complete INI profile is stored under `Configuration/` (see {meth}`~isx3_api.measurement.Measurement.save_measurement_settings`)[cite: 6]. Every INI section becomes a subgroup, and every key-value pair is preserved as a string attribute[cite: 6].

## Measurement Datasets

One `Measurement_<cycle>.<id>` group is created per frequency point (see {meth}`~isx3_api.measurement.Measurement.save_measurement`)[cite: 6]:

| Dataset / Attribute | Type | Description |
|---|---|---|
| `timestamp` | `float64` | PC Unix timestamp (`time.time()`, seconds) when the sweep/point completed[cite: 6] |
| `frequency` | `float64` | Measurement frequency in Hz[cite: 6] |
| `frequency_id` | `int64[]` | Frequency point ID returned by the ISX-3 data frame (`0xB8`)[cite: 3, 6] |
| `real_part` | `float64[]` | Real part of complex impedance $Z_{\mathrm{real}}$ in $\Omega$ (one entry per spectrum)[cite: 6, 7] |
| `imaginary_part` | `float64[]` | Imaginary part of complex impedance $Z_{\mathrm{imag}}$ in $\Omega$ (one entry per spectrum)[cite: 6, 7] |
| `hw_timestamp` | `int64[]` | Optional hardware timestamp (`0x97` mode `1` = `ms` or `2` = `us`, stored in attribute `unit`)[cite: 3, 6] |
| `current_range` | `int64[]` | Optional active current range code (`0x97` option `0x04`) per measurement point[cite: 3, 6] |
| `attrs["created"]` | `str` | ISO-8601 creation timestamp of the measurement group[cite: 6] |
| `attrs["measurement_duration_ms"]` | `float` | Total API acquisition time for the sensor/run in milliseconds (stored on `Sensor_<idx>` or `Measurement`)[cite: 6] |
| `attrs["execution_mode"]` | `str` | Execution mode used (`sweep`, `point_list`, or `single`)[cite: 6] |