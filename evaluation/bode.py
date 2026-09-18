import numpy as np
import matplotlib.pyplot as plt
from scipy import signal

fs = 1000.0
fc = 100.0
N = 4
f = np.logspace(0, np.log10(fs / 2), 2000)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

filters = {
    'Butterworth':  signal.butter(N, fc, btype='low', fs=fs, output='ba'),
    'Chebyshev I':  signal.cheby1(N, 1.0, fc, btype='low', fs=fs, output='ba'),
    'Chebyshev II': signal.cheby2(N, 40.0, fc, btype='low', fs=fs, output='ba'),
    'Elliptic':     signal.ellip(N, 1.0, 40.0, fc, btype='low', fs=fs, output='ba'),
}

for name, (b, a) in filters.items():
    _, h = signal.freqz(b, a, worN=f, fs=fs)
    ax1.semilogx(f, 20 * np.log10(np.abs(h) + 1e-12), label=name, linewidth=2)
    ax2.semilogx(f, np.degrees(np.unwrap(np.angle(h))), label=name, linewidth=2)

ax1.axvline(fc, color='r', linestyle='--', alpha=0.5, label=f'$f_c$ = {fc} Hz')
ax1.axhline(-3, color='gray', linestyle=':', alpha=0.5)
ax1.set_ylabel('Magnitude [dB]')
ax1.set_title(f'Bode Plot Comparison (N={N})')
ax1.set_ylim(-80, 5)
ax1.grid(True, which='both', alpha=0.3)
ax1.legend()

ax2.set_xlabel('Frequency [Hz]')
ax2.set_ylabel('Phase [degrees]')
ax2.grid(True, which='both', alpha=0.3)
ax2.legend()

plt.tight_layout()
plt.savefig("bode_plot_comparison.png", dpi=150)
plt.show()
