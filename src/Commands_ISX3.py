from logging import config
import struct
import serial
import serial.tools.list_ports
import numpy as np
from shapely import buffer
import time
import os
import sys


#import Classes
#helper function to find the classes under the /src path
current_folder = os.path.dirname(os.path.abspath(__file__))
main_folder = os.path.abspath(os.path.join(current_folder, "..")) # Anpassen, falls dein Skript noch tiefer liegt

if main_folder not in sys.path:
    sys.path.append(main_folder)

import src.test_check_User_Input as input_user
#from config.config_transmitter import ISX3Transmitter as ISX3_T
#from evaluation.ISX3_measurment_test import ISX3MeasurementTest as ISX3_Measurement_Test

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

    ACK_TAG = 0x18
    ACK_SUCCESS = 0x83
    NACK_SYNTAX = 0x81
    NACK_NOT_RECOGNIZED = 0x82

    def __init__(self):
        """
                    Initializes an ISX3 device handler.
        """
        self.serial_protocol = None
        self.device = None
        self.frequency_points = 0
        self.ret_hex_int = None
        self.print_msg = True
        self.tcp_protocol = None
        self.frequencies = []
        self.frequency_list = []
        self.tcm = 30 #time of continuous measurement in seconds (default value)

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

            Args:
                port (str): COM port to connect to (e.g., "COM3").
                baudrate (int): Baud rate for the serial connection (default: 9600).
            Raises:
                serial.SerialException: If the connection cannot be established.
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
                print(f"Successfully Connected to {self.device.name}. \n")
            except serial.SerialException as e:
                print("Error: ", e)

            
            #self.system_message_callback_usb_fs()

    def _send_command(self, cmd_tag: int, data: bytes):
        """
        Verpackt die Daten in das Sciospec Frame-Format und sendet sie.
        Format: [CMD-Tag] [Length] [Data...] [CMD-Tag]
        """
        length = len(data)
        if length > 255:
            raise ValueError("Daten-Payload überschreitet maximale Frame-Länge von 255 Bytes.")

        # Frame zusammensetzen
        frame = (bytes([cmd_tag, length]) + data + bytes([cmd_tag]))
        
        # Senden
        print(frame)
        self.device.write(frame)
        self.device.flush()

        # Auf Bestätigung (ACK) warten
        self._wait_for_ack(cmd_tag)

    def _wait_for_ack(self, original_cmd_tag: int):
        """
        Liest den Rückgabe-Frame und prüft auf erfolgreiches Acknowledge.
        Ein ACK-Frame sieht so aus: 0x18 0x01 [Status] 0x18[cite: 2]
        """
        # Wir erwarten 4 Bytes für das ACK
        ack_frame = self.device.read(4)
        
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

    def system_message_callback_usb_fs(self):
        """
        Reads system messages from the serial buffer and interprets them.

        Returns:
            list or tuple or None: Depending on `ret_hex_int`, returns hexadecimal, integer values, both, or None.
        """
        timeout_count = 0
        received = []
        data_count = 0
        
        while True:
            buffer = self.device.read()
            if buffer:
                received.extend(buffer)
                data_count += len(buffer)
                timeout_count = 0
                continue
            timeout_count += 1
            if timeout_count >= 1:
                # Break if we haven't received any data
                break

            received = "".join(str(received))  # If you need all the data
        received_hex = [hex(receive) for receive in received]
        try:
            msg_idx = received_hex.index("0x18")
            if self.print_msg:
                print(MSG_DICT[received_hex[msg_idx + 2]])
        except BaseException:
            if self.print_msg:
                print(MSG_DICT["0x01"])
            # self.print_msg = False
        if self.print_msg:
            print("message buffer:\n", received_hex)
            print("message length:\t", data_count)

        if self.ret_hex_int is None:
            return None
        elif self.ret_hex_int == "hex":
            return received_hex
        elif self.ret_hex_int == "int":
            return received
        elif self.ret_hex_int == "both":
            return received, received_hex
        return None
    
    def write_command_string(self, command):
        """
                Writes a command to the device and processes the resulting system message.

                Args:
                    command (bytearray): Formatted command frame.
                """
        self.device.write(command)
        self.system_message_callback_usb_fs()

    def start_measurement(self, spectra, id, measurement_settings, time_of_continuous_measurement = None):
        """
        Starts the measurement process on the ISX3 device.
        when spectra is 0, it starts a continuous measurement for the specified duration.
        continuous measurement can be stopped by sending the command (B8 01 00 B8).
       
         Args:
            spectra (int): Number of spectra to measure. If 0, starts a continuous measurement.
            id (int): Identifier for the measurement.
            time_of_continuous_measurement (float, optional): Duration in seconds for continuous measurement. Required if spectra is 0.
        
            returns: results (list): List of tuples containing (frequency_id, real_part, imaginary_part) for each measurement.
        """

        if not self.device:
            print("Device not connected.")
            return []

        spectra = input_user.check_input_spectra(spectra)
        expected_results = spectra * 1
        #specific tags for the ISX3
        cmd_tag = 0xB8 #cmd_tag for Start Measure
        data_start = bytes([0x01]) + spectra.to_bytes(2, 'big') #starts measurement for number of spectra (if spectra is 0 starts a continuous measurement. Send the command (B8 01 00 B8) to stop the continuous run)
        data_stop = bytes([ 0x00]) #stops measurement
        

        if spectra == 0:
            self.tcm = time_of_continuous_measurement #time of continuous measurement in seconds
            data = data_start
            print (f"starts continuous measurement for {self.tcm} s.")
            self.device.write(bytes([cmd_tag, len(data)]) + data + bytes([cmd_tag]))
            results = self.read_measurement_data(expected_results=expected_results, timeout=10.0)
            time.sleep(self.tcm)
            data = data_stop
            self.device.write(bytes([cmd_tag, len(data)]) + data + bytes([cmd_tag]))
           
            print("continuous measurement stopped.")
        else:
            data = data_start
            print (f"starts measurement Nr.{id} for {spectra} measurement cycles.")
            self.device.write(bytes([cmd_tag, len(data)]) + data + bytes([cmd_tag]))
            results = self.read_measurement_data(expected_results=expected_results, timeout=10.0, measurement_settings = measurement_settings)

        print(f"Results for Measurement Nr. {id}:", results)
        return results


    def read_measurement_data(self, expected_results, timeout, measurement_settings):
        """
        Reads measurement data from the ISX3 device.
        
        Args:
            expected_results (int): Total number of expected measurement results.
            timeout (float): Maximum time to wait for measurement results.      
            
        return: 
            results: list of tuples containing (frequency_id, real_part, imaginary_part) for each measurement.
            
        """
        tag = self.device.read(1)
        while tag and tag[0] != 0xB8:
            tag = self.device.read(1)

        length = self.device.read(1)[0]
        payload = self.device.read(length)
        end_tag = self.device.read(1)
        if end_tag[0] != 0xB8:
            raise ValueError("Invalid end tag in measurement frame")

        freq_id = int.from_bytes(payload[0:2], "big")
        real = struct.unpack(">f", payload[2:6])[0]
        imag = struct.unpack(">f", payload[6:10])[0]
        results = {
                "id": freq_id,
                "real": real,
                "imag": imag,
            }
    

        """
        command_tag = 0xB8 #byte for start measurement command-tag
        start_time = time.time()
        #results = {}
        buffer = bytearray()

        while time.time() - start_time < timeout:
            
            bytes = self.device.read(1) #reads continuously up to 256 bytes 
            #if not bytes:
               # continue
            buffer.extend(bytes)

            print (buffer)
            while True:
                start = buffer.find(command_tag.to_bytes(1, "big"))
                length = buffer[start+1]
                frame_length = 1 + 1 + length + 1  # CT + LE + Payload + CT

                if start == -1: 
                    buffer.clear()  
                    break #no start measurement CT found

                if start > 0:
                    del buffer[:start] #clear buffer before first measurement-data

                if len(buffer) < frame_length:
                    break #no complete measurement frame

                frame = buffer[:frame_length]

                if frame[-1] != command_tag:
                    del buffer[0] #checks last byte of the frame -> if not start measurement CT-> delete first CT and retry
                    continue

                del buffer[:frame_length]
                
                #read frame
                freq_id = int.from_bytes(frame[2:4], "big")

                if length == 0x0A: #no timestamp / no current range
                    real = struct.unpack(">f",frame[4:8])[0]
                    imag = struct.unpack(">f",frame[8:12])[0]
                    results = {
                        "id": freq_id,
                        "real": real,
                        "imag": imag,
                    }

                elif length == 0x0E: #timestamp ms
                    timestamp_ms = int.from_bytes(frame[4:8],"big")
                    real = struct.unpack(">f",frame[8:12])[0]
                    imag = struct.unpack(">f",frame[12:16])[0]
                    results = {            
                        "id": freq_id,
                        "timestamp": timestamp_ms,
                        "timestamp_unit": "ms",
                        "real": real,
                        "imag": imag,
                        }

                elif length == 0x0F and measurement_settings.current_range ==0: #timestamp us no current range
                    timestamp_us = int.from_bytes(frame[4:9],"big")
                    real = struct.unpack(">f",frame[9:13])[0]
                    imag = struct.unpack(">f",frame[13:17])[0]
                    results = {            
                        "id": freq_id,
                        "timestamp": timestamp_us,
                        "timestamp_unit": "us",
                        "real": real,
                        "imag": imag,
                        }

                elif length == 0x0B: #current range
                    current_range = int.from_bytes(frame[4],"big")
                    real = struct.unpack(">f",frame[5:9])[0]
                    imag = struct.unpack(">f",frame[9:13])[0]
                    results = {            
                        "id": freq_id,
                        "current_range": current_range,
                        "timestamp_unit": "us",
                        "real": real,
                        "imag": imag,
                        }
                    

                elif length == 0x0F and measurement_settings.current_range !=0: #timestamp + current range
                    timestamp_ms = int.from_bytes(frame[4:8],"big")
                    current_range = int.from_bytes(frame[8],"big")
                    real = struct.unpack(">f",frame[9:13])[0]
                    imag = struct.unpack(">f",frame[13:17])[0]
                    results = {            
                        "id": freq_id,
                        "timestamp": timestamp_ms,
                        "timestamp_unit": "ms",
                        "current_range": current_range,
                        "real": real,
                        "imag": imag,
                        }

                else:
                    raise ValueError(
                        f"Unknown measurement frame length: 0x{length:02X}"
                    )
        """

        return results

    def software_reset(self):
        """
                Sends a software reset command to the device.

                Returns:
                    None
                """
        self.print_msg = True
        self.write_command_string(bytearray([0xA1, 0x00, 0xA1]))
        self.print_msg = False


    def get_ip_address(self):
        """
        Liest IP-Adresse des ISX-3 aus (Get IP Command 0xBE).
        Syntax: [CT=0xBE] [01] [01] [CT=0xBE]
        Return: [CT=0xBE] [05] [01] [A][B][C][D] [CT=0xBE]
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
    
    def set_options_and_fe_settings(self, settings): # config: ISX3DeviceConfig
        """
        Configures the frontend settings for the measurement.

        Args:
            timestamp_mode (int): Zeitstempel im Datenframe aktivieren: 0 = Deaktiviert, 1 = ms-Zeitstempel (4 Byte uint32), 2 = µs-Zeitstempel (5 Byte uint56)
            enable_current_range_output (int): Strommessbereich im Rückgabeframe mitsenden (0 = Deaktiviert, 1 = Aktiviert)
            measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point).
            measurement_channel (str): Measurement channel to use (e.g., "Main Port").
            current_measurement_range (str): Current measurement range (e.g., "10mA").
            voltage_measurement_range (str): Voltage measurement range (e.g., "1V").
            #Extension Port Kanal-Auswahl (Befehl 0xB2 / 0xB3). Werte hängen vom angeschlossenen Modul ab (z. B. MuxModule)
            counter_port (int): 
            reference_port (int):
            working_sense_port (int):   
            working_port (int):
            DC_bias_enabled (bool): Whether to enable DC bias.
            bias_voltage (float): DC bias voltage in volts.
            sync_time_us (int): Time between two spectrum measurements in microseconds.
        
            Returns:
            None
        """

        #get options and frontend settings from settings dictionary
        timestamp_mode = settings["timestamp_mode"] # Zeitstempel im Datenframe aktivieren: 0 = Deaktiviert, 1 = ms-Zeitstempel (4 Byte uint32), 2 = µs-Zeitstempel (5 Byte uint56)
        enable_current_range_output = settings["enable_current_range_output"] #Strommessbereich im          
        measurement_mode=settings["measurement_mode"]
        measurement_channel=settings["measurement_channel"]
        current_measurement_range=settings["current_measurement_range"]
        voltage_measurement_range=settings["voltage_measurement_range"]
        counter_port=settings["counter_port"]
        reference_port=settings["reference_port"]
        working_sense_port=settings["working_sense_port"]
        working_port=settings["working_port"]
        DC_bias_enabled=settings["DC_bias_enabled"]
        bias_voltage=settings["bias_voltage"]
        sync_time_us=settings["sync_time_us"]

        print("Übertrage Options...")
        
        if timestamp_mode == 1:
            self._send_command(0x97, bytes([0x01, 0x01])) # Enable ms[cite: 2]
        elif timestamp_mode == 2:
            self._send_command(0x97, bytes([0x02, 0x01])) # Enable us[cite: 2]
        else:
            self._send_command(0x97, bytes([0x01, 0x00])) # Disable
            self._send_command(0x97, bytes([0x02, 0x00])) 

        # Enable/Disable Current Range
        self._send_command(0x97, bytes([0x04, 1 if enable_current_range_output else 0])) # [cite: 2]

        # 3. Frontend (0xB0)[cite: 2]
        print("Übertrage Frontend-Settings...")
        # Clear old frontend settings to avoid overflow
        cmd_tag = 0xB0 # CT -> Set FE Settings
        data = bytes([0xFF, 0xFF, 0xFF])  
        self._send_command(cmd_tag = cmd_tag, data = data)
        # Sende neue Frontend-Settings (Mode, Channel, C-Range, V-Range)
        fe_payload = struct.pack('>BBBB', 
                                    measurement_mode,
                                    measurement_channel,
                                    current_measurement_range,
                                    voltage_measurement_range)
        self._send_command(0xB0, fe_payload) # [cite: 2]
        
        # 4. Extension Port (0xB2)[cite: 2]
        """
        print("Übertrage Extension Port-Settings...")
        ext_payload = struct.pack('>BBBB',
                                    counter_port,
                                    reference_port,
                                    working_sense_port,
                                    working_port)
        self._send_command(0xB2, ext_payload) #[cite: 2]
        """
        # 6. DC Bias (0xB6 0x33 / 0x30)[cite: 2]
        print("Übertrage DC Bias...")
        # Value setzen
        bias_payload = bytes([0x33]) + struct.pack('>f', bias_voltage) #[cite: 2]
        self._send_command(0xB6, bias_payload) #[cite: 2]
        # Aktivieren/Deaktivieren
        self._send_command(0xB6, bytes([0x30, 1 if DC_bias_enabled else 0])) #[cite: 2]
        
        # 7. Sync Time (0xB9)[cite: 2]
        print("Übertrage Sync Time...")
        sync_payload = struct.pack('>I', sync_time_us) #[cite: 2]
        self._send_command(0xB9, sync_payload) #[cite: 2]
        
    def set_frequency_setup(self, current_setup): # config: ISX3DeviceConfig
        """
        Configures the measurement setup parameters for a single frequency point.

        Args:
            
            frequency(float or str): Frequency point for single frequency measurement
            precision (float): Measurement precision.
            amplitude (str): Signal amplitude.
            excitation_type (str): Type of excitation, "voltage" or "current".
            point_delay_us (int) Punkt-Verzögerung zwischen Messpunkten in Mikrosekunden (EOP 0x01, uint32)
            phase_sync (int) Phasensynchrones Umschalten (EOP 0x02): 0 = Inaktiv, 1 = Aktiv
        """

        #get settings from current_setup dictionary
        measurement_mode=current_setup["measurement_mode"]
        measurement_channel=current_setup["measurement_channel"]
        current_measurement_range=current_setup["current_measurement_range"]
        voltage_measurement_range=current_setup["voltage_measurement_range"]
        frequency = current_setup["frequency"]  #frequency (float): Frequency point for single frequency measurement
        precision = current_setup["precision"] #precision (float): Measurement precision
        amplitude = current_setup["amplitude"] #amplitude (float): Signal amplitude
        excitation_type = current_setup["excitation_type"] #excitation_type (str): Type of excitation, "voltage
        point_delay_us = current_setup["point_delay_us"] #point_delay_us (int): Delay between frequency points in microseconds
        phase_sync = current_setup["phase_sync"] #phase_sync (bool): Whether to synchronize the phase between frequency points

        self.print_msg = False
        # resets the setup
        cmd_tag = 0x86 # CT -> Set FS Settings
        data = bytes([0x01])  
        self._send_command(cmd_tag = cmd_tag, data = data)

        # 3. Frontend (0xB0)[cite: 2]
        print("Übertrage Frontend-Settings...")
        # Clear old frontend settings to avoid overflow
        #cmd_tag = 0xB0 # CT -> Set FE Settings
        data = bytes([0xFF, 0xFF, 0xFF])  
        self._send_command(0xB0, data = data)
        # Sende neue Frontend-Settings (Mode, Channel, C-Range, V-Range)
        fe_payload = struct.pack('>BBBB', 
                                    measurement_mode,
                                    measurement_channel,
                                    current_measurement_range,
                                    voltage_measurement_range)
        self._send_command(0xB0, fe_payload) # [cite: 2]

        # Frequency Setup (0xB6)[cite: 2]
        print("Übertrage Frequency-Setup...")
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
     

        