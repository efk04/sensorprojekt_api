"""
measurement.py - Zentraler Messungs-Orchestrator fuer das Sciospec ISX-3.

Steuert den Ablauf von Einzel- und Sweep-Messungen, verwaltet die Live-Visualisierung
und speichert saemtliche Messdaten sowie Metadaten im HDF5-Format.
"""

from datetime import datetime
import os
import re
import time
import configparser
import h5py
import matplotlib.pyplot as plt

from .commands import ISX3
from .config_handler import ConfigBuilder, select_config_file
from .plot_templates import PlotTemplates


def parse_mux_sensor_expression(raw_sensors: str) -> tuple[list[int], dict[int, tuple | list[tuple]]]:
    """
    Parst komplexe MUX-Sensoreingaben.
    Unterstuetzt:
    1. Elektroden-Gruppen (Multi-Pin Ganging):
       '1: CE:1,5,9, RE:2,6,10, WS:3,7,11, WE:4,8,12'
       (Mehrere Sensoren koennen mit ';' getrennt werden)
    2. Einfache Custom-Pins mit Doppelpunkt:
       '1: 2,5,8,6; 2: 22,22,23,23'
    3. Standard-Bereiche und Listen:
       '1-8' oder '1, 3, 5'
    """
    active_sensors: list[int] = []
    custom_sensor_pins_map: dict[int, tuple | list[tuple]] = {}

    # Pruefen, ob benannte Elektroden (CE, RE, WS, WE) enthalten sind
    if any(lbl in raw_sensors.upper() for lbl in ("CE", "RE", "WS", "WE")):
        blocks = [b.strip() for b in raw_sensors.split(";") if b.strip()]
        for blk in blocks:
            m_head = re.match(r"^(\d+)\s*[:=]\s*(.+)$", blk)
            if m_head and any(lbl in m_head.group(2).upper() for lbl in ("CE", "RE", "WS", "WE")):
                s_id = int(m_head.group(1))
                rest = m_head.group(2)
            else:
                s_id = 1
                rest = blk

            role_matches = list(re.finditer(r"\b(CE|RE|WS|WE)\s*[:=]\s*([0-9,\s\-]+)", rest, flags=re.IGNORECASE))
            role_pins: dict[str, list[int]] = {}
            for rm in role_matches:
                role = rm.group(1).upper()
                val_str = rm.group(2)
                pins: list[int] = []
                for token in val_str.split(","):
                    t = token.strip()
                    if not t:
                        continue
                    if "-" in t:
                        a, b = t.split("-", 1)
                        if a.strip().isdigit() and b.strip().isdigit():
                            pins.extend(range(int(a), int(b) + 1))
                    elif t.isdigit():
                        pins.append(int(t))
                if pins:
                    role_pins[role] = pins

            if role_pins:
                ce_l = role_pins.get("CE", role_pins.get("RE", [1]))
                re_l = role_pins.get("RE", ce_l)
                we_l = role_pins.get("WE", role_pins.get("WS", [2]))
                ws_l = role_pins.get("WS", we_l)

                max_len = max(len(ce_l), len(re_l), len(ws_l), len(we_l))
                pin_tuples = []
                for i in range(max_len):
                    c_p = ce_l[i] if i < len(ce_l) else ce_l[-1]
                    r_p = re_l[i] if i < len(re_l) else re_l[-1]
                    s_p = ws_l[i] if i < len(ws_l) else ws_l[-1]
                    w_p = we_l[i] if i < len(we_l) else we_l[-1]
                    pin_tuples.append((c_p, r_p, s_p, w_p))

                custom_sensor_pins_map[s_id] = pin_tuples if len(pin_tuples) > 1 else pin_tuples[0]
                if s_id not in active_sensors:
                    active_sensors.append(s_id)
        return active_sensors, custom_sensor_pins_map

    # Klassische Custom-Pins (z.B. '1: 2,5,8,6') oder gemischte ';' Bloecke
    if ":" in raw_sensors or "=" in raw_sensors:
        pattern = re.compile(r"(\d+)\s*[:=]\s*(\d+(?:\s*,\s*\d+){1,3})")
        for match in pattern.finditer(raw_sensors):
            s_id = int(match.group(1).strip())
            pins = [int(p.strip()) for p in match.group(2).split(",") if p.strip().isdigit()]
            if len(pins) == 4:
                custom_sensor_pins_map[s_id] = tuple(pins)
                if s_id not in active_sensors:
                    active_sensors.append(s_id)
            elif len(pins) == 2:
                custom_sensor_pins_map[s_id] = (pins[0], pins[0], pins[1], pins[1])
                if s_id not in active_sensors:
                    active_sensors.append(s_id)
        return active_sensors, custom_sensor_pins_map

    # Standard-Bereiche wie '1-2' oder '1,3'
    for part in raw_sensors.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            active_sensors.extend(range(int(start_s), int(end_s) + 1))
        elif part.isdigit():
            active_sensors.append(int(part))

    return active_sensors, custom_sensor_pins_map


