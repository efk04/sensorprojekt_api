"""
Filename: command_functions.py
Author: Fedor Keil
Date: 2026-05-21
Version: 0.1
Description: Implemantierung der Commands zur Ansteuerung des ISX3-Gerät.
"""







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