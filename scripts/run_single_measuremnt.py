import serial
import struct


# Connect
PORT = "COM4"
BAUDRATE = 115200
ser = serial.Serial(PORT, BAUDRATE, timeout=2.0)


# Initialize setup
ser.write(bytes([0xB6, 0x01, 0x01, 0xB6]))
ack = ser.read(4)
print("Init ACK:", ack)


# Set FE-Settings
# reset / clear channel stack
ser.write(bytes([0xB0, 0x03, 0xFF, 0xFF, 0xFF, 0xB0]))
ack = ser.read(4)
print("FE clear ACK:", ack)

# mode=4-point, channel=BNC, current range=10mA
ser.write(bytes([0xB0, 0x03, 0x02, 0x01, 0x01, 0xB0]))
ack = ser.read(4)
print("FE set ACK:", ack)


# Add frequency points (each point: freq/precision/amplitude as 4-byte floats)
frequencies = [100, 1000, 10000, 100000, 1000000]
precision = 1.0
amplitude = 0.1  # V

for freq in frequencies:
    payload = struct.pack(">fff", float(freq), precision, amplitude)
    ser.write(bytes([0xB6, 0x0D, 0x02]) + payload + bytes([0xB6]))
    ack = ser.read(4)
    print(f"Add freq {freq} Hz ACK:", ack)


# Start measurement: measure the configured setup once (1 spectrum)
ser.write(bytes([0xB8, 0x03, 0x01]) + (1).to_bytes(2, "big") + bytes([0xB8]))
ack = ser.read(4)
print("Start ACK:", ack)


# Read one result frame per configured frequency point
for _ in frequencies:
    tag = ser.read(1)
    while tag and tag[0] != 0xB8:
        tag = ser.read(1)

    length = ser.read(1)[0]
    payload = ser.read(length)
    end_tag = ser.read(1)

    freq_id = int.from_bytes(payload[0:2], "big")
    real = struct.unpack(">f", payload[2:6])[0]
    imag = struct.unpack(">f", payload[6:10])[0]

    print(f"freq_id={freq_id} real={real:.4f} imag={imag:.4f}")

ser.close()
