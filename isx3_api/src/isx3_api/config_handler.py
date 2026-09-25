import configparser
import numpy as np
from dataclasses import asdict, dataclass

# ==============================================================================
# Datenstrukturen für die verschiedenen Konfigurations-Bereiche
# ==============================================================================

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
    extension_port: ExtensionPortConfig
    frequency_setup: FrequencySetupConfig
    dc_bias: DCBiasConfig
    sync_time: SyncTimeConfig
    measurement: MeasurementConfig



class ConfigParser:
    """
    Parser für die Sciospec ISX-3 / ISX-3mini Geräte-Konfigurationsdatei.
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.parser = configparser.ConfigParser()
        # Verhindert, dass ConfigParser alle Keys automatisch klein schreibt
        self.parser.optionxform = str 
        
    def parse(self) -> DeviceConfig:
        """Liest die Datei ein und gibt ein typisiertes Konfigurationsobjekt zurück."""
        # Lese die INI Datei
        if not self.parser.read(self.file_path, encoding='utf-8'):
            raise FileNotFoundError(f"Die Konfigurationsdatei '{self.file_path}' konnte nicht gefunden/gelesen werden.")

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
            frequency_hz=[float(f) for f in self.parser.get(sec, 'frequency_hz', fallback='1000.0').split(',')],
            precision=self.parser.getfloat(sec, 'precision', fallback=1.0),
            start_frequency_hz=self.parser.getfloat(sec, 'start_frequency_hz', fallback=100.0),
            stop_frequency_hz=self.parser.getfloat(sec, 'stop_frequency_hz', fallback=100000.0),
            count=self.parser.getint(sec, 'count', fallback=10),
            scale=self.parser.get(sec, 'scale', fallback='linear'),
            excitation_type=self.parser.getint(sec, 'excitation_type', fallback=1),
            amplitude=self.parser.getfloat(sec, 'amplitude', fallback=0.01),
            point_delay_us=self.parser.getint(sec, 'point_delay_us', fallback=0),
            phase_sync=self.parser.getboolean(sec, 'phase_sync', fallback=False)
        )

    def _parse_dc_bias(self) -> DCBiasConfig:
        sec = 'DCBias'
        return DCBiasConfig(
            dc_bias_enabled=self.parser.getboolean(sec, 'dc_bias_enabled', fallback=0),
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


    def parse_api_settings(self) -> ApiSettingsConfig:
        """Liest nur die API-Einstellungen (nicht Teil der Gerätekonfiguration)."""
        if not self.parser.read(self.file_path, encoding='utf-8'):
            raise FileNotFoundError(f"Die Konfigurationsdatei '{self.file_path}' konnte nicht gefunden/gelesen werden.")

        sec = 'ApiSettings'
        return ApiSettingsConfig(
            plot_type=self.parser.get(sec, 'plot_type', fallback='bode').strip().lower(),
            continuous_measurement=self.parser.getboolean(sec, 'continuous_measurement', fallback=False)
        )


class ConfigBuilder:

    def __init__(self, config_path: str = "config/config.ini"):
        self.measurement_setup_queue = []  #list of dictionarys to hold measurement setups
        self.settings = {} # empty dictionary to hold measurement settings from user
        self.parser = ConfigParser(config_path)

    def get_settings_from_config(self):
        #print("davor")
        config_settings = self.parser.parse_as_flat_dict(False)
        #print(config_settings)
        #print("danach")
        return config_settings
        

    def generate_measurement_queue(self):
        #generates a queue of measurement setups (self.measurement_setup_queue) to be executed in the measurement loop

        #reset queue so repeated calls don't accumulate stale setups from a previous run
        self.measurement_setup_queue = []

        #self.settings = self.get_temp_test_settings() #uses temp test_settings
        self.settings = self.parser.parse_as_flat_dict(False)
        #print("Settings from config: ", self.settings)

        #frequency_queue_hz = [self.settings["frequency_hz"]]
        match self.settings["mode"]:
            case "sweep":
                if self.settings["scale"] == "linear":
                    frequency_queue_hz = np.linspace(self.settings["start_frequency_hz"], self.settings["stop_frequency_hz"], self.settings["count"]).tolist()
                elif self.settings["scale"] == "logarithmic":
                    frequency_queue_hz = np.logspace(np.log10(self.settings["start_frequency_hz"]), np.log10(self.settings["stop_frequency_hz"]), self.settings["count"]).tolist()
            case "single":
                frequency_queue_hz = self.settings["frequency_hz"]

        
        for index, freq in enumerate(frequency_queue_hz): 
            #first setup id is 1
            setup_id = index + 1
            single_setup = {
                "id": setup_id,
                "timestamp_mode": self.settings["timestamp_mode"], # Zeitstempel im Datenframe aktivieren: 0 = Deaktiviert, 1 = ms-Zeitstempel (4 Byte uint32), 2 = µs-Zeitstempel (5 Byte uint56)
                "enable_current_range_output": int(self.settings["enable_current_range_output"]), #Strommessbereich im Rückgabeframe mitsenden(0 = Deaktiviert, 1 = Aktiviert)
                "measurement_mode":self.settings["measurement_mode"], #measurement_mode (int): Measurement mode (1=2-point, 2=4-point, 3=3-point)
                "measurement_channel":self.settings["measurement_channel"], #measurement_channel (str): Measurement channel to use (e.g., "Main Port")
                "current_range":self.settings["current_range"], #current_measurement_range (str): Current measurement range (e.g., "10mA")
                "voltage_range":self.settings["voltage_range"], #voltage_measurement_range (str): Voltage measurement range (e.g., "1V")
                "counter_port": self.settings["counter_port"],
                "reference_port": self.settings["reference_port"],
                "working_sense_port": self.settings["working_sense_port"],
                "working_port": self.settings["working_port"],
                "mode":self.settings["mode"], #frequency_sweep (str): Measurement mode, "sweep" or "single" (see FrequencySetupConfig.mode).
                "frequency":freq, #frequency of measurment
                "start_frequency_hz":self.settings["start_frequency_hz"],   #start_frequency (str): Starting frequency, e.g., "1kHz"
                "stop_frequency_hz":self.settings["stop_frequency_hz"], #end_frequency (str): Ending frequency, e.g., "10MHz"
                "count":self.settings["count"],  #count (int): Number of frequency points
                "scale":self.settings["scale"], #scale (str): Scale type, 1 -> log or 0 -> linear
                "precision":self.settings["precision"], #precision (float): Measurement precision.
                "amplitude":self.settings["amplitude"], #amplitude (str): Signal amplitude.
                "excitation_type":self.settings["excitation_type"], #excitation_type (str): Type of excitation, "voltage" or "current".
                "point_delay_us": self.settings["point_delay_us"],
                "phase_sync": int(self.settings["phase_sync"]), #Phasensynchrones Umschalten (EOP 0x02): 0 = Inaktiv, 1 = Aktiv
                "dc_bias_enabled": int(self.settings["dc_bias_enabled"]), # DC-Bias (EOP 0x03): 0 = Inaktiv, 1 = Aktiv
                "bias_voltage_v": self.settings["bias_voltage_v"], # Bias-Spannung in Volt (float, Bereich: -1.0 V bis +1.0 V)
                "number_of_spectra": self.settings["number_of_spectra"], #number (int) of measurement repetitions in the measurement loop
                "sync_time_us": self.settings["sync_time_us"], #Zeit zwischen zwei Spektrenmessungen in Mikrosekunden (uint32)
                "time_of_continuous_measurement": self.settings["time_of_continuous_measurement"] #Zeitraum (in s) in der die Messung mit diesen Einstellungen wiederholt wird (0 -> Einzelmessung)
                
            }

            #includes setup in queue
            self.measurement_setup_queue.append(single_setup)
        return self.measurement_setup_queue



def select_config_file() -> str | None:
    """
    Opens a file dialog to select the config.ini file for a measurement.

    :return: path of the selected config file (None if the user cancelled the dialog).
    """
    from tkinter import Tk, filedialog

    #hidden tkinter window, only needed as parent for the file dialog
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    config_path = filedialog.askopenfilename(
        title="Select measurement config file",
        filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
    )
    root.destroy()

    return config_path or None