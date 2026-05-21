"""
Filename: command_functions.py
Author: Fedor Keil
Date: 2026-05-21
Version: 0.1
Description: Implemantierung der Commands zur Ansteuerung des ISX3-Gerät.
"""

def save_settings():
    return bytearray([0x90, 0x00, 0x90])

def set_option(ob,cd):
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