# Measuring

This section explains the options for setting the measurement frequencies and how continuous measurement works.

## FrequencySetup - mode

In the `[FrequencySetup]` section of the config file, the `mode` option lets you choose between `auto` and `user_defined`.

The `auto` mode uses the values of `start_frequency_hz`, `stop_frequency_hz`, `count`, and `scale` to generate a list of frequencies at which to measure.

The `user_defined` mode uses the value of `frequency_hz`. Here you can specify a single frequency at which to measure. You can also provide a comma-separated list of values, for example:

```python
frequency_hz = 67.0, 69.0, 420.0
```

## Continuous Measuring

In the `[Measurement]` section of the config file, you can set `number_of_spectra`. This defines how many times the frequency list is run back to back. If this value is set to `0`, the measurement is continuous and runs until you stop it manually.