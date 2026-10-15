"""
measurement.py - Zentraler Messungs-Orchestrator für das Sciospec ISX-3.

Koordiniert das Laden der Konfiguration, die Initialisierung der Hardware,
die Abarbeitung der Frequenz-Messpunkte, das MUX32-Routing, die optionale
Open-Kompensation, das HDF5-Logging sowie die Live-Plots.
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

    def save_measurement_settings(self, config_path: str) -> None:
        """Sichert die komplette Konfigurationsdatei als Metadaten in der HDF5-Datei."""
        group_name = "Configuration"
        ini = configparser.ConfigParser(interpolation=None)
        ini.optionxform = str

        if not ini.read(config_path, encoding="utf-8"):
            raise FileNotFoundError(f"Konfigurationsdatei '{config_path}' konnte nicht gelesen werden.")

        full_path = os.path.join("measurements", self.filename)
        with h5py.File(full_path, "a") as h5_file:
            config_group = h5_file.create_group(group_name, track_order=True)
            config_group.attrs["source_file"] = os.path.basename(config_path)

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

            # Rohdaten mitspeichern, falls Kompensation aktiv war
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

        number_of_spectra = current_setup["number_of_spectra"]
        step_id = current_setup["id"]

        results = self.device.start_measurement(
            spectra=number_of_spectra,
            id=step_id,
            measurement_settings=measurement_settings,
        )
        timestamp = time.time()

        freq_value = current_setup["frequency"]
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

    def measurement(self, config_path: str = None) -> None:
        """Führt Frequenz-Sweeps durch (direkt oder über MUX32, optional mit Kompensation)."""
        if not config_path:
            config_path = select_config_file()

        self.config_builder = ConfigBuilder(config_path)
        self.measurement_settings = self.config_builder.get_settings_from_config()
        self.measurement_queue = self.config_builder.generate_measurement_queue()
        self.plot_type = self.measurement_settings.get("plot_type", "bode")

        # 1. Konfiguration robust parsen
        mux_enabled = False
        mux_mode = 4
        raw_sensors = "1"
        switch_delay = 0.05
        comp_enabled = False
        comp_file = ""

        p = getattr(self.config_builder, "parser", None)
        mux_sec = None
        comp_sec = None

        if p and hasattr(p, "sections"):
            for sec in p.sections():
                if sec.lower() == "mux":
                    mux_sec = sec
                elif sec.lower() == "compensation":
                    comp_sec = sec

        if not mux_sec or not comp_sec:
            ini_direct = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
            if ini_direct.read(config_path, encoding="utf-8"):
                for sec in ini_direct.sections():
                    if sec.lower() == "mux" and not mux_sec:
                        p = ini_direct
                        mux_sec = sec
                    elif sec.lower() == "compensation" and not comp_sec:
                        p = ini_direct
                        comp_sec = sec

        if p and mux_sec:
            def clean_opt(opt, default=""):
                if hasattr(p, "has_option") and p.has_option(mux_sec, opt):
                    val = p.get(mux_sec, opt)
                    return val.split("#")[0].split(";")[0].strip()
                return default

            mux_enabled = clean_opt("enabled", "false").lower() in ("true", "1", "yes", "on")
            try:
                mux_mode = int(clean_opt("mode", "4"))
            except ValueError:
                mux_mode = 4

            raw_sensors = clean_opt("active_sensors", "1")
            try:
                switch_delay = float(clean_opt("switch_delay_s", "0.05"))
            except ValueError:
                switch_delay = 0.05

        if p and comp_sec:
            def clean_comp(opt, default=""):
                if hasattr(p, "has_option") and p.has_option(comp_sec, opt):
                    val = p.get(comp_sec, opt)
                    return val.split("#")[0].split(";")[0].strip()
                return default

            comp_enabled = clean_comp("enabled", "false").lower() in ("true", "1", "yes", "on")
            comp_file = clean_comp("open_file", "calibration/open_calibration.h5")

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

        # 3. Kompensation initialisieren
        if comp_enabled:
            if os.path.exists(comp_file):
                self.compensator.load_open_calibration(comp_file)
            else:
                print(f"[WARNUNG] Kompensationsdatei '{comp_file}' nicht gefunden. Messung erfolgt unkompensiert.")
                comp_enabled = False

        # 4. HDF5-Datei vorbereiten
        self.create_h5_file()
        self.save_measurement_settings(config_path)

        # 5. Hardware initialisieren
        self.device.connect_device_fs(settings=self.measurement_settings)
        self.device.set_options(settings=self.measurement_settings)

        if mux_enabled:
            self.measurement_settings["measurement_channel"] = 2
            for step in self.measurement_queue:
                step["measurement_channel"] = 2

            try:
                self.device._send_command(self.device.CMD_GET_EXTENSION_MODULE, b"")
            except Exception:
                pass

            fe_mode = 2 if mux_mode == 4 else 1
            c_range = self.measurement_settings.get("current_range", 1)
            v_range = self.measurement_settings.get("voltage_range", 1)
            self.device._send_command(self.device.CMD_SETUP_FRONTEND, bytes([0xFF, 0xFF, 0xFF]))
            self.device._send_command(
                self.device.CMD_SETUP_FRONTEND, bytes([fe_mode, 0x02, c_range, v_range])
            )

        print(f"[INFO] Mess-Queue generiert ({len(self.measurement_queue)} Frequenzpunkte pro Spektrum).")
        if comp_enabled and self.compensator.is_loaded():
            print("[INFO] Software-Kompensation AKTIV (Admittanz-Korrektur).")
        else:
            print("[INFO] Rohdaten-Messung (keine Kompensation).")

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
                    print(f"\n--- Starte Messdurchlauf über Hauptbuchsen ---")

                self.current_results = []

                for current_setup in self.measurement_queue:
                    step_results, timestamp = self.start_single_step(
                        current_setup, self.measurement_settings
                    )

                    # Optionale Kompensation anwenden
                    if comp_enabled and self.compensator.is_loaded():
                        current_s_idx = sensor_idx if mux_enabled else 0
                        re_comp, im_comp = self.compensator.compensate_spectrum(
                            frequency=float(current_setup["frequency"]),
                            real_list=step_results["real"],
                            imag_list=step_results["imag"],
                            sensor_idx=current_s_idx,
                        )
                        # Rohdaten sichern
                        step_results["real_raw"] = list(step_results["real"])
                        step_results["imag_raw"] = list(step_results["imag"])
                        # Kompensierte Werte für Speicherung und Plot setzen
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
                        self.device.set_extension_port(0, 0, 0, 0)
                    except Exception:
                        pass
                if hasattr(self.device, "device") and self.device.device and self.device.device.is_open:
                    self.device.device.close()
                    print("[OK] Serielle Schnittstelle geschlossen.")

        plt.ioff()
        plt.show()