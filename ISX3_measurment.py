#Measurment Hauptfunktion

#Imports
from datetime import datetime
import time
import matplotlib.pyplot as plt
import h5py
import numpy as np
import pandas as pd
import json

#import Classes
from src.TEST_ISX3 import ISX3
import src.test_check_User_Input as check_user_input


class user_input:
    def __init__(self):
        self.measurement_setup_queue = []  #list of dictionarys to hold measurement setups
        self.raw_settings = {} # empty dictionary to hold raw measurement settings from user

    def get_all_measurement_settings_from_user(self):
        #gets raw measurement settings from user

        #Standard measurement parameters for code testing
        test_settings = {
            "measurement_mode": 4, #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
            "measurement_channel": "bnc port", #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
            "current_measurement_range": 'autoranging', #current_measurement_range (str): Current measurement range (e.g., "10mA")
            "voltage_measurement_range": '1V', #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
            "frequency_sweep": False, #frequency_sweep (bool): Whether to perform a frequency sweep (usage of the start, endfrequency, the count and scale option).
            "frequency_list": [1000.0, 2000.0, 5000.0, 10000.0, 50000.0], #frequency_list (list): List of frequencies to measure. , 2000.0, 5000.0, 10000.0, 20000.0, 50000.0
            "start_frequency": 1000.0,     #start_frequency (str): Starting frequency, e.g., "1kHz".
            "end_frequency": 50000.0,    #end_frequency (str): Ending frequency, e.g., "10MHz".
            "count": 21, #count (int): Number of frequency points.
            "scale": 'log', #scale (str): Scale type, "log" or "linear".
            "precision": 1.0, #precision (float): Measurement precision.
            "amplitude": 0.25, #amplitude (str): Signal amplitude.
            "excitation_type": 'voltage', #excitation_type (str): Type of excitation, "voltage" or "current". 
            "spectra": 1, #number (int) of measurement repetitions in the measurement loop

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
                "measurement_mode":self.raw_settings["measurement_mode"], #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
                "measurement_channel":self.raw_settings["measurement_channel"], #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
                "current_measurement_range":self.raw_settings["current_measurement_range"], #current_measurement_range (str): Current measurement range (e.g., "10mA")
                "voltage_measurement_range":self.raw_settings["voltage_measurement_range"], #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
                "frequency_sweep":self.raw_settings["frequency_sweep"], #frequency_sweep (bool): Whether to perform a frequency sweep (True/False).
                "frequency":freq, #frequency of measurment
                "start_frequency":self.raw_settings["start_frequency"],   #start_frequency (str): Starting frequency, e.g., "1kHz"
                "end_frequency":self.raw_settings["end_frequency"], #end_frequency (str): Ending frequency, e.g., "10MHz"
                "count":self.raw_settings["count"],  #count (int): Number of frequency points
                "scale":self.raw_settings["scale"], #scale (str): Scale type, "log" or "linear"
                "precision":self.raw_settings["precision"], #precision (float): Measurement precision.
                "amplitude":self.raw_settings["amplitude"], #amplitude (str): Signal amplitude.
                "excitation_type":self.raw_settings["excitation_type"], #excitation_type (str): Type of excitation, "voltage" or "current".
                "spectra": self.raw_settings["spectra"], #number (int) of measurement repetitions in the measurement loop
               
            }

            #includes setup in queue
            self.measurement_setup_queue.append(single_setup)
        return self.measurement_setup_queue
    

input = user_input()    
#input.generate_measurement_queue()

queue = input.generate_measurement_queue()
print(queue)

"""
Nächste Schritte
1. Schleifenfunktion (Laden, messen, auswerten, speichern) über listeninhalt in queue definieren
2. Load_setup funktion -> muss einstellungen in die befehle und in 4 bit format übersetzen -> orientierung an set_single_freuency_point
    -> Gleichzeitig Messsetup in H5 gruppe der Messung speichern -> Name der Gruppe nach setup_id
3. start measurment funktion integriern
4. liveplot update funktion
5. speichern der ergebnisse in h5 
    -> Gleichzeitig Messsetup in H5 gruppe der Messung speichern -> Name der Gruppe nach setup_id
"""
class plot_template:

    def __init__(self):
        self.fig = plt.figure(figsize=(10,5))

    def impedance_frequency_plot(self, frequency, freq_id, real, imag):
        #creates a plot that shows the impedance in realation to the frequency
        self.fig
        plt.plot(frequency, real, 'ro',color='g') #red circles for real values
        plt.plot(frequency, imag, 'bs',color='g') #blue squres for imag values

        plt.show()

        
        

    
            
    
    def nyquist_plot(self):
        pass

    def bode_plot(self):
        pass


