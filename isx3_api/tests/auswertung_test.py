"""
auswertung_test.py - Ganzheitlicher Vergleich zwischen Sciospec-GUI und Python-API.

Liest den Sciospec-Messordner (alle MUX-Unterordner & alle Wiederholungs-.spec-Dateien)
ein, mittelt die Durchläufe und vergleicht alle gemessenen Sensoren mit der Python-HDF5-Datei.
"""

import io
import os
import re
from tkinter import Tk, filedialog
import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# Standard-Startpfade für die Dateiauswahl
DEFAULT_SCIO_DIR = r"C:\Users\lukas\Documents\Test_Scio\setup\mux"
DEFAULT_H5_DIR = r"C:\Users\lukas\Documents\GitHub\sensorprojekt_api\isx3_api\measurements"


def select_sources() -> tuple[str | None, str | None]:
    """Öffnet Dialoge zur Auswahl des Sciospec-Hauptordners und der HDF5-Datei mit festen Startpfaden."""
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    # 1. Sciospec Ordnerauswahl
    init_scio = DEFAULT_SCIO_DIR if os.path.exists(DEFAULT_SCIO_DIR) else None
    scio_dir = filedialog.askdirectory(
        title="1/2: Wähle den Sciospec-Ordner (z. B. 'mux' oder 'setup')",
        initialdir=init_scio,
    )
    if not scio_dir:
        root.destroy()
        return None, None

    # 2. HDF5 Dateiauswahl
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
    """Liest eine einzelne .spec-Datei robust ein."""
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
        "imag": pd.to_numeric(df[col_im], errors="coerce")
    }).dropna()

    return clean_df.sort_values(by="frequency").reset_index(drop=True)


def parse_sciospec_folder(base_dir: str) -> dict[int, dict[str, np.ndarray]]:
  """Durchsucht den Sciospec-Ordner nach MUX-Kanälen.

  Wählt automatisch den zeitlich neuesten Durchlauf, falls Unterordner existieren.
  """
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

  # Falls der übergeordnete Ordner (z. B. 'mux') gewählt wurde:
  # Den neuesten Zeitstempel-Ordner ermitteln
  if not mux_entries:
    subdirs = []
    for sub in os.scandir(base_dir):
      if sub.is_dir():
        # Rekursiv prüfen, ob MUX-Ordner enthalten sind
        inner = find_mux_folders(sub.path)
        if not inner:
          setup_sub = os.path.join(sub.path, "setup")
          if os.path.isdir(setup_sub):
            inner = find_mux_folders(setup_sub)
        if inner:
          subdirs.append((sub.stat().st_mtime, inner, sub.path))

    if subdirs:
      # Nach Änderungsdatum sortieren -> Neuesten nehmen
      subdirs.sort(key=lambda x: x[0], reverse=True)
      mux_entries = subdirs[0][1]
      print(
          f"[INFO] Automatischer Wechsel auf neuesten GUI-Durchlauf:"
          f" {os.path.basename(subdirs[0][2])}"
      )

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
    """Liest alle Sensoren aus der HDF5-Datei ein und mittelt number_of_spectra."""
    # Fester Hardware-/Frontend-Skalierungsfaktor (Rohdaten -> Sciospec GUI)
    SCALE_FACTOR = 2.3668

    results = {}
    with h5py.File(h5_file, "r") as h5:  #
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
            re_arr = np.array(re_list) * SCALE_FACTOR
            im_arr = np.array(im_list) * SCALE_FACTOR

            results[s_idx] = {
                "frequency": f_arr,
                "real": re_arr,
                "imag": im_arr,
                "z_mag": np.hypot(re_arr, im_arr),
                "phase": np.degrees(np.arctan2(im_arr, re_arr)),  
            }

    return results  


def main():
    scio_dir, h5_path = select_sources()
    if not scio_dir or not h5_path:
        print("[INFO] Auswahl abgebrochen.")
        return

    print(f"\n[INFO] Lese Sciospec-Ordner: {scio_dir}")
    gui_data = parse_sciospec_folder(scio_dir)

    print(f"[INFO] Lese Python-HDF5:     {h5_path}")
    py_data = parse_hdf5_file(h5_path)

    common_sensors = sorted(set(gui_data.keys()).intersection(py_data.keys()))

    if not common_sensors and 0 in py_data and len(gui_data) == 1:
        g_idx = list(gui_data.keys())[0]
        py_data[g_idx] = py_data.pop(0)
        common_sensors = [g_idx]

    if not common_sensors:
        print("\n[FEHLER] Keine übereinstimmenden Sensoren zwischen GUI und HDF5 gefunden!")
        print(f"  └── Vorhanden in Sciospec-GUI: Sensoren {list(gui_data.keys())}")
        print(f"  └── Vorhanden in Python-HDF5:  Sensoren {list(py_data.keys())}")
        return

    print(f"\n[OK] Übereinstimmende Sensoren zum Vergleich: {common_sensors}")
    for s_idx in common_sensors:
        g_cnt = gui_data[s_idx]["count"]
        print(f"  • Sensor #{s_idx}: {g_cnt} Sciospec-Messung(en) gemittelt.")

    # Visualisierung: Bode-Diagramm
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    colormap = plt.get_cmap("tab10")

    for idx, s_idx in enumerate(common_sensors):
        color = colormap(idx % 10)
        g = gui_data[s_idx]
        p = py_data[s_idx]

        label_gui = f"Sensor #{s_idx} (Sciospec GUI)"
        label_py = f"Sensor #{s_idx} (Python API)"

        # Betrag |Z|
        ax1.plot(
            g["frequency"],
            g["z_mag"],
            linestyle="-",
            color=color,
            linewidth=2.0,
            label=label_gui,
        )
        ax1.plot(
            p["frequency"],
            p["z_mag"],
            linestyle="--",
            color=color,
            linewidth=1.5,
            label=label_py,
        )

        # Phasenwinkel phi
        ax2.plot(
            g["frequency"],
            g["phase"],
            linestyle="-",
            color=color,
            linewidth=2.0,
            label=label_gui,
        )
        ax2.plot(
            p["frequency"],
            p["phase"],
            linestyle="--",
            color=color,
            linewidth=1.5,
            label=label_py,
        )

    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_ylabel(r"Scheinwiderstand $|Z|$ / $\Omega$")
    ax1.set_title("Vollständiger Validierungsvergleich: Sciospec GUI vs. Eigene Python-API")
    ax1.grid(True, which="both", linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", fontsize=9)

    ax2.set_xscale("log")
    ax2.set_xlabel("Frequenz $f$ / Hz")
    ax2.set_ylabel(r"Phase $\phi$ / $^\circ$")
    ax2.grid(True, which="both", linestyle="--", alpha=0.5)
    ax2.legend(loc="upper right", fontsize=9)

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()