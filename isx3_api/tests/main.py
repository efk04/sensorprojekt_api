"""
main.py - Einstiegspunkt fuer das ISX-3 Mess-Framework.

Ermoeglicht drei Arbeitsweisen:
1. Grafische Benutzeroberflaeche (GUI) zur komfortablen Bedienung.
2. Laden einer vorhandenen INI-Datei ueber die Pfadeingabe.
3. Schrittweiser, interaktiver Konsolen-Assistent zur Erstellung neuer Profile.
"""

import sys
import os
import configparser
import serial.tools.list_ports

# Sicherstellen, dass das Modul isx3_api im src-Verzeichnis importiert werden kann
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from isx3_api.measurement import Measurement
from isx3_api.config_gui import run_gui
from isx3_api.config_handler import parse_value_with_prefix


def interactive_console_config() -> str | None:
    """
    Fuehrt interaktiv durch die Erstellung einer neuen .ini-Konfigurationsdatei
    direkt im Terminal (nuetzlich fuer Headless-Systeme ohne GUI).
    """
    print("\n" + "=" * 70)
    print(" INTERAKTIVE KONSOLEN-KONFIGURATION FUER SCIOSPEC ISX-3")
    print("=" * 70)

    config_dir = os.path.abspath("config")
    os.makedirs(config_dir, exist_ok=True)

    ini = configparser.ConfigParser()
    ini.optionxform = str

    # Alle Standard-Sektionen im Konfigurations-Objekt anlegen
    for sec in [
        "Connection", "MUX", "Frontend", "ExtensionPort",
        "FrequencySetup", "FrequencyBlocks", "DCBias", "SyncTime", "Options", "Measurement", "ApiSettings"
    ]:
        ini.add_section(sec)

    # 0. Geraete-Modell waehlen (Unterscheidung Standard vs. Medical Research)
    print("\n--- 0. GERAETE-MODELL WAEHLEN ---")
    print("  [1] ISX-3 / ISX-3mini (Standard - Klassisches 0xB0 / 0xB2 Protokoll) [Standard]")
    print("  [2] Medical Research ISX-3 (Neues 15-Byte 0xB0 Protokoll ohne 0xB2)")
    dev_choice = input("Waehle Geraete-Modell (1 oder 2) [Standard: 1]: ").strip()
    is_med = (dev_choice == "2")
    dev_ver = "medical" if is_med else "standard"
    ini.set("Connection", "device_version", dev_ver)

    print("\n" + "-" * 70)
    if is_med:
        print(" [INFOBOX: MEDICAL RESEARCH ISX-3 AKTIV]")
        print(" • Amplituden-Eingabe: Spitze-Spitze in App / Vpp (wie in der Sciospec-Software).")
        print("   Beispiel: '0.0001' (oder '100u') = 100 µApp -> API halbiert intern fuer Firmware.")
        print(" • Spannungsbereiche: ±2.0 Vpp (= ±1.0 Vp) bzw. ±180 mVpp (= ±90 mVp).")
    else:
        print(" [INFOBOX: STANDARD ISX-3 / ISX-3mini AKTIV]")
        print(" • Amplituden-Eingabe: Echter Spitzenwert (Peak) in A / V.")
        print("   Beispiel: '0.0001' = 100 µA Peak (wird 1:1 ohne Halbierung gesendet).")
        print(" • Spannungsbereiche: ±1.0 V Peak bzw. ±0.09 V (±90 mV) Peak.")
    print("-" * 70)

    # 1. Serielle Verbindung (USB / Virtueller COM-Port)
    print("\n--- 1. SERIELLE VERBINDUNG (USB / VIRTUAL COM PORT) ---")
    available_ports = [p.device for p in serial.tools.list_ports.comports()]
    if not available_ports:
        available_ports = ["COM12", "COM1", "COM3", "COM6"]

    print("  Verfuegbare COM-Ports:")
    for idx, p in enumerate(available_ports, 1):
        print(f"    [{idx}] {p}")

    port_in = input(f"Waehle Listenplatz (1-{len(available_ports)}) oder tippe Port (z.B. '12' fuer COM12): ").strip()
    if port_in.isdigit() and 1 <= int(port_in) <= len(available_ports):
        selected_port = available_ports[int(port_in) - 1]
    elif port_in.isdigit():
        selected_port = f"COM{port_in}"
    else:
        selected_port = port_in.upper() if port_in else "COM12"
        if not selected_port.startswith("COM"):
            selected_port = f"COM{selected_port}"
    ini.set("Connection", "port", selected_port)

    print("  Gaengige Baudraten:")
    print("    [1] 9600")
    print("    [2] 57600")
    print("    [3] 115200 [Standard]")
    print("    [4] 230400")
    print("    [5] 921600")
    print("    [6] Benutzerdefinierte Baudrate eingeben")
    baud_choice = input("Waehle Baudrate (1-6) [Standard: 3]: ").strip()
    baud_map = {"1": "9600", "2": "57600", "3": "115200", "4": "230400", "5": "921600"}
    if baud_choice in baud_map:
        selected_baud = baud_map[baud_choice]
    elif baud_choice == "6":
        selected_baud = input("Gib die benutzerdefinierte Baudrate als Zahl ein: ").strip()
    else:
        selected_baud = "115200"
    ini.set("Connection", "baudrate", selected_baud if selected_baud.isdigit() else "115200")

    # 2. Betriebsart & Routing (Main Port vs. Multiplexer)
    print("\n--- 2. BETRIEBSART & ROUTING ---")
    print("  [1] Main Port (Front-BNC - Standard 2-, 3- oder 4-Leiter)")
    print("  [2] MUX32 / MUX64 Multiplexer (Interner oder Externer MUX)")
    mode_choice = input("Waehle Betriebsart (1 oder 2) [Standard: 1]: ").strip()
    is_mux = (mode_choice == "2")

    if is_mux:
        ini.set("MUX", "enabled", "True")
        default_sens = "22: 22,22,23,23" if is_med else "1-8"
        sensors = input(f"Aktive Sensoren / Pins eingeben (z.B. '1-8' oder '22: 22,22,23,23') [Standard: {default_sens}]: ").strip()
        ini.set("MUX", "active_sensors", sensors if sensors else default_sens)

        print("  Leiter-Modus fuer MUX:")
        print("    [1] 2-Leiter")
        print("    [2] 4-Leiter [Standard]")
        m_mode_choice = input("Waehle Leiter-Modus (1 oder 2) [Standard: 2]: ").strip()
        m_mode = "2" if m_mode_choice == "1" else "4"
        ini.set("MUX", "mode", m_mode)

        if is_med:
            print("  Welcher Multiplexer soll beim Medical-Geraet angesteuert werden?")
            print("    [2] Externer Multiplexer (ext. Mux32 / ExtensionPort = 0x02)")
            print("    [3] Interner Multiplexer (int. Mux32 / InternalMux = 0x03) [Standard]")
            m_ch_in = input("Waehle MUX-Kanal (2 oder 3) [Standard: 3]: ").strip()
            mux_ch = "2" if m_ch_in == "2" else "3"
        else:
            mux_ch = "2"

        sw_delay = input("  MUX Switch Delay in Sekunden [Standard: 0.10]: ").strip() or "0.10"
        ini.set("MUX", "channel", mux_ch)
        ini.set("MUX", "switch_delay_s", sw_delay)
        ini.set("Frontend", "measurement_mode", "1" if m_mode == "2" else "2")
        ini.set("Frontend", "measurement_channel", mux_ch)
    else:
        ini.set("MUX", "enabled", "False")
        ini.set("MUX", "mode", "4")
        ini.set("MUX", "channel", "3" if is_med else "2")
        ini.set("MUX", "active_sensors", "1-8")
        ini.set("MUX", "switch_delay_s", "0.10")
        print("  Elektroden-Konfiguration (Main BNC):")
        print("    [1] 2-Leiter / 2-Point")
        print("    [2] 4-Leiter Kelvin / 4-Point [Standard]")
        print("    [3] 3-Leiter / 3-Point")
        bnc_m = input("Waehle Konfiguration (1, 2 oder 3) [Standard: 2]: ").strip()
        fe_m = "1" if bnc_m == "1" else ("3" if bnc_m == "3" else "2")
        ini.set("Frontend", "measurement_mode", fe_m)
        ini.set("Frontend", "measurement_channel", "1")

    for ep_key in ["counter_port", "reference_port", "working_sense_port", "working_port"]:
        ini.set("ExtensionPort", ep_key, "0")

    # 3. Analoge Frontend-Messbereiche
    print("\n--- 3. ANALOGE FRONTEND-MESSBEREICHE ---")
    print("  Strommessbereiche (Current Range):")
    print("    [0] Autoranging (Dynamisch fuer Spulen L / Kondensatoren C)")
    print("    [1] ±10 mA  (100 Ω Range)")
    print("    [2] ±100 µA (10 kΩ Range) [Standard]")
    print("    [4] ±1 µA   (1 MΩ Range)")
    print("    [6] ±10 nA  (100 MΩ Range)")
    c_rng = input("Waehle Strombereich (0, 1, 2, 4 oder 6) [Standard: 2]: ").strip()
    ini.set("Frontend", "current_range", c_rng if c_rng in ["0", "1", "2", "4", "6"] else "2")

    print("  Spannungsmessbereiche (Voltage Range - laut Handbuch nur 1 oder 2):")
    if is_med:
        print("    [1] ±2.0 Vpp (±1.0 Vp Default) [Standard]")
        print("    [2] ±180 mVpp (±90 mVp High Gain)")
    else:
        print("    [1] ±1.0 V Peak (Default) [Standard]")
        print("    [2] ±0.09 V / ±90 mV Peak (High Gain)")
    v_rng = input("Waehle Spannungsbereich (1 oder 2) [Standard: 1]: ").strip()
    ini.set("Frontend", "voltage_range", v_rng if v_rng in ["1", "2"] else "1")

    # 4. Frequenz-Bloecke (Unterstuetzung fuer mehrere Bloecke)
    print("\n--- 4. FREQUENZBLOECKE KONFIGURIEREN ---")
    block_idx = 1
    while True:
        print(f"\n  >>> Frequenzblock #{block_idx} <<<")
        start_f = input("  Start-Frequenz in Hz (z.B. 100 oder 1k) [Standard: 100.0]: ").strip() or "100.0"
        stop_f = input("  Stop-Frequenz in Hz (z.B. 1M oder 1000000) [Standard: 1000000.0]: ").strip() or "1000000.0"
        steps = input("  Anzahl Frequenzpunkte (Steps) [Standard: 21]: ").strip() or "21"

        print("  Skalierung: [1] Logarithmisch (Standard) | [2] Linear")
        scale_in = input("  Waehle Skalierung (1 oder 2) [Standard: 1]: ").strip()
        scale_val = "linear" if scale_in == "2" else "logarithmic"

        print("  Precision: [0] Low (Schnell) | [1] Medium (Standard) | [2] High | [3] Very High")
        prec_in = input("  Waehle Precision (0-3) [Standard: 1]: ").strip()
        prec_val = {"0": "0.0", "1": "1.0", "2": "2.0", "3": "3.0"}.get(prec_in, "1.0")

        if is_med:
            print("  Anregungsart: [1] Voltage (Spannung in Vpp) | [2] Current (Strom in App - Standard)")
        else:
            print("  Anregungsart: [1] Voltage (Spannung in V Peak) | [2] Current (Strom in A Peak - Standard)")
        exc_in = input("  Waehle Anregungsart (1 oder 2) [Standard: 2]: ").strip()
        exc_val = "1" if exc_in == "1" else "2"

        default_amp = "0.1" if exc_val == "1" else "0.0001"
        unit_label = ("Vpp" if exc_val == "1" else "App") if is_med else ("V Peak" if exc_val == "1" else "A Peak")
        amp_in = input(f"  Amplitude in {unit_label} (z.B. {default_amp} oder 100u) [Standard: {default_amp}]: ").strip() or default_amp
        amp_clean = str(parse_value_with_prefix(amp_in))

        ini.set("FrequencyBlocks", f"block_{block_idx}_start", start_f)
        ini.set("FrequencyBlocks", f"block_{block_idx}_stop", stop_f)
        ini.set("FrequencyBlocks", f"block_{block_idx}_steps", steps)
        ini.set("FrequencyBlocks", f"block_{block_idx}_scale", scale_val)
        ini.set("FrequencyBlocks", f"block_{block_idx}_precision", prec_val)
        ini.set("FrequencyBlocks", f"block_{block_idx}_exc_type", exc_val)
        ini.set("FrequencyBlocks", f"block_{block_idx}_amplitude", amp_clean)

        if block_idx == 1:
            ini.set("FrequencySetup", "mode", "sweep")
            ini.set("FrequencySetup", "start_frequency_hz", start_f)
            ini.set("FrequencySetup", "stop_frequency_hz", stop_f)
            ini.set("FrequencySetup", "count", steps)
            ini.set("FrequencySetup", "scale", scale_val)
            ini.set("FrequencySetup", "precision", prec_val)
            ini.set("FrequencySetup", "excitation_type", exc_val)
            ini.set("FrequencySetup", "amplitude", amp_clean)

        more = input("\n  Weiteren Frequenzblock hinzufuegen? (j/[N]): ").strip().lower()
        if more in ["j", "ja", "y", "yes"]:
            block_idx += 1
        else:
            break

    # 5. Timing & spektrale Wiederholungen
    print("\n--- 5. TIMING & SPEKTRALE WIEDERHOLUNGEN ---")
    spectra = input("  Anzahl Spectra (Average Count / Wiederholungen) [Standard: 1]: ").strip() or "1"
    ini.set("Measurement", "number_of_spectra", spectra)

    pt_delay = input("  Point Delay / Settling Time in ms [Standard: 20.0]: ").strip() or "20.0"
    ini.set("FrequencySetup", "point_delay_ms", pt_delay)

    sync_us = input("  Sync-Time zwischen Sweeps in µs [Standard: 0]: ").strip() or "0"
    ini.set("SyncTime", "sync_time_us", sync_us)

    ph_sync_in = input("  Phase Synchronization aktivieren (nur fuer f >= 100 kHz)? (j/[N]): ").strip().lower()
    ini.set("FrequencySetup", "phase_sync", "True" if ph_sync_in in ["j", "ja", "y", "yes"] else "False")

    # 6. Optionen & Zeitstempel (Befehl 0x97)
    print("\n--- 6. HARDWARE-OPTIONEN (0x97) ---")
    ini.set("DCBias", "dc_bias_enabled", "False")
    ini.set("DCBias", "bias_voltage_v", "0.0")

    print("  Hardware-Zeitstempel (in HDF5 unter 'hw_timestamp'):")
    print("    [0] Aus [Standard]")
    print("    [1] Millisekunden (4 Byte)")
    print("    [2] Mikrosekunden (5 Byte)")
    ts_in = input("  Waehle Zeitstempel (0, 1 oder 2) [Standard: 0]: ").strip()
    ini.set("Options", "timestamp_mode", ts_in if ts_in in ["0", "1", "2"] else "0")

    cr_out_in = input("  Aktuellen Current-Range im Messframe ausgeben (Option 0x04)? (j/[N]): ").strip().lower()
    ini.set("Options", "enable_current_range_output", "True" if cr_out_in in ["j", "ja", "y", "yes"] else "False")

    # 7. Live-Plot Einstellungen
    print("\n--- 7. VISUALISIERUNG & LIVE-PLOT ---")
    lp_en_in = input("  Live-Plot waehrend der Messung anzeigen? ([J]/n): ").strip().lower()
    ini.set("ApiSettings", "live_plot_enabled", "False" if lp_en_in in ["n", "nein", "no"] else "True")

    print("  Diagramm-Typ:")
    print("    [1] bode (Log-Log) [Standard]")
    print("    [2] bode_lin (Lineare Y-Achse)")
    print("    [3] nyquist")
    print("    [4] impedance_frequency (Real- & Imaginaerteil)")
    pt_in = input("  Waehle Diagramm-Typ (1-4) [Standard: 1]: ").strip()
    pt_map = {"1": "bode", "2": "bode_lin", "3": "nyquist", "4": "impedance_frequency"}
    ini.set("ApiSettings", "plot_type", pt_map.get(pt_in, "bode"))

    print("  Live-Plot Aktualisierungs-Modus:")
    print("    [1] point (Nach jedem Punkt) [Standard]")
    print("    [2] sweep (Erst nach komplettem Sweep)")
    lpm_in = input("  Waehle Aktualisierungs-Modus (1 oder 2) [Standard: 1]: ").strip()
    ini.set("ApiSettings", "live_plot_mode", "sweep" if lpm_in == "2" else "point")
    ini.set("ApiSettings", "continuous_measurement", "False")

    # Profil dauerhaft sichern oder temporaer nutzen
    save_choice = input("\nKonfiguration dauerhaft als .ini speichern? ([J]/n): ").strip().lower()
    if save_choice in ["", "j", "ja", "y", "yes"]:
        custom_name = input("Dateiname fuer die INI eingeben [Standard: config]: ").strip() or "config"
        if not custom_name.lower().endswith(".ini"):
            custom_name += ".ini"
        target_path = os.path.join(config_dir, custom_name)
        with open(target_path, "w", encoding="utf-8") as f:
            ini.write(f)
        print(f"[OK] Konfiguration dauerhaft gespeichert unter: {target_path}")
        return target_path
    else:
        temp_path = os.path.join(config_dir, "temp_run.ini")
        with open(temp_path, "w", encoding="utf-8") as f:
            ini.write(f)
        print("[INFO] Konfiguration fuer diesen Durchlauf temporaer angelegt.")
        return temp_path


