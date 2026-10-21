"""
measurement.py - Zentraler Messungs-Orchestrator für das Sciospec ISX-3.
"""

from datetime import datetime
import os
import time
import configparser
import h5py
import matplotlib.pyplot as plt

from .commands import ISX3
from .config_handler import ConfigBuilder, select_config_file
from .plot_templates import PlotTemplates


class Measurement:
    """Steuert den gesamten Ablauf einer Impedanz-Messkampagne."""

    def __init__(self):
        self.device = ISX3()
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

    def create_h5_file(self, mode_prefix: str = "MAIN") -> str:
        os.makedirs("measurements", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.filename = f"measurement_{mode_prefix}_{timestamp}.h5"
        full_path = os.path.join("measurements", self.filename)

        with h5py.File(full_path, "w"):
            pass

        print(f"[OK] HDF5-Messdatei erstellt: {full_path}")
        return full_path

    def save_measurement_settings(
        self, config_path: str, mux_enabled: bool = False
    ) -> None:
        group_name = "Configuration"
        ini = configparser.ConfigParser(interpolation=None, inline_comment_prefixes=("#", ";"))
        ini.optionxform = str

        if not ini.read(config_path, encoding="utf-8"):
            raise FileNotFoundError(f"Konfigurationsdatei '{config_path}' konnte nicht gelesen werden.")

        full_path = os.path.join("measurements", self.filename)
        with h5py.File(full_path, "a") as h5_file:
            config_group = h5_file.create_group(group_name, track_order=True)
            config_group.attrs["source_file"] = os.path.basename(config_path)
            config_group.attrs["measurement_type"] = "MUX" if mux_enabled else "MAIN"

            for section in ini.sections():
                section_group = config_group.create_group(section, track_order=True)
                for key, value in ini.items(section, raw=True):
                    section_group.attrs[key] = str(value)

    def save_measurement(
        self,
        results_data: dict,
        timestamp: float,
        current_setup: dict,
        icm: int,
        sensor_idx: int = 0,
    ) -> None:
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

            if any(results_data.get("current_range", [])):
                group.create_dataset("current_range", data=[r for r in results_data["current_range"] if r is not None])

            group.attrs["created"] = datetime.now().isoformat()

    def start_single_step(
        self, current_setup: dict, measurement_settings: dict
    ) -> tuple[dict, float]:
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
        match self.plot_type:
            case "impedance_frequency":
                self.plot_templates.impedance_frequency(results, current_results, len_queue)
            case "nyquist":
                self.plot_templates.nyquist(results, current_results, len_queue)
            case _:
                self.plot_templates.bode(results, current_results, len_queue)

        plt.pause(0.01)

    def measurement(self, config_path: str | None = None) -> str | None:
        if not config_path:
            config_path = select_config_file()
            if not config_path:
                print("[INFO] Keine Konfigurationsdatei ausgewählt. Abbruch.")
                return None

        self.config_builder = ConfigBuilder(config_path)
        self.measurement_settings = self.config_builder.get_settings_from_config()
        self.measurement_queue = self.config_builder.generate_measurement_queue()
        self.plot_type = self.measurement_settings.get("plot_type", "bode")

        mux_enabled = bool(self.measurement_settings.get("mux_enabled", False))
        mux_mode = int(self.measurement_settings.get("mux_mode", 4))
        mux_chan = int(self.measurement_settings.get("channel", 2))
        raw_sensors = str(self.measurement_settings.get("active_sensors", "1-8"))
        switch_delay = float(self.measurement_settings.get("switch_delay_s", 0.10))

        main_fe_mode = int(self.measurement_settings.get("measurement_mode", 2))
        c_range = int(self.measurement_settings.get("current_range", 2))
        v_range = int(self.measurement_settings.get("voltage_range", 1))

        live_plot_enabled = bool(self.measurement_settings.get("live_plot_enabled", True))
        live_plot_mode = str(self.measurement_settings.get("live_plot_mode", "point")).strip().lower()

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

        mode_prefix = "MUX" if mux_enabled else "MAIN"
        h5_full_path = self.create_h5_file(mode_prefix=mode_prefix)
        self.save_measurement_settings(config_path, mux_enabled=mux_enabled)

        if not self.device.connect_device_fs(settings=self.measurement_settings):
            return None

        self.device.set_options(settings=self.measurement_settings)

        fe_mode = 2 if (mux_enabled and mux_mode == 4) else (1 if mux_enabled else main_fe_mode)
        fe_chan = mux_chan if mux_enabled else 1

        for step in self.measurement_queue:
            step["measurement_channel"] = fe_chan
            step["measurement_mode"] = fe_mode
            step["current_range"] = c_range
            step["voltage_range"] = v_range

        try:
            for sensor_idx in active_sensors:
                if mux_enabled:
                    print(f"\n==========================================")
                    print(f" Starte Sweep für MUX-Sensor #{sensor_idx}")
                    print(f"==========================================")
                    self.device.route_mux_sensor(sensor_idx=sensor_idx, wire_mode=mux_mode)
                    time.sleep(max(0.05, switch_delay))
                else:
                    self.device.active_mux_pins = None
                    print(f"\n--- Starte Messdurchlauf über MAIN PORT ---")

                self.current_results = []

                for idx, current_setup in enumerate(self.measurement_queue):
                    step_results, timestamp = self.start_single_step(
                        current_setup, self.measurement_settings
                    )

                    if not step_results.get("id"):
                        continue

                    self.save_measurement(
                        results_data=step_results,
                        timestamp=timestamp,
                        current_setup=current_setup,
                        icm=1,
                        sensor_idx=sensor_idx if mux_enabled else 0,
                    )

                    self.current_results.append(step_results)

                    if live_plot_enabled:
                        is_last_point = (idx == len(self.measurement_queue) - 1)
                        if live_plot_mode == "point" or is_last_point:
                            self.update_live_plot(
                                results=step_results,
                                current_setup=current_setup,
                                current_results=self.current_results,
                                len_queue=len(self.measurement_queue),
                            )

            print(f"\n[OK] Alle Messungen erfolgreich abgeschlossen. Datei: {h5_full_path}")

        except KeyboardInterrupt:
            print("\n[INFO] Messung manuell abgebrochen.")
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
        return h5_full_path