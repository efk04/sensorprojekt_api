### IMPORTS ###
from logging import config
import time
import serial
import configparser
import struct

from src.TEST_ISX3 import ISX3
import command_functions as command

def create_config():
    config = configparser.ConfigParser()
    # Add sections and key-value pairs
    config['Options'] = {
        'time_stamp': 0,            # 0 = disabled, 1 = ms, 2 = us
        'frequency_range': [0,10],  # [MinF, MaxF] in Hz
        'current_range': 0          # 0 = disabled, 1 = ms
    }
    config['Frontend Settings'] = {
    
    }
    config['ExtensionPort Channel Settings'] = {
    
    }
    config['Ethernet Configuration'] = {
    
    }
    config['Setup'] = {
    
    }
    # Write the configuration to a file
    with open('config.ini', 'w') as configfile:
        config.write(configfile)


device = 0
### FUNCTIONS ###
def read_answer(dev):
    timeout_count = 0
    received = []
    data_count = 0

    while True:
        buffer = dev.read()
        if buffer:
            received.extend(buffer)
            data_count += len(buffer)
            timeout_count = 0
            continue
        timeout_count += 1
        if timeout_count >= 1:
            # Break if we haven't received any data
            break
    received_hex = [hex(receive) for receive in received]        
    return received_hex
    #return bytearray(int(h, 16) for h in received_hex)

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

"""
configfile = configparser.ConfigParser()
upload_config()
device.write(command.get_options(0x04))
result = 0
result = read_answer(device)
print("Time stamp option:", result)
"""
configfile = configparser.ConfigParser()
command.download_config(device, configfile)



#device.close()