from TEST_ISX3 import ISX3
import time

#Verbindungsaufbau
device = ISX3()
device.connect_device_fs("COM3")

#Testbefehl
#get_device_id = bytearray([0xD1, 00, 0xD1])
#device.write_command_string(get_device_id)

def command_save_settings():
    return bytearray([0x90, 0x00, 0x90])

def command_set_option(OB,CD):
    length = 0x02
    return bytearray([0x97, length, OB, CD, 0x97])

#get_fs_settings = bytearray([0xB0,0x03, 0x01, 0x01, 0x00, 0xB0])
device.write_command_string(command_set_option(0x01, 0x01))



#get ethernet configuration
"""
get_IP_adress = bytearray ([0xBE,0x01,0x01,0xBE])
get_MAC_adress = bytearray ([0xBE,0x01,0x02,0xBE])

print( "IP-Adresse: ")
device.write_command_string(get_IP_adress)
print("MAC-Adresse: ")
device.write_command_string(get_MAC_adress)

device.get_ip_address()
"""