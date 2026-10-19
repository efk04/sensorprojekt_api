"""
config_handler.py - Konfigurationsparser und Mess-Queue-Generator für das ISX-3.
"""

import configparser
from dataclasses import asdict, dataclass
import numpy as np


@dataclass
class ApiSettingsConfig:
    plot_type: str
    continuous_measurement: bool


@dataclass
class ConnectionConfig:
    interface_type: str
    port: str
    baudrate: int
    ip_address: str
    tcp_port: int
    tcp_watchdog_interval_s: int


@dataclass
class OptionsConfig:
    timestamp_mode: int
    enable_current_range_output: bool


@dataclass
class FrontendConfig:
    measurement_mode: int
    measurement_channel: int
    current_range: int
    voltage_range: int
    hardware_scale_factor: float


@dataclass
class MuxConfig:
    enabled: bool
    mode: int
    active_sensors: str
    switch_delay_s: float


@dataclass
class CompensationConfig:
    enabled: bool
    open_file: str


@dataclass
class ExtensionPortConfig:
    counter_port: int
    reference_port: int
    working_sense_port: int
    working_port: int


@dataclass
class FrequencySetupConfig:
    mode: str
    frequency_hz: list[float]
    precision: float
    start_frequency_hz: float
    stop_frequency_hz: float
    count: int
    scale: str
    excitation_type: int
    amplitude: float
    point_delay_us: int
    phase_sync: bool


@dataclass
class DCBiasConfig:
    dc_bias_enabled: bool
    bias_voltage_v: float


@dataclass
class SyncTimeConfig:
    sync_time_us: int


@dataclass
class MeasurementConfig:
    number_of_spectra: int


@dataclass
class DeviceConfig:
    connection: ConnectionConfig
    options: OptionsConfig
    frontend: FrontendConfig
    mux: MuxConfig
    compensation: CompensationConfig
    extension_port: ExtensionPortConfig
    frequency_setup: FrequencySetupConfig
    dc_bias: DCBiasConfig
    sync_time: SyncTimeConfig
    measurement: MeasurementConfig


