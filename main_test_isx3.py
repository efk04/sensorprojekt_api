### IMPORTS ###
import time
from unittest import case
import serial

from TEST_ISX3 import ISX3
import command_functions as command



### FUNCTIONS ###
def read_answer():
    timeout_count = 0
    received = []
    data_count = 0

    while True:
        buffer = device.read()
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

def convert_timestamp_option(option):
    print("Option: ", option)
    match option:
        case "0x0":
            return("disabled")
        case "0x01":
            return("ms")
        case "0x02":
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
    
    #device.write(command.get_options(0x04))     # defekt
    #result[3] = read_answer()[3]
    #print(read_answer())
    return result

def print_main_menu():
    print("Mainmenu:")
    print("1 => Options")
    print("2 => Measuring")

def print_options_menu(options):
    print("Options:")
    print("1 => Time stamp: ", convert_timestamp_option(options[0]))
    print("2 => Frequency range: ", options[1:5], "Hz - ", options[5:9], "Hz")

def print_timestamp_menu():
    print("Time stamp options:")
    print("0 => disabled")
    print("1 => ms")
    print("2 => us")

def print_frequency_menu():
    print("Frequency range options:")
    print("1 => Change minimum frequency")
    print("2 => Change maximum frequency")


### MAIN ###

# Verbindungsaufbau
#device = ISX3()
device = serial.Serial(port="COM3", baudrate=115200, timeout=1)
#device.connect_device_fs("COM3")

menu = 0




# Hauptmenü
print_main_menu()
userinput = input("Please select an option: ")

match userinput:
    
    case "1":
        options = get_full_options()
        
        print_options_menu(options)
        userinput = input("Change an option: ")
        
        if userinput == "1":
            print_timestamp_menu()
            userinput = input("Select a time stamp option: ")
            device.write(command.set_option(0x01, int(userinput)))
    
    
    case "2":
        print("Measuring:")


#device.write_command_string(command.set_option(0x01, 0x01))