class Measurement:
    """Steuert den gesamten Ablauf einer Impedanz-Messkampagne."""

    def __init__(self):
        self.device = ISX3()
        self.config_builder = None
        self.plot_templates = PlotTemplates()

        self.filename = ""
        self.plot_type = "bode"
        self.measurement_settings = {}
        self.measurement_queue = []
        self.current_results = []
        self.manual_stop = False

        # Interaktiven Plot-Modus aktivieren
        plt.ion()
        plt.rcParams["keymap.quit"] = []

    def create_h5_file(self, mode_prefix: str = "MAIN") -> str:
        """Erstellt eine leere HDF5-Messdatei im Ordner 'measurements/'."""
        os.makedirs("measurements", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.filename = f"measurement_{mode_prefix}_{timestamp}.h5"
        full_path = os.path.join("measurements", self.filename)

        with h5py.File(full_path, "w"):
            pass

        print(f"[OK] HDF5-Messdatei erstellt: {full_path}")
        return full_path

    def save_measurement_settings(
        self, config_path: str, mux_enabled: bool = False, device_version: str = "standard"
    ) -> None:
        """Sichert die gesamte INI-Konfiguration als HDF5-Gruppe Configuration."""
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
            config_group.attrs["device_version"] = device_version

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
        """Speichert Realteil, Imaginaerteil, Frequenz und Zeitstempel in HDF5."""
        if not results_data.get("id"):
            raise ValueError("Keine gueltigen Messdaten zum Speichern vorhanden.")

        current_id = f"{icm}.{current_setup['id']}"
        if sensor_idx > 0:
            group_name = f"Sensor_{sensor_idx}/Measurement_{current_id}"
        else:
            group_name = f"Measurement_{current_id}"

        full_path = os.path.join("measurements", self.filename)

        with h5py.File(full_path, "a") as h5_file:
            group = h5_file.require_group(group_name)

            if "timestamp" in group:
                group["timestamp"][...] = timestamp
            else:
                group.create_dataset("timestamp", data=timestamp)

            if "frequency" in group:
                group["frequency"][...] = float(current_setup["frequency"])
            else:
                group.create_dataset("frequency", data=float(current_setup["frequency"]))

            if "frequency_id" in group:
                group["frequency_id"][...] = results_data["id"]
            else:
                group.create_dataset("frequency_id", data=results_data["id"])

            if "real_part" in group:
                group["real_part"][...] = results_data["real"]
            else:
                group.create_dataset("real_part", data=results_data["real"])

            if "imaginary_part" in group:
                group["imaginary_part"][...] = results_data["imag"]
            else:
                group.create_dataset("imaginary_part", data=results_data["imag"])

            # Hardware-Zeitstempel (Befehl 0x97) sichern
            hw_ts_list = [t for t in results_data.get("timestamp", []) if t is not None]
            if hw_ts_list:
                if "hw_timestamp" in group:
                    group["hw_timestamp"][...] = hw_ts_list
                else:
                    ds_ts = group.create_dataset("hw_timestamp", data=hw_ts_list)
                    units = [u for u in results_data.get("timestamp_unit", []) if u is not None]
                    ds_ts.attrs["unit"] = units[0] if units else "unknown"

            # Current-Range Rueckmeldung sichern
            cr_data = [r for r in results_data.get("current_range", []) if r is not None]
            if cr_data:
                if "current_range" in group:
                    group["current_range"][...] = cr_data
                else:
                    group.create_dataset("current_range", data=cr_data)

            group.attrs["created"] = datetime.now().isoformat()

    def start_single_step(
        self, current_setup: dict, measurement_settings: dict
    ) -> tuple[dict, float]:
        """Fuehrt eine einzelne Punktmessung aus."""
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
        """Aktualisiert die Diagrammansicht."""
        match self.plot_type:
            case "impedance_frequency":
                self.plot_templates.impedance_frequency(results, current_results, len_queue)
            case "nyquist":
                self.plot_templates.nyquist(results, current_results, len_queue)
            case "bode_lin":
                self.plot_templates.bode(results, current_results, len_queue, linear_y=True)
            case _:
                self.plot_templates.bode(results, current_results, len_queue, linear_y=False)

        plt.pause(0.01)

    def measurement(self, config_path: str | None = None) -> str | None:
        """Hauptmethode: Fuehrt den gesamten Messzyklus aus."""
        if not config_path:
            config_path = select_config_file()
            if not config_path:
                print("[INFO] Keine Konfigurationsdatei ausgewaehlt. Abbruch.")
                return None

        self.config_builder = ConfigBuilder(config_path)
        self.measurement_settings = self.config_builder.get_settings_from_config()
        self.measurement_queue = self.config_builder.generate_measurement_queue()
        self.plot_type = self.measurement_settings.get("plot_type", "bode")

        device_version = str(self.measurement_settings.get("device_version", "standard")).strip().lower()
        freq_mode = str(self.measurement_settings.get("mode", "sweep")).strip().lower()

        mux_enabled = bool(self.measurement_settings.get("mux_enabled", False))
        mux_mode = int(self.measurement_settings.get("mux_mode", 4))
        mux_chan = int(self.measurement_settings.get("mux_channel", 2))
        raw_sensors = str(self.measurement_settings.get("mux_active_sensors", "1-8"))
        switch_delay = float(self.measurement_settings.get("mux_switch_delay_s", 0.10))

        main_fe_mode = int(self.measurement_settings.get("measurement_mode", 2))
        c_range = int(self.measurement_settings.get("current_range", 2))
        v_range = int(self.measurement_settings.get("voltage_range", 1))
        if v_range not in (1, 2):
            v_range = 1

        live_plot_enabled = bool(self.measurement_settings.get("live_plot_enabled", True))
        live_plot_mode = str(self.measurement_settings.get("live_plot_mode", "point")).strip().lower()

        if mux_enabled:
            active_sensors, custom_sensor_pins_map = parse_mux_sensor_expression(raw_sensors)
        else:
            active_sensors = [0]
            custom_sensor_pins_map = {}

        mode_prefix = "MUX" if mux_enabled else "MAIN"
        h5_full_path = self.create_h5_file(mode_prefix=mode_prefix)
        self.save_measurement_settings(
            config_path, mux_enabled=mux_enabled, device_version=device_version
        )

        if not self.device.connect_device_fs(settings=self.measurement_settings):
            return None

        self.device.set_options(settings=self.measurement_settings)

        fe_mode = 2 if (mux_enabled and mux_mode == 4) else (1 if mux_enabled else main_fe_mode)
        fe_chan = mux_chan if mux_enabled else 1

        for step in self.measurement_queue:
            step["device_version"] = device_version
            step["measurement_channel"] = fe_chan
            step["measurement_mode"] = fe_mode
            step["current_range"] = c_range
            step["voltage_range"] = v_range

        try:
            for sensor_idx in active_sensors:
                t_start = time.time()

                if mux_enabled:
                    print(f"\n==========================================")
                    print(f" Starte Messung ({freq_mode.upper()}) fuer MUX-Sensor #{sensor_idx} [{device_version.upper()}]")
                    print(f"==========================================")
                    c_pins = custom_sensor_pins_map.get(sensor_idx)
                    self.device.route_mux_sensor(sensor_idx=sensor_idx, wire_mode=mux_mode, custom_pins=c_pins)
                    time.sleep(max(0.05, switch_delay))
                else:
                    self.device.active_mux_pins = None
                    print(f"\n--- Starte Messdurchlauf ({freq_mode.upper()}) ueber MAIN PORT [{device_version.upper()}] ---")

                self.current_results = []

                if freq_mode == "sweep" and len(self.measurement_queue) > 1:
                    blocks = self.config_builder.parse_frequency_blocks()
                    total_count = len(self.measurement_queue)
                    number_of_spectra = int(self.measurement_queue[0]["number_of_spectra"])

                    self.device.configure_hardware_sweep(
                        blocks=blocks,
                        global_settings=self.measurement_settings,
                        switch_delay_s=switch_delay,
                    )

                    total_expected_frames = total_count * number_of_spectra
                    timestamp = time.time()

                    raw_sweep_data = self.device.start_measurement(
                        spectra=number_of_spectra,
                        id=1,
                        measurement_settings=self.measurement_settings,
                        expected_frames=total_expected_frames,
                    )

                    for pt_idx, step_setup in enumerate(self.measurement_queue):
                        indices = [spec_i * total_count + pt_idx for spec_i in range(number_of_spectra)]
                        valid_indices = [i for i in indices if i < len(raw_sweep_data.get("id", []))]
                        if not valid_indices:
                            continue

                        freq_val = float(step_setup["frequency"])
                        point_results = {
                            "id": [raw_sweep_data["id"][i] for i in valid_indices],
                            "real": [raw_sweep_data["real"][i] for i in valid_indices],
                            "imag": [raw_sweep_data["imag"][i] for i in valid_indices],
                            "timestamp": [raw_sweep_data["timestamp"][i] for i in valid_indices],
                            "timestamp_unit": [raw_sweep_data["timestamp_unit"][i] for i in valid_indices],
                            "current_range": [raw_sweep_data["current_range"][i] for i in valid_indices],
                            "frequencies": [freq_val] * len(valid_indices),
                        }

                        self.save_measurement(
                            results_data=point_results,
                            timestamp=timestamp,
                            current_setup=step_setup,
                            icm=1,
                            sensor_idx=sensor_idx if mux_enabled else 0,
                        )
                        self.current_results.append(point_results)

                        if live_plot_enabled:
                            is_last_point = (pt_idx == len(self.measurement_queue) - 1)
                            if live_plot_mode == "point" or is_last_point:
                                self.update_live_plot(
                                    results=point_results,
                                    current_setup=step_setup,
                                    current_results=self.current_results,
                                    len_queue=len(self.measurement_queue),
                                )
                else:
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

                t_end = time.time()
                duration_ms = (t_end - t_start) * 1000.0

                full_path = os.path.join("measurements", self.filename)
                with h5py.File(full_path, "a") as h5_file:
                    group_key = f"Sensor_{sensor_idx}" if mux_enabled else "Measurement"
                    grp = h5_file.require_group(group_key)
                    grp.attrs["measurement_duration_ms"] = duration_ms

                print(f"[INFO] Sensor #{sensor_idx} abgeschlossen. Reale API-Messzeit: {duration_ms:.2f} ms")

            print(f"\n[OK] Alle Messungen erfolgreich abgeschlossen. Datei: {h5_full_path}")

        except KeyboardInterrupt:
            print("\n[INFO] Messung manuell abgebrochen.")
        finally:
            if self.device:
                try:
                    self.device.stop_measurement()
                except Exception:
                    pass
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