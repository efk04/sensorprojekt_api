"""
config_gui.py - Grafisches Konfigurationsfenster fuer das Sciospec ISX-3.

Bietet dynamische Einheitenumschaltung (Standard: Peak A/V vs. Medical: Peak-to-Peak App/Vpp),
Frequenzblock-Tabellen, MUX-Pin-Hilfe (inkl. Multi-Pin Electrode Ganging),
Aenderungserkennung vor Messstart sowie den synchronen System-Baseline-Drift-Check.
"""

import os
import configparser
import tkinter as tk
from tkinter import messagebox, ttk
import serial.tools.list_ports

from .commands import ISX3
from .measurement import Measurement
from .config_handler import (
    parse_frequency_input,
    parse_precision_input,
    parse_value_with_prefix,
)


class ConfigGUI:
    """Tkinter-Hauptfenster fuer Konfiguration, Hardware-Diagnose und Messsteuerung."""

    PRECISION_PRESETS = [
        "0 (low - fastest)",
        "1 (medium - default)",
        "2 (high - slow)",
        "3 (very high - slowest)",
    ]

    DEVICE_VERSIONS = [
        "standard (ISX-3 / ISX-3mini)",
        "medical (Medical Research ISX-3)",
    ]

    EXC_VALUES_STANDARD = [
        "1 (Voltage / Spannung in V Peak)",
        "2 (Current / Strom in A Peak)",
    ]
    EXC_VALUES_MEDICAL = [
        "1 (Voltage / Spannung in Vpp)",
        "2 (Current / Strom in App)",
    ]

    # Laut Handbuch Kap. 8.5.5 (0xB0) sind fuer Voltage Range nur 1 und 2 zulaessig
    VR_VALUES_STANDARD = [
        "1 (±1.0 V Peak Default)",
        "2 (±0.09 V / ±90 mV Peak High Gain)",
    ]
    VR_VALUES_MEDICAL = [
        "1 (±2.0 Vpp / ±1.0 Vp Default)",
        "2 (±180 mVpp / ±90 mVp High Gain)",
    ]

    # Strommessbereiche (0 = Dynamisches Autoranging)
    CR_VALUES_STANDARD = [
        "0 (Autoranging - Dynamisch)",
        "1 (±10 mA / 100 Ω)",
        "2 (±100 µA / 10 kΩ)",
        "4 (±1 µA / 1 MΩ)",
        "6 (±10 nA / 100 MΩ)",
    ]
    CR_VALUES_MEDICAL = [
        "0 (Autoranging - Dynamisch für L/C)",
        "1 (±10 mA / 100 Ω Range)",
        "2 (±100 µA / 10 kΩ Range)",
        "4 (±1 µA / 1 MΩ Range)",
        "6 (±10 nA / 100 MΩ Range)",
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Sciospec ISX-3 - Professioneller Mess-Manager (Standard & Medical)")
        self.root.geometry("1120x910")
        self.root.minsize(1000, 800)

        self.config_dir = os.path.abspath("config")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_path = os.path.join(self.config_dir, "config.ini")
        self._saved_snapshot = None

        if not os.path.exists(self.config_path):
            self._write_default_ini(self.config_path)

        self._build_ui()
        self.load_ini_to_form()

    def _is_medical(self) -> bool:
        """Prueft, ob der Medical-Modus aktiv ist."""
        return "medical" in self.device_version_var.get().lower()

    def _get_form_state_snapshot(self) -> tuple:
        """Erstellt einen eindeutigen Fingerabdruck aller aktuellen GUI-Einstellungen."""
        blocks_state = tuple(
            tuple(str(v) for v in self.block_tree.item(item_id, "values"))
            for item_id in self.block_tree.get_children()
        )
        return (
            self.profile_name_var.get().strip(),
            self.device_version_var.get(),
            self.port_var.get().strip(),
            self.baud_var.get().strip(),
            self.mode_selector_var.get(),
            self.main_bnc_mode_var.get(),
            self.mux_sensors_var.get().strip(),
            self.mux_mode_var.get().strip(),
            self.mux_chan_var.get(),
            self.mux_delay_var.get().strip(),
            self.exc_type_var.get(),
            self.amp_var.get().strip(),
            self.curr_range_var.get(),
            self.volt_range_var.get(),
            self.spectra_var.get().strip(),
            self.delay_var.get().strip(),
            self.sync_time_var.get().strip(),
            bool(self.phase_sync_var.get()),
            self.ts_mode_var.get(),
            bool(self.curr_range_out_var.get()),
            bool(self.live_plot_enabled_var.get()),
            self.plot_type_var.get(),
            self.live_plot_mode_var.get(),
            blocks_state,
        )

    def _has_unsaved_changes(self) -> bool:
        """Gibt True zurueck, wenn seit dem letzten Laden/Speichern etwas verstellt wurde."""
        if self._saved_snapshot is None:
            return True
        return self._get_form_state_snapshot() != self._saved_snapshot

    @staticmethod
    def _write_default_ini(target_path: str) -> None:
        """Schreibt eine Standardkonfiguration, falls noch keine existiert."""
        default_content = """[Connection]
device_version = standard
port = COM12
baudrate = 115200

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

    def _show_pin_help(self) -> None:
        """Zeigt ein Informationsfenster fuer die MUX-Pin-Adressierung an."""
        help_text = (
            "Hilfe zur Pin-Belegung (MUX32 / MUX64 / TipSensor):\n\n"
            "1. Standard-Bereiche & Listen (z.B. '1-2' oder '1,3'):\n"
            "   • Automatische 4-Leiter-Berechnung (Sensor 1 -> 1,2,3,4; Sensor 2 -> 5,6,7,8).\n"
            "   • Im 2-Leiter-Modus automatisch 2 Pins pro Sensor (Sensor 1 -> 1,1,2,2).\n\n"
            "2. Individuelle 4-Pin-Belegung mit Doppelpunkt (CE, RE, WS, WE):\n"
            "   • Beispiel: '1: 2,5,8,6' oder '22: 22,22,23,23'\n"
            "   • Mehrere Sensoren mit Semikolon: '1: 2,5,8,6; 2: 22,22,23,23'\n\n"
            "3. Parallelschalten mehrerer Elektroden (Multi-Pin Ganging):\n"
            "   • Beispiel fuer TipSensor / Streifenelektroden:\n"
            "     '1: CE:1,5,9, RE:2,6,10, WS:3,7,11, WE:4,8,12'\n"
            "   • Mehrere Konfigurationen nacheinander mit Semikolon ';' trennen."
        )
        messagebox.showinfo("MUX Pin-Belegung", help_text, parent=self.root)

    def _show_device_comparison_info(self) -> None:
        """Zeigt Details zu Geraete-Unterschieden an."""
        info_text = (
            "Detaillierter Vergleich: Standard ISX-3 vs. Medical Research ISX-3\n"
            "==================================================================\n\n"
            "1. AMPLITUDEN-EINGABE (Peak vs. Peak-to-Peak):\n"
            "   • Standard ISX-3: Eingabe als echter Spitzenwert (Peak: A bzw. V).\n"
            "   • Medical Research ISX-3: Eingabe als Spitze-Spitze (App bzw. Vpp).\n"
            "     -> Die API halbiert App / Vpp automatisch fuer die Hardware!\n\n"
            "2. SPANNUNGSMESSBEREICHE (Voltage Range in 0xB0):\n"
            "   • Standard: 1 = ±1.0 V Peak | 2 = ±0.09 V (±90 mV) Peak\n"
            "   • Medical: 1 = ±2.0 Vpp | 2 = ±180 mVpp\n\n"
            "3. SYSTEM-BASELINE-DRIFT-CHECK:\n"
            "   • Ueberprueft die thermische Stabilitaet des internen 2 kΩ Referenzpfads auf MUX-Port 3."
        )
        messagebox.showinfo("Info: Standard vs. Medical Einstellungen", info_text, parent=self.root)

    def _log(self, msg: str) -> None:
        """Gibt Meldungen im Statusfenster der GUI und im Terminal aus."""
        if hasattr(self, "log_text"):
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.root.update_idletasks()
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
        # 1. Profil-Verwaltung oben
        profile_frame = ttk.LabelFrame(self.root, text=" Profil-Verwaltung & Diagnose ", padding=8)
        profile_frame.pack(fill=tk.X, padx=10, pady=4)

        ttk.Label(profile_frame, text="Profil-Name:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.profile_name_var = tk.StringVar(value="config")
        ttk.Entry(profile_frame, textvariable=self.profile_name_var, width=18).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Button(profile_frame, text="Profil speichern", command=self.save_named_profile).grid(row=0, column=2, padx=5)

        ttk.Label(profile_frame, text="Vorhandene Profile:").grid(row=0, column=3, sticky=tk.W, padx=10)
        self.profiles_combo = ttk.Combobox(profile_frame, width=20, state="readonly")
        self.profiles_combo.grid(row=0, column=4, padx=5)
        self.profiles_combo.bind("<<ComboboxSelected>>", self.load_selected_profile)
        self.refresh_profile_list()

        ttk.Button(
            profile_frame,
            text="System-Baseline-Drift-Check",
            command=self.run_selftest_action,
        ).grid(row=0, column=5, padx=10)

        ttk.Button(profile_frame, text="MESSUNG STARTEN", command=self.start_measurement_action).grid(
            row=0, column=6, padx=10, sticky=tk.E
        )

        # 2. Status-Banner oben
        self.info_banner_frame = tk.Frame(self.root, bg="#e8f4f8", highlightbackground="#006699", highlightthickness=1, padx=10, pady=6)
        self.info_banner_frame.pack(fill=tk.X, padx=10, pady=4)

        self.info_banner_label = tk.Label(
            self.info_banner_frame,
            text="",
            bg="#e8f4f8",
            fg="#00334e",
            font=("Segoe UI", 9, "bold"),
            justify=tk.LEFT,
            anchor="w",
        )
        self.info_banner_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(
            self.info_banner_frame,
            text="Details (Standard vs. Medical)",
            command=self._show_device_comparison_info,
        ).pack(side=tk.RIGHT, padx=5)

        # 3. Haupt-Notebook
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        tab_main = ttk.Frame(notebook, padding=10)
        tab_signal = ttk.Frame(notebook, padding=10)
        tab_plot = ttk.Frame(notebook, padding=10)

        notebook.add(tab_main, text=" 1. Geraet, USB/COM, Kanal & Frequenzbloecke ")
        notebook.add(tab_signal, text=" 2. Anregung, Messbereiche & Timing ")
        notebook.add(tab_plot, text=" 3. Zeitstempel & Live-Plot ")

        # TAB 1: Verbindung
        conn_frame = ttk.LabelFrame(tab_main, text=" Geraete-Modell & Serielle Verbindung (USB / Virtual COM Port) ", padding=8)
        conn_frame.pack(fill=tk.X, pady=4)

        ttk.Label(conn_frame, text="Geraete-Modell:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=4)
        self.device_version_var = tk.StringVar(value=self.DEVICE_VERSIONS[0])
        dev_combo = ttk.Combobox(
            conn_frame,
            textvariable=self.device_version_var,
            values=self.DEVICE_VERSIONS,
            width=32,
            state="readonly",
        )
        dev_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=4)
        dev_combo.bind("<<ComboboxSelected>>", self._on_device_version_change)

        ttk.Label(conn_frame, text="COM-Port:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5), pady=4)
        self.port_var = tk.StringVar(value="COM12")
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, values=self._get_available_com_ports(), width=10)
        self.port_combo.grid(row=0, column=3, padx=3, pady=4)
        ttk.Button(conn_frame, text="Neu laden", command=self._refresh_com_ports).grid(row=0, column=4, padx=2, pady=4)

        ttk.Label(conn_frame, text="Baudrate:").grid(row=0, column=5, sticky=tk.W, padx=(15, 5), pady=4)
        self.baud_var = tk.StringVar(value="115200")
        ttk.Combobox(conn_frame, textvariable=self.baud_var, values=["9600", "57600", "115200", "230400", "921600"], width=10).grid(row=0, column=6, padx=3, pady=4)

        # TAB 1: Routing & MUX
        mode_frame = ttk.LabelFrame(tab_main, text=" Betriebsart & Hardware-Routing (0xB0 / 0xB2) ", padding=8)
        mode_frame.pack(fill=tk.X, pady=4)

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
        ttk.Entry(self.frame_mux, textvariable=self.mux_sensors_var, width=28).grid(row=0, column=1, padx=5)

        ttk.Button(self.frame_mux, text="Hilfe zu Pins", command=self._show_pin_help).grid(row=0, column=2, padx=5)

        ttk.Label(self.frame_mux, text="Leiter-Modus:").grid(row=0, column=3, sticky=tk.W, padx=8)
        self.mux_mode_var = tk.StringVar(value="4")
        ttk.Combobox(self.frame_mux, textvariable=self.mux_mode_var, values=["2", "4"], width=5, state="readonly").grid(row=0, column=4, padx=5)

        ttk.Label(self.frame_mux, text="MUX-Port (0xB0):").grid(row=0, column=5, sticky=tk.W, padx=8)
        self.mux_chan_var = tk.StringVar(value="2 (ext. Mux32 / ExtPort)")
        self.mux_chan_combo = ttk.Combobox(
            self.frame_mux,
            textvariable=self.mux_chan_var,
            values=["2 (ext. Mux32 / ExtPort)", "3 (int. Mux32 / InternalMux)"],
            width=24,
            state="readonly",
        )
        self.mux_chan_combo.grid(row=0, column=6, padx=5)

        ttk.Label(self.frame_mux, text="Switch Delay (s):").grid(row=0, column=7, sticky=tk.W, padx=8)
        self.mux_delay_var = tk.StringVar(value="0.10")
        ttk.Entry(self.frame_mux, textvariable=self.mux_delay_var, width=7).grid(row=0, column=8, padx=5)

        # TAB 1: Frequenz-Bloecke
        block_frame = ttk.LabelFrame(tab_main, text=" Frequenz-Bloecke & Block-Spezifische Anregung (0xB6 0x03) ", padding=8)
        block_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        columns = ("min_f", "max_f", "steps", "scale", "precision", "exc_type", "amplitude")
        self.block_tree = ttk.Treeview(block_frame, columns=columns, show="headings", height=4)
        self.block_tree.heading("min_f", text="Min f [Hz]")
        self.block_tree.heading("max_f", text="Max f [Hz]")
        self.block_tree.heading("steps", text="Steps")
        self.block_tree.heading("scale", text="Scale")
        self.block_tree.heading("precision", text="Precision")
        self.block_tree.heading("exc_type", text="Anregung")
        self.block_tree.heading("amplitude", text="Amplitude [A / V]")

        self.block_tree.column("min_f", width=105, anchor=tk.CENTER)
        self.block_tree.column("max_f", width=105, anchor=tk.CENTER)
        self.block_tree.column("steps", width=60, anchor=tk.CENTER)
        self.block_tree.column("scale", width=90, anchor=tk.CENTER)
        self.block_tree.column("precision", width=85, anchor=tk.CENTER)
        self.block_tree.column("exc_type", width=130, anchor=tk.CENTER)
        self.block_tree.column("amplitude", width=130, anchor=tk.CENTER)
        self.block_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.block_tree.bind("<Double-1>", lambda event: self._edit_frequency_block())

        btn_subframe = ttk.Frame(block_frame)
        btn_subframe.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)

        ttk.Button(btn_subframe, text="Block hinzufuegen", command=self._add_frequency_block).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_subframe, text="Block bearbeiten", command=self._edit_frequency_block).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_subframe, text="Block loeschen", command=self._delete_frequency_block).pack(side=tk.LEFT, padx=3)

        # TAB 2: Signal & Bereiche
        exc_frame = ttk.LabelFrame(tab_signal, text=" Globale Anregung & Analoge Frontend-Messbereiche ", padding=10)
        exc_frame.pack(fill=tk.X, pady=5)

        self.tab2_mode_hint = tk.Label(
            exc_frame,
            text="",
            bg="#fff8dc",
            fg="#333333",
            font=("Segoe UI", 9),
            justify=tk.LEFT,
            anchor="w",
            padx=8,
            pady=5,
            relief=tk.SOLID,
            bd=1,
        )
        self.tab2_mode_hint.grid(row=0, column=0, columnspan=3, sticky=tk.W + tk.E, padx=5, pady=6)

        ttk.Label(exc_frame, text="Globale Anregungsart:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        self.exc_type_var = tk.StringVar(value=self.EXC_VALUES_STANDARD[1])
        self.exc_combo = ttk.Combobox(
            exc_frame,
            textvariable=self.exc_type_var,
            values=self.EXC_VALUES_STANDARD,
            width=34,
            state="readonly",
        )
        self.exc_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=4)
        self.exc_combo.bind("<<ComboboxSelected>>", self._on_excitation_change)

        self.amp_label = ttk.Label(exc_frame, text="Globale Signalamplitude [A / V Peak]:")
        self.amp_label.grid(row=2, column=0, sticky=tk.W, padx=5, pady=4)
        self.amp_var = tk.StringVar(value="0.0001")
        ttk.Entry(exc_frame, textvariable=self.amp_var, width=36).grid(row=2, column=1, sticky=tk.W, padx=5, pady=4)
        self.amp_unit_hint = ttk.Label(exc_frame, text="(z.B. 0.0001 = 100 µA Peak)", foreground="#555555")
        self.amp_unit_hint.grid(row=2, column=2, sticky=tk.W, padx=5)

        ttk.Label(exc_frame, text="Current Range (Strommessbereich):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=4)
        self.curr_range_var = tk.StringVar(value=self.CR_VALUES_STANDARD[2])
        self.curr_range_combo = ttk.Combobox(
            exc_frame,
            textvariable=self.curr_range_var,
            values=self.CR_VALUES_STANDARD,
            width=34,
            state="readonly",
        )
        self.curr_range_combo.grid(row=3, column=1, sticky=tk.W, padx=5, pady=4)

        self.volt_range_label = ttk.Label(exc_frame, text="Voltage Range (Spannungsmessbereich):")
        self.volt_range_label.grid(row=4, column=0, sticky=tk.W, padx=5, pady=4)
        self.volt_range_var = tk.StringVar(value=self.VR_VALUES_STANDARD[0])
        self.volt_range_combo = ttk.Combobox(
            exc_frame,
            textvariable=self.volt_range_var,
            values=self.VR_VALUES_STANDARD,
            width=34,
            state="readonly",
        )
        self.volt_range_combo.grid(row=4, column=1, sticky=tk.W, padx=5, pady=4)

        prec_frame = ttk.LabelFrame(tab_signal, text=" Timing, Spektrale Wiederholungen & Mittelung ", padding=10)
        prec_frame.pack(fill=tk.X, pady=5)

        ttk.Label(prec_frame, text="Anzahl Spectra (Average Count / Wiederholungen):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=4)
        self.spectra_var = tk.StringVar(value="3")
        ttk.Entry(prec_frame, textvariable=self.spectra_var, width=28).grid(row=0, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(prec_frame, text="Point Delay / Settling Time (ms):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=4)
        self.delay_var = tk.StringVar(value="20.0")
        ttk.Entry(prec_frame, textvariable=self.delay_var, width=28).grid(row=1, column=1, sticky=tk.W, padx=5, pady=4)

        ttk.Label(prec_frame, text="Sync-Time zwischen Sweeps (µs):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=4)
        self.sync_time_var = tk.StringVar(value="0")
        ttk.Entry(prec_frame, textvariable=self.sync_time_var, width=28).grid(row=2, column=1, sticky=tk.W, padx=5, pady=4)

        self.phase_sync_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            prec_frame,
            text="Phase Synchronization aktivieren (nur fuer f >= 100 kHz)",
            variable=self.phase_sync_var,
        ).grid(row=3, column=0, columnspan=3, sticky=tk.W, padx=5, pady=4)

        # TAB 3: Optionen & Plot
        opt_frame = ttk.LabelFrame(tab_plot, text=" Datenframe-Optionen (0x97) ", padding=10)
        opt_frame.pack(fill=tk.X, pady=5)

        ttk.Label(opt_frame, text="Hardware-Zeitstempel (in HDF5 unter 'hw_timestamp'):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.ts_mode_var = tk.StringVar(value="0 (Aus)")
        ttk.Combobox(
            opt_frame,
            textvariable=self.ts_mode_var,
            values=["0 (Aus)", "1 (Millisekunden - 4 Byte)", "2 (Mikrosekunden - 5 Byte)"],
            width=26,
            state="readonly",
        ).grid(row=0, column=1, columnspan=2, sticky=tk.W, padx=5, pady=3)

        self.curr_range_out_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            opt_frame,
            text="Aktuellen Current-Range im Messframe ausgeben (Option 0x04)",
            variable=self.curr_range_out_var,
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=3)

        plot_frame = ttk.LabelFrame(tab_plot, text=" Visualisierung & Live-Plot Optionen ", padding=10)
        plot_frame.pack(fill=tk.X, pady=5)

        self.live_plot_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(plot_frame, text="Live-Plot waehrend Messung anzeigen", variable=self.live_plot_enabled_var).grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)

        ttk.Label(plot_frame, text="Diagramm-Typ:").grid(row=0, column=1, sticky=tk.W, padx=15, pady=3)
        self.plot_type_var = tk.StringVar(value="bode")
        ttk.Combobox(
            plot_frame,
            textvariable=self.plot_type_var,
            values=["bode", "bode_lin", "nyquist", "impedance_frequency"],
            width=22,
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
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        self.log_text = tk.Text(log_frame, height=6, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._on_mode_change(None)
        self._update_device_specific_labels()

    def _update_device_specific_labels(self) -> None:
        """Passt Labels und Hinweise je nach gewaehltem Geraetetyp an."""
        is_med = self._is_medical()

        exc_code = "1" if self.exc_type_var.get().startswith("1") else "2"
        vr_code = self.volt_range_var.get().split()[0] if self.volt_range_var.get() else "1"
        if vr_code not in ("1", "2"):
            vr_code = "1"
        cr_code = self.curr_range_var.get().split()[0] if self.curr_range_var.get() else "2"

        if is_med:
            self.info_banner_frame.configure(bg="#e6f7ee", highlightbackground="#1b8a5a")
            self.info_banner_label.configure(
                bg="#e6f7ee",
                fg="#0d4d31",
                text=(
                    "AKTIVER MODUS: MEDICAL RESEARCH ISX-3\n"
                    "• Amplituden-Eingabe: Spitze-Spitze in App / Vpp (API halbiert automatisch fuer Hardware).\n"
                    "• Spannungsbereiche: ±2.0 Vpp / ±180 mVpp | Interner MUX = Port 3."
                ),
            )
            self.tab2_mode_hint.configure(
                bg="#e6f7ee",
                fg="#0d4d31",
                text=(
                    "Medical-Modus aktiv: Gib Amplituden als App / Vpp (Spitze-Spitze) ein.\n"
                    "Fuer Spulen (L) und Kondensatoren (C) empfiehlt sich Current Range = '0 (Autoranging)'."
                ),
            )
            self.exc_combo["values"] = self.EXC_VALUES_MEDICAL
            self.exc_type_var.set(self.EXC_VALUES_MEDICAL[0] if exc_code == "1" else self.EXC_VALUES_MEDICAL[1])

            self.volt_range_combo["values"] = self.VR_VALUES_MEDICAL
            vr_map = {"1": self.VR_VALUES_MEDICAL[0], "2": self.VR_VALUES_MEDICAL[1]}
            self.volt_range_var.set(vr_map.get(vr_code, self.VR_VALUES_MEDICAL[0]))

            self.curr_range_combo["values"] = self.CR_VALUES_MEDICAL
            cr_map = {c.split()[0]: c for c in self.CR_VALUES_MEDICAL}
            self.curr_range_var.set(cr_map.get(cr_code, self.CR_VALUES_MEDICAL[2]))

            unit_str = "Vpp" if exc_code == "1" else "App"
            self.amp_label.configure(text=f"Globale Signalamplitude [{unit_str} (Spitze-Spitze)]:")
            self.amp_unit_hint.configure(text=f"(z.B. 0.0001 oder 100u = 100 µ{unit_str})")
            self.block_tree.heading("amplitude", text="Amplitude [App / Vpp]")
        else:
            self.info_banner_frame.configure(bg="#e8f4f8", highlightbackground="#006699")
            self.info_banner_label.configure(
                bg="#e8f4f8",
                fg="#00334e",
                text=(
                    "AKTIVER MODUS: STANDARD ISX-3 / ISX-3mini\n"
                    "• Amplituden-Eingabe: Echter Spitzenwert (Peak) in A / V (wird 1:1 an Hardware gesendet).\n"
                    "• Spannungsbereiche: ±1.0 V Peak / ±0.09 V Peak | MUX ueber Extension Port (Port 2 via 0xB2)."
                ),
            )
            self.tab2_mode_hint.configure(
                bg="#e8f4f8",
                fg="#00334e",
                text=(
                    "Standard-Modus aktiv: Gib Amplituden als echte Spitzenwerte (Peak in A / V) ein.\n"
                    "0.0001 entspricht hier direkt 100 µA Peak."
                ),
            )
            self.exc_combo["values"] = self.EXC_VALUES_STANDARD
            self.exc_type_var.set(self.EXC_VALUES_STANDARD[0] if exc_code == "1" else self.EXC_VALUES_STANDARD[1])

            self.volt_range_combo["values"] = self.VR_VALUES_STANDARD
            vr_map = {"1": self.VR_VALUES_STANDARD[0], "2": self.VR_VALUES_STANDARD[1]}
            self.volt_range_var.set(vr_map.get(vr_code, self.VR_VALUES_STANDARD[0]))

            self.curr_range_combo["values"] = self.CR_VALUES_STANDARD
            cr_map = {c.split()[0]: c for c in self.CR_VALUES_STANDARD}
            self.curr_range_var.set(cr_map.get(cr_code, self.CR_VALUES_STANDARD[2]))

            unit_str = "V Peak" if exc_code == "1" else "A Peak"
            self.amp_label.configure(text=f"Globale Signalamplitude [{unit_str}]:")
            self.amp_unit_hint.configure(text=f"(z.B. 0.0001 = 100 µ{unit_str[0]} Peak)")
            self.block_tree.heading("amplitude", text="Amplitude [A / V Peak]")

        for item_id in self.block_tree.get_children():
            vals = list(self.block_tree.item(item_id, "values"))
            if len(vals) >= 6:
                is_volt = "Voltage" in str(vals[5]) or str(vals[5]).strip() == "1"
                if is_med:
                    vals[5] = "Voltage [Vpp]" if is_volt else "Current [App]"
                else:
                    vals[5] = "Voltage [V Peak]" if is_volt else "Current [A Peak]"
                self.block_tree.item(item_id, values=vals)

    def _on_device_version_change(self, event) -> None:
        self._update_device_specific_labels()
        if self._is_medical():
            self._log("[INFO] Medical Research ISX-3 gewaehlt: Eingaben in App / Vpp, int. MUX Port 3 aktiv.")
        else:
            self._log("[INFO] Standard ISX-3 gewaehlt: Eingaben in A / V (Peak), ext. MUX Port 2 aktiv.")

    def _add_frequency_block(self) -> None:
        is_med = self._is_medical()
        dlg = tk.Toplevel(self.root)
        dlg.title("Frequenzblock hinzufuegen")
        dlg.geometry("430x450")
        dlg.transient(self.root)
        dlg.grab_set()

        mode_note = "Medical-Modus: Amplitude als Spitze-Spitze (App / Vpp)" if is_med else "Standard-Modus: Amplitude als Spitzenwert (A / V Peak)"
        lbl_hint = ttk.Label(dlg, text=f"Einheiten wie '100k', '1M' oder '100u' werden erkannt.\n{mode_note}", foreground="#0055aa", justify=tk.LEFT)
        lbl_hint.grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=6)

        ttk.Label(dlg, text="Min f [Hz]:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        e_min = ttk.Entry(dlg, width=22)
        e_min.grid(row=1, column=1, padx=10, pady=5)
        e_min.insert(0, "100")

        ttk.Label(dlg, text="Max f [Hz]:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        e_max = ttk.Entry(dlg, width=22)
        e_max.grid(row=2, column=1, padx=10, pady=5)
        e_max.insert(0, "1M")

        ttk.Label(dlg, text="Steps (Punkte):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        e_steps = ttk.Entry(dlg, width=22)
        e_steps.grid(row=3, column=1, padx=10, pady=5)
        e_steps.insert(0, "21")

        ttk.Label(dlg, text="Scale:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        cb_scale = ttk.Combobox(dlg, values=["logarithmic", "linear"], width=20, state="readonly")
        cb_scale.grid(row=4, column=1, padx=10, pady=5)
        cb_scale.set("logarithmic")

        ttk.Label(dlg, text="Precision:").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
        cb_prec = ttk.Combobox(dlg, values=self.PRECISION_PRESETS, width=20, state="normal")
        cb_prec.grid(row=5, column=1, padx=10, pady=5)
        cb_prec.set("1 (medium - default)")

        exc_choices = ["Current [App]", "Voltage [Vpp]"] if is_med else ["Current [A Peak]", "Voltage [V Peak]"]
        ttk.Label(dlg, text="Anregungsart:").grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
        cb_exc = ttk.Combobox(dlg, values=exc_choices, width=20, state="readonly")
        cb_exc.grid(row=6, column=1, padx=10, pady=5)
        cb_exc.set(exc_choices[0])

        amp_lbl_text = "Amplitude [App / Vpp]:" if is_med else "Amplitude [A / V Peak]:"
        ttk.Label(dlg, text=amp_lbl_text).grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)
        e_amp = ttk.Entry(dlg, width=22)
        e_amp.grid(row=7, column=1, padx=10, pady=5)
        e_amp.insert(0, "0.0001")

        def on_ok():
            try:
                mn = parse_frequency_input(e_min.get().strip())
                mx = parse_frequency_input(e_max.get().strip())
                st = int(e_steps.get().strip())
                sc = cb_scale.get()
                pr = parse_precision_input(cb_prec.get())
                is_v = "Voltage" in cb_exc.get()
                exc = ("Voltage [Vpp]" if is_med else "Voltage [V Peak]") if is_v else ("Current [App]" if is_med else "Current [A Peak]")
                amp = parse_value_with_prefix(e_amp.get().strip())
                self.block_tree.insert("", tk.END, values=(mn, mx, st, sc, pr, exc, amp))
                dlg.destroy()
            except Exception as ex:
                messagebox.showerror("Fehler", f"Ungueltige Eingabe: {ex}", parent=dlg)

        ttk.Button(dlg, text="Hinzufuegen", command=on_ok).grid(row=8, column=0, columnspan=2, pady=12)

    def _edit_frequency_block(self) -> None:
        selected = self.block_tree.selection()
        if not selected:
            messagebox.showwarning("Kein Block gewaehlt", "Bitte waehle einen Frequenzblock in der Tabelle aus.")
            return

        is_med = self._is_medical()
        item_id = selected[0]
        vals = self.block_tree.item(item_id, "values")

        dlg = tk.Toplevel(self.root)
        dlg.title("Frequenzblock bearbeiten")
        dlg.geometry("430x450")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Min f [Hz]:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        e_min = ttk.Entry(dlg, width=22)
        e_min.grid(row=1, column=1, padx=10, pady=5)
        e_min.insert(0, vals[0])

        ttk.Label(dlg, text="Max f [Hz]:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        e_max = ttk.Entry(dlg, width=22)
        e_max.grid(row=2, column=1, padx=10, pady=5)
        e_max.insert(0, vals[1])

        ttk.Label(dlg, text="Steps (Punkte):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        e_steps = ttk.Entry(dlg, width=22)
        e_steps.grid(row=3, column=1, padx=10, pady=5)
        e_steps.insert(0, vals[2])

        ttk.Label(dlg, text="Scale:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        cb_scale = ttk.Combobox(dlg, values=["logarithmic", "linear"], width=20, state="readonly")
        cb_scale.grid(row=4, column=1, padx=10, pady=5)
        cb_scale.set(vals[3])

        ttk.Label(dlg, text="Precision:").grid(row=5, column=0, sticky=tk.W, padx=10, pady=5)
        cb_prec = ttk.Combobox(dlg, values=self.PRECISION_PRESETS, width=20, state="normal")
        cb_prec.grid(row=5, column=1, padx=10, pady=5)
        cb_prec.set(self._format_precision_for_ui(float(vals[4])))

        exc_choices = ["Current [App]", "Voltage [Vpp]"] if is_med else ["Current [A Peak]", "Voltage [V Peak]"]
        ttk.Label(dlg, text="Anregungsart:").grid(row=6, column=0, sticky=tk.W, padx=10, pady=5)
        cb_exc = ttk.Combobox(dlg, values=exc_choices, width=20, state="readonly")
        cb_exc.grid(row=6, column=1, padx=10, pady=5)
        default_exc = vals[5] if len(vals) > 5 else exc_choices[0]
        cb_exc.set(exc_choices[1] if "Voltage" in str(default_exc) else exc_choices[0])

        amp_lbl_text = "Amplitude [App / Vpp]:" if is_med else "Amplitude [A / V Peak]:"
        ttk.Label(dlg, text=amp_lbl_text).grid(row=7, column=0, sticky=tk.W, padx=10, pady=5)
        e_amp = ttk.Entry(dlg, width=22)
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
                is_v = "Voltage" in cb_exc.get()
                exc = ("Voltage [Vpp]" if is_med else "Voltage [V Peak]") if is_v else ("Current [App]" if is_med else "Current [A Peak]")
                amp = parse_value_with_prefix(e_amp.get().strip())
                self.block_tree.item(item_id, values=(mn, mx, st, sc, pr, exc, amp))
                dlg.destroy()
            except Exception as ex:
                messagebox.showerror("Fehler", f"Ungueltige Eingabe: {ex}", parent=dlg)

        ttk.Button(dlg, text="Speichern", command=on_ok).grid(row=8, column=0, columnspan=2, pady=12)

    def _delete_frequency_block(self) -> None:
        selected = self.block_tree.selection()
        if not selected:
            messagebox.showwarning("Kein Block gewaehlt", "Bitte waehle einen Frequenzblock in der Tabelle aus.")
            return
        for item_id in selected:
            self.block_tree.delete(item_id)

    def _on_mode_change(self, event) -> None:
        if "MUX32" in self.mode_selector_var.get():
            self.frame_main.pack_forget()
            self.frame_mux.pack(fill=tk.BOTH, expand=True)
        else:
            self.frame_mux.pack_forget()
            self.frame_main.pack(fill=tk.BOTH, expand=True)

    def _on_excitation_change(self, event) -> None:
        self._update_device_specific_labels()

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
        if not sel:
            return
        target_path = os.path.join(self.config_dir, f"{sel}.ini")
        if os.path.exists(target_path):
            if self._has_unsaved_changes():
                ans = messagebox.askyesnocancel(
                    "Ungespeicherte Aenderungen",
                    f"Du hast im aktuellen Profil '{self.profile_name_var.get()}' Einstellungen geaendert, aber noch nicht gespeichert.\n\n"
                    f"Moechtest du die Aenderungen vor dem Wechsel zu '{sel}.ini' speichern?",
                    parent=self.root,
                )
                if ans is None:
                    # Abbrechen -> Auswahl in Combobox zuruecksetzen
                    self.profiles_combo.set(self.profile_name_var.get())
                    return
                if ans is True:
                    self.save_current_form()

            self.config_path = target_path
            self.profile_name_var.set(sel)
            self.load_ini_to_form()
            self._log(f"[OK] Profil gewechselt zu: {sel}.ini")

    def load_ini_to_form(self) -> None:
        """Laedt bestehende Werte aus der INI-Datei in alle Eingabefelder."""
        try:
            ini = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
            ini.read(self.config_path, encoding="utf-8")

            dev_ver = ini.get("Connection", "device_version", fallback="standard").strip().lower()
            is_med = "medical" in dev_ver
            self.device_version_var.set(self.DEVICE_VERSIONS[1] if is_med else self.DEVICE_VERSIONS[0])

            self.port_var.set(ini.get("Connection", "port", fallback="COM12"))
            self.baud_var.set(str(ini.getint("Connection", "baudrate", fallback=115200)))

            mux_enabled = ini.getboolean("MUX", "enabled", fallback=False)
            self.mode_selector_var.set("MUX32 Multiplexer (Zusatzkarte)" if mux_enabled else "Main Port (Front-BNC)")
            self.mux_sensors_var.set(ini.get("MUX", "active_sensors", fallback="1-8"))
            self.mux_mode_var.set(str(ini.getint("MUX", "mode", fallback=4)))
            m_chan = ini.getint("MUX", "channel", fallback=2)
            self.mux_chan_var.set("3 (int. Mux32 / InternalMux)" if m_chan == 3 else "2 (ext. Mux32 / ExtPort)")
            self.mux_delay_var.set(str(ini.getfloat("MUX", "switch_delay_s", fallback=0.10)))

            fe_mode = ini.getint("Frontend", "measurement_mode", fallback=2)
            fe_mode_map = {
                1: "1 (2-Leiter / 2-Point)",
                2: "2 (4-Leiter Kelvin / 4-Point)",
                3: "3 (3-Leiter / 3-Point)",
            }
            self.main_bnc_mode_var.set(fe_mode_map.get(fe_mode, "2 (4-Leiter Kelvin / 4-Point)"))

            cr_val = str(ini.getint("Frontend", "current_range", fallback=2))
            cr_list = self.CR_VALUES_MEDICAL if is_med else self.CR_VALUES_STANDARD
            cr_map = {c.split()[0]: c for c in cr_list}
            self.curr_range_var.set(cr_map.get(cr_val, cr_list[2]))

            vr_val = str(ini.getint("Frontend", "voltage_range", fallback=1))
            if vr_val not in ("1", "2"):
                vr_val = "1"
            vr_list = self.VR_VALUES_MEDICAL if is_med else self.VR_VALUES_STANDARD
            vr_map = {v.split()[0]: v for v in vr_list}
            self.volt_range_var.set(vr_map.get(vr_val, vr_list[0]))

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
                        is_v = "1" in exc_raw or "Volt" in exc_raw
                        exc_str = ("Voltage [Vpp]" if is_med else "Voltage [V Peak]") if is_v else ("Current [App]" if is_med else "Current [A Peak]")
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
                exc_str = ("Voltage [Vpp]" if is_med else "Voltage [V Peak]") if exc_t == 1 else ("Current [App]" if is_med else "Current [A Peak]")
                amp_val = ini.get("FrequencySetup", "amplitude", fallback="0.0001")
                self.block_tree.insert("", tk.END, values=(mn, mx, st, sc, pr, exc_str, amp_val))

            exc_t = ini.getint("FrequencySetup", "excitation_type", fallback=2)
            exc_list = self.EXC_VALUES_MEDICAL if is_med else self.EXC_VALUES_STANDARD
            self.exc_type_var.set(exc_list[0] if exc_t == 1 else exc_list[1])

            self.amp_var.set(ini.get("FrequencySetup", "amplitude", fallback="0.0001"))
            self.delay_var.set(ini.get("FrequencySetup", "point_delay_ms", fallback="20.0"))
            self.phase_sync_var.set(ini.getboolean("FrequencySetup", "phase_sync", fallback=False))

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

            self._on_mode_change(None)
            self._update_device_specific_labels()
            self._saved_snapshot = self._get_form_state_snapshot()
            self._log(f"[OK] Profil geladen: {os.path.basename(self.config_path)}")
        except Exception as e:
            messagebox.showerror("Fehler beim Laden", str(e))

    def save_named_profile(self) -> None:
        name = self.profile_name_var.get().strip()
        if not name:
            messagebox.showwarning("Name fehlt", "Bitte gib einen gueltigen Profilnamen ein.")
            return
        self.config_path = os.path.join(self.config_dir, f"{name}.ini")
        if self.save_current_form():
            self.refresh_profile_list()
            self.profiles_combo.set(name)
            messagebox.showinfo("Gespeichert", f"Profil '{name}.ini' wurde vollstaendig gesichert.")

    def save_current_form(self) -> bool:
        """Schreibt alle Formulareinstellungen zurueck in die INI-Datei."""
        try:
            name = self.profile_name_var.get().strip() or "config"
            self.config_path = os.path.join(self.config_dir, f"{name}.ini")
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

            for old_tcp_key in ["interface_type", "ip_address", "tcp_port", "tcp_watchdog_interval_s"]:
                if ini.has_option("Connection", old_tcp_key):
                    ini.remove_option("Connection", old_tcp_key)

            dev_ver_str = "medical" if self._is_medical() else "standard"
            ini.set("Connection", "device_version", dev_ver_str)
            ini.set("Connection", "port", self.port_var.get().strip())
            ini.set("Connection", "baudrate", self.baud_var.get().strip())

            is_mux = "MUX32" in self.mode_selector_var.get()
            mux_ch_str = self.mux_chan_var.get().split()[0]
            ini.set("MUX", "enabled", str(is_mux))
            ini.set("MUX", "mode", self.mux_mode_var.get().strip())
            ini.set("MUX", "channel", mux_ch_str)
            ini.set("MUX", "active_sensors", self.mux_sensors_var.get().strip())
            ini.set("MUX", "switch_delay_s", self.mux_delay_var.get().strip())

            fe_mode_str = self.main_bnc_mode_var.get().split()[0]
            vr_str = self.volt_range_var.get().split()[0]
            if vr_str not in ("1", "2"):
                vr_str = "1"
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
                default_exc_lbl = "Current [App]" if self._is_medical() else "Current [A Peak]"
                self.block_tree.insert("", tk.END, values=("100.0", "10000000.0", "101", "logarithmic", "1.0", default_exc_lbl, "0.0001"))
                children = self.block_tree.get_children()

            for idx, item_id in enumerate(children, start=1):
                vals = self.block_tree.item(item_id, "values")
                ini.set("FrequencyBlocks", f"block_{idx}_start", str(vals[0]))
                ini.set("FrequencyBlocks", f"block_{idx}_stop", str(vals[1]))
                ini.set("FrequencyBlocks", f"block_{idx}_steps", str(vals[2]))
                ini.set("FrequencyBlocks", f"block_{idx}_scale", str(vals[3]))
                ini.set("FrequencyBlocks", f"block_{idx}_precision", str(vals[4]))

                exc_str = str(vals[5]) if len(vals) > 5 else "Current"
                exc_code = "1" if ("Voltage" in exc_str or str(exc_str).strip() == "1") else "2"
                ini.set("FrequencyBlocks", f"block_{idx}_exc_type", exc_code)

                amp_raw = vals[6] if len(vals) > 6 else "0.0001"
                amp_parsed = str(parse_value_with_prefix(amp_raw))
                ini.set("FrequencyBlocks", f"block_{idx}_amplitude", amp_parsed)

            first_vals = self.block_tree.item(children[0], "values")
            ini.set("FrequencySetup", "mode", "sweep")
            ini.set("FrequencySetup", "start_frequency_hz", str(first_vals[0]))
            ini.set("FrequencySetup", "stop_frequency_hz", str(first_vals[1]))
            ini.set("FrequencySetup", "count", str(first_vals[2]))
            ini.set("FrequencySetup", "scale", str(first_vals[3]))
            ini.set("FrequencySetup", "precision", str(first_vals[4]))

            first_exc = str(first_vals[5]) if len(first_vals) > 5 else "Current"
            ini.set("FrequencySetup", "excitation_type", "1" if ("Voltage" in first_exc or str(first_exc).strip() == "1") else "2")

            first_amp_raw = first_vals[6] if len(first_vals) > 6 else self.amp_var.get().strip()
            ini.set("FrequencySetup", "amplitude", str(parse_value_with_prefix(first_amp_raw)))

            ini.set("FrequencySetup", "point_delay_ms", self.delay_var.get().strip())
            ini.set("FrequencySetup", "phase_sync", str(self.phase_sync_var.get()))

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

            self._saved_snapshot = self._get_form_state_snapshot()
            self._log(f"[OK] Einstellungen gespeichert in: {os.path.basename(self.config_path)}")
            return True
        except Exception as e:
            messagebox.showerror("Fehler beim Speichern", str(e))
            return False

    def run_selftest_action(self) -> None:
        """Fuehrt die synchrone Baseline-Drift-Pruefung auf dem internen 2 kΩ Referenzpfad aus."""
        port = self.port_var.get().strip() or "COM12"
        try:
            baudrate = int(self.baud_var.get().strip() or 115200)
        except ValueError:
            baudrate = 115200

        self._log("\n" + "=" * 75)
        self._log(f"[BASELINE-CHECK] Starte Stabilitaetspruefung an {port} (MUX-Port 3)...")
        self._log("=" * 75)

        tester = ISX3()
        report = tester.run_baseline_drift_check(port=port, baudrate=baudrate, mux_channel=3, cycles=5, freq_hz=1000.0)

        if report.get("error"):
            err_msg = report["error"]
            self._log(f"[BASELINE-FEHLER] {err_msg}")
            messagebox.showerror("Baseline-Pruefung fehlgeschlagen", f"Fehler waehrend der Diagnose:\n{err_msg}", parent=self.root)
            return

        mean_z = report.get("mean_z", 0.0)
        drift_pct = report.get("drift_pct", 0.0)
        is_stable = report.get("stable", False)
        readings = report.get("readings", [])

        summary_lines = [f"Messwerte (5 Zyklen): {', '.join([f'{r:.2f} Ohm' for r in readings])}"]
        line = f"Mittelwert: {mean_z:.2f} Ohm | Maximaler Drift: {drift_pct:.3f}% (Grenze: <= 0.2%)"
        self._log(line)
        summary_lines.append(line)

        verdict_header = (
            "GESAMTERGEBNIS: SYSTEM STABIL UND EINSATZBEREIT!\nDie Drift liegt im zulaessigen Toleranzbereich (<= 0.2%)."
            if is_stable
            else "GESAMTERGEBNIS: SYSTEM DRIFTET ZU STARK!\nDie Abweichung ueberschreitet 0.2% - bitte Geraet warmwerden lassen."
        )
        self._log("-" * 75)
        self._log(verdict_header.replace("\n", " "))
        self._log("=" * 75)

        full_popup_text = f"{verdict_header}\n\n" + "\n\n".join(summary_lines)
        if is_stable:
            messagebox.showinfo("Baseline-Pruefung erfolgreich", full_popup_text, parent=self.root)
        else:
            messagebox.showwarning("Baseline-Pruefung: Instabilitaet erkannt", full_popup_text, parent=self.root)

    def start_measurement_action(self) -> None:
        """Prueft auf ungespeicherte Aenderungen, fragt den Nutzer und startet die Messkampagne."""
        if self._has_unsaved_changes():
            prof_name = self.profile_name_var.get().strip() or "config"
            ans = messagebox.askyesnocancel(
                "Ungespeicherte Aenderungen erkannt",
                f"Du hast die Einstellungen in der Oberfläche geaendert, aber noch nicht in '{prof_name}.ini' gespeichert.\n\n"
                "• [Ja]: Aenderungen jetzt speichern und damit messen (Empfohlen)\n"
                "• [Nein]: Aenderungen verwerfen und mit dem alten Stand der Datei messen\n"
                "• [Abbrechen]: Messung noch nicht starten",
                parent=self.root,
            )
            if ans is None:
                self._log("[INFO] Messstart abgebrochen (ungespeicherte Aenderungen).")
                return
            elif ans is True:
                if not self.save_current_form():
                    return
                self.refresh_profile_list()
                self.profiles_combo.set(prof_name)
            else:
                # Nutzer hat 'Nein' gewaehlt -> Formular auf den gespeicherten Datei-Stand zuruecksetzen
                self._log("[INFO] Ungespeicherte GUI-Aenderungen verworfen. Lade letzten Stand aus INI...")
                self.load_ini_to_form()

        self._log(f"\n[INFO] Starte Messkampagne mit '{os.path.basename(self.config_path)}'...")
        try:
            meas = Measurement()
            meas.measurement(config_path=self.config_path)
            self._log("[OK] Messung erfolgreich beendet.")
        except Exception as e:
            self._log(f"[FEHLER] {str(e)}")
            messagebox.showerror("Messfehler", str(e))


def run_gui():
    """Startet die GUI."""
    root = tk.Tk()
    app = ConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()