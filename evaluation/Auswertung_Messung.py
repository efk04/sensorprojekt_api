# Darstellung der Messergebnisse aus der CSV-Datei
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import h5py
import glob
import os

"""
Zu erstellende Funktionen
1. Einzelmessung
-> Namen für gemessenen Datensatz generieren
    System für Namensspeicherung -> Aktuell: per Datum
-> Datenspeicherung in HDF5-Format 
-> Auslesen der HDF5-Datei
""-> Frequency-ID als Frequenzwert""
-> Darstellung mithilfe von Plotfuntkion -> hinzufügen von Datenwerten ermöglichen
2. Sweep-Messung    
-> Anpassen der Einzelmessung-Funktionen für Sweep-Messung
    Wie wird der Sweep gespeichert?
    Was muss bei den Einzelmessungsfunktionen weiterverwendet werden -> Schleifen?

3. kontinuierliche Messung
-> Anpassen der Einzelmessung-Funktionen für kontinuierliche Messung
    Wie werden die kontinuierlichen Werte gespeichert?
    Was muss bei den Einzelmessungsfunktionen weiterverwendet werden -> Schleifen?
"""
def get_latest_measurement_file(directory="."):
    """Sucht nach der neuesten 'measurement_results_*.h5' Datei."""
    pattern = os.path.join(directory, "measurement_results_*.h5")
    files = glob.glob(pattern)
    if not files:
        return None
    return sorted(files)[-1]

class H5LiveReader:
    def __init__(self, filename):
        self.filename = filename
        self.read_groups = set()  # Speichert die Namen der bereits gelesenen Gruppen
        self.plot_data = {}       # Speichert die aufbereiteten Daten für den Plot

    def h5py_read_and_update_data(self):
        """
        opens latest measurment file
        loads the measurment data in numpy.ndarray

        """

        new_data_found = False
        try:
            with h5py.File(self.filename, 'r', libver='latest',swmr=True) as f:
                print(f"--- Datei '{self.filename}' erfolgreich geöffnet ---")

                #aktuelle gruppen auslesen
                current_groups = set(f.keys())
                # Finde die Gruppen, die wir noch NICHT gelesen haben (Mengen-Differenz)
                new_groups = current_groups - self.read_groups

                #Gruppen chronolgisch sortieren -> Nach Erstellungsdatum sortieren
                for group_name in sorted(new_groups):
                    group = f[group_name]
                    
                    # Wir prüfen, ob die Datasets aus deiner Datei existieren
                    if 'real_part' in group.keys() and 'imaginary_part' in group.keys():
                        
                        # Daten auslesen
                        real_data = group['real_part'][:]
                        imag_data = group['imaginary_part'][:]
                        freq_data = group['frequency_id'][:]
                        
                        # Konsolenausgabe zur Kontrolle
                        print(f"Neue Daten aus {group_name} geladen: Form={real_data.shape}")
                        
                        #Die Daten im Dictionary für den Plot speichern!
                        self.plot_data[group_name] = {
                            'frequency': freq_data,
                            'real': real_data,
                            'imaginary': imag_data
                        }

                self.read_groups.add(group_name)
                new_data_found = True
        except OSError: 
            # Kann passieren, wenn die Datei im exakt selben Millisekunden-Bruchteil 
            # vom Writer blockiert wird, bevor SWMR richtig greift. Einfach überspringen.
            pass    

        print(f"New data found: {new_data_found}")
        return new_data_found


    def get_all_data(self):
            """Gibt die aktuell geladenen Daten für die Plot-Funktion zurück."""
            return self.plot_data

class H5LiveEvaluator:
    """
    Diese Manager-Klasse kapselt das Plot-Fenster und steuert den Reader.
    Sie wird in der main.py aufgerufen.
    """
    def __init__(self, directory="."):
        self.directory = directory
        self.reader = None
        
        # Plot-Fenster einmalig vorbereiten
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        plt.ion()  # Interaktiven Modus aktivieren

    def update(self):
        """Prüft auf neue Dateien/Daten und aktualisiert das Diagramm."""
        latest_file = get_latest_measurement_file(self.directory)
        
        if not latest_file:
            print("Warte auf erste Messdatei...", end="\r")
            return

        # Falls eine neue Datei erstellt wurde oder der Reader noch nicht existiert
        if self.reader is None or self.reader.filename != latest_file:
            print(f"\n[INFO] Wechsle zu neuester Messdatei: {latest_file}")
            self.reader = H5LiveReader(latest_file)
            self.ax1.clear()
            self.ax2.clear()

        # Neue Daten auslesen
        has_new_data = self.reader.h5py_read_and_update_data()
        
        # Plot aktualisieren, wenn neue Gruppen gefunden wurden
        if has_new_data:
            self._plot_live_data(self.reader.get_all_data())

    def _plot_live_data(self, data_to_plot):
        """Interne Methode zum Zeichnen der Daten."""
        self.ax1.clear()
        self.ax2.clear()
        
        if not data_to_plot:
            return

        for group_name, values in data_to_plot.items():
            freq = values['frequency']
            real = values['real']
            imag = values['imaginary']
            complex_part = np.sqrt(real**2 + imag**2)
            
            # Diagramm 1: Real- und Imaginärteil
            self.ax1.plot(freq, real, 'o', linewidth=1.5, label=f"{group_name} (Real)")
            self.ax1.plot(freq, imag, 's', linewidth=1.5, label=f"{group_name} (Imag)")
            
            # Diagramm 2: Betrag
            self.ax2.plot(freq, complex_part, 'd', linewidth=1.5, label=f"{group_name} (Betrag)")

        # Styling Ax1
        self.ax1.set_ylabel("Widerstand [Ω]")
        self.ax1.set_title("Real- und Imaginärteil im Verlauf der Frequenz", fontsize=12, fontweight='bold')
        self.ax1.grid(True, linestyle='--', alpha=0.6)
        self.ax1.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0.)
        
        # Styling Ax2
        self.ax2.set_xlabel("Frequenz (Hz)")
        self.ax2.set_ylabel("Komplexer Betrag |Z|")
        self.ax2.set_title("Komplexer Betrag (Magnitude) im Verlauf der Frequenz", fontsize=12, fontweight='bold')
        self.ax2.grid(True, linestyle='--', alpha=0.6)
        self.ax2.legend(loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0.)
        
        plt.tight_layout()
        plt.draw()
        plt.pause(0.01)

    def freeze_window(self):
        """Hält das Fenster am Ende dauerhaft offen."""
        plt.ioff()
        print("\n[INFO] Messung beendet. Plot-Fenster bleibt geöffnet (manuell schließen).")
        plt.show()

