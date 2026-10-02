# API reference

The API is split into four modules. For most use cases only
{class}`~isx3_api.measurement.Measurement` is needed.

| Module | Main classes |
|---|---|
| {doc}`measurement` | {class}`~isx3_api.measurement.Measurement` |
| {doc}`commands` | {class}`~isx3_api.commands.ISX3` |
| {doc}`config_handler` | {class}`~isx3_api.config_handler.ConfigParser`, {class}`~isx3_api.config_handler.ConfigBuilder` |
| {doc}`plot_templates` | {class}`~isx3_api.plot_templates.PlotTemplates` |

The main classes can be imported directly from the package:

```python
from isx3_api import Measurement, ISX3, ConfigParser, ConfigBuilder, PlotTemplates
```

```{toctree}
:maxdepth: 2

measurement
commands
config_handler
plot_templates
```
