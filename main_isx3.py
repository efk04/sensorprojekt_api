### IMPORTS ###
from logging import config
import time
import serial
import configparser
import struct

from TEST_ISX3 import ISX3
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

def main_menu():
    print("Mainmenu:")
    print("1 => Options")
    print("2 => Measuring")
    userinput = input("Please select an option: ")
    return userinput

def options_menu():
    options = get_full_options()
    print("Options:")
    print("1 => Time stamp: ", options[0])
    print("2 => Frequency range: ", options[1:5], "Hz - ", options[5:9], "Hz")
    print("3 => Current range: ", options[1:5], "Hz - ", options[5:9], "Hz")

    userinput = input("Please select an option: ")
    return userinput

def print_timestamp_menu():
    print("Time stamp options:")
    print("0 => disabled")
    print("1 => ms")
    print("2 => us")

def print_frequency_menu():
    print("Frequency range options:")
    print("1 => Change minimum frequency")
    print("2 => Change maximum frequency")

def config_to_bytearray(config_value: list[float]) -> bytearray:
    if len(config_value) == 1:
        value = config_value[0]
        packed_bytes = struct.pack('<f', value)
        return bytearray(packed_bytes)
    if len(config_value) == 2:
        min_f, max_f = config_value
        packed_bytes = struct.pack('<ff', min_f, max_f)
        return bytearray(packed_bytes)
    else:
        raise ValueError("Config value must contain either one or two floating-point values")

def upload_config():
    # load config file
    config = configparser.ConfigParser()
    config.read('config.ini')

    # load values from config file
    time_stamp = config_to_bytearray(eval(config['Options']['time_stamp']))
    frequency_range = config_to_bytearray(eval(config['Options']['frequency_range']))
    current_range = config_to_bytearray(eval(config['Options']['current_range']))

    """
    print("Uploading configuration to device...")
    print("OPTIONS:")
    print("Time stamp: ", bytearray([int(time_stamp, 16)]))
    print("Frequency range: ", frequency_range[0:4], " ", frequency_range[4:8])
    print("Current range: ", bytearray([int(current_range, 16)]))
    """
    # Upload
    device.write(command.set_option(0x01, int(time_stamp, 16)))
    device.write(command.set_option(0x03, frequency_range))
    device.write(command.set_option(0x04, int(current_range, 16)))



### MAIN ###


# Verbindungsaufbau
device = ISX3()
device = serial.Serial(port="COM3", baudrate=115200, timeout=1)

upload_config()



#device.close()


#get_ethernet_config()
'''
device.set_fs_settings(
    4, #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
   "bnc port" , #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
   'autoranging' , #current_measurement_range (str): Current measurement range (e.g., "10mA")
   '1V' , #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
)


#add single frequency

device.set_setup_single_frequency_point(
    1000.0,  #frequency (float or str): Frequency point for single frequency measurement
    1.0, #precision (float): Measurement precision
    0.25, #amplitude (str or float): Signal amplitude
    'voltage' #excitation_type (str): Type of excitation, "voltage" or "current"
)
#Wir können nur eine Einzelfrequenz oder eine Frequenzliste (min-max, n-steps, scale) in das setup laden 
#z.B eine zweite Einzelfrequenz in das Setup hinzuzufügen ist nicht möglich
#genauso werden mehrere Frequenzlisten genauso zusammengefasst

device.set_setup_single_frequency_point(
    100.0,  #frequency (float or str): Frequency point for single frequency measurement
    1.0, #precision (float): Measurement precision
    0.25, #amplitude (str or float): Signal amplitude
    'voltage' #excitation_type (str): Type of excitation, "voltage" or "current"
)

device.start_measurement(spectra=10)


#device.write(command.get_options(0x04))     # defekt
#result = read_answer(device)
#print(result)


"""
while True:
    userinput = main_menu()
    match userinput:
        case "1":
            userinput = options_menu()
"""
            
#device.write_command_string(command.set_option(0x01, 0x01))
'''