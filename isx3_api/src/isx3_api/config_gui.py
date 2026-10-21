"""
config_gui.py - Vollständiges grafisches Konfigurations- und Steuerungsfenster für das ISX-3 (ohne Kompensation).
"""

import os
import configparser
import tkinter as tk
from tkinter import messagebox, ttk
import serial.tools.list_ports

from .measurement import Measurement
from .config_handler import parse_precision_input


class ConfigGUI:
    """Vollständiges Tkinter-Konfigurationsfenster mit allen Hardware-, MUX- und Plot-Parametern."""

    PRECISION_PRESETS = [
        "0 (low - fastest)",
        "1 (medium - default)",
        "2 (high - slow)",
        "3 (very high - slowest)",
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Sciospec ISX-3 - Professioneller Mess-Manager")
        self.root.geometry("980x820")
        self.root.minsize(900, 740)

        self.config_dir = os.path.abspath("config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_path = os.path.join(self.config_dir, "config.ini")

        if not os.path.exists(self.config_path):
            self._write_default_ini(self.config_path)

        self._build_ui()
        self.load_ini_to_form()

    @staticmethod
    def _write_default_ini(target_path: str) -> None:
        """Schreibt ein vollständiges INI-Template ohne Kompensation."""
        default_content = """[Connection]
interface_type = COM
port = COM12
baudrate = 115200
ip_address = 192.168.1.100
tcp_port = 5000
tcp_watchdog_interval_s = 60

[MUX]
enabled = False
mode = 4
channel = 2
active_sensors = 1-8
switch_delay_s = 0.10

[Frontend]
measurement_mode = 2
measurement_channel = 1
current_range = 2
voltage_range = 1

[ExtensionPort]
counter_port = 0
reference_port = 0
working_sense_port = 0
working_port = 0

[FrequencySetup]
mode = sweep
frequency_hz = 1000.0
start_frequency_hz = 100.0
stop_frequency_hz = 10000000.0
count = 101
scale = logarithmic
precision = 1.0
excitation_type = 2
amplitude = 0.0001
point_delay_ms = 20.0
phase_sync = False

[DCBias]
dc_bias_enabled = False
bias_voltage_v = 0.0

[SyncTime]
sync_time_us = 0

[Options]
timestamp_mode = 0
enable_current_range_output = False

[Measurement]
number_of_spectra = 3

[ApiSettings]
plot_type = bode
continuous_measurement = False
use_hardware_sweep = False
live_plot_enabled = True
live_plot_mode = point
"""
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(default_content)

    def _show_info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text)

    def _log(self, msg: str) -> None:
        if hasattr(self, "log_text"):
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        print(msg)

    @staticmethod
    def _format_precision_for_ui(val: float) -> str:
        mapping = {
            0.0: "0 (low - fastest)",
            1.0: "1 (medium - default)",
            2.0: "2 (high - slow)",
            3.0: "3 (very high - slowest)",
        }
        for k, text in mapping.items():
            if abs(val - k) < 1e-6:
                return text
        return str(int(val)) if float(val).is_integer() else str(val)

    def _get_available_com_ports(self) -> list[str]:
        ports = [p.device for p in serial.tools.list_ports.comports()]
        return ports if ports else ["COM1", "COM3", "COM6", "COM12"]

    def _refresh_com_ports(self) -> None:
        ports = self._get_available_com_ports()
        self.port_combo["values"] = ports
        self._log(f"[INFO] Gefundene COM-Ports: {', '.join(ports)}")

    def _build_ui(self) -> None:
        # --- PROFIL-VERWALTUNG OBEN ---
        profile_frame = ttk.LabelFrame(self.root, text=" Profil-Verwaltung ", padding=8)
        profile_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(profile_frame, text="Profil-Name:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.profile_name_var = tk.StringVar(value="config")
        ttk.Entry(profile_frame, textvariable=self.profile_name_var, width=20).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Button(profile_frame, text="💾 Profil speichern", command=self.save_named_profile).grid(row=0, column=2, padx=5)

        ttk.Label(profile_frame, text="Vorhandene Profile:").grid(row=0, column=3, sticky=tk.W, padx=15)
        self.profiles_combo = ttk.Combobox(profile_frame, width=22, state="readonly")
        self.profiles_combo.grid(row=0, column=4, padx=5)
        self.profiles_combo.bind("<<ComboboxSelected>>", self.load_selected_profile)
        self.refresh_profile_list()

        ttk.Button(profile_frame, text="🚀 MESSUNG STARTEN", command=self.start_measurement_action).grid(
            row=0, column=5, padx=20, sticky=tk.E
        )

        # --- TABS ---
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tab_main = ttk.Frame(notebook, padding=10)
        tab_signal = ttk.Frame(notebook, padding=10)
        tab_plot = ttk.Frame(notebook, padding=10)

        notebook.add(tab_main, text=" 1. Schnittstelle, Kanal & Frequenz ")
        notebook.add(tab_signal, text=" 2. Anregung, Messbereiche & Precision ")
        notebook.add(tab_plot, text=" 3. DC-Bias & Live-Plot ")

        # =====================================================================
        # TAB 1: SCHNITTSTELLE, ROUTING & FREQUENZ
        # =====================================================================
        conn_frame = ttk.LabelFrame(tab_main, text=" Verbindung (USB / RS232 / Ethernet) ", padding=8)
        conn_frame.pack(fill=tk.X, pady=5)

        ttk.Label(conn_frame, text="Schnittstelle:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.interface_var = tk.StringVar(value="COM")
        interface_combo = ttk.Combobox(conn_frame, textvariable=self.interface_var, values=["COM", "TCP"], width=8, state="readonly")
        interface_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=3)
        interface_combo.bind("<<ComboboxSelected>>", self._on_interface_change)

        self.com_subframe = ttk.Frame(conn_frame)
        self.com_subframe.grid(row=0, column=2, columnspan=5, sticky=tk.W, padx=10)

        ttk.Label(self.com_subframe, text="COM-Port:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.port_var = tk.StringVar(value="COM12")
        self.port_combo = ttk.Combobox(self.com_subframe, textvariable=self.port_var, values=self._get_available_com_ports(), width=10)
        self.port_combo.grid(row=0, column=1, padx=3)
        ttk.Button(self.com_subframe, text="🔄", width=3, command=self._refresh_com_ports).grid(row=0, column=2, padx=2)

        ttk.Label(self.com_subframe, text="Baudrate:").grid(row=0, column=3, sticky=tk.W, padx=10)
        self.baud_var = tk.StringVar(value="115200")
        ttk.Combobox(self.com_subframe, textvariable=self.baud_var, values=["9600", "57600", "115200", "230400", "921600"], width=10).grid(row=0, column=4, padx=3)

        self.tcp_subframe = ttk.Frame(conn_frame)
        ttk.Label(self.tcp_subframe, text="IP-Adresse:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.ip_var = tk.StringVar(value="192.168.1.100")
        ttk.Entry(self.tcp_subframe, textvariable=self.ip_var, width=15).grid(row=0, column=1, padx=3)

        ttk.Label(self.tcp_subframe, text="TCP-Port:").grid(row=0, column=2, sticky=tk.W, padx=10)
        self.tcp_port_var = tk.StringVar(value="5000")
        ttk.Entry(self.tcp_subframe, textvariable=self.tcp_port_var, width=8).grid(row=0, column=3, padx=3)

        ttk.Label(self.tcp_subframe, text="Watchdog (s):").grid(row=0, column=4, sticky=tk.W, padx=10)
        self.watchdog_var = tk.StringVar(value="60")
        ttk.Entry(self.tcp_subframe, textvariable=self.watchdog_var, width=6).grid(row=0, column=5, padx=3)

        # Betriebsart & Hardware-Routing
        mode_frame = ttk.LabelFrame(tab_main, text=" Betriebsart & Hardware-Routing (0xB0 / 0xB2) ", padding=8)
        mode_frame.pack(fill=tk.X, pady=5)

        ttk.Label(mode_frame, text="Messvariante:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.mode_selector_var = tk.StringVar(value="Main Port (Front-BNC)")
        self.mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_selector_var,
            values=["Main Port (Front-BNC)", "MUX32 Multiplexer (Zusatzkarte)"],
            width=32,
            state="readonly",
        )
        self.mode_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        self.mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)

        self.dynamic_container = ttk.Frame(mode_frame)
        self.dynamic_container.grid(row=1, column=0, columnspan=6, sticky=tk.W + tk.E, pady=5)

        self.frame_main = ttk.Frame(self.dynamic_container)
        ttk.Label(self.frame_main, text="Elektroden-Konfiguration:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.main_bnc_mode_var = tk.StringVar(value="2 (4-Leiter Kelvin)")
        ttk.Combobox(
            self.frame_main,
            textvariable=self.main_bnc_mode_var,
            values=[
                "1 (2-Leiter / 2-Point)",
                "2 (4-Leiter Kelvin / 4-Point)",
                "3 (3-Leiter / 3-Point)",
            ],
            width=28,
            state="readonly",
        ).grid(row=0, column=1, padx=5)

        self.frame_mux = ttk.Frame(self.dynamic_container)
        ttk.Label(self.frame_mux, text="Aktive Sensoren:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.mux_sensors_var = tk.StringVar(value="1-8")
        ttk.Entry(self.frame_mux, textvariable=self.mux_sensors_var, width=10).grid(row=0, column=1, padx=5)

        ttk.Label(self.frame_mux, text="Leiter-Modus:").grid(row=0, column=2, sticky=tk.W, padx=8)
        self.mux_mode_var = tk.StringVar(value="4")
        ttk.Combobox(self.frame_mux, textvariable=self.mux_mode_var, values=["2", "4"], width=5, state="readonly").grid(row=0, column=3, padx=5)

        ttk.Label(self.frame_mux, text="MUX-Port (0xB0):").grid(row=0, column=4, sticky=tk.W, padx=8)
        self.mux_chan_var = tk.StringVar(value="2 (ExtPort)")
        ttk.Combobox(
            self.frame_mux,
            textvariable=self.mux_chan_var,
            values=["2 (ExtPort)", "3 (InternalMux / EXT2)"],
            width=20,
            state="readonly",
        ).grid(row=0, column=5, padx=5)

        ttk.Label(self.frame_mux, text="Switch Delay (s):").grid(row=0, column=6, sticky=tk.W, padx=8)
        self.mux_delay_var = tk.StringVar(value="0.10")
        ttk.Entry(self.frame_mux, textvariable=self.mux_delay_var, width=7).grid(row=0, column=7, padx=5)

        # Frequenz-Setup
        freq_frame = ttk.LabelFrame(tab_main, text=" Frequenz-Konfiguration (0xB6) ", padding=8)
        freq_frame.pack(fill=tk.X, pady=5)

        ttk.Label(freq_frame, text="Frequenz-Modus:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.freq_mode_var = tk.StringVar(value="sweep")
        freq_mode_combo = ttk.Combobox(freq_frame, textvariable=self.freq_mode_var, values=["sweep", "single"], width=10, state="readonly")
        freq_mode_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=3)
        freq_mode_combo.bind("<<ComboboxSelected>>", self._on_freq_mode_change)

        ttk.Label(freq_frame, text="Einzelfrequenz(en) [bei 'single']:").grid(row=0, column=2, sticky=tk.W, padx=15, pady=3)
        self.single_freqs_var = tk.StringVar(value="1000.0")
        self.single_freqs_entry = ttk.Entry(freq_frame, textvariable=self.single_freqs_var, width=28)
        self.single_freqs_entry.grid(row=0, column=3, columnspan=3, sticky=tk.W, padx=5, pady=3)

        ttk.Label(freq_frame, text="Startfrequenz:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.start_val_var = tk.StringVar(value="100")
        ttk.Entry(freq_frame, textvariable=self.start_val_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=2, pady=3)
        self.start_unit_var = tk.StringVar(value="Hz")
        ttk.Combobox(freq_frame, textvariable=self.start_unit_var, values=["Hz", "kHz", "MHz"], width=6, state="readonly").grid(row=1, column=2, sticky=tk.W, padx=2, pady=3)

        ttk.Label(freq_frame, text="Stopfrequenz:").grid(row=1, column=3, sticky=tk.W, padx=15, pady=3)
        self.stop_val_var = tk.StringVar(value="10")
        ttk.Entry(freq_frame, textvariable=self.stop_val_var, width=10).grid(row=1, column=4, sticky=tk.W, padx=2, pady=3)
        self.stop_unit_var = tk.StringVar(value="MHz")
        ttk.Combobox(freq_frame, textvariable=self.stop_unit_var, values=["Hz", "kHz", "MHz"], width=6, state="readonly").grid(row=1, column=5, sticky=tk.W, padx=2, pady=3)

        ttk.Label(freq_frame, text="Punkteanzahl (Count):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        self.count_var = tk.StringVar(value="101")
        ttk.Entry(freq_frame, textvariable=self.count_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=2, pady=3)

        ttk.Label(freq_frame, text="Skalierung:").grid(row=2, column=3, sticky=tk.W, padx=15, pady=3)
        self.scale_var = tk.StringVar(value="logarithmic")
        ttk.Combobox(freq_frame, textvariable=self.scale_var, values=["logarithmic", "linear"], width=12, state="readonly").grid(row=2, column=4, columnspan=2, sticky=tk.W, padx=2, pady=3)

        # =====================================================================
        # TAB 2: ANREGUNG, MESSBEREICHE, PRECISION & TIMING
        # =====================================================================
        exc_frame = ttk.LabelFrame(tab_signal, text=" Anregung & Analoge Frontend-Messbereiche ", padding=10)
        exc_frame.pack(fill=tk.X, pady=5)

        ttk.Label(exc_frame, text="Anregungsart (Excitation Type):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=4)
        self.exc_type_var = tk.StringVar(value="2 (Current / Strom in A)")
        exc_combo = ttk.Combobox(
            exc_frame,
            textvariable=self.exc_type_var,
            values=["1 (Voltage / Spannung in V)", "2 (Current / Strom in A)"],
            width=26,
            state="readonly",
        )
        exc_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=4)
        exc_combo.bind("<<ComboboxSelected>>", self._on_excitation_change)

        self.amp_label = ttk.Label(exc_frame, text="Signalamplitude (Peak in A / V):")
        self.amp_label.grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        self.amp_var = tk.StringVar(value="0.0001")
        ttk.Entry(exc_frame, textvariable=self.amp_var, width=28).grid(row=1, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(exc_frame, text="Current Range (Strommessbereich):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=4)
        self.curr_range_var = tk.StringVar(value="2 (±100uA / 10kΩ)")
        ttk.Combobox(
            exc_frame,
            textvariable=self.curr_range_var,
            values=[
                "0 (Autoranging - nur bei Voltage!)",
                "1 (±10mA / 100Ω)",
                "2 (±100uA / 10kΩ)",
                "4 (±1uA / 1MΩ)",
                "6 (±10nA / 100MΩ)",
            ],
            width=26,
            state="readonly",
        ).grid(row=2, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(exc_frame, text="Voltage Range (Spannungsmessbereich):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=4)
        self.volt_range_var = tk.StringVar(value="1 (±1.0V Default)")
        ttk.Combobox(
            exc_frame,
            textvariable=self.volt_range_var,
            values=[
                "0 (Autoranging)",
                "1 (±1.0V Default)",
                "2 (±0.09V High Gain)",
            ],
            width=26,
            state="readonly",
        ).grid(row=3, column=1, sticky=tk.W, padx=5, pady=4)

        prec_frame = ttk.LabelFrame(tab_signal, text=" Integrationszeit (Precision), Timing & Mittelung ", padding=10)
        prec_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prec_frame, text="Precision (0–10 oder Preset):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=4)
        self.precision_var = tk.StringVar(value="1 (medium - default)")
        self.precision_combo = ttk.Combobox(
            prec_frame,
            textvariable=self.precision_var,
            values=self.PRECISION_PRESETS,
            width=26,
            state="normal",
        )
        self.precision_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(prec_frame, text="Anzahl Spectra (Wiederholungen):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        self.spectra_var = tk.StringVar(value="3")
        ttk.Entry(prec_frame, textvariable=self.spectra_var, width=28).grid(row=1, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(prec_frame, text="Point Delay (ms):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=4)
        self.delay_var = tk.StringVar(value="20.0")
        ttk.Entry(prec_frame, textvariable=self.delay_var, width=28).grid(row=2, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(prec_frame, text="Sync-Time zwischen Sweeps (µs):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=4)
        self.sync_time_var = tk.StringVar(value="0")
        ttk.Entry(prec_frame, textvariable=self.sync_time_var, width=28).grid(row=3, column=1, sticky=tk.W, padx=5, pady=4)

        self.phase_sync_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            prec_frame,
            text="Phase Synchronization aktivieren (nur für f >= 100 kHz bei resonanten Sensoren)",
            variable=self.phase_sync_var,
        ).grid(row=4, column=0, columnspan=3, sticky=tk.W, padx=5, pady=4)

        # =====================================================================
        # TAB 3: DC-BIAS, PROTOKOLL-OPTIONEN & LIVE-PLOT (OHNE KOMPENSATION)
        # =====================================================================
        opt_frame = ttk.LabelFrame(tab_plot, text=" DC-Bias (nur Main Port) & Datenframe-Optionen (0x97) ", padding=10)
        opt_frame.pack(fill=tk.X, pady=5)

        self.dc_bias_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="DC-Bias aktiv (nur BNC Port 1)", variable=self.dc_bias_var).grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)

        ttk.Label(opt_frame, text="Bias-Spannung (-1.0 bis +1.0 V):").grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)
        self.bias_volt_var = tk.StringVar(value="0.0")
        ttk.Entry(opt_frame, textvariable=self.bias_volt_var, width=10).grid(row=0, column=2, sticky=tk.W, padx=5, pady=3)

        ttk.Label(opt_frame, text="Hardware-Zeitstempel (0x97):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.ts_mode_var = tk.StringVar(value="0 (Aus)")
        ttk.Combobox(
            opt_frame,
            textvariable=self.ts_mode_var,
            values=["0 (Aus)", "1 (Millisekunden - 4 Byte)", "2 (Mikrosekunden - 5 Byte)"],
            width=26,
            state="readonly",
        ).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5, pady=3)

        self.curr_range_out_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_frame,
            text="Aktuellen Current-Range im Messframe ausgeben (0x97 Option 0x04)",
            variable=self.curr_range_out_var,
        ).grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=3)

        plot_frame = ttk.LabelFrame(tab_plot, text=" Visualisierung & Ausführungs-Optionen ", padding=10)
        plot_frame.pack(fill=tk.X, pady=5)

        self.live_plot_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(plot_frame, text="Live-Plot während Messung anzeigen", variable=self.live_plot_enabled_var).grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)

        ttk.Label(plot_frame, text="Diagramm-Typ:").grid(row=0, column=1, sticky=tk.W, padx=15, pady=3)
        self.plot_type_var = tk.StringVar(value="bode")
        ttk.Combobox(
            plot_frame,
            textvariable=self.plot_type_var,
            values=["bode", "nyquist", "impedance_frequency"],
            width=20,
            state="readonly",
        ).grid(row=0, column=2, sticky=tk.W, padx=5, pady=3)

        ttk.Label(plot_frame, text="Aktualisierungs-Modus:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.live_plot_mode_var = tk.StringVar(value="point (Nach jedem Frequenzpunkt)")
        ttk.Combobox(
            plot_frame,
            textvariable=self.live_plot_mode_var,
            values=["point (Nach jedem Frequenzpunkt)", "sweep (Erst nach komplettem Sweep)"],
            width=32,
            state="readonly",
        ).grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=5, pady=3)

        # --- LOG FRAME UNTEN ---
        log_frame = ttk.LabelFrame(self.root, text=" Live-Status & Log ", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=6, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._on_interface_change(None)
        self._on_mode_change(None)
        self._on_freq_mode_change(None)

    def _on_interface_change(self, event) -> None:
        if self.interface_var.get() == "TCP":
            self.com_subframe.grid_remove()
            self.tcp_subframe.grid(row=0, column=2, columnspan=5, sticky=tk.W, padx=10)
        else:
            self.tcp_subframe.grid_remove()
            self.com_subframe.grid(row=0, column=2, columnspan=5, sticky=tk.W, padx=10)

    def _on_mode_change(self, event) -> None:
        if "MUX32" in self.mode_selector_var.get():
            self.frame_main.pack_forget()
            self.frame_mux.pack(fill=tk.BOTH, expand=True)
        else:
            self.frame_mux.pack_forget()
            self.frame_main.pack(fill=tk.BOTH, expand=True)

    def _on_freq_mode_change(self, event) -> None:
        if self.freq_mode_var.get() == "single":
            self.single_freqs_entry.configure(state="normal")
        else:
            self.single_freqs_entry.configure(state="disabled")

    def _on_excitation_change(self, event) -> None:
        exc_code = int(self.exc_type_var.get().split()[0])
        if exc_code == 2 and self.curr_range_var.get().startswith("0"):
            self.curr_range_var.set("2 (±100uA / 10kΩ)")
            self._log("[HINWEIS] Autoranging (0) ist bei Stromanregung nicht erlaubt -> Umgestellt auf Range 2 (±100µA).")

    def refresh_profile_list(self) -> None:
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            files = sorted([f[:-4] for f in os.listdir(self.config_dir) if f.endswith(".ini")])
            self.profiles_combo["values"] = files
            if "config" in files:
                self.profiles_combo.set("config")
            elif files:
                self.profiles_combo.set(files[0])
        except Exception as e:
            self._log(f"[FEHLER] Konnte Profil-Liste nicht laden: {e}")

    def load_selected_profile(self, event) -> None:
        sel = self.profiles_combo.get()
        if sel:
            target_path = os.path.join(self.config_dir, f"{sel}.ini")
            if os.path.exists(target_path):
                self.config_path = target_path
                self.profile_name_var.set(sel)
                self.load_ini_to_form()
                self._log(f"[OK] Profil gewechselt zu: {sel}.ini")

    def load_ini_to_form(self) -> None:
        try:
            ini = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
            ini.read(self.config_path, encoding="utf-8")

            # Connection
            self.interface_var.set(ini.get("Connection", "interface_type", fallback="COM"))
            self.port_var.set(ini.get("Connection", "port", fallback="COM12"))
            self.baud_var.set(str(ini.getint("Connection", "baudrate", fallback=115200)))
            self.ip_var.set(ini.get("Connection", "ip_address", fallback="192.168.1.100"))
            self.tcp_port_var.set(str(ini.getint("Connection", "tcp_port", fallback=5000)))
            self.watchdog_var.set(str(ini.getint("Connection", "tcp_watchdog_interval_s", fallback=60)))

            # MUX & Main Mode
            mux_enabled = ini.getboolean("MUX", "enabled", fallback=False)
            self.mode_selector_var.set("MUX32 Multiplexer (Zusatzkarte)" if mux_enabled else "Main Port (Front-BNC)")
            self.mux_sensors_var.set(ini.get("MUX", "active_sensors", fallback="1-8"))
            self.mux_mode_var.set(str(ini.getint("MUX", "mode", fallback=4)))
            m_chan = ini.getint("MUX", "channel", fallback=2)
            self.mux_chan_var.set("3 (InternalMux / EXT2)" if m_chan == 3 else "2 (ExtPort)")
            self.mux_delay_var.set(str(ini.getfloat("MUX", "switch_delay_s", fallback=0.10)))

            # Frontend
            fe_mode = ini.getint("Frontend", "measurement_mode", fallback=2)
            fe_mode_map = {
                1: "1 (2-Leiter / 2-Point)",
                2: "2 (4-Leiter Kelvin / 4-Point)",
                3: "3 (3-Leiter / 3-Point)",
            }
            self.main_bnc_mode_var.set(fe_mode_map.get(fe_mode, "2 (4-Leiter Kelvin / 4-Point)"))

            cr_val = ini.getint("Frontend", "current_range", fallback=2)
            cr_map = {
                0: "0 (Autoranging - nur bei Voltage!)",
                1: "1 (±10mA / 100Ω)",
                2: "2 (±100uA / 10kΩ)",
                4: "4 (±1uA / 1MΩ)",
                6: "6 (±10nA / 100MΩ)",
            }
            self.curr_range_var.set(cr_map.get(cr_val, f"{cr_val}"))

            vr_val = ini.getint("Frontend", "voltage_range", fallback=1)
            vr_map = {
                0: "0 (Autoranging)",
                1: "1 (±1.0V Default)",
                2: "2 (±0.09V High Gain)",
            }
            self.volt_range_var.set(vr_map.get(vr_val, "1 (±1.0V Default)"))

            # FrequencySetup
            self.freq_mode_var.set(ini.get("FrequencySetup", "mode", fallback="sweep").strip().lower())
            self.single_freqs_var.set(ini.get("FrequencySetup", "frequency_hz", fallback="1000.0"))

            start_hz = float(ini.get("FrequencySetup", "start_frequency_hz", fallback="100.0"))
            if start_hz >= 1e6 and start_hz % 1e6 == 0:
                self.start_val_var.set(str(int(start_hz / 1e6)))
                self.start_unit_var.set("MHz")
            elif start_hz >= 1e3 and start_hz % 1e3 == 0:
                self.start_val_var.set(str(int(start_hz / 1e3)))
                self.start_unit_var.set("kHz")
            else:
                self.start_val_var.set(str(start_hz))
                self.start_unit_var.set("Hz")

            stop_hz = float(ini.get("FrequencySetup", "stop_frequency_hz", fallback="10000000.0"))
            if stop_hz >= 1e6 and stop_hz % 1e6 == 0:
                self.stop_val_var.set(str(int(stop_hz / 1e6)))
                self.stop_unit_var.set("MHz")
            elif stop_hz >= 1e3 and stop_hz % 1e3 == 0:
                self.stop_val_var.set(str(int(stop_hz / 1e3)))
                self.stop_unit_var.set("kHz")
            else:
                self.stop_val_var.set(str(stop_hz))
                self.stop_unit_var.set("Hz")

            self.count_var.set(ini.get("FrequencySetup", "count", fallback="101"))
            self.scale_var.set(ini.get("FrequencySetup", "scale", fallback="logarithmic"))

            exc_t = ini.getint("FrequencySetup", "excitation_type", fallback=2)
            self.exc_type_var.set("1 (Voltage / Spannung in V)" if exc_t == 1 else "2 (Current / Strom in A)")
            self.amp_var.set(ini.get("FrequencySetup", "amplitude", fallback="0.0001"))
            self.delay_var.set(ini.get("FrequencySetup", "point_delay_ms", fallback="20.0"))
            self.phase_sync_var.set(ini.getboolean("FrequencySetup", "phase_sync", fallback=False))

            raw_prec = ini.get("FrequencySetup", "precision", fallback="1.0")
            prec_val = parse_precision_input(raw_prec)
            self.precision_var.set(self._format_precision_for_ui(prec_val))

            # DCBias & SyncTime & Options
            self.dc_bias_var.set(ini.getboolean("DCBias", "dc_bias_enabled", fallback=False))
            self.bias_volt_var.set(ini.get("DCBias", "bias_voltage_v", fallback="0.0"))
            self.sync_time_var.set(str(ini.getint("SyncTime", "sync_time_us", fallback=0)))

            ts_m = ini.getint("Options", "timestamp_mode", fallback=0)
            ts_map = {
                0: "0 (Aus)",
                1: "1 (Millisekunden - 4 Byte)",
                2: "2 (Mikrosekunden - 5 Byte)",
            }
            self.ts_mode_var.set(ts_map.get(ts_m, "0 (Aus)"))
            self.curr_range_out_var.set(ini.getboolean("Options", "enable_current_range_output", fallback=False))

            # Measurement & ApiSettings
            self.spectra_var.set(ini.get("Measurement", "number_of_spectra", fallback="3"))
            self.plot_type_var.set(ini.get("ApiSettings", "plot_type", fallback="bode"))
            self.live_plot_enabled_var.set(ini.getboolean("ApiSettings", "live_plot_enabled", fallback=True))
            live_mode = ini.get("ApiSettings", "live_plot_mode", fallback="point")
            if "sweep" in live_mode:
                self.live_plot_mode_var.set("sweep (Erst nach komplettem Sweep)")
            else:
                self.live_plot_mode_var.set("point (Nach jedem Frequenzpunkt)")

            self._on_interface_change(None)
            self._on_mode_change(None)
            self._on_freq_mode_change(None)
            self._log(f"[OK] Profil geladen: {os.path.basename(self.config_path)}")
        except Exception as e:
            messagebox.showerror("Fehler beim Laden", str(e))

    def save_named_profile(self) -> None:
        name = self.profile_name_var.get().strip()
        if not name:
            messagebox.showwarning("Name fehlt", "Bitte gib einen gültigen Profilnamen ein.")
            return
        self.config_path = os.path.join(self.config_dir, f"{name}.ini")
        if self.save_current_form():
            self.refresh_profile_list()
            self.profiles_combo.set(name)
            messagebox.showinfo("Gespeichert", f"Profil '{name}.ini' wurde vollständig gesichert.")

    def save_current_form(self) -> bool:
        try:
            raw_prec_input = self.precision_var.get().strip()
            try:
                first_tok = raw_prec_input.split()[0].replace(",", ".")
                test_val = float(first_tok)
                if not (0.0 <= test_val <= 10.0):
                    messagebox.showwarning(
                        "Ungültige Precision",
                        "Der Precision-Wert muss laut Hersteller zwischen 0.0 und 10.0 liegen.",
                    )
                    return False
            except ValueError:
                pass
            prec_float = parse_precision_input(raw_prec_input)
            self.precision_var.set(self._format_precision_for_ui(prec_float))

            exc_type_int = int(self.exc_type_var.get().split()[0])
            curr_range_int = int(self.curr_range_var.get().split()[0])
            if exc_type_int == 2 and curr_range_int == 0:
                messagebox.showwarning(
                    "Ungültige Kombination",
                    "Autoranging (Current Range = 0) ist bei Stromanregung nicht möglich!",
                )
                return False

            if not os.path.exists(self.config_path):
                self._write_default_ini(self.config_path)

            ini = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
            ini.optionxform = str
            ini.read(self.config_path, encoding="utf-8")

            for sec in [
                "Connection", "MUX", "Frontend", "ExtensionPort",
                "FrequencySetup", "DCBias", "SyncTime", "Options", "Measurement", "ApiSettings"
            ]:
                if not ini.has_section(sec):
                    ini.add_section(sec)

            # Sektion [Compensation] komplett entfernen falls vorhanden
            if ini.has_section("Compensation"):
                ini.remove_section("Compensation")

            # Connection
            ini.set("Connection", "interface_type", self.interface_var.get())
            ini.set("Connection", "port", self.port_var.get().strip())
            ini.set("Connection", "baudrate", self.baud_var.get().strip())
            ini.set("Connection", "ip_address", self.ip_var.get().strip())
            ini.set("Connection", "tcp_port", self.tcp_port_var.get().strip())
            ini.set("Connection", "tcp_watchdog_interval_s", self.watchdog_var.get().strip())

            # MUX
            is_mux = "MUX32" in self.mode_selector_var.get()
            mux_ch_str = self.mux_chan_var.get().split()[0]
            ini.set("MUX", "enabled", str(is_mux))
            ini.set("MUX", "mode", self.mux_mode_var.get().strip())
            ini.set("MUX", "channel", mux_ch_str)
            ini.set("MUX", "active_sensors", self.mux_sensors_var.get().strip())
            ini.set("MUX", "switch_delay_s", self.mux_delay_var.get().strip())

            # Frontend
            fe_mode_str = self.main_bnc_mode_var.get().split()[0]
            vr_str = self.volt_range_var.get().split()[0]
            ini.set("Frontend", "measurement_mode", fe_mode_str)
            ini.set("Frontend", "measurement_channel", mux_ch_str if is_mux else "1")
            ini.set("Frontend", "current_range", str(curr_range_int))
            ini.set("Frontend", "voltage_range", vr_str)

            # ExtensionPort
            for ep_key in ["counter_port", "reference_port", "working_sense_port", "working_port"]:
                if not ini.has_option("ExtensionPort", ep_key):
                    ini.set("ExtensionPort", ep_key, "0")

            # FrequencySetup
            def unit_to_hz(val_str: str, unit_str: str) -> float:
                try:
                    v = float(val_str)
                except ValueError:
                    v = 100.0
                u = unit_str.lower()
                if "k" in u:
                    return v * 1e3
                if "m" in u:
                    return v * 1e6
                return v

            start_hz = unit_to_hz(self.start_val_var.get(), self.start_unit_var.get())
            stop_hz = unit_to_hz(self.stop_val_var.get(), self.stop_unit_var.get())

            ini.set("FrequencySetup", "mode", self.freq_mode_var.get())
            ini.set("FrequencySetup", "frequency_hz", self.single_freqs_var.get().strip())
            ini.set("FrequencySetup", "start_frequency_hz", str(start_hz))
            ini.set("FrequencySetup", "stop_frequency_hz", str(stop_hz))
            ini.set("FrequencySetup", "count", self.count_var.get().strip())
            ini.set("FrequencySetup", "scale", self.scale_var.get())
            ini.set("FrequencySetup", "precision", str(prec_float))
            ini.set("FrequencySetup", "excitation_type", str(exc_type_int))
            ini.set("FrequencySetup", "amplitude", self.amp_var.get().strip())
            ini.set("FrequencySetup", "point_delay_ms", self.delay_var.get().strip())
            ini.set("FrequencySetup", "phase_sync", str(self.phase_sync_var.get()))

            # DCBias, SyncTime & Options
            ini.set("DCBias", "dc_bias_enabled", str(self.dc_bias_var.get()))
            ini.set("DCBias", "bias_voltage_v", self.bias_volt_var.get().strip())
            ini.set("SyncTime", "sync_time_us", self.sync_time_var.get().strip())

            ts_str = self.ts_mode_var.get().split()[0]
            ini.set("Options", "timestamp_mode", ts_str)
            ini.set("Options", "enable_current_range_output", str(self.curr_range_out_var.get()))

            # Measurement & ApiSettings
            ini.set("Measurement", "number_of_spectra", self.spectra_var.get().strip())
            ini.set("ApiSettings", "plot_type", self.plot_type_var.get())
            ini.set("ApiSettings", "continuous_measurement", "False")
            ini.set("ApiSettings", "use_hardware_sweep", "False")
            ini.set("ApiSettings", "live_plot_enabled", str(self.live_plot_enabled_var.get()))
            plot_mode_val = "point" if "point" in self.live_plot_mode_var.get() else "sweep"
            ini.set("ApiSettings", "live_plot_mode", plot_mode_val)

            with open(self.config_path, "w", encoding="utf-8") as f:
                ini.write(f)
            return True
        except Exception as e:
            messagebox.showerror("Fehler beim Speichern", str(e))
            return False

    def start_measurement_action(self) -> None:
        if not self.save_current_form():
            return
        self._log(f"\n[INFO] Starte Messkampagne mit '{os.path.basename(self.config_path)}'...")
        try:
            meas = Measurement()
            meas.measurement(config_path=self.config_path)
            self._log("[OK] Messung erfolgreich beendet.")
        except Exception as e:
            self._log(f"[FEHLER] {str(e)}")
            messagebox.showerror("Messfehler", str(e))


def run_gui():
    root = tk.Tk()
    app = ConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()