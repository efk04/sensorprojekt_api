"""
batch_vergleich_visualisierung.py - Vollautomatischer Batch-Vergleich
für eigene API-HDF5-Messdateien (.h5) und Sciospec-GUI-Messordner (.scio5).
Inklusive exakter Berechnung der Hardware-Messzeit für EINEN einzelnen Sweep.
"""

import os
import re
from tkinter import Tk, filedialog
import h5py
import matplotlib.pyplot as plt
import numpy as np

DEFAULT_API_DIR = r"C:\Users\lukas\Documents\GitHub\sensorprojekt_api\isx3_api\measurements"
DEFAULT_SPEC_DIR = r"C:\Users\lukas\Documents\Test_Scio\medical"

KOMBI_SUBFOLDERS = [
    "spec_int_21_22_0_0001App_high_v2Vpp_a0_0001A_c_100_1k",
    "spec_int_21_22_0_001Vpp_high_v2Vpp_a0_0001A_c_1k_100k",
    "spec_int_21_22_0_0001App_medium_v2Vpp_a0_0001A_c_100k_1M",
    "spec_int_21_22_0_001Vpp_medium_v2Vpp_a0_0001A_c_1M_10M",
]


def select_folder(title: str, initial_dir: str = "") -> str | None:
    """Öffnet einen Dialog zur Ordnerauswahl."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    init = initial_dir if os.path.exists(initial_dir) else os.getcwd()
    selected_dir = filedialog.askdirectory(title=title, initialdir=init)
    root.destroy()
    return selected_dir or None


def _sort_meas_keys(keys: list[str]) -> list[str]:
    """Sortiert Measurement-Keys natürlich nach ihren enthaltenen Zahlen (z.B. Measurement_1.2)."""
    def key_func(k: str):
        nums = re.findall(r"\d+", k)
        return [int(n) for n in nums] if nums else [0]
    return sorted(keys, key=key_func)


def _normalize_to_seconds(dt_raw: float) -> float:
    """
    Rechnet eine rohe Zeitdifferenz anhand der typischen Größenordnung eines Sweeps
    in Sekunden um (falls sie in µs oder ms gespeichert wurde).
    """
    if dt_raw <= 0:
        return 0.0
    # Werte > 10.000 deuten bei einem einzelnen Sweep auf Mikrosekunden (µs) oder 100-µs-Ticks hin
    if dt_raw > 10000.0:
        return dt_raw / 1e6
    # Werte zwischen 50 und 10.000 deuten oft auf Millisekunden (ms) hin, sofern ein Sweep < 5 s dauert
    return dt_raw


def _format_sweep_time(seconds: float | None) -> str:
    """Formatiert die Einzel-Sweep-Zeit übersichtlich in ms oder s."""
    if seconds is None or seconds <= 0:
        return ""
    if seconds < 1.0:
        return f"{seconds * 1000.0:.1f} ms ({seconds * 1e6:.0f} µs)"
    return f"{seconds:.3f} s ({seconds * 1000.0:.1f} ms)"


def _read_meas_group_list(
    parent_grp: h5py.Group | h5py.File, meas_keys: list[str]
) -> dict[str, np.ndarray | float | None] | None:
    """
    Liest eine Liste von Measurement_X Gruppen exakt wie im Originalskript aus[cite: 1]
    und berechnet die reine Hardware-Messzeit für EINEN einzelnen Sweep.
    """
    f_list, re_list, im_list = [], [], []
    # Speichert pro Frequenzpunkt das Array der Zeitstempel (über alle Wiederholungen/Bursts)
    ts_per_freq = []

    for m_key in _sort_meas_keys(meas_keys):
        ds = parent_grp[m_key]
        if not isinstance(ds, h5py.Group):
            continue
        if "frequency" not in ds or "real_part" not in ds or "imaginary_part" not in ds:
            continue

        f_val = float(np.mean(ds["frequency"][()]))
        re_val = float(np.mean(ds["real_part"][()]))
        im_val = float(np.mean(ds["imaginary_part"][()]))

        f_list.append(f_val)
        re_list.append(re_val)
        im_list.append(im_val)

        # Zeitstempel dieses Frequenzpunkts auslesen
        t_found = None
        for t_name in ["timestamp", "time", "timestamps", "Timestamp", "Time"]:
            if t_name in ds:
                try:
                    t_arr = np.asarray(ds[t_name][()], dtype=float).flatten()
                    if t_arr.size > 0:
                        t_found = t_arr
                        break
                except Exception:
                    pass
            elif t_name in ds.attrs:
                try:
                    t_found = np.array([float(ds.attrs[t_name])], dtype=float)
                    break
                except Exception:
                    pass

        if t_found is not None:
            ts_per_freq.append(t_found)

    if not f_list:
        return None

    # Berechnung der Messzeit für EINEN Sweep:
    sweep_time_s = None
    if len(ts_per_freq) >= 2:
        # Prüfen, wie viele Wiederholungen (Sweeps) pro Frequenzpunkt vorliegen
        min_repeats = min(len(arr) for arr in ts_per_freq)

        if min_repeats >= 1:
            # Matrix: Zeilen = Frequenzpunkte (f_0 ... f_N), Spalten = Sweep-Wiederholung (0 ... k)
            ts_matrix = np.array([arr[:min_repeats] for arr in ts_per_freq], dtype=float)

            # Fall 1: Jeder Spaltenindex ist ein eigener Durchlauf über alle Frequenzen
            # Dauer eines Sweeps = Zeit beim letzten Frequenzpunkt minus Zeit beim ersten Frequenzpunkt
            sweep_spans = np.abs(ts_matrix[-1, :] - ts_matrix[0, :])
            valid_spans = sweep_spans[sweep_spans > 0]

            if valid_spans.size > 0:
                dt_single = float(np.median(valid_spans))
                # Wenn innerhalb eines Frequenzpunkts ein Burst gemessen wurde, noch die Schrittweite eines Punkts addieren
                n_pts = len(ts_per_freq)
                dt_single = dt_single * (n_pts / max(n_pts - 1, 1))
                sweep_time_s = _normalize_to_seconds(dt_single)
            elif min_repeats > 1:
                # Fall 2: Innerhalb jedes Frequenzpunkts wurden Bursts aufgezeichnet
                point_spans = [np.abs(arr[-1] - arr[0]) for arr in ts_per_freq if len(arr) > 1]
                if point_spans:
                    dt_single = float(np.sum(point_spans))
                    sweep_time_s = _normalize_to_seconds(dt_single)

    f_arr = np.array(f_list, dtype=float)
    re_arr = np.array(re_list, dtype=float)
    im_arr = np.array(im_list, dtype=float)

    return {
        "frequency": f_arr,
        "real": re_arr,
        "imag": im_arr,
        "z_mag": np.hypot(re_arr, im_arr),
        "phase": np.degrees(np.arctan2(im_arr, re_arr)),
        "sweep_time_s": sweep_time_s,
    }


def parse_api_hdf5(h5_path: str) -> tuple[dict[str, dict], list[float]]:
    """
    Liest das eigene Python-API HDF5-Format aus[cite: 1].
    Berechnet die Sweep-Dauer separat pro Sensor/Kanal.
    """
    results = {}
    block_transitions = []

    with h5py.File(h5_path, "r") as h5:
        if "Configuration" in h5 and "FrequencyBlocks" in h5["Configuration"]:
            fb_grp = h5["Configuration"]["FrequencyBlocks"]
            for k in sorted(fb_grp.attrs.keys()):
                if "_stop" in k:
                    try:
                        block_transitions.append(float(fb_grp.attrs[k]))
                    except ValueError:
                        pass

        # Fall A: Liegen Measurement_X Gruppen direkt im Root der Datei?
        root_meas_keys = [
            k for k in h5.keys()
            if isinstance(h5[k], h5py.Group) and (k.startswith("Measurement_") or "frequency" in h5[k])
        ]
        if root_meas_keys:
            parsed_data = _read_meas_group_list(h5, root_meas_keys)
            if parsed_data:
                results["API Main Port"] = parsed_data

        # Fall B: Untergruppen durchsuchen (Sensor_X, Measurement, Main, etc.)[cite: 1]
        for k in h5.keys():
            if k in ["Configuration", "setup"] or k in root_meas_keys:
                continue
            grp = h5[k]
            if not isinstance(grp, h5py.Group):
                continue

            meas_keys = [
                mk for mk in grp.keys()
                if isinstance(grp[mk], h5py.Group) and (mk.startswith("Measurement_") or "frequency" in grp[mk])
            ]
            if not meas_keys:
                continue

            if k.startswith("Sensor_"):
                parts = k.split("_")
                label = f"API Sensor #{int(parts[1])}" if len(parts) > 1 and parts[1].isdigit() else f"API {k}"
            elif k == "Measurement" or "main" in k.lower() or "bnc" in k.lower():
                label = "API Main Port"
            else:
                label = f"API {k}"

            parsed_data = _read_meas_group_list(grp, meas_keys)
            if parsed_data:
                results[label] = parsed_data

    return results, sorted(list(set(block_transitions)))


def parse_sciospec_gui_hdf5(h5_path: str) -> tuple[dict[str, dict[str, np.ndarray]], list[float]]:
    """Liest das native Sciospec-Software HDF5-Format (.scio5 / .h5) aus[cite: 1]."""
    results = {}
    block_transitions = []

    try:
        with h5py.File(h5_path, "r") as h5:
            for top_key in h5.keys():
                top_obj = h5[top_key]
                if not isinstance(top_obj, h5py.Group):
                    continue

                if "setup" in top_obj and "frequencySetting" in top_obj["setup"]:
                    try:
                        f_set = top_obj["setup"]["frequencySetting"][()]
                        if hasattr(f_set, "dtype") and f_set.dtype.names and "maxFrequency" in f_set.dtype.names:
                            for row in np.atleast_1d(f_set):
                                block_transitions.append(float(row["maxFrequency"]))
                    except Exception:
                        pass

                if "data" not in top_obj:
                    continue

                data_grp = top_obj["data"]
                for port_key in data_grp.keys():
                    port_obj = data_grp[port_key]
                    if not isinstance(port_obj, h5py.Group):
                        continue
                    if "frequency" not in port_obj or "measurementData" not in port_obj:
                        continue

                    f_arr = np.array(port_obj["frequency"][()], dtype=float).flatten()
                    raw_meas = np.array(port_obj["measurementData"][()], dtype=float)

                    if raw_meas.ndim == 3:
                        mean_meas = np.mean(raw_meas, axis=0)
                        re_arr = mean_meas[:, 0]
                        im_arr = mean_meas[:, 1]
                    elif raw_meas.ndim == 2:
                        re_arr = raw_meas[:, 0]
                        im_arr = raw_meas[:, 1]
                    else:
                        continue

                    min_len = min(len(f_arr), len(re_arr), len(im_arr))
                    f_arr = f_arr[:min_len]
                    re_arr = re_arr[:min_len]
                    im_arr = im_arr[:min_len]

                    label = f"Sciospec GUI ({port_key})"
                    results[label] = {
                        "frequency": f_arr,
                        "real": re_arr,
                        "imag": im_arr,
                        "z_mag": np.hypot(re_arr, im_arr),
                        "phase": np.degrees(np.arctan2(im_arr, re_arr)),
                    }
    except Exception as e:
        print(f"    [FEHLER beim Lesen von {os.path.basename(h5_path)}]: {e}")

    return results, sorted(list(set(block_transitions)))


def find_valid_sciospec_data_in_dir(folder_path: str) -> tuple[dict[str, dict[str, np.ndarray]], list[float]]:
    """Sucht rekursiv im Sciospec-Messordner nach der .scio5/.h5 Datei mit den Messdaten[cite: 4, 5]."""
    if not os.path.isdir(folder_path):
        return {}, []

    candidates = []
    for root_dir, _, files in os.walk(folder_path):
        for f in files:
            if f.endswith(".scio5") or (f.endswith(".h5") and not f.startswith("api_")):
                full_p = os.path.join(root_dir, f)
                if "measurement config.scio5" in f.lower():
                    candidates.insert(0, full_p)
                else:
                    candidates.append(full_p)

    for c in candidates:
        data, trans = parse_sciospec_gui_hdf5(c)
        if data:
            return data, trans

    return {}, []


def assemble_kombi_spec_data(spec_root: str, spec_dirs_map: dict[str, str]) -> tuple[dict[str, dict[str, np.ndarray]], list[float]]:
    """Setzt die 4 Teil-Messungen für api_kombi_test in der vorgegebenen Reihenfolge zusammen."""
    combined_f, combined_re, combined_im = [], [], []
    transitions = []

    for sub in KOMBI_SUBFOLDERS:
        sub_key = sub.lower()
        if sub_key not in spec_dirs_map:
            print(f"  [WARNUNG] Kombi-Teilordner nicht gefunden: {sub}")
            continue

        actual_dir = os.path.join(spec_root, spec_dirs_map[sub_key])
        data, _ = find_valid_sciospec_data_in_dir(actual_dir)
        if not data:
            print(f"  [WARNUNG] Keine Messdaten im Kombi-Teilordner: {sub}")
            continue

        first_data = next(iter(data.values()))
        combined_f.append(first_data["frequency"])
        combined_re.append(first_data["real"])
        combined_im.append(first_data["imag"])
        transitions.append(float(np.max(first_data["frequency"])))

    if not combined_f:
        return {}, []

    f_all = np.concatenate(combined_f)
    re_all = np.concatenate(combined_re)
    im_all = np.concatenate(combined_im)

    result = {
        "Sciospec GUI (Kombi 4 Blöcke)": {
            "frequency": f_all,
            "real": re_all,
            "imag": im_all,
            "z_mag": np.hypot(re_all, im_all),
            "phase": np.degrees(np.arctan2(im_all, re_all)),
        }
    }
    return result, transitions[:-1]


def save_and_plot_pair(
    pair_name: str,
    api_label: str,
    spec_label: str,
    api_series: dict,
    spec_series: dict,
    transitions: list[float],
    save_folder: str,
    show_interactive: bool = True,
) -> None:
    """Erstellt den Vergleichsplot mit Einzel-Sweep-Dauer und speichert ihn unter measurements/plots."""
    fig, (ax_z, ax_p) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    sweep_time_s = api_series.get("sweep_time_s")
    time_formatted = _format_sweep_time(sweep_time_s)
    dur_str = f" (1 Sweep: {time_formatted})" if time_formatted else ""

    lbl_api = f"{api_label}{dur_str}"
    lbl_spec = f"{spec_label}"

    # API plotten
    ax_z.plot(api_series["frequency"], api_series["z_mag"], "o-", color="#0055cc", linewidth=1.8, markersize=4, label=lbl_api)
    ax_p.plot(api_series["frequency"], api_series["phase"], "o-", color="#0055cc", linewidth=1.8, markersize=4, label=lbl_api)

    # Sciospec GUI plotten
    ax_z.plot(spec_series["frequency"], spec_series["z_mag"], "s--", color="#e63900", linewidth=1.5, markersize=4, alpha=0.85, label=lbl_spec)
    ax_p.plot(spec_series["frequency"], spec_series["phase"], "s--", color="#e63900", linewidth=1.5, markersize=4, alpha=0.85, label=lbl_spec)

    # Block-Übergänge einzeichnen
    for t in transitions:
        ax_z.axvline(t, color="gray", linestyle=":", alpha=0.7)
        ax_p.axvline(t, color="gray", linestyle=":", alpha=0.7)

    ax_z.set_xscale("log")
    ax_z.set_yscale("log")
    ax_p.set_xscale("log")

    title_dur = f" | Dauer pro Sweep: {time_formatted}" if time_formatted else ""
    ax_z.set_ylabel(r"Betrag $|Z|$ / $\Omega$")
    ax_z.set_title(f"Vergleich: {pair_name}\n{api_label} vs. {spec_label}{title_dur}")
    ax_z.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_z.legend(loc="best", fontsize=9)

    ax_p.set_xlabel("Frequenz $f$ / Hz")
    ax_p.set_ylabel(r"Phase $\phi$ / °")
    ax_p.grid(True, which="both", linestyle="--", alpha=0.5)
    ax_p.legend(loc="best", fontsize=9)

    plt.tight_layout()

    safe_channel = re.sub(r'[^a-zA-Z0-9_-]', '_', api_label)
    out_filename = f"{pair_name}_{safe_channel}.png"
    out_path = os.path.join(save_folder, out_filename)
    fig.savefig(out_path, dpi=200)
    print(f"  [GESPEICHERT] {out_path} {('-> Sweep-Zeit: ' + time_formatted) if time_formatted else ''}")

    if show_interactive:
        plt.show()
    plt.close(fig)


def main():
    print("=" * 70)
    print(" AUTOMATISCHER BATCH-VERGLEICH: API vs. SCIOSPEC GUI")
    print("=" * 70)

    print("\n-> Bitte Ordner mit den API-Dateien (.h5) wählen...")
    api_dir = select_folder("Ordner mit API-Dateien (.h5) wählen", DEFAULT_API_DIR)
    if not api_dir:
        print("[INFO] Kein API-Ordner gewählt. Abbruch.")
        return

    if os.path.basename(os.path.normpath(api_dir)).lower() == "plots":
        api_dir = os.path.dirname(os.path.normpath(api_dir))
        print(f"[HINWEIS] Unterordner 'plots' erkannt -> Korrigiere auf Hauptordner: {api_dir}")

    print("-> Bitte Ordner mit den Sciospec-Messordnern wählen (z.B. medical)...")
    spec_dir = select_folder("Ordner mit Sciospec-Unterordnern wählen", DEFAULT_SPEC_DIR)
    if not spec_dir:
        print("[INFO] Kein Sciospec-Ordner gewählt. Abbruch.")
        return

    show_choice = input("\nSollen die Plots zusätzlich nacheinander am Bildschirm geöffnet werden? ([J]/n): ").strip().lower()
    show_interactive = show_choice not in ["n", "no", "nein"]

    plots_dir = os.path.join(api_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    print(f"\n[OK] Speicherort für Plots: {plots_dir}")

    spec_dirs_map = {
        d.lower(): d
        for d in os.listdir(spec_dir)
        if os.path.isdir(os.path.join(spec_dir, d))
    }

    api_files = [
        f for f in os.listdir(api_dir)
        if f.lower().endswith(".h5") and f.lower().startswith("api_")
    ]
    print(f"[OK] Gefundene API-Messdateien: {len(api_files)}")

    for api_file in sorted(api_files):
        api_path = os.path.join(api_dir, api_file)
        base_name = os.path.splitext(api_file)[0]

        print("\n" + "-" * 60)
        print(f"Verarbeite: {api_file}")

        api_data, api_trans = parse_api_hdf5(api_path)
        if not api_data:
            with h5py.File(api_path, "r") as h5_dbg:
                print(f"  [WARNUNG] Keine Messdaten erkannt. Root-Keys in Datei: {list(h5_dbg.keys())}")
            continue

        # 1. Sonderfall: api_kombi_test
        if base_name.lower() == "api_kombi_test":
            spec_data, spec_trans = assemble_kombi_spec_data(spec_dir, spec_dirs_map)
            if not spec_data:
                print("  [ÜBERSPRUNGEN] Sciospec-Ordner für Kombi-Test nicht vollständig gefunden.")
                continue

            all_trans = sorted(list(set(api_trans + spec_trans)))
            ak = next(iter(api_data.keys()))
            sk = next(iter(spec_data.keys()))
            save_and_plot_pair(
                pair_name=base_name,
                api_label=ak,
                spec_label=sk,
                api_series=api_data[ak],
                spec_series=spec_data[sk],
                transitions=all_trans,
                save_folder=plots_dir,
                show_interactive=show_interactive,
            )
            continue

        # 2. Regulärer Fall: api_xxx -> spec_xxx
        expected_spec_folder_lower = ("spec_" + base_name[4:]).lower()
        if expected_spec_folder_lower not in spec_dirs_map:
            print(f"  [NICHT GEFUNDEN] Kein Ordner '{expected_spec_folder_lower}' in {spec_dir}")
            continue

        actual_spec_folder = spec_dirs_map[expected_spec_folder_lower]
        target_spec_path = os.path.join(spec_dir, actual_spec_folder)

        spec_data, spec_trans = find_valid_sciospec_data_in_dir(target_spec_path)
        if not spec_data:
            print(f"  [KEINE DATEN] Keine gültigen Sciospec-Messdaten in: {actual_spec_folder}")
            continue

        all_trans = sorted(list(set(api_trans + spec_trans)))
        api_keys = list(api_data.keys())
        spec_keys = list(spec_data.keys())

        num_channels = min(len(api_keys), len(spec_keys))
        for i in range(num_channels):
            ak = api_keys[i]
            sk = spec_keys[i]
            save_and_plot_pair(
                pair_name=base_name,
                api_label=ak,
                spec_label=sk,
                api_series=api_data[ak],
                spec_series=spec_data[sk],
                transitions=all_trans,
                save_folder=plots_dir,
                show_interactive=show_interactive,
            )


if __name__ == "__main__":
    main()