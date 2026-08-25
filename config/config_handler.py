import configparser
from dataclasses import asdict, dataclass

# ==============================================================================
# Datenstrukturen für die verschiedenen Konfigurations-Bereiche
# ==============================================================================

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

@dataclass
class ExtensionPortConfig:
    counter_port: int
    reference_port: int
    working_sense_port: int
    working_port: int

@dataclass
class FrequencySetupConfig:
    mode: str
    frequency_hz: float
    precision: float
    start_frequency_hz: float
    stop_frequency_hz: float
    count: int
    scale: int
    excitation_type: int
    amplitude: float
    point_delay_us: int
    phase_sync: bool

@dataclass
class DCBiasConfig:
    enabled: bool
    bias_voltage_v: float

@dataclass
class SyncTimeConfig:
    sync_time_us: int

@dataclass
class MeasurementConfig:
    number_of_spectra: int

@dataclass
class ISX3DeviceConfig:
    connection: ConnectionConfig
    options: OptionsConfig
    frontend: FrontendConfig
    extension_port: ExtensionPortConfig
    frequency_setup: FrequencySetupConfig
    dc_bias: DCBiasConfig
    sync_time: SyncTimeConfig
    measurement: MeasurementConfig


# ==============================================================================
# Parser Klasse
# ==============================================================================

class ISX3ConfigParser:
    """
    Parser für die Sciospec ISX-3 / ISX-3mini Geräte-Konfigurationsdatei.
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.parser = configparser.ConfigParser()
        # Verhindert, dass ConfigParser alle Keys automatisch klein schreibt
        self.parser.optionxform = str 
        
    def parse(self) -> ISX3DeviceConfig:
        """Liest die Datei ein und gibt ein typisiertes Konfigurationsobjekt zurück."""
        # Lese die INI Datei
        if not self.parser.read(self.file_path, encoding='utf-8'):
            raise FileNotFoundError(f"Die Konfigurationsdatei '{self.file_path}' konnte nicht gefunden/gelesen werden.")

        return ISX3DeviceConfig(
            connection=self._parse_connection(),
            options=self._parse_options(),
            frontend=self._parse_frontend(),
            extension_port=self._parse_extension_port(),
            frequency_setup=self._parse_frequency_setup(),
            dc_bias=self._parse_dc_bias(),
            sync_time=self._parse_sync_time(),
            measurement=self._parse_measurement()
        )

    def _parse_connection(self) -> ConnectionConfig:
        sec = 'Connection'
        return ConnectionConfig(
            interface_type=self.parser.get(sec, 'interface_type', fallback='COM'),
            port=self.parser.get(sec, 'port', fallback='COM1'),
            baudrate=self.parser.getint(sec, 'baudrate', fallback=115200),
            ip_address=self.parser.get(sec, 'ip_address', fallback='192.168.1.100'),
            tcp_port=self.parser.getint(sec, 'tcp_port', fallback=8888),
            tcp_watchdog_interval_s=self.parser.getint(sec, 'tcp_watchdog_interval_s', fallback=60)
        )

    def _parse_options(self) -> OptionsConfig:
        sec = 'Options'
        return OptionsConfig(
            timestamp_mode=self.parser.getint(sec, 'timestamp_mode', fallback=0),
            enable_current_range_output=self.parser.getboolean(sec, 'enable_current_range_output', fallback=False)
        )

    def _parse_frontend(self) -> FrontendConfig:
        sec = 'Frontend'
        return FrontendConfig(
            measurement_mode=self.parser.getint(sec, 'measurement_mode', fallback=1),
            measurement_channel=self.parser.getint(sec, 'measurement_channel', fallback=1),
            current_range=self.parser.getint(sec, 'current_range', fallback=0),
            voltage_range=self.parser.getint(sec, 'voltage_range', fallback=1)
        )

    def _parse_extension_port(self) -> ExtensionPortConfig:
        sec = 'ExtensionPort'
        return ExtensionPortConfig(
            counter_port=self.parser.getint(sec, 'counter_port', fallback=0),
            reference_port=self.parser.getint(sec, 'reference_port', fallback=0),
            working_sense_port=self.parser.getint(sec, 'working_sense_port', fallback=0),
            working_port=self.parser.getint(sec, 'working_port', fallback=0)
        )

    def _parse_frequency_setup(self) -> FrequencySetupConfig:
        sec = 'FrequencySetup'
        return FrequencySetupConfig(
            mode=self.parser.get(sec, 'mode', fallback='sweep'),
            frequency_hz=self.parser.getfloat(sec, 'frequency_hz', fallback=1000.0),
            precision=self.parser.getfloat(sec, 'precision', fallback=1.0),
            start_frequency_hz=self.parser.getfloat(sec, 'start_frequency_hz', fallback=100.0),
            stop_frequency_hz=self.parser.getfloat(sec, 'stop_frequency_hz', fallback=100000.0),
            count=self.parser.getint(sec, 'count', fallback=10),
            scale=self.parser.getint(sec, 'scale', fallback=1),
            excitation_type=self.parser.getint(sec, 'excitation_type', fallback=1),
            amplitude=self.parser.getfloat(sec, 'amplitude', fallback=0.01),
            point_delay_us=self.parser.getint(sec, 'point_delay_us', fallback=0),
            phase_sync=self.parser.getboolean(sec, 'phase_sync', fallback=False)
        )

    def _parse_dc_bias(self) -> DCBiasConfig:
        sec = 'DCBias'
        return DCBiasConfig(
            enabled=self.parser.getboolean(sec, 'enabled', fallback=False),
            bias_voltage_v=self.parser.getfloat(sec, 'bias_voltage_v', fallback=0.0)
        )

    def _parse_sync_time(self) -> SyncTimeConfig:
        sec = 'SyncTime'
        return SyncTimeConfig(
            sync_time_us=self.parser.getint(sec, 'sync_time_us', fallback=0)
        )

    def _parse_measurement(self) -> MeasurementConfig:
        sec = 'Measurement'
        return MeasurementConfig(
            number_of_spectra=self.parser.getint(sec, 'number_of_spectra', fallback=1)
        )

    def parse_as_dict(self) -> dict:
        """Parses the config and returns a nested dictionary of all values."""
        config_object = self.parse()
        return asdict(config_object)

    def parse_as_flat_dict(self, use_prefix: bool = False) -> dict:
        """
        Parses the config and returns a single-level (flattened) dictionary.
        :param use_prefix: If True, keys become 'section_key' (e.g., 'connection_baudrate').
                           If False, keys are left as-is (e.g., 'baudrate').
        """
        nested_dict = self.parse_as_dict()
        flat_dict = {}
        
        for section, values in nested_dict.items():
            if isinstance(values, dict):
                for key, val in values.items():
                    flat_key = f"{section}_{key}" if use_prefix else key
                    flat_dict[flat_key] = val
                    
        return flat_dict