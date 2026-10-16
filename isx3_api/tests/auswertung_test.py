"""
auswertung_test.py - Universeller Validierungsvergleich zwischen Sciospec-GUI und Python-API.
Unterstützt sowohl MUX32-Kanalstrukturen als auch flache Main-Port-Ordner.
"""

import io
import os
import re
from tkinter import Tk, filedialog
import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_SCIO_DIR = r"C:\Users\lukas\Documents\Test_Scio\setup\mux"
DEFAULT_H5_DIR = r"C:\Users\lukas\Documents\GitHub\sensorprojekt_api\isx3_api\measurements"

FALLBACK_SCALE_FOR_OLD_H5 = 1.0


def select_sources() -> tuple[str | None, str | None]:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    init_scio = DEFAULT_SCIO_DIR if os.path.exists(DEFAULT_SCIO_DIR) else None
    scio_dir = filedialog.askdirectory(
        title="1/2: Wähle den Sciospec-Ordner (z.B. 'mux' oder 'MAIN PORT')",
        initialdir=init_scio,
    )
    if not scio_dir:
        root.destroy()
        return None, None

    init_h5 = DEFAULT_H5_DIR if os.path.exists(DEFAULT_H5_DIR) else None
    h5_path = filedialog.askopenfilename(
        title="2/2: Wähle die Python-HDF5-Messdatei (.h5)",
        initialdir=init_h5,
        filetypes=[("HDF5 Messdaten", "*.h5 *.hdf5"), ("Alle Dateien", "*.*")],
    )
    root.destroy()

    if not h5_path:
        return None, None

    return scio_dir, h5_path


