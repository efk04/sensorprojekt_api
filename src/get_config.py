"""
user-input class for:
- getting the user config for the measurement settings
- preparing the measurement settings in a measurement settings queue
"""

#Imports
import numpy as np
import os
import sys

#import Classes
#helper function to find the classes under the  path
current_folder = os.path.dirname(os.path.abspath(__file__))
main_folder = os.path.abspath(os.path.join(current_folder, "..")) 

if main_folder not in sys.path:
    sys.path.append(main_folder)

from config.config_handler import ISX3ConfigParser


class get_config:


    def __init__(self):
        self.measurement_setup_queue = []  #list of dictionarys to hold measurement setups
        self.settings = {} # empty dictionary to hold measurement settings from user
        self.ISX3config = ISX3ConfigParser("config/config.ini")

    def get_settings_from_config(self):
        config_settings = self.ISX3config.parse_as_flat_dict(False)
        print(config_settings)
        return config_settings
    
    def get_test_settings(self):
        #gets measurement settings from user

        #Standard measurement parameters for code testing
        test_settings = {
            "interface_type": 'COM' , #COM -> (Seriell/USB) or TCP -> (Ethernet) (Ethernet connection is not implemented yet)
            "port": 'COM4', #COM-Port for USB connection ("COM3" on Windows or "/dev/ttyUSB0" on Linux) or IP address for TCP connection
            "baudrate": 9600, #e.g. 9600, 115200, etc. (must match the device's settings)
            "timestamp_mode": 1, # Zeitstempel im Datenframe aktivieren: 0 = Deaktiviert, 1 = ms-Zeitstempel (4 Byte uint32), 2 = µs-Zeitstempel (5 Byte uint56)
            "enable_current_range_output": True, #Strommessbereich im Rückgabeframe mitsenden (False = Deaktiviert, True = Aktiviert)
            "measurement_mode": 2, #measurement_mode (int): Measurement mode  1 = 2-Punkt-Messung (0x01), 2 = 4-Punkt-Messung (0x02), 3 = 3-Punkt-Messung (0x03)
            "measurement_channel": 1, #measurement_channel (int): Measurement channel to use: 1 = BNC Port / Port 1 (0x01), 2 = Extension Port (0x02), 3 = Extension Port 2 / Port 2 (0x03)
            "current_range": 0, #current_measurement_range (int): 0 = Autoranging (0x00), 1 = ±10 mA (0x01), 2 = ±100 µA (0x02), 4 = ±1 µA (0x04), 6 = ±10 nA (0x06)
            "voltage_range": 1, #voltage_measurement_range (int): 0 = Autoranging (0x00), 1 = ±1 V (0x01, Standard), 2 = ±0.09 V (0x02)
            "counter_port": 0, #Extension Port Kanal-Auswahl (Befehl 0xB2 / 0xB3)
            "reference_port": 0, # Werte hängen vom angeschlossenen Modul ab (z. B. MuxModule)
            "working_sense_port": 0,
            "working_port": 0,   
<<<<<<< Updated upstream
            "frequency_sweep": True, #frequency_sweep (bool): Whether to perform a frequency sweep (usage of the start, endfrequency, the count and scale option).
            "frequency_list": [1000.0, 2000.0, 5000.0, 10000.0, 50000.0], #frequency_list (list): List of frequencies to measure.
            "start_frequency": 1000.0,     #start_frequency (str): Starting frequency, e.g., "1kHz".
            "end_frequency": 100000.0,    #end_frequency (str): Ending frequency, e.g., "10MHz".
            "count": 50, #count (int): Number of frequency points.
=======
            'mode': 'sweep', #measurement_mode (str): Whether to perform a frequency sweep (usage of the start, endfrequency, the count and scale option).
            "frequency_hz": [1000.0, 2000.0, 5000.0, 10000.0, 50000.0], #frequency_list (list): List of frequencies to measure.
            "start_frequency_hz": 1000.0,     #start_frequency (str): Starting frequency, e.g., "1kHz".
            "end_frequency_hz": 100000.0,    #end_frequency (str): Ending frequency, e.g., "10MHz".
            "count": 100, #count (int): Number of frequency points.
>>>>>>> Stashed changes
            "scale": 'log', #scale (str): Scale type, "log" or "linear".
            "precision": 2.0, #precision (float): Measurement precision.
            "amplitude": 0.25, #amplitude (float): Signal amplitude.
            "excitation_type": 1, #excitation_type (int): Type of excitation, "voltage" or "current". 
            "point_delay_us": 0, #Punkt-Verzögerung zwischen Messpunkten in Mikrosekunden (EOP 0x01, uint32)
            "phase_sync": 0, # Phasensynchrones Umschalten (EOP 0x02): 0 = Inaktiv, 1 = Aktiv
            "DC_bias_enabled": 0, # DC-Bias (EOP 0x03): 0 = Inaktiv, 1 = Aktiv
            "bias_voltage": 0.0, # Bias-Spannung in Volt (float, Bereich: -1.0 V bis +1.0 V)
            "spectra": 1, #number (int) of measurement repetitions in the measurement loop
            "sync_time_us": 0, #Zeit zwischen zwei Spektrenmessungen in Mikrosekunden (uint32)
            "time_of_continuous_measurement": 30 #time of continuous measurement in seconds, if spectra = 0 (continuous measurement)
        }

        return test_settings

    
    
    def generate_measurement_queue(self):
        #generates a queue of measurement setups (self.measurement_setup_queue) to be executed in the measurement loop

        self.settings = self.get_test_settings()
        #self.settings = self.get_settings_from_config()

        
        #Frequenzliste aufbereiten und validieren
        if self.settings["mode"] == "sweep":
            if self.settings["scale"] == "lin":
                self.settings["frequency_hz"] = np.linspace(self.settings["start_frequency_hz"], self.settings["end_frequency_hz"], self.settings["count"]).tolist()
            elif self.settings["scale"] == "log":
                self.settings["frequency_hz"] = np.logspace(np.log10(self.settings["start_frequency_hz"]), np.log10(self.settings["end_frequency_hz"]), self.settings["count"]).tolist()

        #bei Einzelfrequenz Liste erstellen
        #if frequency_ :


        for index, freq in enumerate(self.settings["frequency_hz"]): 
            #first setup id is 1
            setup_id = index + 1

  

            single_setup = {
                "id": setup_id,
                "timestamp_mode": self.settings["timestamp_mode"], # Zeitstempel im Datenframe aktivieren: 0 = Deaktiviert, 1 = ms-Zeitstempel (4 Byte uint32), 2 = µs-Zeitstempel (5 Byte uint56)
                "enable_current_range_output": self.settings["enable_current_range_output"], #Strommessbereich im Rückgabeframe mitsenden(0 = Deaktiviert, 1 = Aktiviert)
                "measurement_mode":self.settings["measurement_mode"], #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
                "measurement_channel":self.settings["measurement_channel"], #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
                "current_measurement_range":self.settings["current_range"], #current_measurement_range (str): Current measurement range (e.g., "10mA")
                "voltage_measurement_range":self.settings["voltage_range"], #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
                "counter_port": self.settings["counter_port"],
                "reference_port": self.settings["reference_port"],
                "working_sense_port": self.settings["working_sense_port"],
                "working_port": self.settings["working_port"],
                "frequency_sweep":self.settings["mode"], #frequency_sweep (bool): Whether to perform a frequency sweep (True/False).
                "frequency":freq, #frequency of measurment
                "start_frequency":self.settings["start_frequency_hz"],   #start_frequency (str): Starting frequency, e.g., "1kHz"
                "end_frequency":self.settings["end_frequency_hz"], #end_frequency (str): Ending frequency, e.g., "10MHz"
                "count":self.settings["count"],  #count (int): Number of frequency points
                "scale":self.settings["scale"], #scale (str): Scale type, "log" or "linear"
                "precision":self.settings["precision"], #precision (float): Measurement precision.
                "amplitude":self.settings["amplitude"], #amplitude (str): Signal amplitude.
                "excitation_type":self.settings["excitation_type"], #excitation_type (str): Type of excitation, "voltage" or "current".
                "point_delay_us": self.settings["point_delay_us"],
                "phase_sync": self.settings["phase_sync"],
                "DC_bias_enabled": self.settings["DC_bias_enabled"],
                "bias_voltage": self.settings["bias_voltage"],
                "spectra": self.settings["spectra"], #number (int) of measurement repetitions in the measurement loop
                "sync_time_us": self.settings["sync_time_us"],
                "time_of_continuous_measurement": self.settings["time_of_continuous_measurement"]

            }

            #includes setup in queue
            self.measurement_setup_queue.append(single_setup)
        return self.measurement_setup_queue


ISX3Konfig = get_config()
ISX3Konfig.get_settings_from_config()