class ConfigParser:
    """Liest und validiert die ISX-3 INI-Konfigurationsdatei."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.parser = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
        self.parser.optionxform = str

    def _find_section(self, name: str) -> str:
        """Findet Sektionsnamen unabhängig von Groß-/Kleinschreibung."""
        for sec in self.parser.sections():
            if sec.lower() == name.lower():
                return sec
        return name

    def parse(self) -> DeviceConfig:
        if not self.parser.read(self.file_path, encoding="utf-8"):
            raise FileNotFoundError(f"Konfigurationsdatei '{self.file_path}' nicht gefunden.")

        return DeviceConfig(
            connection=self._parse_connection(),
            options=self._parse_options(),
            frontend=self._parse_frontend(),
            mux=self._parse_mux(),
            compensation=self._parse_compensation(),
            extension_port=self._parse_extension_port(),
            frequency_setup=self._parse_frequency_setup(),
            dc_bias=self._parse_dc_bias(),
            sync_time=self._parse_sync_time(),
            measurement=self._parse_measurement(),
        )

    def _parse_connection(self) -> ConnectionConfig:
        sec = self._find_section("Connection")
        return ConnectionConfig(
            interface_type=self.parser.get(sec, "interface_type", fallback="COM"),
            port=self.parser.get(sec, "port", fallback="COM12"),
            baudrate=self.parser.getint(sec, "baudrate", fallback=115200),
            ip_address=self.parser.get(sec, "ip_address", fallback="192.168.1.100"),
            tcp_port=self.parser.getint(sec, "tcp_port", fallback=8888),
            tcp_watchdog_interval_s=self.parser.getint(sec, "tcp_watchdog_interval_s", fallback=60),
        )

    def _parse_options(self) -> OptionsConfig:
        sec = self._find_section("Options")
        return OptionsConfig(
            timestamp_mode=self.parser.getint(sec, "timestamp_mode", fallback=0),
            enable_current_range_output=self.parser.getboolean(sec, "enable_current_range_output", fallback=False),
        )

    def _parse_frontend(self) -> FrontendConfig:
        sec = self._find_section("Frontend")
        return FrontendConfig(
            measurement_mode=self.parser.getint(sec, "measurement_mode", fallback=2),
            measurement_channel=self.parser.getint(sec, "measurement_channel", fallback=1),
            current_range=self.parser.getint(sec, "current_range", fallback=1),
            voltage_range=self.parser.getint(sec, "voltage_range", fallback=1),
            hardware_scale_factor=self.parser.getfloat(sec, "hardware_scale_factor", fallback=1.0),
        )

    def _parse_mux(self) -> MuxConfig:
        sec = self._find_section("MUX")
        return MuxConfig(
            enabled=self.parser.getboolean(sec, "enabled", fallback=False),
            mode=self.parser.getint(sec, "mode", fallback=4),
            active_sensors=self.parser.get(sec, "active_sensors", fallback="8"),
            switch_delay_s=self.parser.getfloat(sec, "switch_delay_s", fallback=0.05),
        )

    def _parse_compensation(self) -> CompensationConfig:
        sec = self._find_section("Compensation")
        return CompensationConfig(
            enabled=self.parser.getboolean(sec, "enabled", fallback=False),
            open_file=self.parser.get(sec, "open_file", fallback="calibration/open_calibration.h5"),
        )

    def _parse_extension_port(self) -> ExtensionPortConfig:
        sec = self._find_section("ExtensionPort")
        return ExtensionPortConfig(
            counter_port=self.parser.getint(sec, "counter_port", fallback=0),
            reference_port=self.parser.getint(sec, "reference_port", fallback=0),
            working_sense_port=self.parser.getint(sec, "working_sense_port", fallback=0),
            working_port=self.parser.getint(sec, "working_port", fallback=0),
        )

    def _parse_frequency_setup(self) -> FrequencySetupConfig:
        sec = self._find_section("FrequencySetup")
        raw_frequencies = self.parser.get(sec, "frequency_hz", fallback="1000.0")
        parsed_frequencies = [float(item.strip()) for item in raw_frequencies.split(",") if item.strip()]
        if not parsed_frequencies:
            parsed_frequencies = [1000.0]

        return FrequencySetupConfig(
            mode=self.parser.get(sec, "mode", fallback="sweep").strip().lower(),
            frequency_hz=parsed_frequencies,
            precision=self.parser.getfloat(sec, "precision", fallback=1.0),
            start_frequency_hz=self.parser.getfloat(sec, "start_frequency_hz", fallback=100.0),
            stop_frequency_hz=self.parser.getfloat(sec, "stop_frequency_hz", fallback=10000000.0),
            count=self.parser.getint(sec, "count", fallback=101),
            scale=self.parser.get(sec, "scale", fallback="logarithmic").strip().lower(),
            excitation_type=self.parser.getint(sec, "excitation_type", fallback=2),
            amplitude=self.parser.getfloat(sec, "amplitude", fallback=0.0001),
            point_delay_us=self.parser.getint(sec, "point_delay_us", fallback=0),
            phase_sync=self.parser.getboolean(sec, "phase_sync", fallback=False),
        )

    def _parse_dc_bias(self) -> DCBiasConfig:
        sec = self._find_section("DCBias")
        return DCBiasConfig(
            dc_bias_enabled=self.parser.getboolean(sec, "dc_bias_enabled", fallback=False),
            bias_voltage_v=self.parser.getfloat(sec, "bias_voltage_v", fallback=0.0),
        )

    def _parse_sync_time(self) -> SyncTimeConfig:
        sec = self._find_section("SyncTime")
        return SyncTimeConfig(
            sync_time_us=self.parser.getint(sec, "sync_time_us", fallback=0),
        )

    def _parse_measurement(self) -> MeasurementConfig:
        sec = self._find_section("Measurement")
        return MeasurementConfig(
            number_of_spectra=self.parser.getint(sec, "number_of_spectra", fallback=1),
        )

    def parse_as_dict(self) -> dict:
        return asdict(self.parse())

    def parse_as_flat_dict(self, use_prefix: bool = False) -> dict:
        nested_dict = self.parse_as_dict()
        flat_dict = {}
        for section, values in nested_dict.items():
            if isinstance(values, dict):
                for key, val in values.items():
                    if not use_prefix and section in ("mux", "compensation"):
                        flat_key = f"{section}_{key}"
                    else:
                        flat_key = f"{section}_{key}" if use_prefix else key
                    flat_dict[flat_key] = val
        return flat_dict

    def parse_api_settings(self) -> ApiSettingsConfig:
        if not self.parser.read(self.file_path, encoding="utf-8"):
            raise FileNotFoundError(f"Konfigurationsdatei '{self.file_path}' nicht gefunden.")
        sec = self._find_section("ApiSettings")
        return ApiSettingsConfig(
            plot_type=self.parser.get(sec, "plot_type", fallback="bode").strip().lower(),
            continuous_measurement=self.parser.getboolean(sec, "continuous_measurement", fallback=False),
        )


class ConfigBuilder:
    """Erzeugt aus den Konfigurationsparametern eine Liste sequenzieller Messpunkte."""

    def __init__(self, config_path: str = "config/config.ini"):
        self.parser = ConfigParser(config_path)
        self.measurement_setup_queue: list[dict] = []
        self.settings: dict = {}

    def get_settings_from_config(self) -> dict:
        self.settings = self.parser.parse_as_flat_dict(False)
        api_cfg = self.parser.parse_api_settings()
        self.settings["plot_type"] = api_cfg.plot_type
        self.settings["continuous_measurement"] = api_cfg.continuous_measurement
        return self.settings

    def generate_measurement_queue(self) -> list[dict]:
        self.measurement_setup_queue = []
        self.settings = self.get_settings_from_config()

        mode = str(self.settings.get("mode", "sweep")).strip().lower()
        scale = str(self.settings.get("scale", "logarithmic")).strip().lower()

        if mode == "single":
            frequency_queue_hz = list(self.settings.get("frequency_hz", [1000.0]))
        else:
            start_f = float(self.settings.get("start_frequency_hz", 100.0))
            stop_f = float(self.settings.get("stop_frequency_hz", 10000000.0))
            count = max(1, int(self.settings.get("count", 101)))

            if scale == "logarithmic":
                if start_f <= 0 or stop_f <= 0:
                    raise ValueError("Frequenzen für logarithmische Skalierung müssen > 0 Hz sein.")
                frequency_queue_hz = np.logspace(np.log10(start_f), np.log10(stop_f), count).tolist()
            else:
                frequency_queue_hz = np.linspace(start_f, stop_f, count).tolist()

        mux_enabled = bool(self.settings.get("mux_enabled", False))
        mux_mode = int(self.settings.get("mux_mode", 4))

        # WICHTIG: Wenn MUX aktiv -> Channel 2 (Extension Port).
        # Wenn MUX inaktiv -> IMMER Channel 1 (BNC Main Port) erzwingen!
        if mux_enabled:
            meas_mode = 2 if mux_mode == 4 else 1
            meas_chan = 2
        else:
            meas_mode = int(self.settings.get("measurement_mode", 2))
            meas_chan = 1

        self.settings["measurement_mode"] = meas_mode
        self.settings["measurement_channel"] = meas_chan

        for index, freq in enumerate(frequency_queue_hz):
            single_setup = {
                "id": index + 1,
                "timestamp_mode": int(self.settings.get("timestamp_mode", 0)),
                "enable_current_range_output": int(bool(self.settings.get("enable_current_range_output", False))),
                "measurement_mode": meas_mode,
                "measurement_channel": meas_chan,
                "current_range": int(self.settings.get("current_range", 1)),
                "voltage_range": int(self.settings.get("voltage_range", 1)),
                "hardware_scale_factor": float(self.settings.get("hardware_scale_factor", 1.0)),
                "counter_port": int(self.settings.get("counter_port", 0)),
                "reference_port": int(self.settings.get("reference_port", 0)),
                "working_sense_port": int(self.settings.get("working_sense_port", 0)),
                "working_port": int(self.settings.get("working_port", 0)),
                "mode": mode,
                "frequency": float(freq),
                "start_frequency_hz": float(self.settings.get("start_frequency_hz", 100.0)),
                "stop_frequency_hz": float(self.settings.get("stop_frequency_hz", 10000000.0)),
                "count": int(self.settings.get("count", 101)),
                "scale": scale,
                "precision": float(self.settings.get("precision", 1.0)),
                "amplitude": float(self.settings.get("amplitude", 0.0001)),
                "excitation_type": int(self.settings.get("excitation_type", 2)),
                "point_delay_us": int(self.settings.get("point_delay_us", 0)),
                "phase_sync": int(bool(self.settings.get("phase_sync", False))),
                "dc_bias_enabled": int(bool(self.settings.get("dc_bias_enabled", False))),
                "bias_voltage_v": float(self.settings.get("bias_voltage_v", 0.0)),
                "number_of_spectra": int(self.settings.get("number_of_spectra", 1)),
                "sync_time_us": int(self.settings.get("sync_time_us", 0)),
            }
            self.measurement_setup_queue.append(single_setup)

        return self.measurement_setup_queue


def select_config_file() -> str | None:
    from tkinter import Tk, filedialog
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    config_path = filedialog.askopenfilename(
        title="Messkonfiguration (.ini) auswählen",
        filetypes=[("INI-Dateien", "*.ini"), ("Alle Dateien", "*.*")],
    )
    root.destroy()
    return config_path or None