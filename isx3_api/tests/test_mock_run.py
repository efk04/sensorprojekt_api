"""
test_mock_run.py - Hardware-Simulation für ISX-3 inklusive MUX32-Schaltmatrix.
"""

import os
import struct
import h5py
from isx3_api import Measurement


class MockSerialWithMux:
    """Simuliert das ISX-3 und fängt MUX-Schaltbefehle ab."""

    def __init__(self):
        self.is_open = True
        self.name = "COM_MOCK_MUX32"
        self.rx_buffer = bytearray()
        self.freq_counter = 0

    @property
    def in_waiting(self) -> int:
        return len(self.rx_buffer)

    def write(self, data: bytes) -> int:
        if not data:
            return 0

        cmd_tag = data[0]

        # 0xB4: Extension Port / MUX32-Schaltbefehl
        if cmd_tag == 0xB4 and len(data) >= 6:
            ce, re, ws, we = data[2], data[3], data[4], data[5]
            print(f"[MOCK-HARDWARE] MUX32 schaltet Relais -> CE={ce}, RE={re}, WS={ws}, WE={we}")
            # Quittung (ACK): 0x18 0x01 0x83 0x18
            self.rx_buffer.extend(bytes([0x18, 0x01, 0x83, 0x18]))

        # 0xB8: Messdaten-Start
        elif cmd_tag == 0xB8 and len(data) >= 5 and data[2] == 0x01:
            self.freq_counter += 1
            # ACK für Messstart
            self.rx_buffer.extend(bytes([0x18, 0x01, 0x83, 0x18]))
            # Simulierter Messframe (Real = 1000 Ohm, Imag = -250 Ohm)
            frame = (
                bytes([0xB8, 0x0A])
                + self.freq_counter.to_bytes(2, "big")
                + struct.pack(">ff", 1000.0, -250.0)
                + bytes([0xB8])
            )
            self.rx_buffer.extend(frame)

        # Standard-ACK für alle Setup-Befehle (0x97, 0xB0, 0xB6, etc.)
        else:
            self.rx_buffer.extend(bytes([0x18, 0x01, 0x83, 0x18]))

        return len(data)

    def read(self, size: int = 1) -> bytes:
        if not self.rx_buffer:
            return b""
        chunk = bytes(self.rx_buffer[:size])
        self.rx_buffer = self.rx_buffer[size:]
        return chunk

    def flush(self) -> None:
        pass

    def reset_input_buffer(self) -> None:
        self.rx_buffer.clear()

    def close(self) -> None:
        self.is_open = False


def verify_hdf5_file(filepath: str):
    """Prüft, ob die MUX-Sensoren sauber in der HDF5-Datei angelegt wurden."""
    print(f"\n=== Validierung der erstellten HDF5-Datei: '{filepath}' ===")
    with h5py.File(filepath, "r") as h5:
        for key in h5.keys():
            if key.startswith("Sensor_"):
                sub_count = len(h5[key].keys())
                print(f"  └── Gruppe: {key} ({sub_count} Messpunkte erfolgreich abgelegt)")
            elif key.startswith("Measurement_"):
                print(f"  └── Gruppe: {key} (Hauptbuchsen-Messung)")
            else:
                print(f"  └── Metadaten: {key}")


def main():
    controller = Measurement()

    # Serielles Gerät durch MUX-Mock ersetzen
    mock_serial = MockSerialWithMux()
    controller.device.device = mock_serial
    controller.device.connect_device_fs = lambda settings: mock_serial

    print("[START] Starte MUX-Simulation mit 'config/config.ini'...")
    controller.measurement("config/config.ini")

    # Überprüfen der erzeugten Datei
    if controller.filename:
        latest_file = os.path.join("measurements", controller.filename)
        verify_hdf5_file(latest_file)


if __name__ == "__main__":
    main()