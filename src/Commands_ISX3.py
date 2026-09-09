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
from config.config_transmitter import ISX3Transmitter as ISX3_T


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

    def connect_device_fs(self, config):
            """
            Connects to the ISX3 device via the specified serial port (USB full-speed).

            Args:
                port (str): COM port to connect to (e.g., "COM3").
                baudrate (int): Baud rate for the serial connection (default: 9600).
            Raises:
                serial.SerialException: If the connection cannot be established.
            """

            port = config.connection.port  # Use the port from the configuration
            baudrate = config.connection.baudrate  # Use the baudrate from the configuration

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
                    baudrate=baudrate, #e.g., 9600, 115200, etc. (must match the device's settings)
                    timeout=1,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS,
                )
                print(f"Successfully Connected to {self.device.name}. \n")
            except serial.SerialException as e:
                print("Error: ", e)

        
            self.system_message_callback_usb_fs()

    
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
    


    def start_measurement(self, spectra, id, time_of_continuous_measurement = None ):
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
        expected_results = spectra * self.frequency_points
        #specific tags for the ISX3
        cmd_tag = 0xB8 #cmd_tag for Start Measure
        data_start = bytearray([ 0x01,0x00, spectra]) #starts measurement for number of spectra (if spectra is 0 starts a continuous measurement. Send the command (B8 01 00 B8) to stop the continuous run)
        data_stop = bytearray([ 0x01,0x00]) #stops measurement

        if spectra == 0:
            self.tcm = time_of_continuous_measurement #time of continuous measurement in seconds
            data = data_start
            print (f"starts continuous measurement for {self.tcm} s.")
            self.ISX3_T._send_command(cmd_tag = cmd_tag, data = data)
            results = self.read_measurement_data(expected_results=expected_results, timeout=10.0)
            time.sleep(self.tcm)
            data = data_stop
            self.ISX3_T._send_command(cmd_tag = cmd_tag, data = data)
            self.ISX3_T._wait_for_ack(cmd_tag = cmd_tag)
            print("continuous measurement stopped.")
        else:
            data = data_start
            print (f"starts measurement Nr.{id} for {spectra} measurement cycles.")
            self.ISX3_T._send_command(cmd_tag = cmd_tag, data = data)
            results = self.read_measurement_data(expected_results=expected_results, timeout=10.0)

        print(f"Results for Measurement Nr. {id}:", results)
        return results


    def read_measurement_data(self, expected_results, timeout):
        """
        Reads measurement data from the ISX3 device.
        
        Args:
            expected_results (int): Total number of expected measurement results.
            timeout (float): Maximum time to wait for measurement results.      
            
        return: 
            results: list of tuples containing (frequency_id, real_part, imaginary_part) for each measurement.
            
        """

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
    

        