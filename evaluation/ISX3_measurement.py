"""
Measurement class for:
- initializing the measurement process
- starting liveplot
- saving the measurement configuration and results to an HDF5 file
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
main_folder = os.path.abspath(os.path.join(current_folder, "..")) 

if main_folder not in sys.path:
    sys.path.append(main_folder)

from src.Commands_ISX3 import ISX3 
from src.Plot_templates import plot_templates
from src.get_config import GetConfig

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
        
        
        #include other librarys
        self.device = ISX3()
        self.config = GetConfig()
        self.plttemp = plot_templates()


        #self.ISX3_T = ISX3Transmitter() 
        #start liveplot (evtl. später noch abfragen ob liveplot gewünscht ist)
        plt.ion() #interactive mode on
    


    def start_measurement(self, current_setup, measurement_settings):
        #start measurment via other library
        #give back data to self.measurment_data
        number_of_spectra = current_setup["number_of_spectra"] #spectra counts the measurement repetitions
        id = current_setup["id"]

        if not self.device:
            print("Device not connected.")
            return []

        expected_results = number_of_spectra * 1

        print(f"Starts the measuring for {number_of_spectra} Cycles...")

        #starts the measuring and Reads the Data
        results = self.device.start_measurement(spectra=number_of_spectra, id = id, measurement_settings = measurement_settings)

        if results is None:
            print (f"No Results for measurement Nr.{id}.")
        else:
            timestamp_measurement = time.time() #gets timestamp when results are recieved in us (microsecs)
            print(f"Results for Measurement Nr. {id}:", results) #debug

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
        
        with h5py.File(f"measurements/{self.filename}", 'a') as f:
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

        frequency = [current_setup["frequency"]]*len(res["id"]) #spectra
        freq_id = res["id"]
        real = res["real"]
        imag = res["imag"]

        #plots the impedance_frequency plot
        #only one plot can be shown in the liveplot! ->Auswahlfunktion für plotformat erstellen?
        #self.plttemp.impedance_frequency_plot( frequency = frequency, freq_id =freq_id,real = real,imag = imag)
        #self.plttemp.nyquist_plot(real = real, imag = imag) 
        self.plttemp.bode_plot(frequency = frequency,real = real,imag = imag)
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
        self.measurements_settings = self.config.get_settings_from_config()
        
        #connects device via USB
        self.device.connect_device_fs(settings = self.measurements_settings) 

        #saves the measurement settings as a group in the h5-file
        self.safe_measurement_settings(settings = self.measurements_settings)
        
        #load measurment settings (Options, frontend settings, Extension port settings, DC bias, SyncTime ) in device 
        self.device.set_options(settings=self.measurements_settings)


        #creats a queue of all measurement setups to be executed in the measurement loop
        measurement_setup_queue = self.config.generate_measurement_queue()
        measurement_start = time.time()
        
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

            #if "time_of_continuous_measurement" > 0 run continuous measurement cycles
            if self.measurement_settings["time_of_continuous_measurement"] > 0 and (time.time() - measurement_start) >= self.measurement_settings["time_of_continuous_measurement"]:
                break



        print('\n----- finished all measurements -----')

        #after finishing measurement loop, keep the plot open for further analysis, until user closes it
        plt.ioff() #interactive mode off
        plt.show() #keep plot open until user closes it



Measurement = Measurement()
Measurement.measurement()