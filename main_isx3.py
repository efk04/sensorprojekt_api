### IMPORTS ###
import time
import serial

from TEST_ISX3 import ISX3
import command_functions as command

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


### MAIN ###
# Verbindungsaufbau
device = ISX3()
#device = serial.Serial(port="COM3", baudrate=115200, timeout=1)
device.connect_device_fs("COM3")


#get_ethernet_config()

device.set_fs_settings(
    4, #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
   "bnc port" , #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
   'autoranging' , #current_measurement_range (str): Current measurement range (e.g., "10mA")
   '1V' , #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
)
#add single frequency
device.set_setup(
     100.0,             #start_frequency (float or str): Starting frequency
     1000000.0,         #end_frequency (float or str): Ending frequency, e.g
     100,             #count (int): Number of frequency points
     "log",           #scale (str): Scale type, "log" or "linear"
     1.0,             #precision (float): Measurement precision 
     #precision testen -> bis 10.0
     0.25,            #amplitude (str or float): Signal amplitude
     'voltage'        #excitation_type (str): Type of excitation
    )

device.save_settings()

device.get_setup()

device.get_fe_settings()



device.start_measurement(spectra=1)


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
#device.close()