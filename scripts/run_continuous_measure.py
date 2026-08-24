###Main_kontinuierlich_Messen###
### IMPORTS ###
from logging import config
import time
import serial
import configparser
import struct
from datetime import datetime
import time
from src.TEST_ISX3 import ISX3
import command_functions as command
from evaluation.Auswertung_Messung import H5LiveEvaluator



###Main###
def continuent_measurment(frequncy_list, h5_filename):
    """
    startet kontinuierliche Schleife zum Messen mehrerer Frequenzen

    """

    for frequency in frequency_list:

        device.set_fs_settings(
            4, #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
            "bnc port" , #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
            'autoranging' , #current_measurement_range (str): Current measurement range (e.g., "10mA")
            '1V' , #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
            )
        
        device.set_setup_single_frequency_point(
            frequency,  #frequency (float or str): Frequency point for single frequency measurement
            1.0, #precision (float): Measurement precision
            0.25, #amplitude (str or float): Signal amplitude
            'voltage' #excitation_type (str): Type of excitation, "voltage" or "current"
        )
        evaluator = H5LiveEvaluator(directory=".")
        device.start_measurement(spectra=1, h5_filename=h5_filename)
        evaluator.update()


        time.sleep(1)  # Wartezeit zwischen den Messungen, um sicherzustellen, dass die Messung abgeschlossen ist 
        
# Verbindungsaufbau
device = ISX3()
#device = serial.Serial(port="COM3", baudrate=115200, timeout=1)
device.connect_device_fs("COM3")



# Diese Datei wird für die gesamte Messkampagne GENUTZT
current_date = datetime.now().strftime("%Y%m%d-%H%M%S")
h5_filename = f"measurement_results_{current_date}.h5"
print(f"[INFO] Erstelle zentrale Messdatei: {h5_filename}")

#Auswertufunktion initialisieren
evaluator = H5LiveEvaluator(directory=".")

frequency_list = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0, 1000.0]
continuent_measurment(frequency_list, h5_filename=h5_filename)
