"""
config_handler.py - Konfigurationsparser und Mess-Queue-Generator für das ISX-3.

Liest INI-Konfigurationsdateien ein, validiert Parameter über typisierte Dataclasses
und berechnet die abzuarbeitende Sequenz von Messpunkten (Frequenz-Sweeps).
"""

import configparser
from dataclasses import asdict, dataclass
import numpy as np


# ==============================================================================
# Datenstrukturen für die einzelnen INI-Sektionen
# ==============================================================================

@dataclass
class ApiSettingsConfig:
    """API- und Darstellungseinstellungen (nicht Teil der Hardware-Konfiguration)."""
    plot_type: str
    continuous_measurement: bool


@dataclass
class ConnectionConfig:
    """Schnittstellenparameter für serielle oder Netzwerkverbindungen."""
    interface_type: str
    port: str
    baudrate: int
    ip_address: str
    tcp_port: int
    tcp_watchdog_interval_s: int


@dataclass
class OptionsConfig:
    """Zusatzoptionen für das Rückgabe-Frame-Format des ISX-3."""
    timestamp_mode: int  # 0 = Deaktiviert, 1 = ms, 2 = µs
    enable_current_range_output: bool


@dataclass
class FrontendConfig:
    """Analoge Frontend-Einstellungen (Messmodus, Messkanäle und Messbereiche)."""
    measurement_mode: int     # 1 = 2-Punkt, 2 = 4-Punkt, 3 = 3-Punkt
    measurement_channel: int  # Kanal-Index (z. B. 1 für Main Port)
    current_range: int        # Strommessbereich (Index/Gain)
    voltage_range: int        # Spannungsmessbereich (Index/Gain)


@dataclass
class ExtensionPortConfig:
    """Routing für optionale Sciospec-Multiplexer-Erweiterungsmodule."""
    counter_port: int
    reference_port: int
    working_sense_port: int
    working_port: int


@dataclass
class FrequencySetupConfig:
    """Parameter für Anregungssignale und Frequenz-Scanning."""
    mode: str                  # 'sweep' oder 'single'
    frequency_hz: list[float]  # Liste von Einzelfrequenzen bei mode='single'
    precision: float           # Messpräzision / Integrationsdauer
    start_frequency_hz: float  # Startfrequenz für Sweep in Hz
    stop_frequency_hz: float   # Stoppfrequenz für Sweep in Hz
    count: int                 # Anzahl der Frequenzpunkte
    scale: str                 # Skalierung: 'linear' oder 'logarithmic'
    excitation_type: int       # 1 = Spannung, 2 = Strom
    amplitude: float           # Signalamplitude (V oder A)
    point_delay_us: int        # Verzögerung zwischen Messpunkten in µs
    phase_sync: bool           # Phasensynchrones Umschalten


@dataclass
class DCBiasConfig:
    """DC-Offset (Gleichspannungsüberlagerung)."""
    dc_bias_enabled: bool
    bias_voltage_v: float      # Spannung in Volt (-1.0 V bis +1.0 V)


@dataclass
class SyncTimeConfig:
    """Pausenzeit zwischen zwei aufeinanderfolgenden Spektren."""
    sync_time_us: int          # Wartezeit in Mikrosekunden


@dataclass
class MeasurementConfig:
    """Globale Messwiederholungen."""
    number_of_spectra: int     # 0 = kontinuierlich, >= 1 = diskrete Zyklenanzahl


@dataclass
class DeviceConfig:
    """Gesamte Hardware- und Messkonfiguration."""
    connection: ConnectionConfig
    options: OptionsConfig
    frontend: FrontendConfig
    extension_port: ExtensionPortConfig
    frequency_setup: FrequencySetupConfig
    dc_bias: DCBiasConfig
    sync_time: SyncTimeConfig
    measurement: MeasurementConfig


# ==============================================================================
# Parser-Klasse
# ==============================================================================

