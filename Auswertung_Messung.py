import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# CSV-Datei laden
file_path = r"C:\Users\turbo\OneDrive\Dokumente\Studium\HTWK\Sensorprojekt\measurement_results.csv"
df = pd.read_csv(file_path)

# Frequenzachse erzeugen:
# 100 Punkte logarithmisch von 100 Hz bis 1 MHz
frequencies = np.logspace(
    np.log10(100),
    np.log10(1e6),
    100
)

# Impedanzanteile
real_part = df["Real Part"]
imag_part = df["Imaginary Part"]
impedanz = df["Impedanz"] = (df["Real Part"]**2 + df["Imaginary Part"]**2)**0.5

# Plot Impedanz über Frequenz
plt.figure(figsize=(10, 6))

plt.semilogx(
    frequencies,
    real_part,
    label="Realteil",
    linewidth=2
)

plt.semilogx(
    frequencies,
    imag_part,
    label="Imaginärteil",
    linewidth=2
)

plt.semilogx(
    frequencies,
    impedanz,
    label="Impedanz",
    linewidth=2
)

plt.xlabel("Frequenz [Hz]")
plt.ylabel("Impedanz [Ω]")
plt.title("Impedanz über Frequenz")
plt.grid(True, which="both", linestyle="--", alpha=0.7)
plt.legend()

plt.tight_layout()
plt.show()

#Nyquist Digramm
"""
plt.figure(figsize=(7, 7))
plt.plot(real_part, -imag_part, "o-")
plt.xlabel("Re(Z) [Ω]")
plt.ylabel("-Im(Z) [Ω]")
plt.title("Nyquist-Plot")
plt.grid(True)
plt.axis("equal")
plt.tight_layout()
plt.show()
"""