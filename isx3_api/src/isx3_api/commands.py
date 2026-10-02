"""
Communication with the Sciospec ISX-3 / ISX-3mini device.

The device is controlled via the serial port (USB full-speed). Every command
is sent as a frame of the form ``[CMD-Tag] [Length] [Data...] [CMD-Tag]``
and acknowledged by the device with an ACK frame (see :data:`MSG_DICT`).
"""

from logging import config
import struct
import serial
import serial.tools.list_ports
import numpy as np
from shapely import buffer
import time
import os
import sys


#: Status codes of the ACK frames (``0x18 0x01 [Status] 0x18``) and their meaning.
MSG_DICT = {
    "0x01": "No message inside the message buffer",
    "0x02": "Timeout: Communication-timeout (less data than expected)",
    "0x04": "Wake-Up Message: System boot ready",
    "0x11": "TCP-Socket: Valid TCP client-socket connection",
    "0x81": "Not-Acknowledge: Command has not been executed",
    "0x82": "Not-Acknowledge: Command could not be recognized",
    "0x83": "Command-Acknowledge: Command has been executed successfully",
    "0x84": "System-Ready Message: System is operational and ready to receive data",
    "0x92": "Data holdup: Measurement data could not be sent via the master interface",
}


class ISX3:
    """
    Device handler for the ISX-3: connecting, configuring and measuring.

    Example:
        >>> isx3 = ISX3()
        >>> isx3.connect_device_fs({"port": "COM3", "baudrate": 115200})
        >>> isx3.set_options(settings)
        >>> isx3.set_frequency_setup(current_setup)
        >>> results = isx3.start_measurement(spectra=1, id=1, measurement_settings=settings)

    Attributes:
        device (serial.Serial): Open serial connection (None if not connected).
        serial_protocol (str): Used serial protocol (``"FS"`` = USB full-speed).
        print_msg (bool): If True, status messages are printed.
    """

    #: Command tag of an ACK frame.
    ACK_TAG = 0x18
    #: Status code: command has been executed successfully.
    ACK_SUCCESS = 0x83
    #: Status code: command has not been executed (wrong syntax).
    NACK_SYNTAX = 0x81
    #: Status code: command could not be recognized.
    NACK_NOT_RECOGNIZED = 0x82

    def __init__(self):
        """
        Initializes an ISX3 device handler (without connecting to the device).
        """
        self.serial_protocol = None
        self.device = None
        self.frequency_points = 0
        self.ret_hex_int = None
        self.print_msg = True
        self.tcp_protocol = None
        self.frequencies = []
        self.frequency_list = []

    def is_port_available(self, port: str) -> bool:
        """
        Checks if the specified COM port is available.

        Args:
            port (str): COM port identifier (e.g., "COM3").

        Returns:
            bool: True if the port is available, False otherwise.
        """
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        return port in available_ports

    def connect_device_fs(self, settings):
            """
            Connects to the ISX3 device via the specified serial port (USB full-speed).

            Errors (port not available, :class:`serial.SerialException`) are
            printed and not raised.

            Args:
                settings (dict): Settings with the keys:

                    - ``port`` (str): COM port to connect to (e.g. ``"COM3"``).
                    - ``baudrate`` (int): Baud rate of the serial connection
                      (must match the device settings, e.g. ``115200``).

            Returns:
                serial.Serial | None: The open serial connection, or None if the
                connection failed.
            """

            port = settings["port"]  # Use the port from the settings
            baudrate = settings["baudrate"]  # Use the baudrate from the settings

            if not self.is_port_available(port):
                print(f"Error: Port {port} is not available.")
                return

            if hasattr(self, "serial_protocol"):
                print(
                    f"Serial connection 'self.serial_protocol' already defined as {self.serial_protocol}."
                )
            else:
                self.serial_protocol = "FS"

            try:
                self.device = serial.Serial(
                    port=port, #e.g., "COM3" on Windows or "/dev/ttyUSB0" on Linux
                    baudrate=baudrate, #e.g. 9600, 115200, etc. (must match the device's settings)
                    timeout=1,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                )
                print(f"Successfully Connected to {self.device.name}")
                return self.device
            except serial.SerialException as e:
                print("Error: ", e)
            

            
            

    def _send_command(self, cmd_tag: int, data: bytes):
        """
        Packs the data into the Sciospec frame format, sends it and waits for the ACK.

        Format: ``[CMD-Tag] [Length] [Data...] [CMD-Tag]``

        Args:
            cmd_tag (int): Command tag (e.g. ``0xB6``).
            data (bytes): Payload of the frame (max. 255 bytes).

        Raises:
            ValueError: If the payload is longer than 255 bytes or the device
                answers with a NACK.
            TimeoutError: If no ACK is received.
            ConnectionError: If an invalid ACK frame is received.
        """
        length = len(data)
        if length > 255:
            raise ValueError("Daten-Payload überschreitet maximale Frame-Länge von 255 Bytes.")

        # Frame zusammensetzen
        frame = (bytes([cmd_tag, length]) + data + bytes([cmd_tag]))
        
        # Senden
        #print("SEND_COMMAND: ", frame)
        self.device.write(frame)
        self.device.flush()

        # Auf Bestätigung (ACK) warten
        self._wait_for_ack(cmd_tag)

    def _wait_for_ack(self, original_cmd_tag: int):
        """
        Reads the answer frame and checks for a successful acknowledge.

        An ACK frame looks like this: ``0x18 0x01 [Status] 0x18``

        Args:
            original_cmd_tag (int): Command tag of the sent command (used in error messages).

        Raises:
            TimeoutError: If less than 4 bytes are received.
            ConnectionError: If the frame is not a valid ACK frame.
            ValueError: If the status is a NACK or unknown.
        """
        # Wir erwarten 4 Bytes für das ACK
        ack_frame = self.device.read(4)
        #print(f"ACK_FRAME: {ack_frame.hex()}")
        
        if len(ack_frame) < 4:
            raise TimeoutError(f"Timeout beim Warten auf ACK für Befehl {hex(original_cmd_tag)}")

        if ack_frame[0] != self.ACK_TAG or ack_frame[3] != self.ACK_TAG:
            raise ConnectionError(f"Ungültiger ACK-Frame empfangen: {ack_frame.hex()}")

        status = ack_frame[2]
        if status == self.ACK_SUCCESS:
            return  # Alles in Ordnung[cite: 2]
        elif status == self.NACK_SYNTAX:
            raise ValueError(f"NACK (0x81): Falsche Syntax für Befehl {hex(original_cmd_tag)}[cite: 2]")
        elif status == self.NACK_NOT_RECOGNIZED:
            raise ValueError(f"NACK (0x82): Befehl {hex(original_cmd_tag)} nicht erkannt[cite: 2]")
        else:
            raise ValueError(f"Unerwarteter Status-Code {hex(status)} empfangen.")


    def start_measurement(self, spectra, id, measurement_settings):
        """
        Starts the measurement process on the ISX3 device (command ``0xB8``).

        When ``spectra`` is 0, it starts a continuous measurement that runs until
        manually stopped (Ctrl+C), at which point the command ``B8 01 00 B8`` is
        sent to stop it. In continuous mode no measurement data is read yet.

        Args:
            spectra (int): Number of spectra to measure. If 0, starts a continuous measurement.
            id (int): Identifier for the measurement.
            measurement_settings (dict): Measurement settings, used to decode the
                data frames (see :meth:`read_measurement_data`).

        Returns:
            dict: Measurement results, see :meth:`read_measurement_data`.
            Empty list if the device is not connected.
        """

        if not self.device:
            print("Device not connected.")
            return []

        
        #specific tags for the ISX3
        cmd_tag = 0xB8 #cmd_tag for Start Measure
        data_start = bytes([0x01]) + spectra.to_bytes(2, 'big') #starts measurement for number of spectra (if spectra is 0 starts a continuous measurement. Send the command (B8 01 00 B8) to stop the continuous run)
        data_stop = bytes([ 0x00]) #stops measurement
        

        if spectra == 0:
            data = data_start
            #print("starts continuous measurement. Press Ctrl+C to stop.")
            self.device.write(bytes([cmd_tag, len(data)]) + data + bytes([cmd_tag]))
            #NOTE: frame capture during continuous mode isn't implemented yet -
            #read_measurement_data() only supports reading a known, fixed number of frames (spectra > 0),
            #so no measurement data is collected while waiting here; this loop only controls start/stop timing.
            results = {"id": [], "real": [], "imag": [], "timestamp": [], "timestamp_unit": [], "current_range": []}
            try:
                while True:
                    time.sleep(0.1) #idle until the user manually stops the continuous measurement
            except KeyboardInterrupt:
                pass
            data = data_stop
            self.device.write(bytes([cmd_tag, len(data)]) + data + bytes([cmd_tag]))

            print("continuous measurement stopped.")
        else:
            data = data_start
            #print (f"starts measurement Nr.{id} for {spectra} measurement cycles.")
            self.device.write(bytes([cmd_tag, len(data)]) + data + bytes([cmd_tag]))
            results = self.read_measurement_data(spectra=spectra, timeout=10.0, measurement_settings = measurement_settings)

        #print(f"Results for Measurement Nr. {id}:", results)
        return results


    def read_measurement_data(self, spectra, timeout, measurement_settings):
        """
        Reads measurement data frames from the ISX3 device.

        Structure of a data frame (``0xB8 [Length] [Data] 0xB8``)::

            id (2 byte) | timestamp (4 byte ms / 5 byte µs)* | current range (1 byte)* | real (4 byte) | imag (4 byte)

        ``*`` only if timestamp / current range output is activated
        (see :meth:`set_options`).

        Args:
            spectra (int): Number of data frames to read.
            timeout (float): Maximum time to wait for measurement results
                (currently not used).
            measurement_settings (dict): Measurement settings, the key
                ``enable_current_range_output`` is used to decode the frames.

        Returns:
            dict: Measurement results with the keys ``id``, ``real``, ``imag``,
            ``timestamp``, ``timestamp_unit``, ``current_range`` and
            ``frequencies`` (one list each).

        Raises:
            ValueError: If a frame has an invalid end tag or an unknown length.
        """
        current_range = 0
        timestamp_ms = 0
        timestamp_us = 0

        results = {"id": [],
                   "real": [],
                   "imag": [],
                   "timestamp":[],
                   "timestamp_unit": [],
                   "current_range": [],
                   "frequencies": []
        }

        while len(results["id"]) < spectra:
            tag = self.device.read(1)
            while tag and tag[0] != 0xB8:
                tag = self.device.read(1)

            length = self.device.read(1)[0]
            frame = self.device.read(length) 
            end_tag = self.device.read(1)
            if end_tag[0] != 0xB8:
                raise ValueError("Invalid end tag in measurement frame")

            #frame: /id(2byte)/timestamp(4->ms or 5->us byte)*/current_range(1byte)*/real(4byte)/imag(4byte)
            #*only if timestamp/current_range is activated
            freq_id = int.from_bytes(frame[0:2], "big")

            if length == 0x0A: #no timestamp / no current range
                real = struct.unpack(">f",frame[2:6])[0]
                imag = struct.unpack(">f",frame[6:10])[0]


            elif length == 0x0E: #timestamp ms
                timestamp_ms = struct.unpack(">i",frame[2:6])[0]
                real = struct.unpack(">f",frame[6:10])[0]
                imag = struct.unpack(">f",frame[10:14])[0]


            elif length == 0x0F and measurement_settings["enable_current_range_output"] == 0: #timestamp us no current range
                timestamp_us = struct.unpack(">i",frame[2:7])[0]
                real = struct.unpack(">f",frame[7:11])[0]
                imag = struct.unpack(">f",frame[11:15])[0]


            elif length == 0x0B: #current range
                current_range = frame[3]
                real = struct.unpack(">f",frame[3:7])[0]
                imag = struct.unpack(">f",frame[7:11])[0]

                

            elif length == 0x0F and  measurement_settings["enable_current_range_output"] != 0: #timestamp + current range
                timestamp_ms = struct.unpack(">i",frame[2:6])[0]
                current_range = frame[6]
                real = struct.unpack(">f",frame[7:11])[0]
                imag = struct.unpack(">f",frame[11:15])[0]


            else:
                raise ValueError(
                    f"Unknown measurement frame length: 0x{length:02X}"
                )

            #write results      
            results["id"].append(freq_id),
            results["real"].append(real),
            results["imag"].append(imag),
                    
            if timestamp_ms != 0:
                results["timestamp"].append(timestamp_ms)
                results["timestamp_unit"].append("ms")
            else:
                results["timestamp"].append(None)
                                
            if timestamp_us != 0:
                results["timestamp"].append(timestamp_us)
                results["timestamp_unit"].append("us")
            else:
                results["timestamp"].append(None)

            if current_range != 0:
                results["current_range"].append(current_range)
            else:
                results["timestamp"].append(None)


        return results

    def software_reset(self):
        """
        Sends a software reset command (``A1 00 A1``) to the device.
        """
        self.print_msg = True
        self.write_command_string(bytearray([0xA1, 0x00, 0xA1]))
        self.print_msg = False


    def get_ip_address(self):
        """
        Reads the IP address of the ISX-3 (Get IP command ``0xBE``).

        - Request: ``[CT=0xBE] [01] [01] [CT=0xBE]``
        - Answer: ``[CT=0xBE] [05] [01] [A] [B] [C] [D] [CT=0xBE]``

        Returns:
            str: IP address in the form ``"A.B.C.D"``.
        """
        self.device.reset_input_buffer()
        
        # Step 1: Get IP Command senden
        request = bytearray([0xBE, 0x01, 0x01, 0xBE])
        self.device.write(request)
        print("→ Get IP gesendet:", request.hex())
        
        # Step 2: Response lesen (9 Bytes erwartet)
        response = self.device.read(12)  # Etwas mehr für Sicherheit
        
        # IP extrahieren (Bytes 3-6)
        ip_bytes = response[3:7]
        ip_str = '.'.join([str(b) for b in ip_bytes])
        
        print(f"✅ IP-Adresse: **{ip_str}**")
        print(f"   Frame:     {response.hex()}")
        
        return ip_str
    
    def set_options(self, settings): # config: ISX3DeviceConfig
        """
        Sends the general measurement options to the device.

        This includes the timestamp and current range output (``0x97``),
        the DC bias (``0xB6``) and the sync time (``0xB9``). The extension port
        settings (``0xB2``) are not sent yet.

        Args:
            settings (dict): Measurement settings (e.g. from
                :meth:`isx3_api.config_handler.ConfigParser.parse_as_flat_dict`)
                with the keys:

                - ``timestamp_mode`` (int): Timestamp in the data frame:
                  0 = disabled, 1 = ms timestamp (4 byte uint32),
                  2 = µs timestamp (5 byte uint56).
                - ``enable_current_range_output`` (int): Send the current range
                  in the data frame (0 = disabled, 1 = enabled).
                - ``measurement_mode``, ``measurement_channel``, ``current_range``,
                  ``voltage_range`` (int): Frontend settings.
                - ``counter_port``, ``reference_port``, ``working_sense_port``,
                  ``working_port`` (int): Extension port channel selection
                  (values depend on the connected module, e.g. MuxModule).
                - ``dc_bias_enabled`` (bool): Whether to enable DC bias.
                - ``bias_voltage_v`` (float): DC bias voltage in volts.
                - ``sync_time_us`` (int): Time between two spectrum measurements
                  in microseconds.
        """

        #get options and frontend settings from settings dictionary
        timestamp_mode = settings["timestamp_mode"] # Zeitstempel im Datenframe aktivieren: 0 = Deaktiviert, 1 = ms-Zeitstempel (4 Byte uint32), 2 = µs-Zeitstempel (5 Byte uint56)
        enable_current_range_output = settings["enable_current_range_output"] #Strommessbereich im          
        measurement_mode=settings["measurement_mode"]
        measurement_channel=settings["measurement_channel"]
        current_range=settings["current_range"]
        voltage_range=settings["voltage_range"]
        counter_port=settings["counter_port"]
        reference_port=settings["reference_port"]
        working_sense_port=settings["working_sense_port"]
        working_port=settings["working_port"]
        dc_bias_enabled=settings["dc_bias_enabled"]
        bias_voltage_v=settings["bias_voltage_v"]
        sync_time_us=settings["sync_time_us"]

        #print("Übertrage Options...")
        
        if timestamp_mode == 1:
            self._send_command(0x97, bytes([0x01, 0x01])) # Enable ms[cite: 2]
        elif timestamp_mode == 2:
            self._send_command(0x97, bytes([0x02, 0x01])) # Enable us[cite: 2]
        else:
            self._send_command(0x97, bytes([0x01, 0x00])) # Disable
            self._send_command(0x97, bytes([0x02, 0x00])) 

        # Enable/Disable Current Range
        self._send_command(0x97, bytes([0x04, 1 if enable_current_range_output else 0])) # [cite: 2]

        
        
        # 3. Extension Port (0xB2)[cite: 2] - not used yet
        """
        print("Übertrage Extension Port-Settings...")
        ext_payload = struct.pack('>BBBB',
                                    counter_port,
                                    reference_port,
                                    working_sense_port,
                                    working_port)
        self._send_command(0xB2, ext_payload) #[cite: 2]
        """
        # 4. DC Bias (0xB6 0x33 / 0x30)[cite: 2]
        #print("Übertrage DC Bias...")
        # Value setzen
        bias_payload = bytes([0x33]) + struct.pack('>f', bias_voltage_v) #[cite: 2]
        self._send_command(0xB6, bias_payload) #[cite: 2]
        # Aktivieren/Deaktivieren
        self._send_command(0xB6, bytes([0x30, 1 if dc_bias_enabled else 0])) #[cite: 2]
        
        # 5. Sync Time (0xB9)[cite: 2]
        #print("Übertrage Sync Time...")
        sync_payload = struct.pack('>I', sync_time_us) #[cite: 2]
        self._send_command(0xB9, sync_payload) #[cite: 2]
        
    def set_frequency_setup(self, current_setup): # config: ISX3DeviceConfig
        """
        Configures the measurement setup for a single frequency point.

        Resets the old setup, sends the frontend settings (``0xB0``) and adds
        the frequency point with its extended options (EOPs) to the frequency
        setup (``0xB6``).

        Args:
            current_setup (dict): One measurement setup from
                :meth:`isx3_api.config_handler.ConfigBuilder.generate_measurement_queue`
                with the keys:

                - ``measurement_mode`` (int): Measurement mode (1 = 2-point,
                  2 = 4-point, 3 = 3-point).
                - ``measurement_channel`` (int): Measurement channel to use.
                - ``current_range`` (int): Index of the current measurement range.
                - ``voltage_range`` (int): Index of the voltage measurement range.
                - ``frequency`` (float): Frequency of the measurement in Hz.
                - ``precision`` (float): Measurement precision.
                - ``amplitude`` (float): Signal amplitude.
                - ``excitation_type`` (int): Type of excitation (EOP ``0x03``,
                  only sent if not 1).
                - ``point_delay_us`` (int): Delay between measurement points in
                  microseconds (EOP ``0x01``, uint32).
                - ``phase_sync`` (int): Phase synchronous switching
                  (EOP ``0x02``): 0 = inactive, 1 = active.
        """

        #get settings from current_setup dictionary
        measurement_mode=current_setup["measurement_mode"]
        measurement_channel=current_setup["measurement_channel"]
        current_range=current_setup["current_range"]
        voltage_range=current_setup["voltage_range"]
        frequency = current_setup["frequency"]  #frequency (float): Frequency point for single frequency measurement
        precision = current_setup["precision"] #precision (float): Measurement precision
        amplitude = current_setup["amplitude"] #amplitude (float): Signal amplitude
        excitation_type = current_setup["excitation_type"] #excitation_type (str): Type of excitation, "voltage
        point_delay_us = current_setup["point_delay_us"] #point_delay_us (int): Delay between frequency points in microseconds
        phase_sync = current_setup["phase_sync"] #phase_sync (bool): Whether to synchronize the phase between frequency points

        self.print_msg = False
        # resets the setup
        cmd_tag = 0xB6 # CT -> Set FS Settings
        data = bytes([0x01])  
        self._send_command(cmd_tag = cmd_tag, data = data)

        
        #1 Frontend (0xB0)[cite: 2]
        #print("Übertrage Frontend-Settings...")
        # Clear old frontend settings to avoid overflow
        #cmd_tag = 0xB0 # CT -> Set FE Settings
        data = bytes([0xFF, 0xFF, 0xFF])  
        self._send_command(0xB0, data = data)
        # Sende neue Frontend-Settings (Mode, Channel, C-Range, V-Range)
        fe_payload = struct.pack('>BBBB', 
                                    measurement_mode,
                                    measurement_channel,
                                    current_range,
                                    voltage_range)
        self._send_command(0xB0, fe_payload) # [cite: 2]
        
        #2 Frequency Setup (0xB6)[cite: 2]
        #print("Übertrage Frequency-Setup...")
        # Init / Clear current setup
        
        # Extended Options (EOPs) vorbereiten[cite: 2]
        eops = b''
        if point_delay_us > 0:
            eops += bytes([0x01]) + struct.pack('>I', point_delay_us) # [cite: 2]
        if phase_sync:
            eops += bytes([0x02]) + struct.pack('>I', 1) # [cite: 2]
        if excitation_type != 1:  
            eops += bytes([0x03]) + struct.pack('>I', excitation_type) #[cite: 2]

        # Frequenzpunkt hinzufügen
        # Single Frequency: 0x02 [Freq] [Prec] [Amp] [EOPs...][cite: 2]
        payload = bytes([0x02]) + struct.pack('>fff', 
                                                frequency, 
                                                precision, 
                                                amplitude)
        
        self._send_command(cmd_tag, payload + eops) # [cite: 2]  