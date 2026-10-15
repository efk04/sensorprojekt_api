"""
compensation.py - Software-Kompensation (Open/Leerlauf) für das Sciospec ISX-3.

Berechnet die korrigierte Probenimpedanz durch Subtraktion der parasitären
Leitungs- und MUX-Admittanz: Y_DUT = Y_raw - Y_open.
"""

import os
import h5py
import numpy as np


class ImpedanceCompensator:
    """Verwaltet Kalibrierdaten und führt die Admittanz-Kompensation durch."""

    def __init__(self, open_file_path: str | None = None):
        self.open_file_path = open_file_path
        # Struktur: {sensor_idx: {frequenz_hz: z_open_complex}}
        self.open_data: dict[int, dict[float, complex]] = {}

        if open_file_path and os.path.exists(open_file_path):
            self.load_open_calibration(open_file_path)

    def is_loaded(self) -> bool:
        """Prüft, ob gültige Kompensationsdaten vorliegen."""
        return len(self.open_data) > 0

    def load_open_calibration(self, file_path: str) -> None:
        """Liest die Leerlauf-Messdaten aus einer HDF5-Datei ein."""
        self.open_data = {}
        with h5py.File(file_path, "r") as h5:
            sensor_groups = [k for k in h5.keys() if k.startswith("Sensor_")]
            if not sensor_groups:
                sensor_keys = [(0, h5)]
            else:
                sensor_keys = [
                    (int(k.split("_")[1]), h5[k])
                    for k in sensor_groups
                    if k.split("_")[1].isdigit()
                ]

            for s_idx, grp in sensor_keys:
                self.open_data[s_idx] = {}
                for m_key in grp.keys():
                    if not m_key.startswith("Measurement_"):
                        continue
                    f_val = float(np.mean(grp[m_key]["frequency"][()]))
                    re_val = float(np.mean(grp[m_key]["real_part"][()]))
                    im_val = float(np.mean(grp[m_key]["imaginary_part"][()]))
                    self.open_data[s_idx][f_val] = complex(re_val, im_val)

        sensors_found = list(self.open_data.keys())
        print(f"[OK] Open-Kompensation geladen: {len(sensors_found)} Sensor-Kanal/Kanäle {sensors_found} aus '{os.path.basename(file_path)}'")

    def compensate_point(self, frequency: float, re: float, im: float, sensor_idx: int = 0) -> tuple[float, float]:
        """
        Kompensiert einen einzelnen Frequenzpunkt:
        Y_DUT = Y_raw - Y_open
        Z_DUT = 1 / Y_DUT
        """
        z_raw = complex(re, im)
        if abs(z_raw) == 0:
            return re, im

        s_dict = self.open_data.get(sensor_idx)
        if not s_dict:
            s_dict = self.open_data.get(0)

        if not s_dict:
            return re, im

        # Nächstliegenden Frequenzpunkt der Kalibrierung suchen (Toleranz 5%)
        best_freq = min(s_dict.keys(), key=lambda f: abs(f - frequency))
        if abs(best_freq - frequency) / max(frequency, 1e-6) > 0.05:
            return re, im

        z_open = s_dict[best_freq]
        if abs(z_open) == 0:
            return re, im

        # Admittanzen berechnen: Y = 1 / Z
        y_raw = 1.0 / z_raw
        y_open = 1.0 / z_open

        # Streuleitwert abziehen
        y_dut = y_raw - y_open

        if abs(y_dut) == 0:
            return re, im

        z_dut = 1.0 / y_dut
        return float(z_dut.real), float(z_dut.imag)

    def compensate_spectrum(
        self, frequency: float, real_list: list[float], imag_list: list[float], sensor_idx: int = 0
    ) -> tuple[list[float], list[float]]:
        """Kompensiert alle Wiederholungen (Spectra) eines Frequenzschritts."""
        comp_re = []
        comp_im = []
        for r, i in zip(real_list, imag_list):
            cr, ci = self.compensate_point(frequency, r, i, sensor_idx)
            comp_re.append(cr)
            comp_im.append(ci)
        return comp_re, comp_im