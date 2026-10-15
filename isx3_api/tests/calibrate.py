"""
calibrate.py - Nimmt eine Leerlauf-Referenzmessung (Open) auf
und speichert sie als Kalibrierbasis für die Software-Kompensation.
"""

import os
import shutil
from isx3_api.measurement import Measurement


def main():
    config_file = r"config\config.ini"
    cal_dir = "calibration"
    cal_target = os.path.join(cal_dir, "open_calibration.h5")
    os.makedirs(cal_dir, exist_ok=True)

    print("=" * 60)
    print(" SCIOSPEC ISX-3 / MUX32: OPEN-KOMPENSATION AUFNEHMEN")
    print("=" * 60)
    print("WICHTIG:")
    print("  1. Bitte stelle sicher, dass an den MUX-Klemmen KEIN Sensor")
    print("     bzw. keine Flüssigkeit anliegt (Elektroden komplett OFFEN).")
    print(f"  2. Die Einstellungen werden aus '{config_file}' übernommen.")
    print("=" * 60)

    input("\nDrücke ENTER, um die Leerlauf-Messung zu starten...")

    meas = Measurement()
    # Sicherstellen, dass während der Kalibrieraufnahme keine alte Kompensation aktiv ist
    meas.measurement(config_path=config_file)

    # Die soeben erzeugte Datei aus 'measurements/' als Kalibrierdatei sichern
    created_file = os.path.join("measurements", meas.filename)
    if os.path.exists(created_file):
        shutil.copy2(created_file, cal_target)
        print("\n" + "=" * 60)
        print(f"[OK] Kalibrierdatei erfolgreich gespeichert:")
        print(f"     -> {os.path.abspath(cal_target)}")
        print("=" * 60)
        print("Du kannst nun deinen Sensor anschließen und 'python tests/main.py' starten.")
    else:
        print("[FEHLER] Kalibrierdatei konnte nicht kopiert werden.")


if __name__ == "__main__":
    main()