class Measurement:
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
        
        #device definieren aus device class, bzw. aus anderer library
        self.device = ISX3()
        self.input = user_input()
        self.plttemp = plot_template()

        #start liveplot (evtl. später noch abfragen ob liveplot gewünscht ist)
        plt.ion() #interactive mode on
    
    def _init_plot_template(self):
        #hier plot_template einfügen -> am besten in eine eigene Klasse auslagern
        pass


    def load_measurement_setup(self, settings):
        #load measurement setup for one frequency setup from self.measurement_setup_queue in device 
        #1. load the fs_settings from measurement_setup_queue

        self.device.set_fs_settings(
            measurement_mode=settings["measurement_mode"],
            measurement_channel=settings["measurement_channel"],
            current_measurement_range=settings["current_measurement_range"],
            voltage_measurement_range=settings["voltage_measurement_range"],
        )

    def load_freq_setup(self, current_setup):
                
        #2. load the frequency from measurement_setup_queue
        self.device.set_setup_single_frequency_point(
            frequency = current_setup["frequency"],  #frequency (float or str): Frequency point for single frequency measurement
            precision = current_setup["precision"], #precision (float): Measurement precision
            amplitude = current_setup["amplitude"], #amplitude (str or float): Signal amplitude
            excitation_type = current_setup["excitation_type"] #excitation_type (str): Type of excitation, "voltage
        )
        
    def start_measurement(self, current_setup):
        #start measurment via other library
        #give back data to self.measurment_data
        results = []
        results = self.device.start_measurement(spectra = current_setup["spectra"], id = current_setup["id"]) #spectra counts the measurement repetitions
        return results
    
    def safe_measurement_settings(self,settings):
        #saves the general sttings for the measurement before the measurement

        group_name = "1-Measurement_Settings"

        #gets measurements_settings dictionary from user and writes it as a string as a json file (in welcher form sollen die einstellungen gespeichert werden?)
        measurement_settings_json = json.dumps(settings)
        
        with h5py.File(self.filename,'a') as f:
            group = f.create_group(group_name)

            #measurement settings
            group.create_dataset("measurement_settings", data=[measurement_settings_json])#saves measurement settings
        return f


    def safe_measurment(self, results, current_setup ):
        #defines H5 filename and saves measurement settings and the measurement results in H5 format via h5py (1 group per measurement repetition)
       
        id = current_setup["id"]
    

        if  not results:
            raise ValueError("no results")
        
        #creates groupnames with the id -> Number of measurement
        group_name = f"Measurement_{id}"

        with h5py.File(self.filename, 'a') as f:

            group = f.create_group(group_name)

            #measurement results

            group.create_dataset("frequency", data = current_setup["frequency"]) #single frequency point
            group.create_dataset("frequency_id", data=[r[0] for r in results]) #counts number of measurements with one frequency
            group.create_dataset("real_part", data=[r[1] for r in results])
            group.create_dataset("imaginary_part", data=[r[2] for r in results])


            group.attrs["created"] = datetime.now().isoformat()

        print(f"Measurement Nr. {id} was saved in h5 file: {self.filename}")

        return f
        


    def update_live_plot(self, results, current_setup):
        #update and scale live plot with new data
        #1. get data from self.measurment_data
        #2. bestehende Linie mit neuen daten aktualisieren (verhindert neues Fenster)
        #3. Achsen Grenzwert dynamisch anpassen
        #4. canvas neu zeichnen, einfügen von plt.pause(0.01) um das Fenster zu aktualisieren / für GUI Ergebnisverarbeitung
     

        frequency = current_setup["frequency"]
        freq_id = [r[0] for r in results]
        real = [r[1] for r in results]
        imag = [r[2] for r in results]   

        #plots the impedance_frequency plot
        self.plttemp.impedance_frequency_plot( frequency = frequency, freq_id =freq_id,real = real,imag = imag)
            
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

        #creates a new H5 file for the whole measurement campaign, and saves the data in H5 format
        current_date = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.filename = f"measurement_results_{current_date}.h5"
        h5_file = h5py.File(self.filename, 'w')
        print(f"Creates Measurement-File: {self.filename}")

        #connects device via USB
        self.device.connect_device_fs("COM3") 

        #saves the measurement settings as a group in the h5-file
        self.measurements_settings = self.input.get_all_measurement_settings_from_user()
        self.safe_measurement_settings(settings = self.measurements_settings)
        
        #load measurment settings
        self.load_measurement_setup(settings = self.measurements_settings)

        #creats a queue of all measurement setups to be executed in the measurement loop
        measurement_setup_queue = self.input.generate_measurement_queue()
       
        
        #Measurement loop for all frequency setups in measurement_setup_queue
        while measurement_setup_queue:
            #get next measurement setup from measurement_setup_queue
            current_setup = measurement_setup_queue.pop(0)
            print(f'\n----- Starts Measurement with ID: {current_setup["id"]} ---') #id, bzw anderen Zähler hinzufügen, um überblick über ausgeführte Messungen zu behalten

            #load frequnecy setup in device
            self.load_freq_setup(current_setup=current_setup)

            #start measurment and collect data
            results = self.start_measurement(current_setup = current_setup)
            print(results)
     

            
            #update live plot with new data
            self.update_live_plot(results = results, current_setup=current_setup)

            #save measurment data in H5 format
            self.safe_measurment(results = results, current_setup=current_setup)

            

        print('\n----- finished all measurements -----')

        #after finishing measurement loop, keep the plot open for further analysis, until user closes it
        plt.ioff() #interactive mode off
        plt.show() #keep plot open until user closes it


Measurement = Measurement()
#starts measurement, live plot and save data in H5 format
Measurement.measurement()
        