def main():
    """Startmenue fuer das Mess-Framework."""
    print("=" * 70)
    print(" Sciospec ISX-3 (Standard & Medical Research) - Mess-Framework")
    print("=" * 70)
    print("Wie moechtest du fortfahren?")
    print("  [1] Grafische Benutzeroberflaeche (GUI) oeffnen")
    print("  [2] Vorhandene INI-Konfigurationsdatei ueber Pfad laden")
    print("  [3] Interaktive Konsolen-Eingabe starten")

    choice = input("\nDeine Wahl (1, 2 oder 3): ").strip()
    config_file = None

    if choice == "2":
        config_file = input("Gib den Pfad zur .ini-Datei ein: ").strip().strip('"')
        if not os.path.exists(config_file):
            print(f"[FEHLER] Die Datei '{config_file}' wurde nicht gefunden!")
            return
        print(f"[INFO] Verwende Konfiguration: {config_file}")
    elif choice == "3":
        config_file = interactive_console_config()
        if not config_file:
            print("[INFO] Abbruch.")
            return
    else:
        print("[INFO] Oeffne grafisches Konfigurationsfenster (GUI)...")
        run_gui()
        return

    if config_file:
        print(f"[INFO] Starte Messung mit Konfiguration: {config_file}")
        measurement_controller = Measurement()
        measurement_controller.measurement(config_path=config_file)


if __name__ == "__main__":
    main()