def load_single_spec(spec_path: str) -> pd.DataFrame:
    with open(spec_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    header_idx = None
    for idx, line in enumerate(lines):
        if "frequency" in line.lower():
            header_idx = idx
            break

    if header_idx is None:
        raise ValueError(f"Keine Header-Zeile in '{spec_path}' gefunden.")

    df = pd.read_csv(io.StringIO("".join(lines[header_idx:])), sep=None, engine="python")
    df.columns = [c.strip() for c in df.columns]

    col_f = next(c for c in df.columns if "freq" in c.lower())
    col_re = next(c for c in df.columns if c.lower().strip().startswith("re") or "re[" in c.lower())
    col_im = next(c for c in df.columns if c.lower().strip().startswith("im") or "im[" in c.lower())

    clean_df = pd.DataFrame({
        "frequency": pd.to_numeric(df[col_f], errors="coerce"),
        "real": pd.to_numeric(df[col_re], errors="coerce"),
        "imag": pd.to_numeric(df[col_im], errors="coerce"),
    }).dropna()

    return clean_df.sort_values(by="frequency").reset_index(drop=True)


def parse_sciospec_folder(base_dir: str) -> dict[int, dict[str, np.ndarray]]:
    pin_regex = re.compile(r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)")

    def find_mux_folders(target_dir: str):
        found = []
        try:
            for entry in os.scandir(target_dir):
                if entry.is_dir() and pin_regex.search(entry.name):
                    found.append(entry)
        except Exception:
            pass
        return found

    # 1. Prüfen, ob direkte MUX-Unterordner im gewählten Pfad liegen
    mux_entries = find_mux_folders(base_dir)

    # 2. Falls nicht, rekursiv im gesamten Verzeichnis nach MUX-Ordnern suchen (z.B. wenn man den 'setup'-Ordner auswählt)
    if not mux_entries:
        for root, dirs, _ in os.walk(base_dir):
            for d in dirs:
                if pin_regex.search(d):
                    full_path = os.path.join(root, d)
                    # Nur hinzufügen, wenn nicht doppelt
                    if full_path not in [e.path for e in mux_entries]:
                        # Simuliere ein scandir-Entry-Objekt via custom class oder Pfadliste
                        class DummyEntry:
                            def __init__(self, name, path):
                                self.name = name
                                self.path = path
                        mux_entries.append(DummyEntry(d, full_path))

    # 3. FALLBACK FÜR MAIN-PORT: Wenn gar keine MUX-Ordner existieren, suche alle .spec-Dateien (auch in "MAIN PORT"-Unterordnern)
    if not mux_entries:
        spec_files_root = []
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.lower().endswith(".spec"):
                    spec_files_root.append(os.path.join(root, f))

        if spec_files_root:
            dfs = [load_single_spec(sf) for sf in spec_files_root]
            ref_freq = dfs[0]["frequency"].to_numpy()
            all_re = np.array([df["real"].to_numpy() for df in dfs])
            all_im = np.array([df["imag"].to_numpy() for df in dfs])
            mean_re = np.mean(all_re, axis=0)
            mean_im = np.mean(all_im, axis=0)

            return {
                0: {
                    "frequency": ref_freq,
                    "real": mean_re,
                    "imag": mean_im,
                    "z_mag": np.hypot(mean_re, mean_im),
                    "phase": np.degrees(np.arctan2(mean_im, mean_re)),
                    "count": len(spec_files_root),
                }
            }
        else:
            return {}

    # MUX32-Auswertung
    results = {}
    for entry in mux_entries:
        match = pin_regex.search(entry.name)
        if not match:
            continue

        we_pin = int(match.group(4))
        sensor_idx = we_pin // 4

        spec_files = [
            os.path.join(entry.path, f)
            for f in os.listdir(entry.path)
            if f.lower().endswith(".spec")
        ]

        if not spec_files:
            continue

        dfs = [load_single_spec(sf) for sf in spec_files]
        ref_freq = dfs[0]["frequency"].to_numpy()

        all_re = np.array([df["real"].to_numpy() for df in dfs])
        all_im = np.array([df["imag"].to_numpy() for df in dfs])

        mean_re = np.mean(all_re, axis=0)
        mean_im = np.mean(all_im, axis=0)

        results[sensor_idx] = {
            "frequency": ref_freq,
            "real": mean_re,
            "imag": mean_im,
            "z_mag": np.hypot(mean_re, mean_im),
            "phase": np.degrees(np.arctan2(mean_im, mean_re)),
            "count": len(spec_files),
        }

    return results


def parse_hdf5_file(h5_file: str) -> dict[int, dict[str, np.ndarray]]:
    results = {}
    with h5py.File(h5_file, "r") as h5:
        scale_factor = 1.0
        if "Configuration" in h5 and "applied_scale_factor" in h5["Configuration"].attrs:
            scale_factor = float(h5["Configuration"].attrs["applied_scale_factor"])
        else:
            scale_factor = FALLBACK_SCALE_FOR_OLD_H5

        sensor_groups = [k for k in h5.keys() if k.startswith("Sensor_")]
        if not sensor_groups:
            sensor_keys = [(0, h5)]
        else:
            sensor_keys = [
                (int(k.split("_")[1]), h5[k])
                for k in sensor_groups
                if k.split("_")[1].isdigit()
            ]

        for s_idx, grp in sensor_keys:
            meas_keys = sorted(
                [k for k in grp.keys() if k.startswith("Measurement_")],
                key=lambda x: [int(n) for n in x.split("_")[1].split(".")],
            )
            if not meas_keys:
                continue

            f_list, re_list, im_list = [], [], []
            for m_key in meas_keys:
                f_val = float(np.mean(grp[m_key]["frequency"][()]))
                re_val = float(np.mean(grp[m_key]["real_part"][()]))
                im_val = float(np.mean(grp[m_key]["imaginary_part"][()]))

                f_list.append(f_val)
                re_list.append(re_val)
                im_list.append(im_val)

            f_arr = np.array(f_list)
            re_arr = np.array(re_list) * scale_factor
            im_arr = np.array(im_list) * scale_factor

            results[s_idx] = {
                "frequency": f_arr,
                "real": re_arr,
                "imag": im_arr,
                "z_mag": np.hypot(re_arr, im_arr),
                "phase": np.degrees(np.arctan2(im_arr, re_arr)),
            }

    return results


def analyze_and_print_errors(gui_data: dict, py_data: dict, common_sensors: list[int]) -> None:
    print("\n" + "=" * 90)
    print(" STATISTISCHE VALIDIERUNGSANALYSE (Stabiler Bereich: 10 kHz - 1 MHz)")
    print("=" * 90)

    for s_idx in common_sensors:
        g = gui_data[s_idx]
        p = py_data[s_idx]

        common_f = g["frequency"]
        z_gui_interp = g["z_mag"]
        z_py_interp = np.interp(common_f, p["frequency"], p["z_mag"])
        phi_gui_interp = g["phase"]
        phi_py_interp = np.interp(common_f, p["frequency"], p["phase"])

        mask = (common_f >= 10000.0) & (common_f <= 1000000.0)
        if not np.any(mask):
            mask = np.ones_like(common_f, dtype=bool)

        rel_err_z = np.abs(z_py_interp[mask] - z_gui_interp[mask]) / z_gui_interp[mask] * 100.0
        diff_phi = np.abs(phi_py_interp[mask] - phi_gui_interp[mask])

        mean_err_z = float(np.mean(rel_err_z))
        max_err_z = float(np.max(rel_err_z))
        mean_diff_phi = float(np.mean(diff_phi))

        print(f"Sensor / Kanal #{s_idx}:")
        print(f"  • Mittlere Betragsabweichung (|Z|): {mean_err_z:6.3f} % (Max: {max_err_z:6.3f} %)")
        print(f"  • Mittlere Phasendifferenz (phi):     {mean_diff_phi:6.3f}°")
    print("=" * 90 + "\n")


def main():
    scio_dir, h5_path = select_sources()
    if not scio_dir or not h5_path:
        print("[INFO] Auswahl abgebrochen.")
        return

    gui_data = parse_sciospec_folder(scio_dir)
    py_data = parse_hdf5_file(h5_path)

    # Universelles Mapping: Wenn Schlüssel nicht matchen, aber Daten da sind, Keys erzwingen
    if len(gui_data) == 1 and len(py_data) == 1:
        g_key = list(gui_data.keys())[0]
        p_key = list(py_data.keys())[0]
        if g_key != p_key:
            py_data[g_key] = py_data.pop(p_key)

    common_sensors = sorted(set(gui_data.keys()).intersection(py_data.keys()))

    if not common_sensors:
        print(f"[FEHLER] Keine übereinstimmenden Sensoren gefunden. (GUI-Keys: {list(gui_data.keys())}, Py-Keys: {list(py_data.keys())})")
        return

    analyze_and_print_errors(gui_data, py_data, common_sensors)

    num_plots = len(common_sensors)
    if num_plots == 1:
        fig, ax = plt.subplots(figsize=(10, 6))
        axes = [ax]
    else:
        rows = (num_plots + 1) // 2
        fig, axes = plt.subplots(rows, 2, figsize=(14, 3 * rows), sharex=True)
        axes = axes.flatten()

    colormap = plt.get_cmap("tab10")

    for idx, s_idx in enumerate(common_sensors):
        ax = axes[idx] if idx < len(axes) else axes[-1]
        color = colormap(idx % 10)
        
        g = gui_data[s_idx]
        p = py_data[s_idx]

        ax.plot(g["frequency"], g["z_mag"], "-", color=color, linewidth=2.0, label=f"Kanal #{s_idx} (GUI)")
        ax.plot(p["frequency"], p["z_mag"], "--", color="black", linewidth=1.2, label=f"Kanal #{s_idx} (API)")

        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_ylabel(r"$|Z|$ / $\Omega$")
        ax.set_title(f"Messvergleich (Kanal #{s_idx})", fontsize=10, pad=3)
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend(loc="upper right", fontsize=8)

    for ax in axes[-2:]:
        ax.set_xlabel("Frequenz $f$ / Hz")

    fig.suptitle("Validierungsvergleich: Sciospec GUI vs. Python-API (Main Port / MUX)", fontsize=12)
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()