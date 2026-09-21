"""
user-input class for:
- getting the user config for the measurement settings
- preparing the measurement settings in a measurement settings queue
"""

#Imports
import numpy as np

class get_config:


    def __init__(self):
        self.measurement_setup_queue = []  #list of dictionarys to hold measurement setups
        self.raw_settings = {} # empty dictionary to hold raw measurement settings from user

    def get_all_measurement_settings_from_user(self):
        #gets raw measurement settings from user

        #Standard measurement parameters for code testing
        test_settings = {
            "interface_type": 'COM' , #COM -> (Seriell/USB) or TCP -> (Ethernet) (Ethernet connection is not implemented yet)
            "port": 'COM4', #COM-Port for USB connection ("COM3" on Windows or "/dev/ttyUSB0" on Linux) or IP address for TCP connection
            "baudrate": 9600, #e.g. 9600, 115200, etc. (must match the device's settings)
            "timestamp_mode": 1, # Zeitstempel im Datenframe aktivieren: 0 = Deaktiviert, 1 = ms-Zeitstempel (4 Byte uint32), 2 = µs-Zeitstempel (5 Byte uint56)
            "enable_current_range_output": 1, #Strommessbereich im Rückgabeframe mitsenden(0 = Deaktiviert, 1 = Aktiviert)
            "measurement_mode": 2, #measurement_mode (int): Measurement mode  1 = 2-Punkt-Messung (0x01), 2 = 4-Punkt-Messung (0x02), 3 = 3-Punkt-Messung (0x03)
            "measurement_channel": 1, #measurement_channel (int): Measurement channel to use: 1 = BNC Port / Port 1 (0x01), 2 = Extension Port (0x02), 3 = Extension Port 2 / Port 2 (0x03)
            "current_measurement_range": 0, #current_measurement_range (int): 0 = Autoranging (0x00), 1 = ±10 mA (0x01), 2 = ±100 µA (0x02), 4 = ±1 µA (0x04), 6 = ±10 nA (0x06)
            "voltage_measurement_range": 1, #voltage_measurement_range (int): 0 = Autoranging (0x00), 1 = ±1 V (0x01, Standard), 2 = ±0.09 V (0x02)
            "counter_port": 0, #Extension Port Kanal-Auswahl (Befehl 0xB2 / 0xB3)
            "reference_port": 0, # Werte hängen vom angeschlossenen Modul ab (z. B. MuxModule)
            "working_sense_port": 0,
            "working_port": 0,   
            "frequency_sweep": True, #frequency_sweep (bool): Whether to perform a frequency sweep (usage of the start, endfrequency, the count and scale option).
            "frequency_list": [1000.0, 2000.0, 5000.0, 10000.0, 50000.0], #frequency_list (list): List of frequencies to measure.
            "start_frequency": 1000.0,     #start_frequency (str): Starting frequency, e.g., "1kHz".
            "end_frequency": 100000.0,    #end_frequency (str): Ending frequency, e.g., "10MHz".
            "count": 50, #count (int): Number of frequency points.
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

        self.raw_settings = self.get_all_measurement_settings_from_user()

        #Frequenzliste aufbereiten und validieren
        if self.raw_settings["frequency_sweep"]:
            if self.raw_settings["scale"] == "lin":
                self.raw_settings["frequency_list"] = np.linspace(self.raw_settings["start_frequency"], self.raw_settings["end_frequency"], self.raw_settings["count"]).tolist()
            elif self.raw_settings["scale"] == "log":
                self.raw_settings["frequency_list"] = np.logspace(np.log10(self.raw_settings["start_frequency"]), np.log10(self.raw_settings["end_frequency"]), self.raw_settings["count"]).tolist()

 

        for index, freq in enumerate(self.raw_settings["frequency_list"]): 
            #first setup id is 1
            setup_id = index + 1

  

            single_setup = {
                "id": setup_id,
                "timestamp_mode": self.raw_settings["timestamp_mode"], # Zeitstempel im Datenframe aktivieren: 0 = Deaktiviert, 1 = ms-Zeitstempel (4 Byte uint32), 2 = µs-Zeitstempel (5 Byte uint56)
                "enable_current_range_output": self.raw_settings["enable_current_range_output"], #Strommessbereich im Rückgabeframe mitsenden(0 = Deaktiviert, 1 = Aktiviert)
                "measurement_mode":self.raw_settings["measurement_mode"], #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
                "measurement_channel":self.raw_settings["measurement_channel"], #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
                "current_measurement_range":self.raw_settings["current_measurement_range"], #current_measurement_range (str): Current measurement range (e.g., "10mA")
                "voltage_measurement_range":self.raw_settings["voltage_measurement_range"], #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
                "counter_port": self.raw_settings["counter_port"],
                "reference_port": self.raw_settings["reference_port"],
                "working_sense_port": self.raw_settings["working_sense_port"],
                "working_port": self.raw_settings["working_port"],
                "frequency_sweep":self.raw_settings["frequency_sweep"], #frequency_sweep (bool): Whether to perform a frequency sweep (True/False).
                "frequency":freq, #frequency of measurment
                "start_frequency":self.raw_settings["start_frequency"],   #start_frequency (str): Starting frequency, e.g., "1kHz"
                "end_frequency":self.raw_settings["end_frequency"], #end_frequency (str): Ending frequency, e.g., "10MHz"
                "count":self.raw_settings["count"],  #count (int): Number of frequency points
                "scale":self.raw_settings["scale"], #scale (str): Scale type, "log" or "linear"
                "precision":self.raw_settings["precision"], #precision (float): Measurement precision.
                "amplitude":self.raw_settings["amplitude"], #amplitude (str): Signal amplitude.
                "excitation_type":self.raw_settings["excitation_type"], #excitation_type (str): Type of excitation, "voltage" or "current".
                "point_delay_us": self.raw_settings["point_delay_us"],
                "phase_sync": self.raw_settings["phase_sync"],
                "DC_bias_enabled": self.raw_settings["DC_bias_enabled"],
                "bias_voltage": self.raw_settings["bias_voltage"],
                "spectra": self.raw_settings["spectra"], #number (int) of measurement repetitions in the measurement loop
                "sync_time_us": self.raw_settings["sync_time_us"],
                "time_of_continuous_measurement": self.raw_settings["time_of_continuous_measurement"]

            }

            #includes setup in queue
            self.measurement_setup_queue.append(single_setup)
        return self.measurement_setup_queue