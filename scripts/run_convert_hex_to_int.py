import struct

# Die 4 empfangenen Bytes
byte_data = bytes([0x3b, 0x9e, 0x34, 0xd9])

# Als 4-Byte Big-Endian Float ('>f') entpacken
decimal_value = struct.unpack(">f", byte_data)[0]

print(decimal_value)