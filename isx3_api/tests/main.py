"""
main.py - Einstiegspunkt für das ISX-3 Mess-Framework mit optimierter Konsolenführung.
"""

import sys
import os
import configparser
import serial.tools.list_ports

# Füge das src-Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from isx3_api.measurement import Measurement
from isx3_api.config_gui import run_gui


def interactive_console_config() -> str | None:
    """
    Führt den Nutzer komfortabel durch die Konsolen-Konfiguration und 
    erlaubt am Ende das Abspeichern als 'consolen.ini'.
    """
    print("\n" + "=" * 60)
    print(" INTERAKTIVE KONSOLEN-KONFIGURATION FÜR ISX-3")
    print("=" * 60)

    config_dir = os.path.abspath("config")
    os.makedirs(config_dir, exist_ok=True)
    target_path = os.path.join(config_dir, "consolen.ini")

    ini = configparser.ConfigParser()
    ini.optionxform = str

    for sec in ["Connection", "MUX", "Frontend", "ExtensionPort", "FrequencySetup", "FrequencyBlocks", "DCBias", "SyncTime", "Options", "Measurement", "ApiSettings"]:
        ini.add_section(sec)

    # 1. Schnittstelle wählen (1-2)
    print("\n--- 1. SCHNITTSTELLE & VERBINDUNG ---")
    print("  [1] COM (Seriell / USB Virtual COM Port)")
    print("  [2] TCP (Ethernet / Netzwerk)")
    iface_choice = input("Wähle Schnittstelle (1 oder 2) [Standard: 1]: ").strip()
    
    if iface_choice == "2":
        interface = "TCP"
        ini.set("Connection", "interface_type", "TCP")
        ip = input("IP-Adresse eingeben [Standard: 192.168.1.100]: ").strip()
        ini.set("Connection", "ip_address", ip if ip else "192.168.1.100")
        t_port = input("TCP-Port eingeben [Standard: 5000]: ").strip()
        ini.set("Connection", "tcp_port", t_port if t_port else "5000")
    else:
        interface = "COM"
        ini.set("Connection", "interface_type", "COM")
        
        # Verfügbare Ports ermitteln
        available_ports = [p.device for p in serial.tools.list_ports.comports()]
        if not available_ports:
            available_ports = ["COM12", "COM1", "COM3", "COM6"]
        
        print("  Verfügbare COM-Ports:")
        for idx, p in enumerate(available_ports, 1):
            print(f"    [{idx}] {p}")
        
        port_in = input(f"Wähle COM-Port (Ziffer 1-{len(available_ports)}) oder tippe z.B. 'COM12': ").strip()
        if port_in.isdigit() and 1 <= int(port_in) <= len(available_ports):
            selected_port = available_ports[int(port_in) - 1]
        else:
            selected_port = port_in if port_in else "COM12"
            if not selected_port.upper().startswith("COM"):
                selected_port = f"COM{selected_port}"
        ini.set("Connection", "port", selected_port)

        # Baudrate Auswahl
        print("  Gängige Baudraten:")
        print("    [1] 9600")
        print("    [2] 57600")
        print("    [3] 115200 (Standard)")
        print("    [4] 230400")
        print("    [5] 921600")
        print("    [6] Benutzerdefinierte Baudrate eingeben")
        baud_choice = input("Wähle Baudrate (1-6) [Standard: 3]: ").strip()
        baud_map = {"1": "9600", "2": "57600", "3": "115200", "4": "230400", "5": "921600"}
        if baud_choice in baud_map:
            selected_baud = baud_map[baud_choice]
        elif baud_choice == "6":
            selected_baud = input("Gib die benutzerdefinierte Baudrate ein: ").strip()
        else:
            selected_baud = "115200"
        ini.set("Connection", "baudrate", selected_baud if selected_baud else "115200")

    # 2. Betriebsart & Routing
    print("\n--- 2. BETRIEBSART & ROUTING ---")
    print("  [1] Main Port (Front-BNC - Standard 2-, 3- oder 4-Leiter)")
    print("  [2] MUX32 Multiplexer (Zusatzkarte für Sensor-Arrays)")
    mode_choice = input("Wähle Betriebsart (1 oder 2) [Standard: 1]: ").strip()
    
    if mode_choice == "2":
        ini.set("MUX", "enabled", "True")
        sensors = input("Aktive Sensoren / Pins eingeben (z.B. '1-8' oder '1: 4,8,9,12') [Standard: 1-8]: ").strip()
        ini.set("MUX", "active_sensors", sensors if sensors else "1-8")
        
        print("  Leiter-Modus für MUX:")
        print("    [1] 2-Leiter")
        print("    [2] 4-Leiter (Standard)")
        m_mode_choice = input("Wähle Leiter-Modus (1 oder 2) [Standard: 2]: ").strip()
        m_mode = "2" if m_mode_choice == "1" else "4"
        ini.set("MUX", "mode", m_mode)
        ini.set("Frontend", "measurement_mode", "1" if m_mode == "2" else "2")
        ini.set("Frontend", "measurement_channel", "2")
    else:
        ini.set("MUX", "enabled", "False")
        print("  Elektroden-Konfiguration (Main BNC):")
        print("    [1] 2-Leiter / 2-Point")
        print("    [2] 4-Leiter Kelvin / 4-Point (Standard)")
        print("    [3] 3-Leiter / 3-Point")
        bnc_m = input("Wähle Konfiguration (1, 2 oder 3) [Standard: 2]: ").strip()
        fe_m = "1" if bnc_m == "1" else ("3" if bnc_m == "3" else "2")
        ini.set("Frontend", "measurement_mode", fe_m)
        ini.set("Frontend", "measurement_channel", "1")

    # 3. Anregung & Messbereiche
    print("\n--- 3. ANREGUNG & MESSBEREICHE ---")
    print("  [1] Voltage Excitation (Spannung in V)")
    print("  [2] Current Excitation (Strom in A - Standard)")
    exc_type = input("Anregungsart wählen (1 oder 2) [Standard: 2]: ").strip()
    exc_val = "1" if exc_type == "1" else "2"
    ini.set("FrequencySetup", "excitation_type", exc_val)

    amp = input("Signalamplitude (z.B. 0.0001 für 100µA oder 0.1 für 100mV) [Standard: 0.0001]: ").strip()
    ini.set("FrequencySetup", "amplitude", amp if amp else "0.0001")

    if exc_val == "2":
        print("  Strommessbereiche (Current Range):")
        print("    [1] ±10 mA  (100 Ω)")
        print("    [2] ±100 µA (10 kΩ) [Standard]")
        print("    [4] ±1 µA   (1 MΩ)")
        print("    [6] ±10 nA  (100 MΩ)")
        c_rng = input("Wähle Strombereich (1, 2, 4 oder 6) [Standard: 2]: ").strip()
        ini.set("Frontend", "current_range", c_rng if c_rng in ["1", "2", "4", "6"] else "2")
    else:
        ini.set("Frontend", "current_range", "2")

    print("  Spannungsmessbereiche (Voltage Range):")
    print("    [0] Autoranging")
    print("    [1] ±1.0 V (Default) [Standard]")
    print("    [2] ±0.09 V (High Gain)")
    v_rng = input("Wähle Spannungsbereich (0, 1 oder 2) [Standard: 1]: ").strip()
    ini.set("Frontend", "voltage_range", v_rng if v_rng in ["0", "1", "2"] else "1")

    # 4. Frequenz & Precision
    print("\n--- 4. FREQUENZBLOCK & PRECISION ---")
    start_f = input("Start-Frequenz in Hz (z.B. 100 oder 10k) [Standard: 100.0]: ").strip()
    stop_f = input("Stop-Frequenz in Hz (z.B. 10M oder 10000000) [Standard: 10000000.0]: ").strip()
    steps = input("Anzahl Frequenzpunkte (Steps) [Standard: 101]: ").strip()
    
    print("  Skalierung:")
    print("    [1] Logarithmisch [Standard]")
    print("    [2] Linear")
    scale_in = input("Wähle Skalierung (1 oder 2) [Standard: 1]: ").strip()
    scale_val = "linear" if scale_in == "2" else "logarithmic"

    print("  Precision (Integrationszeit):")
    print("    [0] Low (Schnellstmöglich)")
    print("    [1] Medium (Standard)")
    print("    [2] High (Langsam, hohe Stabilität)")
    print("    [3] Very High (Sehr langsam, maximale Stabilität)")
    prec_in = input("Wähle Precision (0-3) [Standard: 1]: ").strip()
    prec_map = {"0": "0.0", "1": "1.0", "2": "2.0", "3": "3.0"}
    prec_val = prec_map.get(prec_in, "1.0")

    ini.set("FrequencySetup", "start_frequency_hz", start_f if start_f else "100.0")
    ini.set("FrequencySetup", "stop_frequency_hz", stop_f if stop_f else "10000000.0")
    ini.set("FrequencySetup", "count", steps if steps else "101")
    ini.set("FrequencySetup", "scale", scale_val)
    ini.set("FrequencySetup", "precision", prec_val)

    ini.set("FrequencyBlocks", "block_1_start", start_f if start_f else "100.0")
    ini.set("FrequencyBlocks", "block_1_stop", stop_f if stop_f else "10000000.0")
    ini.set("FrequencyBlocks", "block_1_steps", steps if steps else "101")
    ini.set("FrequencyBlocks", "block_1_scale", scale_val)
    ini.set("FrequencyBlocks", "block_1_precision", prec_val)

    spectra = input("\nAnzahl Spectra (Mittelung / Wiederholungen) [Standard: 3]: ").strip()
    ini.set("Measurement", "number_of_spectra", spectra if spectra else "3")

    ini.set("ApiSettings", "plot_type", "bode")
    ini.set("ApiSettings", "live_plot_enabled", "True")
    ini.set("ApiSettings", "live_plot_mode", "point")

    # Am Ende fragen, ob gespeichert werden soll
    save_choice = input("\nMöchtest du diese Konfiguration als 'config/consolen.ini' speichern? ([J]/n): ").strip().lower()
    if save_choice in ["", "j", "ja", "y", "yes"]:
        with open(target_path, "w", encoding="utf-8") as f:
            ini.write(f)
        print(f"[OK] Konfiguration gespeichert unter: {target_path}")
        return target_path
    else:
        # Temporäre INI anlegen für den direkten Start, ohne dauerhaft zu speichern
        temp_path = os.path.join(config_dir, "temp_run.ini")
        with open(temp_path, "w", encoding="utf-8") as f:
            ini.write(f)
        print("[INFO] Konfiguration für diesen Durchlauf temporär verwendet.")
        return temp_path


def main():
    print("=" * 60)
    print(" Sciospec ISX-3 - Mess-Framework Einstieg")
    print("=" * 60)
    print("Wie möchtest du fortfahren?")
    print("  [1] Grafische Benutzeroberfläche (GUI) öffnen")
    print("  [2] Vorhandene INI-Konfigurationsdatei über Pfad laden")
    print("  [3] Interaktive Konsolen-Eingabe starten")
    
    choice = input("\nDeine Wahl (1, 2 oder 3) [Standard: 1]: ").strip()

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
        print("[INFO] Öffne grafisches Konfigurationsfenster (GUI)...")
        run_gui()
        return

    if config_file:
        print(f"[INFO] Starte Messung mit Konfiguration: {config_file}")
        measurement_controller = Measurement()
        measurement_controller.measurement(config_path=config_file)


if __name__ == "__main__":
    main()