"""
plot_templates.py - Visualisierungsvorlagen für Impedanzspektroskopie (EIS).

Stellt Vorlagen für Bode-, Nyquist- und Impedanz-Frequenz-Diagramme bereit.
Unterstützt Live-Updates während der Messung und zeigt vergangene Messzyklen
als Referenz im Hintergrund an.
"""

import math
import matplotlib.pyplot as plt


class PlotTemplates:
    """Verwaltet und zeichnet die Diagramme für laufende und vergangene Messungen."""

    def __init__(self):
        # Daten des aktuellen Messzyklus
        self.frequencies: list[float] = []
        self.real: list[float] = []
        self.imag: list[float] = []
        self.freq_id: list[int] = []

        # Ringspeicher für die letzten abgeschlossenen Messzyklen
        self.past_results: list[list[dict]] = []
        self.past_frequencies: list[float] = []
        self.past_real: list[float] = []
        self.past_imag: list[float] = []

    def _flatten(self, item_or_list) -> list:
        """Stellt sicher, dass verschachtelte Listen zu einer flachen 1D-Liste werden."""
        flat = []
        if isinstance(item_or_list, (list, tuple)):
            for element in item_or_list:
                flat.extend(self._flatten(element))
        else:
            flat.append(item_or_list)
        return flat

    def processing_results(self, live_results: dict, current_results: list[dict], len_measurement_queue: int) -> None:
        """
        Extrahiert die aktuellen Punktdaten und verwaltet die Messhistorie (maximal 5 Zyklen).

        :param live_results: Ergebnis-Dictionary des zuletzt empfangenen Messpunkts.
        :param current_results: Bisher gesammelte Messpunkte des aktuellen Durchlaufs.
        :param len_measurement_queue: Gesamtanzahl der Messpunkte pro Durchlauf.
        """
        # Aktuellen Punkt flach einlesen
        self.freq_id = self._flatten(live_results.get("id", []))
        self.real = self._flatten(live_results.get("real", []))
        self.imag = self._flatten(live_results.get("imag", []))
        self.frequencies = self._flatten(live_results.get("frequencies", []))

        # Wenn ein gesamter Frequenz-Sweep vollständig ist, archivieren
        if len(current_results) == len_measurement_queue and len_measurement_queue > 0:
            self.past_results.append(list(current_results))

            # Nur die letzten 5 Messzyklen im Speicher halten
            if len(self.past_results) > 5:
                self.past_results.pop(0)

            # Historien-Listen für die Hintergrunddarstellung konsolidieren
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
        """Zeichnet Real- und Imaginärteil über der Frequenz."""
        self.processing_results(live_results, current_results, len_measurement_queue)

        fig = plt.gcf()
        fig.clf()
        ax = fig.add_subplot(111)

        # Vergangene Zyklen im Hintergrund darstellen (ausgegraut)
        if self.past_real and len(self.past_frequencies) == len(self.past_real):
            ax.plot(self.past_frequencies, self.past_real, "o", color="gray", alpha=0.25, markersize=4)
            ax.plot(self.past_frequencies, self.past_imag, "s", color="gray", alpha=0.25, markersize=4)

        # Aktuelle Daten des laufenden Zyklus
        line_real, = ax.plot(self.frequencies, self.real, "ro-", label=r"$Z_{\mathrm{real}}$")
        line_imag, = ax.plot(self.frequencies, self.imag, "bs-", label=r"$Z_{\mathrm{imag}}$")

        ax.set_xscale("log")
        ax.set_xlabel("Frequenz $f$ / Hz")
        ax.set_ylabel(r"Impedanz $Z$ / $\Omega$")
        ax.set_title("Impedanz über Frequenz")
        ax.grid(True, which="both", linestyle="--", alpha=0.3)
        ax.tick_params(direction="in", which="both", top=True, right=True)

        ax.legend(handles=[line_real, line_imag], loc="upper right", frameon=True)
        fig.tight_layout()

    def nyquist(self, live_results: dict, current_results: list[dict], len_measurement_queue: int) -> None:
        """Zeichnet das Nyquist-Diagramm (Z_imag über Z_real)."""
        self.processing_results(live_results, current_results, len_measurement_queue)

        fig = plt.gcf()
        fig.clf()
        ax = fig.add_subplot(111)

        # Vergangene Zyklen als Referenz im Hintergrund
        if self.past_real and len(self.past_real) == len(self.past_imag):
            ax.plot(self.past_real, self.past_imag, "o", color="gray", alpha=0.25, markersize=4)

        # Aktuelle Messkurve
        line_nyquist, = ax.plot(self.real, self.imag, "bo-", label="Aktuelle Messung")

        ax.set_xlabel(r"Realteil $Z_{\mathrm{real}}$ / $\Omega$")
        ax.set_ylabel(r"Imaginärteil $Z_{\mathrm{imag}}$ / $\Omega$")
        ax.set_title("Nyquist-Diagramm")

        # Null-Achsen hervorheben
        ax.axhline(0, color="black", linewidth=0.8, linestyle=":")
        ax.axvline(0, color="black", linewidth=0.8, linestyle=":")

        # 1:1 Seitenverhältnis für unverzerrte Nyquist-Kreise
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, which="both", linestyle="--", alpha=0.3)
        ax.tick_params(direction="in", which="both", top=True, right=True)

        ax.legend(handles=[line_nyquist], loc="upper right", frameon=True)
        fig.tight_layout()

    def bode(self, live_results: dict, current_results: list[dict], len_measurement_queue: int) -> None:
        """Zeichnet das Bode-Diagramm (Betrag |Z| und Phase phi mit zwei Y-Achsen)."""
        self.processing_results(live_results, current_results, len_measurement_queue)

        fig = plt.gcf()
        fig.clf()

        # Primäre Achse (links): Scheinwiderstand |Z|
        ax1 = fig.add_subplot(111)
        # Sekundäre Achse (rechts): Phasenwinkel phi
        ax2 = ax1.twinx()

        # Vergangene Zyklen im Hintergrund zeichnen
        if self.past_real and len(self.past_real) == len(self.past_imag):
            past_mag = [math.hypot(r, i) for r, i in zip(self.past_real, self.past_imag)]
            past_phase = [math.degrees(math.atan2(i, r)) for r, i in zip(self.past_real, self.past_imag)]
            ax1.plot(self.past_frequencies, past_mag, "o", color="gray", alpha=0.2, markersize=3)
            ax2.plot(self.past_frequencies, past_phase, "s", color="gray", alpha=0.2, markersize=3)

        # Betrag |Z| und Phase phi für aktuelle Daten berechnen
        impedance = [math.hypot(r, i) for r, i in zip(self.real, self.imag)]
        phase = [math.degrees(math.atan2(i, r)) for r, i in zip(self.real, self.imag)]

        line_mag, = ax1.plot(self.frequencies, impedance, "bo-", label=r"Betrag $|Z|$")
        line_phase, = ax2.plot(self.frequencies, phase, "rs-", label=r"Phase $\phi$")

        # Achsenformatierung links (|Z|)
        ax1.set_xscale("log")
        ax1.set_yscale("log")
        ax1.set_xlabel("Frequenz $f$ / Hz")
        ax1.set_ylabel(r"Betrag $|Z|$ / $\Omega$", color="b")
        ax1.tick_params(axis="y", labelcolor="b", direction="in")
        ax1.tick_params(axis="x", direction="in", which="both")
        ax1.grid(True, which="both", linestyle="--", alpha=0.3)

        # Achsenformatierung rechts (Phase)
        ax2.set_ylabel(r"Phase $\phi$ / Grad", color="r")
        ax2.tick_params(axis="y", labelcolor="r", direction="in")

        fig.suptitle("Bode-Diagramm")

        # Kombinierte Legende für beide Achsen
        fig.legend(
            handles=[line_mag, line_phase],
            loc="upper right",
            bbox_to_anchor=(0.90, 0.90),
            frameon=True,
        )
        fig.tight_layout()