# commands

```{eval-rst}
.. automodule:: isx3_api.commands
   :no-members:

ISX3 device handler
-------------------

.. autoclass:: isx3_api.commands.ISX3
   :members:

Status messages
---------------

.. autodata:: isx3_api.commands.MSG_DICT
   :no-value:
```

| Code | Meaning |
|---|---|
| `0x01` | No message inside the message buffer |
| `0x02` | Timeout: Communication-timeout (less data than expected) |
| `0x04` | Wake-Up Message: System boot ready |
| `0x11` | TCP-Socket: Valid TCP client-socket connection |
| `0x81` | Not-Acknowledge: Command has not been executed |
| `0x82` | Not-Acknowledge: Command could not be recognized |
| `0x83` | Command-Acknowledge: Command has been executed successfully |
| `0x84` | System-Ready Message: System is operational and ready to receive data |
| `0x92` | Data holdup: Measurement data could not be sent via the master interface |
