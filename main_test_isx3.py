from TEST_ISX3 import ISX3
import time

#Verbindungsaufbau
device = ISX3()
device.connect_device_fs("COM3")

#device.connect_device_lan("192.168.1.22")
#Testbefehl
#get_device_id = bytearray([0xD1, 00, 0xD1])
#device.write_command_string(get_device_id)

def command_save_settings():
    return bytearray([0x90, 0x00, 0x90])

def command_set_option(ob,cd):
    length = 0x02
    return bytearray([0x97, length, ob, cd, 0x97])

def command_get_options(ob):
    length = 0x01
    return bytearray([0x98, length, ob, 0x98])

def command_reset_system():
    return bytearray([0xA1, 0x00, 0xA1])

def  command_set_fe_settings(measurement_mode, measurement_channel, current_range_settings, voltage_range_settings = None):
    length = 0x03
    if voltage_range_settings is not None:
        length = 0x04
        return bytearray([0xB0, length, measurement_mode, measurement_channel, current_range_settings, voltage_range_settings, 0xB0])
    return bytearray([0xB0, length, measurement_mode, measurement_channel, current_range_settings, 0xB0])

def command_get_fe_settings():
    return bytearray([0xB1, 0x00, 0xB1])

def command_set_extensionPort_channel(counter_port_select, reference_port_select, workingSense_port_select, work_port_select):
    length = 0x04
    return bytearray([0xB2, length, counter_port_select, reference_port_select, workingSense_port_select, work_port_select, 0xB2])

def command_get_extensionPort_channel():
    return bytearray([0xB3, 0x00, 0xB3])

def command_get_extensionPort_module():
    return bytearray([0xB5, 0x00, 0xB5])

def command_set_setup(length, ob, cd):
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

#get_fs_settings = bytearray([0xB0,0x03, 0x01, 0x01, 0x00, 0xB0])
device.write_command_string(command_set_option(0x01, 0x01))



#get ethernet configuration

get_IP_adress = bytearray ([0xBE,0x01,0x01,0xBE])
get_MAC_adress = bytearray ([0xBE,0x01,0x02,0xBE])

print( "IP-Adresse: ")
device.write_command_string(get_IP_adress)
print("MAC-Adresse: ")
device.write_command_string(get_MAC_adress)