class ConfigParser:
    """Liest und validiert die ISX-3 INI-Konfigurationsdatei."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.parser = configparser.ConfigParser()
        # Behält die exakte Groß-/Kleinschreibung der Schlüssel bei
        self.parser.optionxform = str

    def parse(self) -> DeviceConfig:
        """Liest die Konfiguration ein und gibt ein typisiertes DeviceConfig-Objekt zurück."""
        if not self.parser.read(self.file_path, encoding="utf-8"):
            raise FileNotFoundError(f"Die Konfigurationsdatei '{self.file_path}' konnte nicht gelesen werden.")

        return DeviceConfig(
            connection=self._parse_connection(),
            options=self._parse_options(),
            frontend=self._parse_frontend(),
            extension_port=self._parse_extension_port(),
            frequency_setup=self._parse_frequency_setup(),
            dc_bias=self._parse_dc_bias(),
            sync_time=self._parse_sync_time(),
            measurement=self._parse_measurement(),
        )

    def _parse_connection(self) -> ConnectionConfig:
        sec = "Connection"
        return ConnectionConfig(
            interface_type=self.parser.get(sec, "interface_type", fallback="COM"),
            port=self.parser.get(sec, "port", fallback="COM3"),
            baudrate=self.parser.getint(sec, "baudrate", fallback=115200),
            ip_address=self.parser.get(sec, "ip_address", fallback="192.168.1.100"),
            tcp_port=self.parser.getint(sec, "tcp_port", fallback=8888),
            tcp_watchdog_interval_s=self.parser.getint(sec, "tcp_watchdog_interval_s", fallback=60),
        )

    def _parse_options(self) -> OptionsConfig:
        sec = "Options"
        return OptionsConfig(
            timestamp_mode=self.parser.getint(sec, "timestamp_mode", fallback=0),
            enable_current_range_output=self.parser.getboolean(sec, "enable_current_range_output", fallback=False),
        )

    def _parse_frontend(self) -> FrontendConfig:
        sec = "Frontend"
        return FrontendConfig(
            measurement_mode=self.parser.getint(sec, "measurement_mode", fallback=1),
            measurement_channel=self.parser.getint(sec, "measurement_channel", fallback=1),
            current_range=self.parser.getint(sec, "current_range", fallback=0),
            voltage_range=self.parser.getint(sec, "voltage_range", fallback=1),
        )

    def _parse_extension_port(self) -> ExtensionPortConfig:
        sec = "ExtensionPort"
        return ExtensionPortConfig(
            counter_port=self.parser.getint(sec, "counter_port", fallback=0),
            reference_port=self.parser.getint(sec, "reference_port", fallback=0),
            working_sense_port=self.parser.getint(sec, "working_sense_port", fallback=0),
            working_port=self.parser.getint(sec, "working_port", fallback=0),
        )

    def _parse_frequency_setup(self) -> FrequencySetupConfig:
        sec = "FrequencySetup"
        raw_frequencies = self.parser.get(sec, "frequency_hz", fallback="1000.0")
        
        # Bereinigt Leerzeichen und ignoriert leere Split-Elemente
        parsed_frequencies = [
            float(item.strip()) for item in raw_frequencies.split(",") if item.strip()
        ]
        if not parsed_frequencies:
            parsed_frequencies = [1000.0]

        return FrequencySetupConfig(
            mode=self.parser.get(sec, "mode", fallback="sweep").strip().lower(),
            frequency_hz=parsed_frequencies,
            precision=self.parser.getfloat(sec, "precision", fallback=1.0),
            start_frequency_hz=self.parser.getfloat(sec, "start_frequency_hz", fallback=100.0),
            stop_frequency_hz=self.parser.getfloat(sec, "stop_frequency_hz", fallback=100000.0),
            count=self.parser.getint(sec, "count", fallback=10),
            scale=self.parser.get(sec, "scale", fallback="linear").strip().lower(),
            excitation_type=self.parser.getint(sec, "excitation_type", fallback=1),
            amplitude=self.parser.getfloat(sec, "amplitude", fallback=0.01),
            point_delay_us=self.parser.getint(sec, "point_delay_us", fallback=0),
            phase_sync=self.parser.getboolean(sec, "phase_sync", fallback=False),
        )

    def _parse_dc_bias(self) -> DCBiasConfig:
        sec = "DCBias"
        return DCBiasConfig(
            dc_bias_enabled=self.parser.getboolean(sec, "dc_bias_enabled", fallback=False),
            bias_voltage_v=self.parser.getfloat(sec, "bias_voltage_v", fallback=0.0),
        )

    def _parse_sync_time(self) -> SyncTimeConfig:
        sec = "SyncTime"
        return SyncTimeConfig(
            sync_time_us=self.parser.getint(sec, "sync_time_us", fallback=0),
        )

    def _parse_measurement(self) -> MeasurementConfig:
        sec = "Measurement"
        return MeasurementConfig(
            number_of_spectra=self.parser.getint(sec, "number_of_spectra", fallback=1),
        )

    def parse_as_dict(self) -> dict:
        """Gibt die gesamte Gerätekonfiguration als verschachteltes Dictionary zurück."""
        return asdict(self.parse())

    def parse_as_flat_dict(self, use_prefix: bool = False) -> dict:
        """
        Wandelt die Konfiguration in ein einstufiges flaches Dictionary um.
        
        :param use_prefix: Wenn True, erhalten Schlüssel den Sektionsnamen (z. B. 'Frontend_current_range').
        """
        nested_dict = self.parse_as_dict()
        flat_dict = {}

        for section, values in nested_dict.items():
            if isinstance(values, dict):
                for key, val in values.items():
                    flat_key = f"{section}_{key}" if use_prefix else key
                    flat_dict[flat_key] = val

        return flat_dict

    def parse_api_settings(self) -> ApiSettingsConfig:
        """Liest separate Anwendungseinstellungen für Plot und Loop-Verhalten aus."""
        if not self.parser.read(self.file_path, encoding="utf-8"):
            raise FileNotFoundError(f"Die Konfigurationsdatei '{self.file_path}' konnte nicht gelesen werden.")

        sec = "ApiSettings"
        return ApiSettingsConfig(
            plot_type=self.parser.get(sec, "plot_type", fallback="bode").strip().lower(),
            continuous_measurement=self.parser.getboolean(sec, "continuous_measurement", fallback=False),
        )


# ==============================================================================
# Builder-Klasse für Messschritte
# ==============================================================================

class ConfigBuilder:
    """Erzeugt aus den Konfigurationsparametern eine Liste sequenzieller Messpunkte."""

    def __init__(self, config_path: str = "config/config.ini"):
        self.parser = ConfigParser(config_path)
        self.measurement_setup_queue: list[dict] = []
        self.settings: dict = {}

    def get_settings_from_config(self) -> dict:
        """Liefert das flache Dictionary aller Einstellungen."""
        return self.parser.parse_as_flat_dict(False)

    def generate_measurement_queue(self) -> list[dict]:
        """
        Berechnet die auszuführenden Frequenzen und erzeugt die Setup-Warteschlange.

        :return: Liste von Dictionaries, wobei jedes Dictionary einen Messschritt definiert.
        """
        self.measurement_setup_queue = []
        self.settings = self.parser.parse_as_flat_dict(False)

        mode = str(self.settings.get("mode", "sweep")).strip().lower()
        scale = str(self.settings.get("scale", "linear")).strip().lower()

        # Frequenzstützstellen ermitteln
        if mode == "single":
            frequency_queue_hz = list(self.settings.get("frequency_hz", [1000.0]))
        else:
            # Fallback: sweep
            start_f = float(self.settings.get("start_frequency_hz", 100.0))
            stop_f = float(self.settings.get("stop_frequency_hz", 100000.0))
            count = max(1, int(self.settings.get("count", 10)))

            if scale == "logarithmic":
                if start_f <= 0 or stop_f <= 0:
                    raise ValueError("Frequenzen für logarithmische Skalierung müssen größer als 0 Hz sein.")
                frequency_queue_hz = np.logspace(np.log10(start_f), np.log10(stop_f), count).tolist()
            else:
                frequency_queue_hz = np.linspace(start_f, stop_f, count).tolist()

        # Für jeden Frequenzpunkt ein vollständiges Setup-Paket schnüren
        for index, freq in enumerate(frequency_queue_hz):
            single_setup = {
                "id": index + 1,
                "timestamp_mode": int(self.settings.get("timestamp_mode", 0)),
                "enable_current_range_output": int(bool(self.settings.get("enable_current_range_output", False))),
                "measurement_mode": int(self.settings.get("measurement_mode", 1)),
                "measurement_channel": int(self.settings.get("measurement_channel", 1)),
                "current_range": int(self.settings.get("current_range", 0)),
                "voltage_range": int(self.settings.get("voltage_range", 1)),
                "counter_port": int(self.settings.get("counter_port", 0)),
                "reference_port": int(self.settings.get("reference_port", 0)),
                "working_sense_port": int(self.settings.get("working_sense_port", 0)),
                "working_port": int(self.settings.get("working_port", 0)),
                "mode": mode,
                "frequency": float(freq),
                "start_frequency_hz": float(self.settings.get("start_frequency_hz", 100.0)),
                "stop_frequency_hz": float(self.settings.get("stop_frequency_hz", 100000.0)),
                "count": int(self.settings.get("count", 10)),
                "scale": scale,
                "precision": float(self.settings.get("precision", 1.0)),
                "amplitude": float(self.settings.get("amplitude", 0.01)),
                "excitation_type": int(self.settings.get("excitation_type", 1)),
                "point_delay_us": int(self.settings.get("point_delay_us", 0)),
                "phase_sync": int(bool(self.settings.get("phase_sync", False))),
                "dc_bias_enabled": int(bool(self.settings.get("dc_bias_enabled", False))),
                "bias_voltage_v": float(self.settings.get("bias_voltage_v", 0.0)),
                "number_of_spectra": int(self.settings.get("number_of_spectra", 1)),
                "sync_time_us": int(self.settings.get("sync_time_us", 0)),
            }
            self.measurement_setup_queue.append(single_setup)

        return self.measurement_setup_queue


# ==============================================================================
# UI-Hilfsfunktion
# ==============================================================================

def select_config_file() -> str | None:
    """
    Öffnet einen modalen Datei-Auswahldialog zur Selektion der INI-Konfigurationsdatei.

    :return: Dateipfad als String oder None, falls der Nutzer abgebrochen hat.
    """
    from tkinter import Tk, filedialog

    # Unsichtbares Hauptfenster instanziieren, um den Dialog im Vordergrund zu halten
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    config_path = filedialog.askopenfilename(
        title="Messkonfiguration (.ini) auswählen",
        filetypes=[("INI-Dateien", "*.ini"), ("Alle Dateien", "*.*")],
    )
    root.destroy()

    return config_path or None

