"""
ISX3_measurements.py contains the classes for: 
- preparing the measurement config for the measurement process
- setting up plot-templates used for live-plotting and the plotting of saved results
- starting measurement process including the liveplot and saving the results
"""
#Imports
from datetime import datetime
from pathlib import Path
import time
import matplotlib.pyplot as plt
import h5py
import numpy as np
import pandas as pd
import json
import sys
import os
import serial

#import Classes
#helper function to find the classes under the /src path
current_folder = os.path.dirname(os.path.abspath(__file__))
main_folder = os.path.abspath(os.path.join(current_folder, "..")) # Anpassen, falls dein Skript noch tiefer liegt

if main_folder not in sys.path:
    sys.path.append(main_folder)

from src.Commands_ISX3 import ISX3 # Importiere die Klasse ISX3 aus Commands_ISX3.py
import src.test_check_User_Input as check_user_input
from config.config_transmitter import ISX3Transmitter 

class user_input:
    """
    user-input class for:
    - getting the user config for the measurement settings
    - preparing the measurement settings in a measurement settings queue
    """

    def __init__(self):
        self.measurement_setup_queue = []  #list of dictionarys to hold measurement setups
        self.raw_settings = {} # empty dictionary to hold raw measurement settings from user

    def get_all_measurement_settings_from_user(self):
        #gets raw measurement settings from user

        #Standard measurement parameters for code testing
        test_settings = {
            "interface_type": 'COM' , #COM -> (Seriell/USB) or TCP -> (Ethernet) (Ethernet connection is not implemented yet)
            "port": 'COM3', #COM-Port for USB connection ("COM3" on Windows or "/dev/ttyUSB0" on Linux) or IP address for TCP connection
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
            "frequency_sweep": False, #frequency_sweep (bool): Whether to perform a frequency sweep (usage of the start, endfrequency, the count and scale option).
            "frequency_list": [1000.0, 2000.0, 5000.0, 10000.0, 50000.0], #frequency_list (list): List of frequencies to measure.
            "start_frequency": 1000.0,     #start_frequency (str): Starting frequency, e.g., "1kHz".
            "end_frequency": 50000.0,    #end_frequency (str): Ending frequency, e.g., "10MHz".
            "count": 21, #count (int): Number of frequency points.
            "scale": 'log', #scale (str): Scale type, "log" or "linear".
            "precision": 1.0, #precision (float): Measurement precision.
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
            if len(check_user_input.check_frequency_range(self.raw_settings["start_frequency"], self.raw_settings["end_frequency"])) == 2:
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
    

class plot_template:

    """
    plot_template class for:
    - create a template for diffrent plot types (impedance-freq, nyquist, bode) 
      wich is used in the live-plot or in to plot saved h5-file results
    """

    def __init__(self):
        #self.fig = plt.figure(figsize=(10,5))
        self.fig = None
        self.ax1 = None
        self.ax2 = None
        self.line_mag = None
        self.line_phase = None

    """
    def impedance_frequency_plot(self, frequency, freq_id, real, imag):
        #creates a plot that shows the impedance in realation to the frequency
        self.fig
        plt.plot(frequency, real, 'ro',color='g') #red circles for real values
        plt.plot(frequency, imag, 'bs',color='g') #blue squres for imag values

        plt.show()
    """
    def impedance_frequency_plot(self, frequency, freq_id, real, imag):
        #get data
        line_real, = plt.plot(frequency, real, 'ro', color='g', label='Real part')
        line_imag, = plt.plot(frequency, imag, 'bs', color='b', label='Imaginary part')
        #decorate plot
        plt.xscale('log')                      # Logarithmische X-Achse (Standard in der Elektrotechnik/Spektroskopie)
        plt.xlabel('Frequency $f$ / Hz')        # Achsenbeschriftung X mit LaTeX-Formatierung
        plt.ylabel('Impedance $Z$ / $\\Omega$')  # Achsenbeschriftung Y
        plt.title('Impedance as a Function of Frequency')  # Diagrammtitel
        plt.grid(True, which="both", ls="--", alpha=0.3)
        plt.tick_params(direction='in', which='both', top=True, right=True)
        plt.legend(
            handles=[line_real, line_imag],
            labels=[r'$Z_{real}$', r'$Z_{imag}$'],
            loc='center left',     bbox_to_anchor=(1.02, 0.5),  # Positioniert rechts vom Plot
            title='Legend',
            frameon=True
        )
        #move plot to the right to show the legend
        plt.subplots_adjust(right=0.8)

        
        plt.show()
       
    
    def nyquist_plot(self, real, imag):
            # Nyquist-Plot: Z_imag vs Z_real 
            line_nyquist, = plt.plot(real, imag, 'ro', color='b', label='Nyquist data')
            
            # Wissenschaftliches Styling
            plt.xlabel('Real part $Z_{real}$ / $\\Omega$')
            plt.ylabel('Imaginary part $Z_{imag}$ / $\\Omega$')
            plt.title('Nyquist Plot')
            #
            plt.axhline(0, color='black', linewidth=0.8, linestyle='-')
            plt.axvline(0, color='black', linewidth=0.8, linestyle='-')
            max_val = max(max(abs(r) for r in real), max(abs(i) for i in imag)) * 1.15
            # Wichtig beim Nyquist-Plot: Gleiches Seitenverhältnis (Equal Aspect Ratio), 
            # damit Kreise/Halbkreise nicht verzerrt werden!
            plt.gca().set_aspect('equal', adjustable='box')
            
            plt.grid(True, which="both", ls="--", alpha=0.3)
            plt.tick_params(direction='in', which='both', top=True, right=True)
            
            plt.legend(
                handles=[line_nyquist],
                labels=[r'$Z_{imag}$ vs $Z_{real}$'],
                loc='center left',    
                bbox_to_anchor=(1.02, 0.5),  
                title='Legend',
                frameon=True
            )
            
            plt.subplots_adjust(right=0.8)
            plt.show()

    def bode_plot(self):
        pass


class Measurement:
    """
    Measurement class for:
    - initializing the measurement process
    - starting liveplot
    - saving the measurement configuration and results to an HDF5 file
    """

    def __init__(self):
        
                   # Initializes an ISX3 device handler.
        
        self.serial_protocol = None
        self.device = None
        self.frequency_points = 0
        self.ret_hex_int = None
        self.print_msg = True
        self.tcp_protocol = None
        self.frequencies = []


        self.h5_filename = '' #filename of the h5-file
        self.measurements_settings = {} # dictonary for all measurements settings from user
        self.measurement_setup_queue = []  # List to hold measurement setups
        self.results = []  # List to hold measurement data
        
        
        #include other librarys
        self.device = ISX3()
        self.input = user_input()
        self.plttemp = plot_template()

        #self.measurements_settings = self.input.get_all_measurement_settings_from_user()

        #self.ISX3_T = ISX3Transmitter() 
        #start liveplot (evtl. später noch abfragen ob liveplot gewünscht ist)
        plt.ion() #interactive mode on
    


    def start_measurement(self, current_setup, measurement_settings):
        #start measurment via other library
        #give back data to self.measurment_data
        spectra = current_setup["spectra"] #spectra counts the measurement repetitions
        id = current_setup["id"]
        tcm = current_setup["time_of_continuous_measurement"] #time of continuous measurement in seconds, if spectra = 0 (continuous measurement)
        self.measurement_settings = measurement_settings

        if not self.device:
            print("Device not connected.")
            return []

        expected_results = spectra * 1

        print(f"Starts the measuring for {spectra} Cycles...")

        #starts the measuring and Reads the Data
        results = self.device.start_measurement(spectra=spectra, id = id, time_of_continuous_measurement=tcm, measurement_settings = self.measurement_settings) #time_of_continuous_measurement in seconds, if spectra = 0 (continuous measurement)

        if results is None:
            print (f"No Results for measurement Nr.{id}.")
        else:
            timestamp_measurement = time.time() #gets timestamp when results are recieved in us (microsecs)
            print(f"Results for Measurement Nr. {id}:", results)

        return results, timestamp_measurement

    def create_h5_file(self):
        #creates a new H5 file for the whole measurement campaign, and saves the data in H5 format under "measurements"
        current_date = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.filename = f"measurement_results_{current_date}.h5"
        h5_file = h5py.File(f"measurements/{self.filename}", 'w')
        print(f"Creates Measurement-File: {self.filename}")

        
    def safe_measurement_settings(self, settings):
        #saves the general sttings for the measurement before the measurement

        group_name = "1-Measurement_Settings"

        #gets measurements_settings dictionary from user and writes it as a string in a h5 file
        measurement_settings = settings
        measurement_settings_json = json.dumps(measurement_settings)
        
        with h5py.File(self.filename,'a') as f:
            group = f.create_group(group_name)

            #measurement settings
            group.create_dataset("measurement_settings", data=[measurement_settings_json])#saves measurement settings
        return f


    def safe_measurment(self, results, current_setup):
        #defines H5 filename and saves measurement settings and the measurement results in H5 format via h5py (1 group per measurement repetition)
       
        id = current_setup["id"]
        ts = results[1]
        res = results[0]
        
        if  not res:
            raise ValueError("no results")
        
        #creates groupnames with the id -> Number of measurement
        group_name = f"Measurement_{id}"

        with h5py.File(f"measurements/{self.filename}", 'a') as f:

            group = f.create_group(group_name)

            #measurement results
            group.create_dataset("timestamp", data = ts)
            group.create_dataset("frequency", data = current_setup["frequency"]) #single frequency point
            group.create_dataset("frequency_id", data=res["id"]) #counts number of measurements with one frequency
            group.create_dataset("real_part", data=res["real"])
            group.create_dataset("imaginary_part", data=res["imag"])


            group.attrs["created"] = datetime.now().isoformat()

        print(f"Measurement Nr. {id} was saved in h5 file: {self.filename}")

        return f
        


    def update_live_plot(self, results, current_setup):
        #update and scale live plot with new data

        res = results[0]

        frequency = current_setup["frequency"]
        freq_id = res["id"]
        real = res["real"]
        imag = res["imag"]

        #plots the impedance_frequency plot
        #only one plot can be shown in the liveplot! ->Auswahlfunktion für plotformat erstellen?
        self.plttemp.impedance_frequency_plot( frequency = frequency, freq_id =freq_id,real = real,imag = imag)
        #self.plttemp.nyquist_plot(real = real, imag = imag) 
        #self.plttemp.bode_plot(frequency = frequency,real = real,imag = imag)
        plt.pause(0.1)#short break

    #Methode for main loop
    def measurement(self):
        #0. create H5 file for the entire measurement campaign, with timestamp in filename
        #1. connect to device (only once at the beginning of the measurment)
        #2. get all measurement settings out of measurment_settings_file (contains frequency list for the measurment loop)
        #2.1 load measurement settings for given frequeny in device via other library
        #3. start measurment and read measurment_data
        #4. update and scale live plot 
        #5. save measurment data in H5 format


        

        #creates a new H5 file for the whole measurement campaign, and saves the data in H5 format under "measurements"
        current_date = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.filename = f"measurement_results_{current_date}.h5"
        h5_file = h5py.File(f"measurements/{self.filename}", 'w')
        print(f"Creates Measurement-File: {self.filename}")

        #get the measurement config as dictionary
        self.measurements_settings = self.input.get_all_measurement_settings_from_user()
        
        #connects device via USB
        self.device.connect_device_fs(settings = self.measurements_settings) 

        #saves the measurement settings as a group in the h5-file
        self.safe_measurement_settings(settings = self.measurements_settings)
        
        #load measurment settings (Options, frontend settings, Extension port settings, DC bias, SyncTime ) in device 
        self.device.set_options_and_fe_settings(settings=self.measurements_settings)


        #creats a queue of all measurement setups to be executed in the measurement loop
        measurement_setup_queue = self.input.generate_measurement_queue()
       
        
        #Measurement loop for all frequency setups in measurement_setup_queue
        while measurement_setup_queue:
            #get next measurement setup from measurement_setup_queue
            current_setup = measurement_setup_queue.pop(0)
            print(f'\n----- Starts Measurement with ID: {current_setup["id"]} ---') #id, bzw anderen Zähler hinzufügen, um überblick über ausgeführte Messungen zu behalten
            print(current_setup)
            #load frequnecy setup from measurement_setup_queue in device
            self.device.set_frequency_setup(current_setup=current_setup)

            #start measurment and collect data
            results = self.start_measurement(current_setup = current_setup, measurement_settings =  self.measurements_settings)
            print(results)
     
            #update live plot with new data
            self.update_live_plot(results = results, current_setup=current_setup)

            #save measurment data in H5 format
            self.safe_measurment(results = results, current_setup=current_setup)

            

        print('\n----- finished all measurements -----')

        #after finishing measurement loop, keep the plot open for further analysis, until user closes it
        plt.ioff() #interactive mode off
        plt.show() #keep plot open until user closes it


def test_ISX3_measurment():
    input = user_input()    
    #input.generate_measurement_queue()

    queue = input.generate_measurement_queue()
    print(queue)

    Measurement = Measurement()
    #starts measurement, live plot and save data in H5 format
    Measurement.measurement()

#read measurmenet auf ausgabe anpasssen