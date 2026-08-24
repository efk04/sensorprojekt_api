import time
import serial

from src.TEST_ISX3 import ISX3
import command_functions as command
from main import read_answer

device = serial.Serial(port="COM3", baudrate=115200, timeout=1)

print("Testing get_options(timestamp) command:")
com = command.get_options(0x01)
device.write(com)
result = read_answer(device)
print("Input: ", [hex(b) for b in com])
print("Output: ", result)

print("Testing get_options(frequency range) command:")
com = command.get_options(0x03)
device.write(com)
result = read_answer(device)
print("Input: ", [hex(b) for b in com])
print("Output: ", result)

print("Testing get_options(current range) command:")
com = command.get_options(0x04)
device.write(com)
result = read_answer(device)
print("Input: ", [hex(b) for b in com])
print("Output: ", result)

print("Testing set_fe_settings command:")
com = command.set_fe_settings(0x01, 0x01, 0x00)
device.write(com)
result = read_answer(device)
print("Input: ", [hex(b) for b in com])
print("Output: ", result)

print("Testing get_fe_settings command:")
com = command.get_fe_settings()
device.write(com)
result = read_answer(device)
print("Input: ", [hex(b) for b in com])
print("Output: ", result)

device.close()