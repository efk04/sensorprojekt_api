"""
quick_check.py - Vergleicht die exakten Zahlenwerte der GUI (.spec) und der Python-API (.h5)
bei 100 kHz und berechnet den exakten Skalierungsfaktor.
"""

import glob
import os
import h5py
import numpy as np
import pandas as pd

# 1. Neueste .spec Datei der GUI suchen
scio_dir = r"C:\Users\lukas\Documents\Test_Scio\setup\mux"
spec_files = glob.glob(os.path.join(scio_dir, "**", "*.spec"), recursive=True)

if not spec_files:
  print(f"[FEHLER] Keine .spec Dateien in '{scio_dir}' gefunden.")
  exit()

latest_spec = max(spec_files, key=os.path.getmtime)

# 2. Neueste .h5 Datei der Python-API suchen
h5_dir = r"C:\Users\lukas\Documents\GitHub\sensorprojekt_api\isx3_api\measurements"
h5_files = glob.glob(os.path.join(h5_dir, "*.h5"))

if not h5_files:
  print(f"[FEHLER] Keine .h5 Dateien in '{h5_dir}' gefunden.")
  exit()

latest_h5 = max(h5_files, key=os.path.getmtime)

print("=" * 60)
print(f"GUI-Datei:    {os.path.basename(latest_spec)}")
print(f"Python-Datei: {os.path.basename(latest_h5)}")
print("=" * 60)

# Sciospec .spec einlesen
with open(latest_spec, "r", encoding="utf-8", errors="replace") as f:
  lines = f.readlines()

header_idx = next(
    i for i, line in enumerate(lines) if "frequency" in line.lower()
)
df = pd.read_csv(latest_spec, skiprows=header_idx, sep=None, engine="python")
df.columns = [c.strip() for c in df.columns]

col_f = next(c for c in df.columns if "freq" in c.lower())
col_re = next(
    c
    for c in df.columns
    if c.lower().strip().startswith("re") or "re[" in c.lower()
)
col_im = next(
    c
    for c in df.columns
    if c.lower().strip().startswith("im") or "im[" in c.lower()
)

# Zeile bei ca. 100 kHz heraussuchen
row_gui = df.iloc[(df[col_f] - 100000.0).abs().argsort()[:1]]
f_gui = float(row_gui[col_f].values[0])
re_gui = float(row_gui[col_re].values[0])
im_gui = float(row_gui[col_im].values[0])
z_gui = np.hypot(re_gui, im_gui)

# Python .h5 einlesen
with h5py.File(latest_h5, "r") as h5:
  grp = h5["Sensor_8"] if "Sensor_8" in h5 else h5
  meas_keys = [k for k in grp.keys() if k.startswith("Measurement_")]

  best_k = None
  best_diff = float("inf")
  for k in meas_keys:
    f_val = float(np.mean(grp[k]["frequency"][()]))
    if abs(f_val - 100000.0) < best_diff:
      best_diff = abs(f_val - 100000.0)
      best_k = k

  f_py = float(np.mean(grp[best_k]["frequency"][()]))
  re_py = float(np.mean(grp[best_k]["real_part"][()]))
  im_py = float(np.mean(grp[best_k]["imaginary_part"][()]))
  z_py = np.hypot(re_py, im_py)

print("\n--- Spaltenstruktur der Sciospec-Datei ---")
print(f"Gefundene Spalten: {list(df.columns)}")

print(f"\n--- Vergleichswerte bei f ~ 100 kHz ---")
print(f"GUI:    f = {f_gui:9.1f} Hz | Re = {re_gui:10.2f} | Im = {im_gui:10.2f} | |Z| = {z_gui:10.2f} Ohm")
print(f"Python: f = {f_py:9.1f} Hz | Re = {re_py:10.2f} | Im = {im_py:10.2f} | |Z| = {z_py:10.2f} Ohm")

print("\n--- Berechnete Faktoren (GUI / Python) ---")
print(f"Verhältnis |Z|: {z_gui / z_py:.4f}")
print(f"Verhältnis Re:  {re_gui / re_py:.4f}")
print(f"Verhältnis Im:  {im_gui / im_py:.4f}")
print("=" * 60)