### IMPORTS ###
from logging import config
import time
import serial
import configparser
import struct

from src.TEST_ISX3 import ISX3
import command_functions as command

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



### MAIN ###
# Verbindungsaufbau
device = ISX3()
device = serial.Serial(port="COM3", baudrate=115200, timeout=1)

# load config and upload to device
configfile = configparser.ConfigParser()
command.upload_config(device, configfile)



device.close()