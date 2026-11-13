"""
test_hardware_isx3.py - Hardware-in-the-Loop (HIL) Integrationstest
fuer das angeschlossene Sciospec Medical Research ISX-3.

Prueft bei real angeschlossener Hardware:
1. Automatische USB/COM-Port-Erkennung (inkl. interaktiver Nachfrage bei Unklarheit)
2. System-Baseline-Drift-Check auf dem internen 2 kΩ Referenzwiderstand (MUX-Port 3)
3. Einzelpunkt-Messung & sauberes Beenden des Measure-Modus (stop_measurement)
4. Multi-Pin-Parallelschaltung ('1: CE:1,5,9, RE:2,6,10, WS:3,7,11, WE:4,8,12')
5. Hardware-Sweep & HDF5-Persistenz inklusive Zeitmessung (measurement_duration_ms)
"""

import os
import sys
import math
import shutil
import tempfile
import unittest
import h5py
import matplotlib.pyplot as plt
import serial.tools.list_ports

# Modulpfad einbinden
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from isx3_api.commands import ISX3
from isx3_api.measurement import Measurement


def resolve_hardware_port(default_port: str = "COM12") -> str | None:
    """
    Erkennt den COM-Port des Sciospec ISX-3 automatisch anhand der USB-Metadaten
    (Sciospec / FTDI / VID 0x0403). Falls kein Port eindeutig erkannt wird oder mehrere
    Geraete angeschlossen sind, wird der Nutzer im Terminal zur Auswahl aufgefordert.
    """
    ports = list(serial.tools.list_ports.comports())

    # 1. Nach Sciospec- oder typischen FTDI-USB-Chips suchen
    sciospec_candidates = []
    for p in ports:
        desc = f"{p.description or ''} {p.manufacturer or ''} {p.hwid or ''}".lower()
        if "sciospec" in desc or "ftdi" in desc or "0403" in desc:
            sciospec_candidates.append(p.device)

    if len(sciospec_candidates) == 1:
        print(f"[AUTO-DETECT] Sciospec/FTDI-Schnittstelle erkannt auf: {sciospec_candidates[0]}")
        return sciospec_candidates[0]

    # 2. Wenn genau ein Port am System existiert, diesen direkt nehmen
    if len(ports) == 1:
        print(f"[AUTO-DETECT] Einziger verfuegbarer COM-Port erkannt: {ports[0].device} ({ports[0].description})")
        return ports[0].device

    # 3. Wenn default_port (z.B. COM12) vorhanden ist und keine anderen Kandidaten konkurrieren
    available_names = [p.device for p in ports]
    if default_port in available_names and not sciospec_candidates:
        print(f"[AUTO-DETECT] Standard-Port '{default_port}' gefunden.")
        return default_port

    # 4. Interaktive Nachfrage im Terminal, wenn Erkennung nicht eindeutig ist
    print("\n" + "=" * 70)
    print(" COM-PORT AUSWAHL FUER HARDWARE-TEST")
    print("=" * 70)
    if ports:
        print("  Folgende serielle Schnittstellen wurden am PC gefunden:")
        for idx, p in enumerate(ports, start=1):
            print(f"    [{idx}] {p.device:<8} - {p.description}")
        user_in = input(
            f"\n  Bitte Listenplatz (1-{len(ports)}) oder Port-Namen eingeben (z.B. 'COM12', Enter = Abbruch): "
        ).strip()
    else:
        print("  [HINWEIS] Es wurden aktuell keine aktiven COM-Ports vom Betriebssystem gemeldet.")
        user_in = input("  Bitte COM-Port manuell eingeben (z.B. 'COM12') oder Enter zum Ueberspringen: ").strip()

    if not user_in:
        return None

    if user_in.isdigit():
        num = int(user_in)
        if 1 <= num <= len(ports):
            return ports[num - 1].device
        return f"COM{num}"

    port_clean = user_in.upper()
    if not port_clean.startswith("COM") and port_clean.isdigit():
        port_clean = f"COM{port_clean}"
    return port_clean


