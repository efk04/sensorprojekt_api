# UNFERTIG

import struct

input = ['0xb8', '0xf', '0x0', '0x0', '0x0', '0x0', '0x0', '0x4', '0x1', '0x42', '0xda', '0x16', '0xe4', '0x3b', '0x78', '0x18', '0x8e', '0xb8']

def split_isx_answer(input_data):
    """Teilt die Antwort des Messgeräts in die einzelnen Komponenten auf."""

    raw_data = bytes([int(x, 16) for x in input_data])

    if raw_data[0] != 0xb8:
        raise ValueError("Ungültige Antwort: Erwartet '0xb8' als Startbyte.")

    if raw_data[-1] != 0xb8:
        raise ValueError("Ungültige Antwort: Erwartet '0xb8' als Endbyte.")

    len_byte = int(raw_data[1])
    if len_byte != len(raw_data) - 3:  # -3 für Startbyte, Längenbyte und Endbyte
        raise ValueError("Ungültige Antwort: Länge stimmt nicht überein.")

    extracted_id = struct.unpack(">H", raw_data[2:4])[0]


    

split_isx_answer(input)