"""
plot_templates.py - Visualisierungsvorlagen fuer Impedanzspektroskopie (EIS).

Stellt Vorlagen fuer Bode- (logarithmisch & linear), Nyquist- und
Impedanz-Frequenz-Diagramme bereit.
"""

import math
import matplotlib.pyplot as plt


class PlotTemplates:
    """Verwaltet und zeichnet die Diagramme fuer laufende und vergangene Messungen."""

    def __init__(self):
        self.frequencies = []
        self.real = []
        self.imag = []
        self.freq_id = []

        self.past_results = []
        self.past_frequencies = []
        self.past_real = []
        self.past_imag = []

    def _flatten(self, item_or_list):
        """Flacht verschachtelte Listen rekursiv ab."""
        flat = []
        if isinstance(item_or_list, (list, tuple)):
            for element in item_or_list:
                flat.extend(self._flatten(element))
        else:
            flat.append(item_or_list)
        return flat

    def processing_results(self, live_results: dict, current_results: list[dict], len_measurement_queue: int) -> None:
        """Verarbeitet Rohdaten und fuehrt eine Historie der letzten 5 Sweeps mit."""
        self.freq_id = self._flatten(live_results.get("id", []))
        self.real = self._flatten(live_results.get("real", []))
        self.imag = self._flatten(live_results.get("imag", []))
        self.frequencies = self._flatten(live_results.get("frequencies", []))

        if len(current_results) == len_measurement_queue and len_measurement_queue > 0:
            self.past_results.append(list(current_results))

            if len(self.past_results) > 5:
                self.past_results.pop(0)

            self.past_frequencies = []
            self.past_real = []
            self.past_imag = []

            for cycle in self.past_results:
                for point in cycle:
                    if "frequencies" in point:
                        self.past_frequencies.extend(self._flatten(point["frequencies"]))
                    if "real" in point:
                        self.past_real.extend(self._flatten(point["real"]))
                    if "imag" in point:
                        self.past_imag.extend(self._flatten(point["imag"]))

    def impedance_frequency(self, live_results: dict, current_results: list[dict], len_measurement_queue: int) -> None:
        """Zeichnet Real- und Imaginaerteil ueber der Frequenz."""
        self.processing_results(live_results, current_results, len_measurement_queue)

        fig = plt.gcf()
        fig.clf()
        ax = fig.add_subplot(111)

        if self.past_real and len(self.past_frequencies) == len(self.past_real):
            ax.plot(self.past_frequencies, self.past_real, "o", color="gray", alpha=0.25, markersize=4)
            ax.plot(self.past_frequencies, self.past_imag, "s", color="gray", alpha=0.25, markersize=4)

        line_real, = ax.plot(self.frequencies, self.real, "ro-", label=r"$Z_{\mathrm{real}}$")
        line_imag, = ax.plot(self.frequencies, self.imag, "bs-", label=r"$Z_{\mathrm{imag}}$")

        ax.set_xscale("log")
        ax.set_xlabel("Frequenz $f$ / Hz")
        ax.set_ylabel(r"Impedanz $Z$ / $\Omega$")
        ax.set_title("Impedanz ueber Frequenz")
        ax.grid(True, which="both", linestyle="--", alpha=0.3)
        ax.tick_params(direction="in", which="both", top=True, right=True)

        ax.legend(handles=[line_real, line_imag], loc="upper right", frameon=True)
        fig.tight_layout()

    def nyquist(self, live_results: dict, current_results: list[dict], len_measurement_queue: int) -> None:
        """Zeichnet das Nyquist-Diagramm (Realteil auf X, Imaginaerteil auf Y)."""
        self.processing_results(live_results, current_results, len_measurement_queue)

        fig = plt.gcf()
        fig.clf()
        ax = fig.add_subplot(111)

        if self.past_real and len(self.past_real) == len(self.past_imag):
            ax.plot(self.past_real, self.past_imag, "o", color="gray", alpha=0.25, markersize=4)

        line_nyquist, = ax.plot(self.real, self.imag, "bo-", label="Aktuelle Messung")

        ax.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax.set_ylabel(r"Imaginaerteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax.set_title("Nyquist-Diagramm")

        ax.axhline(0, color="black", linewidth=0.8, linestyle=":")
        ax.axvline(0, color="black", linewidth=0.8, linestyle=":")

        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, which="both", linestyle="--", alpha=0.3)
        ax.tick_params(direction="in", which="both", top=True, right=True)

        ax.legend(handles=[line_nyquist], loc="upper right", frameon=True)
        fig.tight_layout()

    def bode(
        self,
        live_results: dict,
        current_results: list[dict],
        len_measurement_queue: int,
        linear_y: bool = False,
    ) -> None:
        """Zeichnet das Bode-Diagramm (Betrag |Z| und Phase ueber Frequenz)."""
        self.processing_results(live_results, current_results, len_measurement_queue)

        fig = plt.gcf()
        fig.clf()

        ax1 = fig.add_subplot(111)
        ax2 = ax1.twinx()

        if self.past_real and len(self.past_real) == len(self.past_imag):
            past_mag = [math.hypot(r, i) for r, i in zip(self.past_real, self.past_imag)]
            past_phase = [math.degrees(math.atan2(i, r)) for r, i in zip(self.past_real, self.past_imag)]
            ax1.plot(self.past_frequencies, past_mag, "o", color="gray", alpha=0.2, markersize=3)
            ax2.plot(self.past_frequencies, past_phase, "s", color="gray", alpha=0.2, markersize=3)

        impedance = [math.hypot(r, i) for r, i in zip(self.real, self.imag)]
        phase = [math.degrees(math.atan2(i, r)) for r, i in zip(self.real, self.imag)]

        line_mag, = ax1.plot(self.frequencies, impedance, "bo-", label=r"Betrag $|Z|$")
        line_phase, = ax2.plot(self.frequencies, phase, "rs-", label=r"Phase $\phi$")

        ax1.set_xscale("log")
        ax1.set_yscale("linear" if linear_y else "log")
        ax1.set_xlabel("Frequenz $f$ / Hz")
        ax1.set_ylabel(r"Betrag $|Z|$ / $\Omega$", color="b")
        ax1.tick_params(axis="y", labelcolor="b", direction="in")
        ax1.tick_params(axis="x", direction="in", which="both")
        ax1.grid(True, which="both", linestyle="--", alpha=0.3)

        ax2.set_ylabel(r"Phase $\phi$ / Grad", color="r")
        ax2.tick_params(axis="y", labelcolor="r", direction="in")

        scale_label = "Linear Y" if linear_y else "Log-Log"
        fig.suptitle(f"Bode-Diagramm ({scale_label})")

        fig.legend(
            handles=[line_mag, line_phase],
            loc="upper right",
            bbox_to_anchor=(0.90, 0.90),
            frameon=True,
        )
        fig.tight_layout()