class TestISX3HardwareIntegration(unittest.TestCase):
    """Hardware-Tests direkt am angeschlossenen Medical Research ISX-3."""

    @classmethod
    def setUpClass(cls):
        cls.baudrate = 115200
        cls.device_version = "medical"
        cls.port = resolve_hardware_port("COM12")

        if not cls.port:
            raise unittest.SkipTest("Kein COM-Port ausgewaehlt oder verfuegbar -> Hardware-Test uebersprungen.")

        available = [p.device for p in serial.tools.list_ports.comports()]
        if cls.port not in available:
            raise unittest.SkipTest(
                f"Der gewaehlte Port '{cls.port}' ist nicht angeschlossen. Verfuegbare Ports: {available}"
            )

        print(f"\n[HW-TEST] Starte Hardware-Tests auf Port {cls.port} ({cls.baudrate} Baud)...")

    def test_01_connection_and_stop_command(self):
        """1. Prueft Verbindungsaufbau, Software-Reset und Stop-Befehl."""
        isx = ISX3()
        dev = isx.connect_device_fs({
            "port": self.port,
            "baudrate": self.baudrate,
            "device_version": self.device_version,
        })
        self.assertIsNotNone(dev, f"Verbindung zu {self.port} fehlgeschlagen.")
        try:
            isx.stop_measurement()
            isx.clear_mux_routing()
        finally:
            if isx.device and isx.device.is_open:
                isx.device.close()

    def test_02_baseline_drift_check_internal_2k(self):
        """2. Prueft den internen 2 kΩ Referenzwiderstand (Pins 22,22,23,23 auf MUX-Port 3)."""
        isx = ISX3()
        report = isx.run_baseline_drift_check(
            port=self.port,
            baudrate=self.baudrate,
            mux_channel=3,
            cycles=5,
            freq_hz=1000.0,
        )
        self.assertIsNone(report.get("error"), f"Baseline-Check Fehler: {report.get('error')}")
        self.assertTrue(report.get("stable"), f"Drift zu hoch: {report.get('drift_pct'):.3f} %")
        mean_z = report.get("mean_z", 0.0)
        self.assertGreater(mean_z, 1800.0)
        self.assertLess(mean_z, 2300.0)

    def test_03_multi_pin_ganging_and_hdf5_sweep(self):
        """3. Testet Multi-Pin-Parallelschaltung (12 Pins) + Hardware-Sweep + HDF5-Speicherung."""
        temp_dir = tempfile.mkdtemp()
        orig_cwd = os.getcwd()
        os.chdir(temp_dir)
        plt.ioff()

        ini_path = os.path.join(temp_dir, "hw_test_multipin.ini")
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(
                f"[Connection]\n"
                f"device_version = {self.device_version}\n"
                f"port = {self.port}\n"
                f"baudrate = {self.baudrate}\n\n"
                f"[MUX]\n"
                f"enabled = True\n"
                f"mode = 4\n"
                f"channel = 2\n"
                f"active_sensors = 1: CE:1,5,9 RE:2,6,10 WS:3,7,11 WE:4,8,12\n"
                f"switch_delay_s = 0.10\n\n"
                f"[Frontend]\n"
                f"measurement_mode = 2\n"
                f"measurement_channel = 2\n"
                f"current_range = 2\n"
                f"voltage_range = 1\n\n"
                f"[FrequencyBlocks]\n"
                f"block_1_start = 100.0\n"
                f"block_1_stop = 100000.0\n"
                f"block_1_steps = 5\n"
                f"block_1_scale = logarithmic\n"
                f"block_1_precision = 1.0\n"
                f"block_1_exc_type = 2\n"
                f"block_1_amplitude = 0.0001\n\n"
                f"[Options]\n"
                f"timestamp_mode = 0\n"
                f"enable_current_range_output = False\n\n"
                f"[Measurement]\n"
                f"number_of_spectra = 2\n\n"
                f"[ApiSettings]\n"
                f"plot_type = bode\n"
                f"live_plot_enabled = False\n"
                f"live_plot_mode = sweep\n"
            )

        try:
            meas = Measurement()
            h5_path = meas.measurement(config_path=ini_path)
            self.assertIsNotNone(h5_path, "Messung hat keinen HDF5-Pfad zurueckgegeben.")
            self.assertTrue(os.path.exists(h5_path), "HDF5-Datei wurde nicht erzeugt.")

            with h5py.File(h5_path, "r") as h5f:
                self.assertIn("Sensor_1", h5f)
                s1 = h5f["Sensor_1"]
                self.assertIn("measurement_duration_ms", s1.attrs)
                self.assertGreater(float(s1.attrs["measurement_duration_ms"]), 0.0)

                meas_keys = [k for k in s1.keys() if k.startswith("Measurement_")]
                self.assertEqual(len(meas_keys), 5)

                re_val = float(s1["Measurement_1.1"]["real_part"][0])
                im_val = float(s1["Measurement_1.1"]["imaginary_part"][0])
                self.assertFalse(math.isnan(re_val))
                self.assertFalse(math.isnan(im_val))
        finally:
            os.chdir(orig_cwd)
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main(verbosity=2)