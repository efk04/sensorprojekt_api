"""
Filename: command_functions.py
Author: Fedor Keil
Date: 2026-05-21
Version: 0.1
Description: Implemantierung der Commands zur Ansteuerung des ISX3-Gerät.
"""

from logging import config


### IO-COMMANDS ###
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

### CONFIGURATION ###
def load_value_from_config(configfile, section: str, key: str, default: list[int]) -> int:
    
    # check if config is initialized
    if configfile is None:
        raise ValueError("Config object is not initialized. Please load the config file first.")
    
    # check if section and key exist in the config and load value
    if section in configfile and key in configfile[section]:
        value = int(configfile[section][key])
    
    # check if the loaded value is in the default list
    if value not in default:
        raise ValueError(f"Invalid value for {key}. Must be one of {default}.")
    else:
        return value

def upload_config(device, configfile):
    # load config file
    configfile.read('config.ini')

    # load values from config file
    ms_time_stamp = load_value_from_config(configfile, 'Options', 'ms_time_stamp', [0, 1])
    us_time_stamp = load_value_from_config(configfile, 'Options', 'us_time_stamp', [0, 1])
    current_range = load_value_from_config(configfile, 'Options', 'current_range', [0, 1])

    print(ms_time_stamp, us_time_stamp, current_range)
   
    
    # Upload
    device.write(set_option(0x01, ms_time_stamp))
    device.write(set_option(0x02, us_time_stamp))
    device.write(set_option(0x04, current_range))

def download_config(device, configfile):

    # Download
    device.write(get_options(0x01))
    time_stamp = read_answer(device)[3]
    device.write(get_options(0x04)) # defekt
    answer = read_answer(device)
    if answer[2] == '0x82':
        print("Warning: Invalid option code for current_range.")
        answer[3] = '0x00'  # Set a default value
    current_range = answer[3]

    # save values to config file
    if time_stamp == '0x00':
        configfile['Options']['ms_time_stamp'] = str(0)
        configfile['Options']['us_time_stamp'] = str(0)
    elif time_stamp == '0x01':
        configfile['Options']['ms_time_stamp'] = str(1)
        configfile['Options']['us_time_stamp'] = str(0)
    elif time_stamp == '0x02':
        configfile['Options']['ms_time_stamp'] = str(0)
        configfile['Options']['us_time_stamp'] = str(1)
    else:
        print("Warning: Invalid time_stamp value received from device. Setting both to 0.")
        configfile['Options']['ms_time_stamp'] = str(0)
        configfile['Options']['us_time_stamp'] = str(0)
    
    if current_range == '0x00':
        configfile['Options']['current_range'] = str(0)
    elif current_range == '0x01':
        configfile['Options']['current_range'] = str(1)
    else:
        print("Warning: Invalid current_range value received from device. Setting to 0.")

    with open('config.ini', 'w') as configfile:
        config.write(configfile)



### SONSTIGE ###
def save_settings():
    return bytearray([0x90, 0x00, 0x90])

def set_option(ob:int, cd:int):
    length = 0x02
    return bytearray([0x97, length, ob, cd, 0x97])

def get_options(ob):
    length = 0x01
    return bytearray([0x98, length, ob, 0x98])

def reset_system():
    return bytearray([0xA1, 0x00, 0xA1])

def  set_fe_settings(measurement_mode, measurement_channel, current_range_settings, voltage_range_settings = None):
    length = 0x03
    if voltage_range_settings is not None:
        length = 0x04
        return bytearray([0xB0, length, measurement_mode, measurement_channel, current_range_settings, voltage_range_settings, 0xB0])
    return bytearray([0xB0, length, measurement_mode, measurement_channel, current_range_settings, 0xB0])

def get_fe_settings():
    return bytearray([0xB1, 0x00, 0xB1])

def set_extensionPort_channel(counter_port_select, reference_port_select, workingSense_port_select, work_port_select):
    length = 0x04
    return bytearray([0xB2, length, counter_port_select, reference_port_select, workingSense_port_select, work_port_select, 0xB2])

def get_extensionPort_channel():
    return bytearray([0xB3, 0x00, 0xB3])

def get_extensionPort_module():
    return bytearray([0xB5, 0x00, 0xB5])

def set_setup(length, ob, cd):
    COMMAND_CODE = 0xB6
    """
    match ob:
        case 0x01: #init
            length = 0x01
            return bytearray([COMMAND_CODE, length, 0x01, COMMAND_CODE])
        case 0x02: #Add single frequency point
            return bytearray([COMMAND_CODE, length, 0x02, cd, COMMAND_CODE])
        case 0x03: #Add frequency list
            return bytearray([COMMAND_CODE, length, 0x03, cd, COMMAND_CODE])
        case 0x05: #Set amplitude
            return bytearray([COMMAND_CODE, length, 0x05, cd, COMMAND_CODE])
    """

def start_measure():
    return bytearray([0xB8, 0x02, 0x01, 0x00, 0xB8])