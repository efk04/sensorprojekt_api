"""
auswertung_visualisierung.py - Mehrfach-Visualisierung für HDF5-Messungen mit mehreren Blöcken.
"""

import os
from tkinter import Tk, filedialog
import h5py
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_H5_DIR = r"C:\Users\lukas\Documents\GitHub\sensorprojekt_api\isx3_api\measurements"

def select_h5_file() -> str | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    init_h5 = DEFAULT_H5_DIR if os.path.exists(DEFAULT_H5_DIR) else None
    h5_path = filedialog.askopenfilename(
        title="Wähle die HDF5-Messdatei (.h5)",
        initialdir=init_h5,
        filetypes=[("HDF5 Messdaten", "*.h5 *.hdf5"), ("Alle Dateien", "*.*")],
    )
    root.destroy()
    return h5_path or None


def parse_hdf5_file(h5_file: str) -> tuple[dict[int, dict[str, np.ndarray]], list[float]]:
    results = {}
    block_transitions = []
    with h5py.File(h5_file, "r") as h5:
        # Frequenz-Grenzen der Blöcke aus der Konfiguration auslesen, falls vorhanden
        if "Configuration" in h5 and "FrequencyBlocks" in h5["Configuration"]:
            fb_grp = h5["Configuration"]["FrequencyBlocks"]
            for k in sorted(fb_grp.attrs.keys()):
                if "_stop" in k:
                    try:
                        block_transitions.append(float(fb_grp.attrs[k]))
                    except ValueError:
                        pass

        sensor_groups = [k for k in h5.keys() if k.startswith("Sensor_") or k == "Measurement"]
        
        for k in sensor_groups:
            s_idx = 0
            if k.startswith("Sensor_"):
                parts = k.split("_")
                if len(parts) > 1 and parts[1].isdigit():
                    s_idx = int(parts[1])
            
            grp = h5[k]
            meas_keys = sorted(
                [mk for mk in grp.keys() if mk.startswith("Measurement_")],
                key=lambda x: [int(n) for n in x.split("_")[1].split(".")],
            )
            if not meas_keys:
                continue

            f_list, re_list, im_list = [], [], []
            for m_key in meas_keys:
                ds = grp[m_key]
                f_val = float(np.mean(ds["frequency"][()]))
                re_val = float(np.mean(ds["real_part"][()]))
                im_val = float(np.mean(ds["imaginary_part"][()]))

                f_list.append(f_val)
                re_list.append(re_val)
                im_list.append(im_val)

            f_arr = np.array(f_list)
            re_arr = np.array(re_list)
            im_arr = np.array(im_list)

            results[s_idx] = {
                "frequency": f_arr,
                "real": re_arr,
                "imag": im_arr,
                "z_mag": np.hypot(re_arr, im_arr),
                "phase": np.degrees(np.arctan2(im_arr, re_arr)),
            }

    return results, sorted(list(set(block_transitions)))


def visualize_h5_multi_block(py_data: dict, transitions: list[float]) -> None:
    if not py_data:
        print("[FEHLER] Keine Daten in der HDF5-Datei gefunden.")
        return

    plt.figure(figsize=(12, 9))
    colors = ['blue', 'orange', 'green', 'purple', 'brown']

    for s_idx, data in py_data.items():
        freqs = data["frequency"]
        z_mag = data["z_mag"]
        phase = data["phase"]

        # Indizes für die Blöcke anhand der Übergänge finden
        indices = [0]
        for t in transitions[:-1]: # Den letzten Stop-Wert brauchen wir nicht als Trenner
            idx = np.searchsorted(freqs, t)
            if 0 < idx < len(freqs):
                indices.append(idx)
        indices.append(len(freqs))

        # 1. Subplot: Betrag |Z|
        plt.subplot(2, 1, 1)
        for i in range(len(indices) - 1):
            start_i = indices[i]
            end_i = indices[i+1]
            col = colors[i % len(colors)]
            label_text = f'Sensor #{s_idx} - Block {i+1}' if s_idx == list(py_data.keys())[0] else ""
            plt.loglog(freqs[start_i:end_i], z_mag[start_i:end_i], 'o-', color=col, label=label_text)

        plt.ylabel(r"Betrag $|Z|$ / $\Omega$")
        plt.title("HDF5 Auswertung: Multi-Block-Messung (Strom- & Spannungswechsel)")
        plt.grid(True, which="both", linestyle="--", alpha=0.5)
        plt.legend(loc="upper right", fontsize=8)

        # 2. Subplot: Phase φ
        plt.subplot(2, 1, 2)
        for i in range(len(indices) - 1):
            start_i = indices[i]
            end_i = indices[i+1]
            col = colors[i % len(colors)]
            plt.semilogx(freqs[start_i:end_i], phase[start_i:end_i], 'o-', color=col)

        # Vertikale Linien für die Moduswechsel einzeichnen
        for t in transitions[:-1]:
            plt.axvline(t, color='red', linestyle=':', label=f'Block-Grenze bei {t} Hz')

        plt.xlabel("Frequenz $f$ / Hz")
        plt.ylabel(r"Phase $\phi$ / °")
        plt.grid(True, which="both", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.show()


def main():
    print("\n--- Multi-Block HDF5 Visualisierung gestartet ---")
    h5_path = select_h5_file()
    if not h5_path:
        print("[INFO] Keine Datei ausgewählt. Abbruch.")
        return

    py_data, transitions = parse_hdf5_file(h5_path)
    visualize_h5_multi_block(py_data, transitions)


if __name__ == "__main__":
    main()