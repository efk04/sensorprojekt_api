import argparse
import struct
import serial

parser = argparse.ArgumentParser()
parser.add_argument("frequency",   help="measurement frequency", type=float)
parser.add_argument("--precision", help="measurement precision", type=float, default=1.0)
parser.add_argument("--amplitude", help="measurement amplitude", type=float, default=0.1)

parser.add_argument("--measurement_mode",       help="measurement mode",        type=int, default=1)
parser.add_argument("--measurement_channel",    help="measurement channel",     type=int, default=1)
parser.add_argument("--current_range_settings", help="current range settings",  type=int, default=0)
parser.add_argument("--voltage_range_settings", help="voltage range settings",  type=int, default=0)


args = parser.parse_args()

PORT = "COM4"
BAUDRATE = 115200
ser = serial.Serial(PORT, BAUDRATE, timeout=2.0)



def write_single_measurement(device, frequency, precision, amplitude, measurement_mode, measurement_channel, current_range_settings, voltage_range_settings):
    device.write(bytes([0xB6, 0x01, 0x01, 0xB6])) #reset frequency list
    ack_reset = device.read(4)

    device.write(bytes([0xB0, 0x03, 0xFF, 0xFF, 0xFF, 0xB0])) # reset front-end settings
    ack_reset_fe = device.read(4)

    payload = struct.pack(">BBBB", measurement_mode, measurement_channel, current_range_settings, voltage_range_settings)
    device.write(bytes([0xB0, len(payload)]) + payload + bytes([0xB0]))
    ack_set_fe = device.read(4)

    payload = struct.pack(">fff", float(frequency), precision, amplitude)
    device.write(bytes([0xB6, 0x0D, 0x02]) + payload + bytes([0xB6]))
    ack_setup = device.read(4)

    device.write(bytes([0xB8, 0x03, 0x01, 0x00, 0x01, 0xB8]))
    ack_measurement = device.read(4)

    return ack_reset, ack_reset_fe, ack_set_fe, ack_setup, ack_measurement

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

def measure_once(device, frequency, precision, amplitude, measurement_mode, measurement_channel, current_range_settings, voltage_range_settings):
    ack_reset, ack_reset_fe, ack_set_fe, ack_setup, ack_measurement = write_single_measurement(device, frequency, precision, amplitude, measurement_mode, measurement_channel, current_range_settings, voltage_range_settings)
    freq_id, real, imag = read_single_measurement(device)
    return freq_id, real, imag, ack_reset, ack_reset_fe, ack_set_fe, ack_setup, ack_measurement

print(args)
print(measure_once(ser, args.frequency, args.precision, args.amplitude, args.measurement_mode, args.measurement_channel, args.current_range_settings, args.voltage_range_settings)[0:3])