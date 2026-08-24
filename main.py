### IMPORTS ###
from html import parser
from logging import config
import time
import serial
import configparser
import struct

from src.TEST_ISX3 import ISX3
import src.command_functions as command

import config.config_transmitter as config_transmitter
import config.config_handler as config_handler

### FUNCTIONS ###

def convert_timestamp_option(option):
    match option:
        case 0x00:
            return("disabled")
        case 0x01:
            return("ms")
        case 0x02:
            return("us")

def get_ethernet_config():
    get_IP_adress = bytearray ([0xBE,0x01,0x01,0xBE])
    get_MAC_adress = bytearray ([0xBE,0x01,0x02,0xBE])
    print( "IP-Adresse: ")
    device.write_command_string(get_IP_adress)
    print("MAC-Adresse: ")
    device.write_command_string(get_MAC_adress)

def get_full_options():
    result = [0xFF,     0xFF,0xFF,0xFF,0xFF,    0xFF,0xFF,0xFF,0xFF]        #[time stamp option, MinF, MaxF]
    
    device.write(command.get_options(0x01))                                 # Time stamp option
    answer = read_answer()
    result[0] = answer[3]

    device.write(command.get_options(0x03))                                 # Frequency range options
    answer = read_answer()
    result[1:5] = answer[3:7]
    result[5:9] = answer[7:11]
    
    device.write(command.get_options(0x04))     # defekt
    result[3] = read_answer()[3]
    print(read_answer())
    return result

def connect_to_device():
    """Verbindungsaufbau zum ISX3-Gerät über die in der Config angegebene Schnittstelle."""
    parser = config_handler.ISX3ConfigParser('config/config.ini') # config laden
    config = parser.parse()

    com_port = config.connection.port # com_port und baudrate aus config lesen
    baud = config.connection.baudrate

    print(f"Verbinde zu {com_port} mit {baud} Baud...")
    
    try:
        # Pyserial Instanz öffnen (OHNE 'with', damit der Port offen bleibt)
        ser = serial.Serial(port=com_port, baudrate=baud, timeout=2.0)
        
        # Transmitter initialisieren
        transmitter = config_transmitter.ISX3Transmitter(ser)
        
        # Gebe Config, Serial-Objekt und Transmitter zurück
        return config, ser, transmitter

    except serial.SerialException as e:
        print(f"Serieller Fehler: Konnte Port {com_port} nicht öffnen. ({e})")
        return None, None, None
    except Exception as e:
        print(f"Fehler bei der Kommunikation: {e}")
        return None, None, None



### MAIN ###
cfg, ser, transmitter = connect_to_device()

# Prüfen, ob die Verbindung erfolgreich war
if cfg and ser and transmitter:
    try:
        transmitter.apply_config(cfg) # config übertragen
        for i in range(1):
            transmitter.start_measurement(cfg.measurement.number_of_spectra)
            data = command.read_answer(ser)
            print(data)

    finally:
        # Sicherstellen, dass der Port am Ende wieder geschlossen wird
        print("Schließe Verbindung...")
        ser.close()