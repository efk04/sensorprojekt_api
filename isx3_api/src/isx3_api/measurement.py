"""
Measurement class for:
- initializing the measurement process
- starting liveplot
- saving the measurement configuration and results to an HDF5 file
"""

#Imports
from datetime import datetime
import time
import matplotlib.pyplot as plt
import h5py
import configparser
import os
import keyboard

from .commands import ISX3
from .plot_templates import PlotTemplates
from .config_handler import ConfigBuilder, ConfigParser, select_config_file

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
        self.manual_stop = False


        self.h5_filename = '' #filename of the h5-file
        self.plot_type = ''
        self.measurement_settings = {} # dictonary for all measurements settings from user
        self.measurement_setup_queue = []  # List to hold measurement setups
        self.results = []  # List to hold measurement data
        
        
        #include other librarys
        self.device = ISX3()
        self.config_builder = ConfigBuilder()
        self.plot_templates = PlotTemplates()


        #self.ISX3_T = ISX3Transmitter() 
        #start liveplot (evtl. später noch abfragen ob liveplot gewünscht ist)
        plt.ion() #interactive mode on
        plt.rcParams['keymap.quit'] = [] # deactivates the command q for refreshing plot


    def start_measurement(self, current_setup, measurement_settings):
        #start measurment via other library
        #give back data to self.measurment_data
        number_of_spectra = current_setup["number_of_spectra"] #spectra counts the measurement repetitions
        id = current_setup["id"]

        if not self.device:
            print("Device not connected.")
            return None, None

        expected_results = number_of_spectra * 1

        #print(f"Starts the measuring for {number_of_spectra} Cycles...")

        #starts the measuring and Reads the Data
        results = self.device.start_measurement(spectra=number_of_spectra, id = id, measurement_settings = measurement_settings)
        timestamp_measurement = None

        if results is None:
            print (f"No Results for measurement Nr.{id}.")
        else:
            timestamp_measurement = time.time() #gets timestamp when results are recieved in us (microsecs)
            #print(f"Results for Measurement Nr. {id}:", results) #debug

        return results, timestamp_measurement

    def create_h5_file(self):
        #creates a new H5 file for the whole measurement campaign, and saves the data in H5 format under "measurements"
        current_date = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.filename = f"measurement_results_{current_date}.h5"
        os.makedirs("measurements", exist_ok=True)
        with h5py.File(f"measurements/{self.filename}", 'w'):
            pass
        print(f"Creates Measurement-File: {self.filename}")

        
    def safe_measurement_settings(self, config_path):
        #saves the whole config file in the h5 file before the measurement
        #structure: Configuration/<Section> (group) -> <key> = "<value>" (attribute, raw string from the ini file)
        #comments are not saved, the config can be recreated with extract_config_from_hdf()

        group_name = "Configuration"

        #read the config file without interpolation so every value is saved exactly as written
        ini = configparser.ConfigParser(interpolation=None)
        ini.optionxform = str #keep the case of the keys
        if not ini.read(config_path, encoding='utf-8'):
            raise FileNotFoundError(f"The config file '{config_path}' could not be read.")

        with h5py.File(f"measurements/{self.filename}", 'a') as f:
            #track_order keeps the order of sections and keys like in the config file
            group = f.create_group(group_name, track_order=True)
            group.attrs["source_file"] = os.path.basename(config_path)

            for section in ini.sections():
                section_group = group.create_group(section, track_order=True)
                for key, value in ini.items(section, raw=True):
                    section_group.attrs[key] = value
        return f


    def safe_measurment(self, results, current_setup, icm):
        #defines H5 filename and saves measurement settings and the measurement results in H5 format via h5py (1 group per measurement repetition)
       
        current_id = str(icm)+"."+str(current_setup["id"])
        ts = results[1]
        res = results[0]
        
        if  not res:
            raise ValueError("no results")
        
        #creates groupnames with the id -> Number of measurement
        group_name = f"Measurement_{current_id}"

        with h5py.File(f"measurements/{self.filename}", 'a') as f:

            group = f.create_group(group_name)

            #measurement results
            group.create_dataset("timestamp", data = ts)
            group.create_dataset("frequency", data = current_setup["frequency"]) #single frequency point
            group.create_dataset("frequency_id", data=res["id"]) #counts number of measurements with one frequency
            group.create_dataset("real_part", data=res["real"])
            group.create_dataset("imaginary_part", data=res["imag"])


            group.attrs["created"] = datetime.now().isoformat()

        #print(f"Measurement Nr. {id} was saved in h5 file: {self.filename}")

        return f
        


    def update_live_plot(self, results, current_setup):
        #update and scale live plot with new data
        res = results[0]

        frequency = [current_setup["frequency"]]*len(res["id"]) #spectra
        freq_id = res["id"]
        real = res["real"]
        imag = res["imag"]

        match self.plot_type:
            case "impedance_frequency":
                self.plot_templates.impedance_frequency(frequency=frequency, freq_id=res["id"], real=real, imag=imag)
            case "nyquist":
                self.plot_templates.nyquist(real=real, imag=imag)
            case _:   # "bode" und alle unbekannten Werte
                self.plot_templates.bode(frequency=frequency, real=real, imag=imag)

        plt.pause(0.1)#short break


    #Methode for main loop
    def measurement(self, config_path: str | None = None):
        # config_path: path to the config.ini file. If None, a file dialog asks for it.
        # 0 create H5 file for the entire measurement campaign, with timestamp in filename
        # 1 connect to device (only once at the beginning of the measurment)
        # 2 get api settings from config file and set plot type
        # 3 get all measurement settings out of measurment_settings_file (contains frequency list for the measurment loop)
        # 4 load measurement settings for given frequeny in device via other library
        # 5 start measurment and read measurment_data
        # 6 update and scale live plot 
        # 7 save measurment data in H5 format
        # 8 close port

        #ask the user for the config file if no path was given
        if config_path is None:
            config_path = select_config_file()
            if not config_path:
                print("No config file selected, measurement cancelled.")
                return
        print(f"Uses config file: {config_path}")
        self.config_builder = ConfigBuilder(config_path)

        #creates a new H5 file for the whole measurement campaign, and saves the data in H5 format under "measurements"
        self.create_h5_file()

        # 2
        self.plot_type = self.config_builder.parser.parse_api_settings().plot_type

        #get the measurement config as dictionary
        self.measurement_settings = self.config_builder.parser.parse_as_flat_dict(False)
        
        #connects device via USB
        serial_connection = self.device.connect_device_fs(settings = self.measurement_settings)

        #saves the whole config file as a group in the h5-file
        self.safe_measurement_settings(config_path = config_path)
        
        #load measurment settings (Options, frontend settings, Extension port settings, DC bias, SyncTime ) in device 
        self.device.set_options(settings=self.measurement_settings)


        #creats a queue of all measurement setups to be executed in the measurement loop
        measurement_setup_queue = self.config_builder.generate_measurement_queue()
        print("Press [e] to stop the measurement manually.")
        
        icm = 0 #running index for continuous measurement

        while True:
            #Measurement loop for all frequency setups in measurement_setup_queue
            temp_measurement_setup_queue = list(measurement_setup_queue)

            #check if manual stop is triggert
            if self.manual_stop == True:
                print("manual measurement stop by pressing [e]")
                break
            
            icm = icm + 1 
            while temp_measurement_setup_queue:

                #get next measurement setup from measurement_setup_queue
                current_setup = temp_measurement_setup_queue.pop(0)
                current_id = str(icm)+"."+str(current_setup["id"])
                #print(f'\n----- Starts Measurement with ID:{current_id} ---') #id, bzw anderen Zähler hinzufügen, um überblick über ausgeführte Messungen zu behalten
                #print(current_setup)
                #load frequnecy setup from measurement_setup_queue in device
                self.device.set_frequency_setup(current_setup=current_setup)

                #start measurment and collect data
                results = self.start_measurement(current_setup = current_setup, measurement_settings =  self.measurement_settings)
                #print(results)
                
                #update live plot with new data
                self.update_live_plot(results = results, current_setup=current_setup)

                #save measurment data in H5 format
                self.safe_measurment(results = results, current_setup=current_setup, icm = icm)

                if keyboard.is_pressed('e'):
                    self.manual_stop = True
                    print("manual measurement stop by pressing [q]")
                    return self.manual_stop


            #if "time_of_continuous_measurement" = 0 run only one measurement cycle
            if self.config_builder.parser.parse_api_settings().continuous_measurement == False:
                break



        print('\n----- finished all measurements -----')
        serial_connection.close()

        #after finishing measurement loop, keep the plot open for further analysis, until user closes it
        plt.ioff() #interactive mode off
        plt.show() #keep plot open until user closes it