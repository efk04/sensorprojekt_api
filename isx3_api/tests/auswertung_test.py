"""
auswertung_test.py - Universeller Validierungsvergleich zwischen Sciospec-GUI und Python-API.
Optimiert für MUX32-Messungen mit getrennten Fenstern für Betrag (|Z|) und Phase (φ).
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

    mux_entries = find_mux_folders(base_dir)

    if not mux_entries:
        for root, dirs, _ in os.walk(base_dir):
            for d in dirs:
                if pin_regex.search(d):
                    full_path = os.path.join(root, d)
                    if full_path not in [e.path for e in mux_entries]:
                        class DummyEntry:
                            def __init__(self, name, path):
                                self.name = name
                                self.path = path
                        mux_entries.append(DummyEntry(d, full_path))

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

    # Aufteilung in Blöcke von maximal 8 Sensoren
    chunk_size = 8
    sensor_chunks = [common_sensors[i:i + chunk_size] for i in range(0, len(common_sensors), chunk_size)]

    colormap = plt.get_cmap("tab10")

    for chunk_idx, chunk in enumerate(sensor_chunks):
        # Fenster 1: Impedanzbetrag (|Z|)
        fig_z, axes_z = plt.subplots(4, 2, figsize=(14, 11), sharex=True)
        axes_z = axes_z.flatten()

        # Fenster 2: Phase (φ)
        fig_phi, axes_phi = plt.subplots(4, 2, figsize=(14, 11), sharex=True)
        axes_phi = axes_phi.flatten()

        for idx, s_idx in enumerate(chunk):
            if idx >= len(axes_z):
                break
            
            color = colormap(idx % 10)
            g = gui_data[s_idx]
            p = py_data[s_idx]

            # --- Plot in Fenster 1: Betrag |Z| ---
            ax_z = axes_z[idx]
            ax_z.plot(g["frequency"], g["z_mag"], "-", color=color, linewidth=1.8, label=f"|Z| (GUI)")
            ax_z.plot(p["frequency"], p["z_mag"], "--", color="black", linewidth=1.0, label=f"|Z| (API)")
            ax_z.set_xscale("log")
            ax_z.set_yscale("log")
            ax_z.set_ylabel(r"$|Z|$ / $\Omega$")
            ax_z.set_title(f"Kanal #{s_idx}", fontsize=9, pad=2)
            ax_z.grid(True, which="both", linestyle="--", alpha=0.4)
            ax_z.legend(loc="upper right", fontsize=6)

            # --- Plot in Fenster 2: Phase ---
            ax_p = axes_phi[idx]
            ax_p.plot(g["frequency"], g["phase"], "-", color=color, linewidth=1.8, label=f"Phase (GUI)")
            ax_p.plot(p["frequency"], p["phase"], "--", color="black", linewidth=1.0, label=f"Phase (API)")
            ax_p.set_xscale("log")
            ax_p.set_ylabel(r"Phase / °")
            ax_p.set_title(f"Kanal #{s_idx}", fontsize=9, pad=2)
            ax_p.grid(True, which="both", linestyle="--", alpha=0.4)
            ax_p.legend(loc="upper right", fontsize=6)

        # Nicht genutzte Subplots bei unvollständigen Chunks ausblenden
        for j in range(len(chunk), len(axes_z)):
            fig_z.delaxes(axes_z[j])
            fig_phi.delaxes(axes_phi[j])

        fig_z.suptitle(f"MUX-Validierung: Impedanzbetrag |Z| (Teil {chunk_idx + 1} von {len(sensor_chunks)})", fontsize=11)
        fig_z.tight_layout()

        fig_phi.suptitle(f"MUX-Validierung: Phase φ (Teil {chunk_idx + 1} von {len(sensor_chunks)})", fontsize=11)
        fig_phi.tight_layout()

    plt.show()


if __name__ == "__main__":
    main()