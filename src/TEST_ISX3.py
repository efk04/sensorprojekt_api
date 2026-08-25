import struct
import serial
import serial.tools.list_ports
import csv
import h5py
import numpy as np
from shapely import buffer
import src.test_check_User_Input as input_user
import time
import socket
import numpy as np

from datetime import datetime
from typing import Iterable, List, Tuple
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

#Standard measurement parameters for code testing
measurement_mode =  4, #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
measurement_channel = "bnc port" , #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
current_measurement_range = 'autoranging' , #current_measurement_range (str): Current measurement range (e.g., "10mA")
voltage_measurement_range = '1V' , #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
frequnecy_sweep = True, #frequnecy_sweep (bool): Whether to perform a frequency sweep (True/False).
frquency_list = [1000.0, 2000.0, 5000.0, 10000.0, 20000.0, 50000.0], #frquency_list (list): List of frequencies to measure.
start_frequency =  1000.0,     #start_frequency (str): Starting frequency, e.g., "1kHz".
end_frequency  = 50000.0,    #end_frequency (str): Ending frequency, e.g., "10MHz".
count = 21, #count (int): Number of frequency points.
scale = 'log', #scale (str): Scale type, "log" or "linear".
precision = 1.0, #precision (float): Measurement precision.
amplitude = 0.25, #amplitude (str): Signal amplitude.
excitation_type = 'voltage' #excitation_type (str): Type of excitation, "voltage" or "current".
class ISX3:
    def __init__(self) -> None:
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

    def connect_device_fs(self, port: str):
            """
            Connects to the ISX3 device via the specified serial port (USB full-speed).

            Args:
                port (str): COM port to connect to (e.g., "COM3").

            Raises:
                serial.SerialException: If the connection cannot be established.
            """
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
                    port=port,
                    baudrate=9600,
                    timeout=1,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                )
                print(f"Successfully Connected to {self.device.name}. \n")
            except serial.SerialException as e:
                print("Error: ", e)

        
            self.system_message_callback_usb_fs()

    """def connect_device_lan (
            self, 
            host: str,
            port: int = 5000,
            local_bind: str | None = None,
            timeout: float = 5.0,
            retries: int = 1,
            retry_backoff: float = 2.0 ):
        

        
        connects to device via LAN
        Args: HOST: IP_Address of device
              Port: If static IP address is used: PORT=5000
                    If DHCP is used: PORT=8888 
         serial.SerialException: If the connection cannot be established.
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if local_bind:
                sock.bind((local_bind, 0))  # port 0 -> ephemeral local port

        if hasattr(self, "tcp_protocol") and self.tcp_protocol is not None:
            print(f"TCP connection already defined as {self.tcp_protocol}.")
            return self.device
# Set non-blocking and start connect (connect_ex returns errno or 0)



        self.tcp_protocol = "TCP"

        attempt = 0
        while attempt < retries:
            attempt += 1
            try:
                print(f"Attempt {attempt}/{retries}: connecting to {host}:{port} (timeout={timeout}s)...")
                sock = socket.create_connection((host, port), timeout=timeout)
                sock.settimeout(None)  # switch to blocking mode for subsequent recv/send
                self.device = sock
                print(f"Successfully connected to {host}:{port}")
                return sock
            except (ConnectionRefusedError, TimeoutError) as e:
                print(f"Connection attempt {attempt} failed: {e}")
                if attempt < retries:
                    wait = retry_backoff ** (attempt - 1)
                    print(f"Retrying in {wait} s...")
                    time.sleep(wait)
                else:
                    print("Max retries reached. Giving up.")
            except OSError as e:
                print(f"OS error during connect: {e}")
                break

        # cleanup / reset state
        self.tcp_protocol = None
        self.device = None
        return None"""
    
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

    def set_fs_settings(self, measurement_mode, measurement_channel,
                        current_measurement_range, voltage_measurement_range):
        """
                Configures the frontend settings for the measurement.

                Args:
                    measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point).
                    measurement_channel (str): Measurement channel to use (e.g., "Main Port").
                    current_measurement_range (str): Current measurement range (e.g., "10mA").
                    voltage_measurement_range (str): Voltage measurement range (e.g., "1V").

                Returns:
                    None
                """
        # Clear stack to avoid overflow
        self.write_command_string(bytearray([0xB0, 0x03, 0xFF, 0xFF, 0xFF, 0xB0]))

        # Convert parameters
        mode = input_user.check_measurement_mode(measurement_mode)
        if mode == -1:
            print(f"Invalid Measurement Mode '{measurement_mode}', set it to default Value (4 Points).")
            mode = 0x02
        current_range = input_user.check_current_range_settings(current_measurement_range)
        if current_range == -1:
            print(f"Invalid range mode '{current_measurement_range}', set it to 'autoranging'.")
            current_range = 0x00
        voltage_range = input_user.check_voltage_range_settings(voltage_measurement_range)
        if voltage_range == -1:
            print(f"Invalid voltage range '{voltage_measurement_range}', set it to ±1V.")
            voltage_range = 0x01
        channel_code = input_user.check_measurement_channel(measurement_channel)
        if channel_code == -1:
            print(f"Invalid Channel '{measurement_channel}', set it to 'Main Port'.")
            channel_code = 0x01

        # 2-byte extension channels (default to 0x0000 if not used)
        ext = [0x00, 0x00]

        # Build command based on measurement mode
        command = [0xB0, 0x04, mode, channel_code ,current_range, voltage_range, 0xB0]
        print(command)
        """if mode == 0x01:  # 2-point
            command = [
                0xB0, 0x09, mode, current_range, voltage_range,
                channel_code, *ext,  # C channel
                channel_code, *ext,  # W channel
                0xB0
            ]
        elif mode == 0x03:  # 3-point
            command = [
                0xB0, 0x0C, mode, current_range, voltage_range,
                channel_code, *ext,  # C channel
                channel_code, *ext,  # R channel
                channel_code, *ext,  # W channel
                0xB0
            ]
        elif mode == 0x02:  # 4-point
            command = [
                0xB0, 0x0F, mode, current_range, voltage_range,
                channel_code, *ext,  # C channel
                channel_code, *ext,  # R channel
                channel_code, *ext,  # S channel
                channel_code, *ext,  # W channel
                0xB0
            ]
        else:
            print("Unsupported measurement mode. Aborting.")
            return"""

        self.write_command_string(bytearray(command))
        #response = self.device.read(4)
        #print("Response from device: ", response)
        #print("FS settings applied.\n")

    def get_fs_settings(self):
        self.device.reset_input_buffer()

        # Step 1: Query number of configured channels
        request = bytearray([0xB1, 0x03, 0x02, 0x00, 0xB1])
        self.device.write(request)
        response = self.device.read(16)

        if len(response) < 6 or response[0] != 0xB1 or response[-1] != 0xB1:
            print("No valid B1 response frame for channel count.\n")
            return

        num_channels = int.from_bytes(response[2:4], "big")
        print(f"Number of configured channels: {num_channels}")

        if num_channels == 0:
            print("No configured frontend channels.\n")
            return

        # Step 2: Query each channel config
        for ch in range(1, num_channels + 1):
            self.device.reset_input_buffer()
            self.device.write(bytearray([0xB1, 0x02, ch, 0xB1]))
            response = self.device.read(32)

            print(f"\nRaw response for channel {ch}:", response.hex())

            for i in range(len(response)):
                if response[i] == 0xB1:
                    end_index = response.find(b'\xB1', i + 1)
                    if end_index != -1:
                        frame = response[i:end_index + 1]
                        print("Valid B1 Frame found:", frame.hex())

                        frame_type = frame[1]
                        mode = frame[2]
                        current = frame[3]
                        voltage = frame[4]

                        def get_channel_info(start_index):
                            ch = frame[start_index]
                            ext = int.from_bytes(frame[start_index + 1:start_index + 3], 'big')
                            print("\n")
                            return ch, ext

                        if frame_type == 0x09 and len(frame) == 17:  # 2-point
                            ch_c, ext_c = get_channel_info(5)
                            ch_w, ext_w = get_channel_info(8)
                            print("2-point configuration:")
                            print(f"Mode: 0x{mode:02X}, Current: 0x{current:02X}, Voltage: 0x{voltage:02X}")
                            print(f"C: 0x{ch_c:02X} (ext: {ext_c}), W: 0x{ch_w:02X} (ext: {ext_w})")

                        elif frame_type == 0x0C and len(frame) == 20:  # 3-point
                            ch_c, ext_c = get_channel_info(5)
                            ch_r, ext_r = get_channel_info(8)
                            ch_w, ext_w = get_channel_info(11)
                            print("3-point configuration:")
                            print(f"Mode: 0x{mode:02X}, Current: 0x{current:02X}, Voltage: 0x{voltage:02X}")
                            print(
                                f"C: 0x{ch_c:02X} (ext: {ext_c}), R: 0x{ch_r:02X} (ext: {ext_r}), W: 0x{ch_w:02X} (ext: {ext_w})")

                        elif frame_type == 0x0F and len(frame) == 23:  # 4-point
                            ch_c, ext_c = get_channel_info(5)
                            ch_r, ext_r = get_channel_info(8)
                            ch_s, ext_s = get_channel_info(11)
                            ch_w, ext_w = get_channel_info(14)
                            print("4-point configuration:")
                            print(f"Mode: 0x{mode:02X}, Current: 0x{current:02X}, Voltage: 0x{voltage:02X}")
                            print(f"C: 0x{ch_c:02X} (ext: {ext_c}), R: 0x{ch_r:02X} (ext: {ext_r}), "
                                  f"S: 0x{ch_s:02X} (ext: {ext_s}), W: 0x{ch_w:02X} (ext: {ext_w})")
                        else:
                            print("Unknown or unsupported frame format.")
                        break
            else:
                print("No valid B1 frame found for this channel.")
        print("\n")

    def set_setup_single_frequency_point(self,frequency, precision, amplitude, excitation_type):
        """
                Configures the measurement setup parameters for a single frequency point.
    
                Args:
                   
                    single_frequency_point (float or str): Frequency point for single frequency measurement.
                    precision (float): Measurement precision.
                    amplitude (str): Signal amplitude.
                    excitation_type (str): Type of excitation, "voltage" or "current".
                """
        self.print_msg = False
        # resets the setup
        self.device.write(bytearray([0x86, 0x01, 0x01, 0x86]))

        self.frequency_points = 1

        frequency_data = input_user.check_single_frequency_point(frequency)
        
        # HIER: Einzelfrequenz entpacken und speichern
        single_f = struct.unpack(">f", bytes(frequency_data))[0]
        self.frequencies = [single_f]

        settings_formatted = [0xB6, 0x0D, 0x02]

        for data in frequency_data:
            settings_formatted.append(data)

        for data in input_user.check_precision(precision):
            settings_formatted.append(data)

        for data in input_user.check_amplitude(amplitude, excitation_type):
            settings_formatted.append(data)

        settings_formatted.append(0xB6)
        settings_formatted = bytearray(settings_formatted)
             
        print(settings_formatted.hex())
        self.write_command_string(settings_formatted)
        print("Set the setup. \n")

    
    def set_frequency_setup(self, frequency_sweep, frequency_list, start_frequency, end_frequency, count, scale, precision, amplitude: str, excitation_type: str):
        """
                Configures the measurement setup parameters for a list of frequency points.
    
                Args:
                    frequency_sweep (bool): Indicates if a frequency sweep is to be performed.
                    frequency_list (list): List of frequency points for measurement.
                    start_frequency (str): Starting frequency.
                    end_frequency (str): Ending frequency.
                    count (int): Number of frequency points.
                    scale (str): Scale type, "log" or "linear".
                    precision (float): Measurement precision.
                    amplitude (str): Signal amplitude.
                    excitation_type (str): Type of excitation, "voltage" or "current".
                """
        self.print_msg = False
        # eigentlich darf hier nur ein Frequenzwert verarbeitet werden, da nur eine Frequenz in Messung geladen wird
        # resets the setup
        self.device.write(bytearray([0x86, 0x01, 0x01, 0x86]))

        #check if frequency_sweep is True or False and set the setup accordingly
        if frequency_sweep:
            
            if len.input_user.check_frequency_range(start_frequency, end_frequency) == 2:
                if scale == "lin":
                    frequency_list = np.linspace(start_frequency, end_frequency, count).tolist()
                elif scale == "log":
                    frequency_list = np.logspace(np.log10(start_frequency), np.log10(end_frequency), count).tolist()

            self.set_setup_frequency_sweep(start_frequency, end_frequency, count, scale, precision, amplitude, excitation_type)
            
        else:
            
            self.frequency_points = len(frequency_list)
            #check if frequency_list is valid and convert to 4-byte representation
            frequency_data = input_user.check_frequency_list(frequency_list)
        
        #creates a list of the choosen frequeny, the precision, the amplitude 

        settings_formatted = [0xB6, 0x0D, 0x02]

        for data in frequency_data:
            settings_formatted.append(data)

        for data in input_user.check_precision(precision):
            settings_formatted.append(data)

        for data in input_user.check_amplitude(amplitude, excitation_type):
            settings_formatted.append(data)

        settings_formatted.append(0xB6)
        settings_formatted = bytearray(settings_formatted)
             
        print(settings_formatted.hex())
        self.write_command_string(settings_formatted)
        print("Set the setup. \n")

    def set_setup_frequency_sweep(self, start_frequency, end_frequency, count, scale, precision, amplitude, excitation_type):
        """
                Configures the measurement setup parameters such as frequency range and signal characteristics.
    
                Args:
                   
                    start_frequency (str): Starting frequency, e.g., "1kHz".
                    end_frequency (str): Ending frequency, e.g., "10MHz".
                    count (int): Number of frequency points.
                    scale (str): Scale type, "log" or "linear".
                    precision (float): Measurement precision.
                    amplitude (str): Signal amplitude.
                    excitation_type (str): Type of excitation, "voltage" or "current".
                """
        self.print_msg = False
        # resets the setup
        self.device.write(bytearray([0x86, 0x01, 0x01, 0x86]))

        self.frequency_points = count

        frequency_data = input_user.check_frequency_range(start_frequency, end_frequency)[0] + input_user.check_frequency_range(start_frequency, end_frequency)[1]

        # HIER: Start- und Endfrequenz entpacken und Liste berechnen
        import math
        start_f = struct.unpack(">f", bytes(frequency_data[:4]))[0]
        end_f = struct.unpack(">f", bytes(frequency_data[4:8]))[0]
        
        if count > 1:
            if scale == "linear":
                self.frequencies = [start_f + i * (end_f - start_f) / (count - 1) for i in range(count)]
            else:  # "log"
                self.frequencies = [start_f * ((end_f / start_f) ** (i / (count - 1))) for i in range(count)]
        else:
            self.frequencies = [start_f]

        settings_formatted = [0xB6, 0x16, 0x03]

        for data in frequency_data:
            settings_formatted.append(data)

        for data in input_user.check_count(count):
            settings_formatted.append(data)

        settings_formatted.append(input_user.check_scale(scale))

        for data in input_user.check_precision(precision):
            settings_formatted.append(data)

        for data in input_user.check_amplitude(amplitude, excitation_type):
            settings_formatted.append(data)

        settings_formatted.append(0xB6)
        print(settings_formatted)
        self.write_command_string(bytearray(settings_formatted))

        print("Set the setup. \n")

    def start_measurement(self, spectra, id ):
        if not self.device:
            print("Device not connected.")
            return []

        
        spectra = input_user.check_input_spectra(spectra)
        expected_results = spectra * self.frequency_points

        print(f"Starts the measuring for {spectra} Cycles...")

        #starts the measuring
        self.device.write(bytearray([0xB8, 0x03, 0x01, 0x00, spectra, 0xB8]))
        """
        Ergebnis = self.device.read(12)
        print(f"Measurement Nr. {id}:",Ergebnis)
        """
        # Reads the Data
        results = self.read_measurement_data(expected_results=expected_results, timeout=10.0)
        
        print(f"Results for Measurement Nr. {id}:", results)
        self.system_message_callback_usb_fs()  # read ACK or NACK

        return results


    def read_measurement_data(self, expected_results, timeout):
        start = time.time()
        results = []
        buffer = []

        while time.time() - start < timeout and len(results) < expected_results:
            byte = self.device.read(1)
        
            if byte:
                buffer.append(byte[0])

                if len(buffer) >= 13:
                    if buffer[-13] == 0xB8 and buffer[-12] == 0x0A and buffer[-1] == 0xB8:
                        frame = buffer[-13:]
                        freq_id = int.from_bytes(frame[2:4], "big")
                        real = struct.unpack(">f", bytes(frame[4:8]))[0]
                        imag = struct.unpack(">f", bytes(frame[8:12]))[0]
                        
                        
                        #include result in results tupel
                        results.append((freq_id, real, imag))
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


    def stop_measurement(self):
        """
        Stops the measurement process.
        :return: None
        """

        self.write_command_string(bytearray([0xB8, 0x01, 0x00, 0xB8]))

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
    
    def save_settings(self):
        self.write_command_string(bytearray([0x90, 0x00, 0x90]))

    def get_setup(self):
        self.write_command_string(bytearray([0xB7, 0x01, 0x01, 0xB7]))
 
    def get_fe_settings(self):
        self.write_command_string(bytearray([0xB1, 0x00, 0xB1]))
        