"""
measurement.py - Zentraler Messungs-Orchestrator für das Sciospec ISX-3.

Koordiniert das Laden der Konfiguration, die Initialisierung der Hardware,
die Abarbeitung der Frequenz-Messpunkte, das MUX32-Routing, die optionale
Hardware-Skalierung und Open-Kompensation, das HDF5-Logging sowie die Live-Plots.
"""

from datetime import datetime
import os
import time
import configparser
import h5py
import matplotlib.pyplot as plt

from .commands import ISX3
from .compensation import ImpedanceCompensator
from .config_handler import ConfigBuilder, select_config_file
from .plot_templates import PlotTemplates


class Measurement:
    """Steuert den gesamten Ablauf einer Impedanz-Messkampagne."""

    def __init__(self):
        """Initialisiert die Treiber, Hilfsobjekte und Speicherstrukturen."""
        self.device = ISX3()
        self.compensator = ImpedanceCompensator()
        self.config_builder: ConfigBuilder | None = None
        self.plot_templates = PlotTemplates()

        self.filename: str = ""
        self.plot_type: str = "bode"
        self.measurement_settings: dict = {}
        self.measurement_queue: list[dict] = []
        self.current_results: list[dict] = []
        self.manual_stop: bool = False

        plt.ion()
        plt.rcParams["keymap.quit"] = []

    def create_h5_file(self) -> str:
        """Erstellt eine neue HDF5-Datei im Ordner 'measurements' mit Zeitstempel im Namen."""
        os.makedirs("measurements", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.filename = f"measurement_results_{timestamp}.h5"
        full_path = os.path.join("measurements", self.filename)

        with h5py.File(full_path, "w"):
            pass

        print(f"[OK] HDF5-Messdatei erstellt: {full_path}")
        return full_path

    def save_measurement_settings(self, config_path: str, scale_factor: float = 1.0) -> None:
        """Sichert die komplette Konfigurationsdatei als Metadaten in der HDF5-Datei."""
        group_name = "Configuration"
        ini = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=("#", ";"))
        ini.optionxform = str

        if not ini.read(config_path, encoding="utf-8"):
            raise FileNotFoundError(f"Konfigurationsdatei '{config_path}' konnte nicht gelesen werden.")

        full_path = os.path.join("measurements", self.filename)
        with h5py.File(full_path, "a") as h5_file:
            config_group = h5_file.create_group(group_name, track_order=True)
            config_group.attrs["source_file"] = os.path.basename(config_path)
            config_group.attrs["applied_scale_factor"] = float(scale_factor)

            for section in ini.sections():
                section_group = config_group.create_group(section, track_order=True)
                for key, value in ini.items(section, raw=True):
                    section_group.attrs[key] = str(value)

    safe_measurement_settings = save_measurement_settings

    def save_measurement(
        self,
        results_data: dict,
        timestamp: float,
        current_setup: dict,
        icm: int,
        sensor_idx: int = 0,
    ) -> None:
        """Speichert das Ergebnis eines Frequenzschritts in einer HDF5-Gruppe."""
        if not results_data.get("id"):
            raise ValueError("Keine gültigen Messdaten zum Speichern vorhanden.")

        current_id = f"{icm}.{current_setup['id']}"
        if sensor_idx > 0:
            group_name = f"Sensor_{sensor_idx}/Measurement_{current_id}"
        else:
            group_name = f"Measurement_{current_id}"

        full_path = os.path.join("measurements", self.filename)

        with h5py.File(full_path, "a") as h5_file:
            group = h5_file.require_group(group_name)

            group.create_dataset("timestamp", data=timestamp)
            group.create_dataset("frequency", data=float(current_setup["frequency"]))
            group.create_dataset("frequency_id", data=results_data["id"])
            group.create_dataset("real_part", data=results_data["real"])
            group.create_dataset("imaginary_part", data=results_data["imag"])

            if "real_raw" in results_data and "imag_raw" in results_data:
                group.create_dataset("real_part_raw", data=results_data["real_raw"])
                group.create_dataset("imaginary_part_raw", data=results_data["imag_raw"])

            if any(results_data.get("current_range", [])):
                group.create_dataset("current_range", data=[r for r in results_data["current_range"] if r is not None])

            group.attrs["created"] = datetime.now().isoformat()

    safe_measurment = lambda self, results, setup, icm: self.save_measurement(results[0], results[1], setup, icm)

    def start_single_step(
        self, current_setup: dict, measurement_settings: dict
    ) -> tuple[dict, float]:
        """Führt die Messung für einen einzelnen Frequenzschritt aus."""
        self.device.set_frequency_setup(current_setup)

        number_of_spectra = int(current_setup["number_of_spectra"])
        step_id = int(current_setup["id"])

        results = self.device.start_measurement(
            spectra=number_of_spectra,
            id=step_id,
            measurement_settings=measurement_settings,
        )
        timestamp = time.time()

        freq_value = float(current_setup["frequency"])
        num_points = len(results.get("id", []))
        results["frequencies"] = [freq_value] * num_points

        return results, timestamp

    def update_live_plot(self, results: dict, current_setup: dict, current_results: list[dict], len_queue: int) -> None:
        """Aktualisiert die grafische Live-Anzeige."""
        match self.plot_type:
            case "impedance_frequency":
                self.plot_templates.impedance_frequency(results, current_results, len_queue)
            case "nyquist":
                self.plot_templates.nyquist(results, current_results, len_queue)
            case _:
                self.plot_templates.bode(results, current_results, len_queue)

        plt.pause(0.01)

    def measurement(self, config_path: str | None = None) -> None:
        """Führt Frequenz-Sweeps durch (direkt oder über MUX32, optional mit Skalierung & Kompensation)."""
        if not config_path:
            config_path = select_config_file()
            if not config_path:
                print("[INFO] Keine Konfigurationsdatei ausgewählt. Abbruch.")
                return

        self.config_builder = ConfigBuilder(config_path)
        self.measurement_settings = self.config_builder.get_settings_from_config()
        self.measurement_queue = self.config_builder.generate_measurement_queue()
        self.plot_type = self.measurement_settings.get("plot_type", "bode")

        # 1. Konfiguration robust auslesen (kompatibel mit altem und neuem ConfigParser)
        mux_enabled = bool(self.measurement_settings.get("mux_enabled", False))
        mux_mode = int(self.measurement_settings.get("mux_mode", 4))
        raw_sensors = str(self.measurement_settings.get("mux_active_sensors", "8"))
        switch_delay = float(self.measurement_settings.get("mux_switch_delay_s", 0.05))

        comp_enabled = bool(self.measurement_settings.get("compensation_enabled", False))
        comp_file = str(self.measurement_settings.get("compensation_open_file", "calibration/open_calibration.h5"))

        scale_factor = float(self.measurement_settings.get("hardware_scale_factor", 1.0))

        # Fallback-Check direkt auf der INI-Datei, falls ein älterer config_handler genutzt wird
        ini_direct = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
        if ini_direct.read(config_path, encoding="utf-8"):
            for sec in ini_direct.sections():
                if sec.lower() == "mux":
                    mux_enabled = ini_direct.getboolean(sec, "enabled", fallback=mux_enabled)
                    mux_mode = ini_direct.getint(sec, "mode", fallback=mux_mode)
                    raw_sensors = ini_direct.get(sec, "active_sensors", fallback=raw_sensors)
                    switch_delay = ini_direct.getfloat(sec, "switch_delay_s", fallback=switch_delay)
                elif sec.lower() == "compensation":
                    comp_enabled = ini_direct.getboolean(sec, "enabled", fallback=comp_enabled)
                    comp_file = ini_direct.get(sec, "open_file", fallback=comp_file)
                elif sec.lower() == "frontend":
                    scale_factor = ini_direct.getfloat(sec, "hardware_scale_factor", fallback=scale_factor)

        # 2. Sensor-Liste parsen
        active_sensors = []
        if mux_enabled:
            for part in raw_sensors.split(","):
                part = part.strip()
                if "-" in part:
                    start_s, end_s = part.split("-")
                    active_sensors.extend(range(int(start_s), int(end_s) + 1))
                elif part.isdigit():
                    active_sensors.append(int(part))
        else:
            active_sensors = [0]

        # 3. Optionale Open-Kompensation initialisieren
        if comp_enabled:
            if os.path.exists(comp_file):
                self.compensator.load_open_calibration(comp_file)
            else:
                print(f"[WARNUNG] Kompensationsdatei '{comp_file}' nicht gefunden. Messung erfolgt unkompensiert.")
                comp_enabled = False

        # 4. HDF5-Datei vorbereiten
        self.create_h5_file()
        self.save_measurement_settings(config_path, scale_factor=scale_factor)

        # 5. Hardware verbinden und Optionen setzen
        if not self.device.connect_device_fs(settings=self.measurement_settings):
            return

        self.device.set_options(settings=self.measurement_settings)

        if mux_enabled:
            fe_mode = 2 if mux_mode == 4 else 1
            self.measurement_settings["measurement_channel"] = 2
            self.measurement_settings["measurement_mode"] = fe_mode
            for step in self.measurement_queue:
                step["measurement_channel"] = 2
                step["measurement_mode"] = fe_mode

        c_range = int(self.measurement_settings.get("current_range", 1))
        print(f"[INFO] Mess-Queue generiert ({len(self.measurement_queue)} Frequenzpunkte pro Spektrum).")
        print(f"[INFO] Current Range Index: {c_range} | Hardware-Scale-Faktor: {scale_factor:.4f}")
        if comp_enabled and self.compensator.is_loaded():
            print("[INFO] Software-Kompensation AKTIV (Admittanz-Korrektur).")
        else:
            print("[INFO] Rohdaten-Messung (keine Software-Kompensation).")

        if mux_enabled:
            print(f"[INFO] MUX32 aktiv ({mux_mode}-Leiter) | Geplante Sensoren: {active_sensors}")
        else:
            print("[INFO] Messung über Frontbuchsen (MAIN PORT, kein MUX).")
        print("[INFO] Messung läuft. Zum Stoppen 'Strg + C' im Terminal drücken.\n")

        try:
            for sensor_idx in active_sensors:
                if mux_enabled:
                    print(f"\n==========================================")
                    print(f" Starte Sweep für Sensor #{sensor_idx}")
                    print(f"==========================================")
                    self.device.route_mux_sensor(sensor_idx=sensor_idx, wire_mode=mux_mode)
                    time.sleep(switch_delay)
                else:
                    self.device.active_mux_pins = None
                    print(f"\n--- Starte Messdurchlauf über Hauptbuchsen ---")

                self.current_results = []

                for current_setup in self.measurement_queue:
                    step_results, timestamp = self.start_single_step(
                        current_setup, self.measurement_settings
                    )

                    # Unskalierte Hardware-Rohdaten sichern, falls Skalierung oder Kompensation aktiv ist
                    if abs(scale_factor - 1.0) > 1e-6 or (comp_enabled and self.compensator.is_loaded()):
                        step_results["real_raw"] = list(step_results["real"])
                        step_results["imag_raw"] = list(step_results["imag"])

                    # 1. Hardware-Skalierungsfaktor anwenden
                    if abs(scale_factor - 1.0) > 1e-6:
                        step_results["real"] = [r * scale_factor for r in step_results["real"]]
                        step_results["imag"] = [i * scale_factor for i in step_results["imag"]]

                    # 2. Optionale Open-Kompensation anwenden
                    if comp_enabled and self.compensator.is_loaded():
                        current_s_idx = sensor_idx if mux_enabled else 0
                        re_comp, im_comp = self.compensator.compensate_spectrum(
                            frequency=float(current_setup["frequency"]),
                            real_list=step_results["real"],
                            imag_list=step_results["imag"],
                            sensor_idx=current_s_idx,
                        )
                        step_results["real"] = re_comp
                        step_results["imag"] = im_comp

                    # In HDF5 ablegen
                    self.save_measurement(
                        results_data=step_results,
                        timestamp=timestamp,
                        current_setup=current_setup,
                        icm=1,
                        sensor_idx=sensor_idx if mux_enabled else 0,
                    )

                    # Live-Plot aktualisieren
                    self.current_results.append(step_results)
                    self.update_live_plot(
                        results=step_results,
                        current_setup=current_setup,
                        current_results=self.current_results,
                        len_queue=len(self.measurement_queue),
                    )

            print("\n[OK] Alle Messungen erfolgreich abgeschlossen.")

        except KeyboardInterrupt:
            print("\n[INFO] Messung manuell durch Benutzer abgebrochen (Strg+C).")
        finally:
            if self.device:
                if mux_enabled:
                    try:
                        self.device.clear_mux_routing()
                    except Exception:
                        pass
                if hasattr(self.device, "device") and self.device.device and self.device.device.is_open:
                    self.device.device.close()
                    print("[OK] Serielle Schnittstelle geschlossen.")

        plt.ioff()
        plt.show()