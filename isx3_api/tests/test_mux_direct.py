"""test_mux_direct.py - Direkte Ansteuerung des MUX32 laut Sciospec-Handbuch."""

import time
import serial

ser = serial.Serial("COM12", 115200, timeout=1.5)
time.sleep(0.2)
ser.reset_input_buffer()


def send_and_wait(name, frame_bytes):
  print(f"\n--> Sende {name}: {frame_bytes.hex()}")
  ser.write(frame_bytes)
  ser.flush()
  time.sleep(0.05)
  resp = ser.read(ser.in_waiting or 4)
  print(f"<-- Antwort:    {resp.hex()}")
  return resp


print("=== Sciospec MUX32 Hardware-Check ===")

# 1. Extension-Modul abfragen (0xB5) - wie im GUI-Logfile
send_and_wait("0xB5 (Get Extension Module)", bytes([0xB5, 0x00, 0xB5]))

# 2. Frontend-Stack leeren (0xB0)
send_and_wait(
    "0xB0 (Clear Stack)", bytes([0xB0, 0x03, 0xFF, 0xFF, 0xFF, 0xB0])
)

# 3. Frontend auf EXTENSION PORT schalten:
# Mode=4pt (0x02), Channel=ExtensionPort (0x02), Range=1 (0x01), Voltage=1 (0x01)
send_and_wait(
    "0xB0 (Set FE to Extension Port)",
    bytes([0xB0, 0x04, 0x02, 0x02, 0x01, 0x01, 0xB0]),
)

# 4. MUX32 Relais schalten (0xB2): CE=1, RE=2, WS=3, WE=4
send_and_wait(
    "0xB2 (Set Extension Channel)",
    bytes([0xB2, 0x04, 0x01, 0x02, 0x03, 0x04, 0xB2]),
)

# 5. Aktiven MUX-Kanal zur Kontrolle zurücklesen (0xB3)
send_and_wait("0xB3 (Get Extension Channel)", bytes([0xB3, 0x00, 0xB3]))

ser.close()
print("\n[FERTIG] Test abgeschlossen.")