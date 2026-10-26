"""
config_gui.py - Grafisches Konfigurationsfenster mit Block-Tabelle, Doppelklick-Edit und Einheiten-Hinweis.
"""

import os
import configparser
import tkinter as tk
from tkinter import messagebox, ttk
import serial.tools.list_ports

from .measurement import Measurement
from .config_handler import parse_frequency_input, parse_precision_input


class ConfigGUI:
    """Vollständiges Tkinter-Konfigurationsfenster mit Frequenzblock-Tabelle und Doppelklick-Bearbeitung."""

    PRECISION_PRESETS = [
        "0 (low - fastest)",
        "1 (medium - default)",
        "2 (high - slow)",
        "3 (very high - slowest)",
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Sciospec ISX-3 - Professioneller Mess-Manager")
        self.root.geometry("1020x900")
        self.root.minsize(940, 800)

        self.config_dir = os.path.abspath("config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_path = os.path.join(self.config_dir, "config.ini")

        if not os.path.exists(self.config_path):
            self._write_default_ini(self.config_path)

        self._build_ui()
        self.load_ini_to_form()

    @staticmethod
    def _write_default_ini(target_path: str) -> None:
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

[FrequencyBlocks]
block_1_start = 100.0
block_1_stop = 10000000.0
block_1_steps = 101
block_1_scale = logarithmic
block_1_precision = 1.0
block_1_exc_type = 2
block_1_amplitude = 0.0001

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
live_plot_enabled = True
live_plot_mode = point
"""
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(default_content)

    def _show_info(self, title: str, text: str) -> None:
        messagebox.showinfo(title, text)

    def _show_pin_help(self) -> None:
        help_text = (
            "Hilfe zur Pin-Belegung (MUX32):\n\n"
            "Du kannst die Sensoren auf zwei Arten definieren:\n"
            "1. Standard-Bereiche (z.B. '1-8'):\n"
            "   Nutzt die automatische 4-Leiter-Berechnung (CE, RE, WS, WE).\n\n"
            "2. Individuelle Pin-Belegung (z.B. '1: 4,8,9,12'):\n"
            "   Weist einem Sensor explizit 4 Pins zu.\n"
            "   Reihenfolge der Pins: Counter (CE), Reference (RE), Working Sense (WS), Work (WE).\n\n"
            "Mehrere Sensoren können mit Kommas getrennt werden:\n"
            "Beispiel: '1: 4,8,9,12, 2: 5,6,7,10'"
        )
        messagebox.showinfo("MUX Pin-Belegung - Hilfe", help_text, parent=self.root)

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

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        tab_main = ttk.Frame(notebook, padding=10)
        tab_signal = ttk.Frame(notebook, padding=10)
        tab_plot = ttk.Frame(notebook, padding=10)

        notebook.add(tab_main, text=" 1. Schnittstelle, Kanal & Frequenzblöcke ")
        notebook.add(tab_signal, text=" 2. Anregung, Messbereiche & Timing ")
        notebook.add(tab_plot, text=" 3. DC-Bias & Live-Plot ")

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
        self.main_bnc_mode_var = tk.StringVar(value="2 (4-Leiter Kelvin / 4-Point)")
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
        ttk.Label(self.frame_mux, text="Aktive Sensoren / Pins:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.mux_sensors_var = tk.StringVar(value="1-8")
        ttk.Entry(self.frame_mux, textvariable=self.mux_sensors_var, width=15).grid(row=0, column=1, padx=5)
        
        ttk.Button(self.frame_mux, text="❓ Hilfe zu Pins", command=self._show_pin_help).grid(row=0, column=2, padx=5)

        ttk.Label(self.frame_mux, text="Leiter-Modus:").grid(row=0, column=3, sticky=tk.W, padx=8)
        self.mux_mode_var = tk.StringVar(value="4")
        ttk.Combobox(self.frame_mux, textvariable=self.mux_mode_var, values=["2", "4"], width=5, state="readonly").grid(row=0, column=4, padx=5)

        ttk.Label(self.frame_mux, text="MUX-Port (0xB0):").grid(row=0, column=5, sticky=tk.W, padx=8)
        self.mux_chan_var = tk.StringVar(value="2 (ExtPort)")
        ttk.Combobox(
            self.frame_mux,
            textvariable=self.mux_chan_var,
            values=["2 (ExtPort)", "3 (InternalMux / EXT2)"],
            width=20,
            state="readonly",
        ).grid(row=0, column=6, padx=5)

        ttk.Label(self.frame_mux, text="Switch Delay (s):").grid(row=0, column=7, sticky=tk.W, padx=8)
        self.mux_delay_var = tk.StringVar(value="0.10")
        ttk.Entry(self.frame_mux, textvariable=self.mux_delay_var, width=7).grid(row=0, column=8, padx=5)

        # Frequenz-Blöcke (Tabelle erweitert um Anregung & Amplitude)
        block_frame = ttk.LabelFrame(tab_main, text=" Frequenz-Blöcke & Block-Spezifische Anregung (0xB6 0x03) ", padding=8)
        block_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("min_f", "max_f", "steps", "scale", "precision", "exc_type", "amplitude")
        self.block_tree = ttk.Treeview(block_frame, columns=columns, show="headings", height=4)
        self.block_tree.heading("min_f", text="Min f [Hz]")
        self.block_tree.heading("max_f", text="Max f [Hz]")
        self.block_tree.heading("steps", text="Steps")
        self.block_tree.heading("scale", text="Scale")
        self.block_tree.heading("precision", text="Precision")
        self.block_tree.heading("exc_type", text="Anregung")
        self.block_tree.heading("amplitude", text="Amplitude")

        self.block_tree.column("min_f", width=110, anchor=tk.CENTER)
        self.block_tree.column("max_f", width=110, anchor=tk.CENTER)
        self.block_tree.column("steps", width=60, anchor=tk.CENTER)
        self.block_tree.column("scale", width=90, anchor=tk.CENTER)
        self.block_tree.column("precision", width=90, anchor=tk.CENTER)
        self.block_tree.column("exc_type", width=110, anchor=tk.CENTER)
        self.block_tree.column("amplitude", width=90, anchor=tk.CENTER)
        self.block_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.block_tree.bind("<Double-1>", lambda event: self._edit_frequency_block())

        btn_subframe = ttk.Frame(block_frame)
        btn_subframe.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

        ttk.Button(btn_subframe, text="➕ Block hinzufügen", command=self._add_frequency_block).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_subframe, text="✏️ Ausgewählten Block bearbeiten (oder Doppelklick)", command=self._edit_frequency_block).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_subframe, text="🗑️ Block löschen", command=self._delete_frequency_block).pack(side=tk.LEFT, padx=3)

        # TAB 2: ANREGUNG, MESSBEREICHE & TIMING
        exc_frame = ttk.LabelFrame(tab_signal, text=" Globale Anregung & Analoge Frontend-Messbereiche ", padding=10)
        exc_frame.pack(fill=tk.X, pady=5)

        ttk.Label(exc_frame, text="Globale Anregungsart:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=4)
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

        self.amp_label = ttk.Label(exc_frame, text="Globale Signalamplitude:")
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

        prec_frame = ttk.LabelFrame(tab_signal, text=" Timing, Spektrale Wiederholungen & Mittelung ", padding=10)
        prec_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prec_frame, text="Anzahl Spectra (Wiederholungen):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=4)
        self.spectra_var = tk.StringVar(value="3")
        ttk.Entry(prec_frame, textvariable=self.spectra_var, width=28).grid(row=0, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(prec_frame, text="Point Delay (ms):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        self.delay_var = tk.StringVar(value="20.0")
        ttk.Entry(prec_frame, textvariable=self.delay_var, width=28).grid(row=1, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(prec_frame, text="Sync-Time zwischen Sweeps (µs):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=4)
        self.sync_time_var = tk.StringVar(value="0")
        ttk.Entry(prec_frame, textvariable=self.sync_time_var, width=28).grid(row=2, column=1, sticky=tk.W, padx=5, pady=4)

        self.phase_sync_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            prec_frame,
            text="Phase Synchronization aktivieren (nur für f >= 100 kHz bei resonanten Sensoren)",
            variable=self.phase_sync_var,
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=4)

        # TAB 3: DC-BIAS, PROTOKOLL-OPTIONEN & LIVE-PLOT
        opt_frame = ttk.LabelFrame(tab_plot, text=" DC-Bias & Datenframe-Optionen (0x97) ", padding=10)
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

        plot_frame = ttk.LabelFrame(tab_plot, text=" Visualisierung & Live-Plot Optionen ", padding=10)
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

        log_frame = ttk.LabelFrame(self.root, text=" Live-Status & Log ", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = tk.Text(log_frame, height=5, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._on_interface_change(None)
        self._on_mode_change(None)

    def _add_frequency_block(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("Frequenzblock hinzufügen")
        dlg.geometry("380x420")
        dlg.transient(self.root)
        dlg.grab_set()

        lbl_hint = ttk.Label(
            dlg,
            text="💡 Tipp: Einheiten wie '100k' oder '1M'\nwerden automatisch umgerechnet.",
            foreground="#0055aa",
            justify=tk.LEFT,
        )
        lbl_hint.grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)

        ttk.Label(dlg, text="Min f [Hz]:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        e_min = ttk.Entry(dlg, width=18)
        e_min.grid(row=1, column=1, padx=10, pady=5)
        e_min.insert(0, "100")

        ttk.Label(dlg, text="Max f [Hz]:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        e_max = ttk.Entry(dlg, width=18)
        e_max.grid(row=2, column=1, padx=10, pady=5)
        e_max.insert(0, "1k")

        ttk.Label(dlg, text="Steps (Punkte):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        e_steps = ttk.Entry(dlg, width=18)
        e_steps.grid(row=3, column=1, padx=10, pady=5)
        e_steps.insert(0, "50")

        ttk.Label(dlg, text="Scale:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        cb_scale = ttk.Combobox(dlg, values=["logarithmic", "linear"], width=16, state="readonly")
        cb_scale.grid(row=4, column=1, padx=10, pady=5)
        cb_scale.set("logarithmic")

        ttk.Label(dlg, text="Precision:").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
        cb_prec = ttk.Combobox(dlg, values=self.PRECISION_PRESETS, width=16, state="normal")
        cb_prec.grid(row=5, column=1, padx=10, pady=5)
        cb_prec.set("1 (medium - default)")

        ttk.Label(dlg, text="Anregungsart:").grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
        cb_exc = ttk.Combobox(dlg, values=["Current (Strom)", "Voltage (Spannung)"], width=16, state="readonly")
        cb_exc.grid(row=6, column=1, padx=10, pady=5)
        cb_exc.set("Current (Strom)")

        ttk.Label(dlg, text="Amplitude (A / V):").grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)
        e_amp = ttk.Entry(dlg, width=18)
        e_amp.grid(row=7, column=1, padx=10, pady=5)
        e_amp.insert(0, "0.0001")

        def on_ok():
            try:
                mn = parse_frequency_input(e_min.get().strip())
                mx = parse_frequency_input(e_max.get().strip())
                st = int(e_steps.get().strip())
                sc = cb_scale.get()
                pr = parse_precision_input(cb_prec.get())
                exc = "Current" if "Current" in cb_exc.get() else "Voltage"
                amp = float(e_amp.get().strip())
                self.block_tree.insert("", tk.END, values=(mn, mx, st, sc, pr, exc, amp))
                dlg.destroy()
            except Exception as ex:
                messagebox.showerror("Fehler", f"Ungültige Eingabe: {ex}", parent=dlg)

        ttk.Button(dlg, text="Hinzufügen", command=on_ok).grid(row=8, column=0, columnspan=2, pady=10)

    def _edit_frequency_block(self) -> None:
        selected = self.block_tree.selection()
        if not selected:
            messagebox.showwarning("Kein Block gewählt", "Bitte wähle einen Frequenzblock in der Tabelle aus.")
            return

        item_id = selected[0]
        vals = self.block_tree.item(item_id, "values")

        dlg = tk.Toplevel(self.root)
        dlg.title("Frequenzblock bearbeiten")
        dlg.geometry("380x420")
        dlg.transient(self.root)
        dlg.grab_set()

        lbl_hint = ttk.Label(
            dlg,
            text="💡 Tipp: Einheiten wie '100k' oder '1M'\nwerden automatisch umgerechnet.",
            foreground="#0055aa",
            justify=tk.LEFT,
        )
        lbl_hint.grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)

        ttk.Label(dlg, text="Min f [Hz]:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        e_min = ttk.Entry(dlg, width=18)
        e_min.grid(row=1, column=1, padx=10, pady=5)
        e_min.insert(0, vals[0])

        ttk.Label(dlg, text="Max f [Hz]:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        e_max = ttk.Entry(dlg, width=18)
        e_max.grid(row=2, column=1, padx=10, pady=5)
        e_max.insert(0, vals[1])

        ttk.Label(dlg, text="Steps (Punkte):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        e_steps = ttk.Entry(dlg, width=18)
        e_steps.grid(row=3, column=1, padx=10, pady=5)
        e_steps.insert(0, vals[2])

        ttk.Label(dlg, text="Scale:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        cb_scale = ttk.Combobox(dlg, values=["logarithmic", "linear"], width=16, state="readonly")
        cb_scale.grid(row=4, column=1, padx=10, pady=5)
        cb_scale.set(vals[3])

        ttk.Label(dlg, text="Precision:").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
        cb_prec = ttk.Combobox(dlg, values=self.PRECISION_PRESETS, width=16, state="normal")
        cb_prec.grid(row=5, column=1, padx=10, pady=5)
        cb_prec.set(self._format_precision_for_ui(float(vals[4])))

        ttk.Label(dlg, text="Anregungsart:").grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
        cb_exc = ttk.Combobox(dlg, values=["Current (Strom)", "Voltage (Spannung)"], width=16, state="readonly")
        cb_exc.grid(row=6, column=1, padx=10, pady=5)
        default_exc = vals[5] if len(vals) > 5 else "Current (Strom)"
        cb_exc.set(default_exc)

        ttk.Label(dlg, text="Amplitude (A / V):").grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)
        e_amp = ttk.Entry(dlg, width=18)
        e_amp.grid(row=7, column=1, padx=10, pady=5)
        default_amp = vals[6] if len(vals) > 6 else "0.0001"
        e_amp.insert(0, default_amp)

        def on_ok():
            try:
                mn = parse_frequency_input(e_min.get().strip())
                mx = parse_frequency_input(e_max.get().strip())
                st = int(e_steps.get().strip())
                sc = cb_scale.get()
                pr = parse_precision_input(cb_prec.get())
                exc = "Current" if "Current" in cb_exc.get() else "Voltage"
                amp = float(e_amp.get().strip())
                self.block_tree.item(item_id, values=(mn, mx, st, sc, pr, exc, amp))
                dlg.destroy()
            except Exception as ex:
                messagebox.showerror("Fehler", f"Ungültige Eingabe: {ex}", parent=dlg)

        ttk.Button(dlg, text="Speichern", command=on_ok).grid(row=8, column=0, columnspan=2, pady=10)

    def _delete_frequency_block(self) -> None:
        selected = self.block_tree.selection()
        if not selected:
            messagebox.showwarning("Kein Block gewählt", "Bitte wähle einen Frequenzblock in der Tabelle aus.")
            return
        for item_id in selected:
            self.block_tree.delete(item_id)

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

            self.interface_var.set(ini.get("Connection", "interface_type", fallback="COM"))
            self.port_var.set(ini.get("Connection", "port", fallback="COM12"))
            self.baud_var.set(str(ini.getint("Connection", "baudrate", fallback=115200)))
            self.ip_var.set(ini.get("Connection", "ip_address", fallback="192.168.1.100"))
            self.tcp_port_var.set(str(ini.getint("Connection", "tcp_port", fallback=5000)))
            self.watchdog_var.set(str(ini.getint("Connection", "tcp_watchdog_interval_s", fallback=60)))

            mux_enabled = ini.getboolean("MUX", "enabled", fallback=False)
            self.mode_selector_var.set("MUX32 Multiplexer (Zusatzkarte)" if mux_enabled else "Main Port (Front-BNC)")
            self.mux_sensors_var.set(ini.get("MUX", "active_sensors", fallback="1-8"))
            self.mux_mode_var.set(str(ini.getint("MUX", "mode", fallback=4)))
            m_chan = ini.getint("MUX", "channel", fallback=2)
            self.mux_chan_var.set("3 (InternalMux / EXT2)" if m_chan == 3 else "2 (ExtPort)")
            self.mux_delay_var.set(str(ini.getfloat("MUX", "switch_delay_s", fallback=0.10)))

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

            for row in self.block_tree.get_children():
                self.block_tree.delete(row)

            loaded_blocks = False
            if ini.has_section("FrequencyBlocks"):
                block_indices = set()
                for key in ini.options("FrequencyBlocks"):
                    if key.startswith("block_") and "_start" in key:
                        try:
                            idx = int(key.split("_")[1])
                            block_indices.add(idx)
                        except ValueError:
                            pass
                if block_indices:
                    for idx in sorted(list(block_indices)):
                        mn = ini.get("FrequencyBlocks", f"block_{idx}_start", fallback="100.0")
                        mx = ini.get("FrequencyBlocks", f"block_{idx}_stop", fallback="10000000.0")
                        st = ini.get("FrequencyBlocks", f"block_{idx}_steps", fallback="101")
                        sc = ini.get("FrequencyBlocks", f"block_{idx}_scale", fallback="logarithmic")
                        pr = ini.get("FrequencyBlocks", f"block_{idx}_precision", fallback="1.0")
                        
                        exc_raw = ini.get("FrequencyBlocks", f"block_{idx}_exc_type", fallback="2")
                        exc_str = "Voltage (Spannung)" if ("1" in exc_raw or "Volt" in exc_raw) else "Current (Strom)"
                        amp_val = ini.get("FrequencyBlocks", f"block_{idx}_amplitude", fallback="0.0001")

                        self.block_tree.insert("", tk.END, values=(mn, mx, st, sc, pr, exc_str, amp_val))
                    loaded_blocks = True

            if not loaded_blocks:
                mn = ini.get("FrequencySetup", "start_frequency_hz", fallback="100.0")
                mx = ini.get("FrequencySetup", "stop_frequency_hz", fallback="10000000.0")
                st = ini.get("FrequencySetup", "count", fallback="101")
                sc = ini.get("FrequencySetup", "scale", fallback="logarithmic")
                pr = ini.get("FrequencySetup", "precision", fallback="1.0")
                exc_t = ini.getint("FrequencySetup", "excitation_type", fallback=2)
                exc_str = "Voltage (Spannung)" if exc_t == 1 else "Current (Strom)"
                amp_val = ini.get("FrequencySetup", "amplitude", fallback="0.0001")
                self.block_tree.insert("", tk.END, values=(mn, mx, st, sc, pr, exc_str, amp_val))

            exc_t = ini.getint("FrequencySetup", "excitation_type", fallback=2)
            self.exc_type_var.set("1 (Voltage / Spannung in V)" if exc_t == 1 else "2 (Current / Strom in A)")
            self.amp_var.set(ini.get("FrequencySetup", "amplitude", fallback="0.0001"))
            self.delay_var.set(ini.get("FrequencySetup", "point_delay_ms", fallback="20.0"))
            self.phase_sync_var.set(ini.getboolean("FrequencySetup", "phase_sync", fallback=False))

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
            exc_type_int = int(self.exc_type_var.get().split()[0])
            curr_range_int = int(self.curr_range_var.get().split()[0])

            if not os.path.exists(self.config_path):
                self._write_default_ini(self.config_path)

            ini = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
            ini.optionxform = str
            ini.read(self.config_path, encoding="utf-8")

            for sec in [
                "Connection", "MUX", "Frontend", "ExtensionPort",
                "FrequencySetup", "FrequencyBlocks", "DCBias", "SyncTime", "Options", "Measurement", "ApiSettings"
            ]:
                if not ini.has_section(sec):
                    ini.add_section(sec)

            if ini.has_section("Compensation"):
                ini.remove_section("Compensation")

            ini.set("Connection", "interface_type", self.interface_var.get())
            ini.set("Connection", "port", self.port_var.get().strip())
            ini.set("Connection", "baudrate", self.baud_var.get().strip())
            ini.set("Connection", "ip_address", self.ip_var.get().strip())
            ini.set("Connection", "tcp_port", self.tcp_port_var.get().strip())
            ini.set("Connection", "tcp_watchdog_interval_s", self.watchdog_var.get().strip())

            is_mux = "MUX32" in self.mode_selector_var.get()
            mux_ch_str = self.mux_chan_var.get().split()[0]
            ini.set("MUX", "enabled", str(is_mux))
            ini.set("MUX", "mode", self.mux_mode_var.get().strip())
            ini.set("MUX", "channel", mux_ch_str)
            ini.set("MUX", "active_sensors", self.mux_sensors_var.get().strip())
            ini.set("MUX", "switch_delay_s", self.mux_delay_var.get().strip())

            fe_mode_str = self.main_bnc_mode_var.get().split()[0]
            vr_str = self.volt_range_var.get().split()[0]
            ini.set("Frontend", "measurement_mode", fe_mode_str)
            ini.set("Frontend", "measurement_channel", mux_ch_str if is_mux else "1")
            ini.set("Frontend", "current_range", str(curr_range_int))
            ini.set("Frontend", "voltage_range", vr_str)

            for ep_key in ["counter_port", "reference_port", "working_sense_port", "working_port"]:
                if not ini.has_option("ExtensionPort", ep_key):
                    ini.set("ExtensionPort", ep_key, "0")

            for key in list(ini.options("FrequencyBlocks")):
                if key.startswith("block_"):
                    ini.remove_option("FrequencyBlocks", key)

            children = self.block_tree.get_children()
            if not children:
                self.block_tree.insert("", tk.END, values=("100.0", "10000000.0", "101", "logarithmic", "1.0", "Current (Strom)", "0.0001"))
                children = self.block_tree.get_children()

            for idx, item_id in enumerate(children, start=1):
                vals = self.block_tree.item(item_id, "values")
                ini.set("FrequencyBlocks", f"block_{idx}_start", str(vals[0]))
                ini.set("FrequencyBlocks", f"block_{idx}_stop", str(vals[1]))
                ini.set("FrequencyBlocks", f"block_{idx}_steps", str(vals[2]))
                ini.set("FrequencyBlocks", f"block_{idx}_scale", str(vals[3]))
                ini.set("FrequencyBlocks", f"block_{idx}_precision", str(vals[4]))
                
                exc_str = str(vals[5]) if len(vals) > 5 else "Current (Strom)"
                exc_code = "1" if ("Voltage" in exc_str or "1" in exc_str) else "2"
                ini.set("FrequencyBlocks", f"block_{idx}_exc_type", exc_code)

                amp_str = str(vals[6]) if len(vals) > 6 else "0.0001"
                ini.set("FrequencyBlocks", f"block_{idx}_amplitude", amp_str)

            first_vals = self.block_tree.item(children[0], "values") if children else ("100.0", "10000000.0", "101", "logarithmic", "1.0", "Current (Strom)", "0.0001")
            ini.set("FrequencySetup", "mode", "sweep")
            ini.set("FrequencySetup", "start_frequency_hz", str(first_vals[0]))
            ini.set("FrequencySetup", "stop_frequency_hz", str(first_vals[1]))
            ini.set("FrequencySetup", "count", str(first_vals[2]))
            ini.set("FrequencySetup", "scale", str(first_vals[3]))
            ini.set("FrequencySetup", "precision", str(first_vals[4]))
            
            first_exc = str(first_vals[5]) if len(first_vals) > 5 else "Current (Strom)"
            ini.set("FrequencySetup", "excitation_type", "1" if ("Voltage" in first_exc or "1" in first_exc) else "2")
            
            first_amp = str(first_vals[6]) if len(first_vals) > 6 else self.amp_var.get().strip()
            ini.set("FrequencySetup", "amplitude", first_amp)

            ini.set("FrequencySetup", "point_delay_ms", self.delay_var.get().strip())
            ini.set("FrequencySetup", "phase_sync", str(self.phase_sync_var.get()))

            ini.set("DCBias", "dc_bias_enabled", str(self.dc_bias_var.get()))
            ini.set("DCBias", "bias_voltage_v", self.bias_volt_var.get().strip())
            ini.set("SyncTime", "sync_time_us", self.sync_time_var.get().strip())

            ts_str = self.ts_mode_var.get().split()[0]
            ini.set("Options", "timestamp_mode", ts_str)
            ini.set("Options", "enable_current_range_output", str(self.curr_range_out_var.get()))

            ini.set("Measurement", "number_of_spectra", self.spectra_var.get().strip())
            ini.set("ApiSettings", "plot_type", self.plot_type_var.get())
            ini.set("ApiSettings", "continuous_measurement", "False")
            if ini.has_option("ApiSettings", "use_hardware_sweep"):
                ini.remove_option("ApiSettings", "use_hardware_sweep")
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