# HDF5 output

Every measurement campaign creates one HDF5 file:

```text
measurements/measurement_results_<YYYYmmdd-HHMMSS>.h5
```

## File structure

```text
measurement_results_20260801-120000.h5
├── Configuration/               (group)
│   ├── attrs: source_file
│   ├── ApiSettings/             (group, one attribute per key)
│   ├── Connection/
│   └── ...
├── Measurement_1.1/             (group)
│   ├── attrs: created
│   ├── timestamp
│   ├── frequency
│   ├── frequency_id
│   ├── real_part
│   └── imaginary_part
├── Measurement_1.2/
└── ...
```

## Configuration

The whole config file is saved before the measurement starts (see
{meth}`~isx3_api.measurement.Measurement.safe_measurement_settings`).
Every section is a group, every key is an attribute with the raw string value
from the INI file. Comments are not saved.

## Measurement groups

One group is created per frequency point
(see {meth}`~isx3_api.measurement.Measurement.safe_measurment`).
The group name is `Measurement_<cycle>.<id>`:

- `<cycle>`: number of the measurement cycle (counts up in continuous measurements),
- `<id>`: number of the frequency point in the cycle, starting at 1.

| Dataset | Description |
|---|---|
| `timestamp` | Time when the results were received (`time.time()`, seconds) |
| `frequency` | Frequency of the measurement in Hz |
| `frequency_id` | Frequency ID from the device data frames |
| `real_part` | Real part of the impedance in Ω |
| `imaginary_part` | Imaginary part of the impedance in Ω |

The attribute `created` contains the time the group was created (ISO format).
