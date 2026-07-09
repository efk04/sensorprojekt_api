###Main_kontinuierlich_Messen###
### IMPORTS ###
from logging import config
import time
import serial
import configparser
import struct
from datetime import datetime
import time
from TEST_ISX3 import ISX3
import command_functions as command
from Auswertung_Messung import H5LiveEvaluator



###Main###
def continuent_measurment(frequncy_list, h5_filename):
    """
    startet kontinuierliche Schleife zum Messen mehrerer Frequenzen

    """

    for frequency in frequency_list:

        frequency = float(frequency)
        print(f"Messung durchgeführt mit Frequenz: {frequency} Hz")  # Konvertiere die Frequenz in einen Float-Wert
        
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

        #Frequenz Mapping für Auswertung
        """
        ->#Wenn Get-Frequency-settings funktioniert -> hier aufrufen
        -> erstellt Mapping-Liste mit Frequenz_ID und tatsächlichem Frequenzwert
        -> tatsächlich verwendete Frequenz: 
        a) Einzelfrequenz -> Variable: single_frequency_point (float or str): Frequency point for single frequency measurement.

        b) Frequenz_Sweep -> Variablen: start_frequency (str): Starting frequency, e.g., "1kHz".
                                        end_frequency (str): Ending frequency, e.g., "10MHz".
                                        count (int): Number of frequency points.
                                        scale (str): Scale type, "log" or "linear"


        """
        frequncy_map = []

        evaluator = H5LiveEvaluator(directory=".")
        device.start_measurement(spectra=1, h5_filename=h5_filename)
        evaluator.update()
        

        time.sleep(1)  # Wartezeit zwischen den Messungen, um sicherzustellen, dass die Messung abgeschlossen ist 
    evaluator.show_plot()

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

device.set_fs_settings(
    4, #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
    "bnc port" , #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
    'autoranging' , #current_measurement_range (str): Current measurement range (e.g., "10mA")
    '1V' , #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
    )

device.set_setup_frequency_sweep(
    1000.0,     #start_frequency (str): Starting frequency, e.g., "1kHz".
    50000.0,    #end_frequency (str): Ending frequency, e.g., "10MHz".
    21, #count (int): Number of frequency points.
    'log', #scale (str): Scale type, "log" or "linear".
    1.0, #precision (float): Measurement precision.
    0.25, #amplitude (str): Signal amplitude.
    'voltage' #excitation_type (str): Type of excitation, "voltage" or "current".                   
)

evaluator = H5LiveEvaluator(directory=".")
device.start_measurement(spectra=1, h5_filename=h5_filename)
evaluator.update()
evaluator.show_plot()
frequency_list = [100.0, 200.0]
#continuent_measurment(frequency_list, h5_filename=h5_filename)

