from time import sleep

import serial
import struct


# Connect
PORT = "COM4"
BAUDRATE = 115200
ser = serial.Serial(PORT, BAUDRATE, timeout=2.0)

# Add frequency points (each point: freq/precision/amplitude as 4-byte floats)
frequencies = [100, 1000, 10000, 100000, 1000000]
precision = 1.0
amplitude = 0.1  # V


def write_single_measurement(device, frequency, precision = 1.0, amplitude = 0.1):
    device.write(bytes([0xB6, 0x01, 0x01, 0xB6])) #reset frequency list
    ack_reset = ser.read(4)

    #ser.write(bytes([0xB0, 0x03, 0xFF, 0xFF, 0xFF, 0xB0]))
    #ack_reset_fe = ser.read(4)
    ser.write(bytes([0xB0, 0x03, 0x01, 0x01, 0x01, 0xB0]))
    ack_set_fe = ser.read(4)

    payload = struct.pack(">fff", float(frequency), precision, amplitude)
    device.write(bytes([0xB6, 0x0D, 0x02]) + payload + bytes([0xB6]))
    ack_setup = ser.read(4)

    device.write(bytes([0xB8, 0x03, 0x01, 0x00, 0x01, 0xB8]))
    ack_measurement = ser.read(4)

    return ack_reset, ack_set_fe, ack_setup, ack_measurement

def read_single_measurement(device):
    # Read one result frame per configured frequency point
    tag = device.read(1)
    while tag and tag[0] != 0xB8:
        tag = device.read(1)

    length = device.read(1)[0]
    payload = device.read(length)
    end_tag = device.read(1)
    if end_tag[0] != 0xB8:
        raise ValueError("Invalid end tag in measurement frame")

    freq_id = int.from_bytes(payload[0:2], "big")
    real = struct.unpack(">f", payload[2:6])[0]
    imag = struct.unpack(">f", payload[6:10])[0]

    return freq_id, real, imag

def measure_once(frequency, precision = 1.0, amplitude = 0.1):
    PORT = "COM4"
    BAUDRATE = 115200
    ser = serial.Serial(PORT, BAUDRATE, timeout=2.0)
    ack_reset, ack_set_fe, ack_setup, ack_measurement = write_single_measurement(ser, frequency, precision, amplitude)
    freq_id, real, imag = read_single_measurement(ser)
    return freq_id, real, imag, ack_reset, ack_set_fe, ack_setup, ack_measurement



for freq in frequencies:
    measurement = measure_once(ser, freq)
    print(freq)
    print(f"Measurement result: freq_id={measurement[0]}, real={measurement[1]:.4f}, imag={measurement[2]:.4f}")


ser.close()
