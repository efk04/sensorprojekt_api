# Measuring

In this part we want to explain what options there are for setting the measuring frequencies. And how the continius measurment works.

##  FrequencySetup - mode
In the config file in the `[FrequencySetup]` part you have the option `mode`. Here you can choose between `auto` and `user_defined`.

The `auto` mode uses the values from `start_frequency_hz`, `stop_frequency_hz`, `count` and `scale` to generate a list of frequencies at wich to measure.

The `user-defined` mode uses the values from `frequency_hz`. The user can give here on frequency at which to measure. It is also possible to give a list of comma seperated values like:

```python
frequency_hz 67.0, 69.0, 420.0
```

## Continius Measuring
In the `[Measurement]` section in the config file the user can set the `number_of_spectra`. This defines how often the frequency list is run back to back. If this value is set to `0` the measurement is coninuous. In this scenario it will measure until the user stops it manually.