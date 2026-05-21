from TEST_ISX3 import ISX3
import time

#Verbindungsaufbau
device = ISX3()
device.connect_device_fs("COM3")

#Testbefehl
get_device_id = bytearray([0xD1, 00, 0xD1])
device.write_command_string(get_device_id)

#get ethernet configuration

get_IP_adress = bytearray ([0xBE,0x01,0x01,0xBE])
get_MAC_adress = bytearray ([0xBE,0x01,0x02,0xBE])

print( "IP-Adresse: ")
device.write_command_string(get_IP_adress)
print("MAC-Adresse: ")
device.write_command_string(get_MAC_adress)

device.get_ip_address()