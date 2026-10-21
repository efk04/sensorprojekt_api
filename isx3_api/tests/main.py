"""
main.py - Einstiegspunkt für das ISX-3 Mess-Framework.
"""

import sys
import os

# Füge das src-Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from isx3_api.measurement import Measurement
from isx3_api.config_gui import run_gui


def main():
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
        print(f"[INFO] Starte Messung mit Konfiguration: {config_file}")
        measurement_controller = Measurement()
        measurement_controller.measurement(config_path=config_file)
    else:
        print("[INFO] Keine INI übergeben. Öffne grafisches Konfigurationsfenster (GUI)...")
        run_gui()


if __name__ == "__main__":
    main()