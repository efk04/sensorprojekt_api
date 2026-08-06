# Sensorprojekt - ScioSpec ISX-3 API

## 1. Projektziel
Ziel ist eine lokal laufende, minimalistische Python-Anwendung/API zur Steuerung und Datenerfassung eines ScioSpec ISX-3 Messgeräts im universitären Laborbetrieb.

Die Software soll es Studierenden ermöglichen:
* das Messgerät über USB/serielle Schnittstelle anzusprechen,
* Messeinstellungen vorzunehmen,
* Messreihen zu starten und zu stoppen,
* Messdaten in Echtzeit zu visualisieren,
* Messergebnisse strukturiert im HDF5-Format zu speichern.

Die Anwendung soll stand-alone, einfach bedienbar, plattformübergreifend auf Windows und Linux lauffähig und leicht erweiterbar sein.

## 2. Zeitplan

## 3. Funktionale Anforderungen

### Geräteverbindung
* Die Anwendung soll erkennen können, ob ein verbundenes Gerät erreichbar ist.
* Die Anwendung soll automatisch eine serielle Verbindung zum ISX-3 über USB herstellen können.
* Bei Verbindungsabbruch soll eine klare Fehlermeldung ausgegeben werden.

### Gerätesteuerung und Statusabfrage
* Die Einstellungen für das Gerät sollen über eine config-Datei vorgenommen werden
* Die Einstellungen aus der Config sollen nach der Anpassung der config oder vor jeder messung an das Gerät übertragen werden
* Der aktuelle Gerätestatus soll abgefragt werden können, z. B. bereit, misst, Fehler.
* Fehlermeldungen vom ISX-3 sollen in Menschenleserbarer Art angezeigt werden

### Messeinstellungen / Messparameter
* Messparameter sollen vor der Messung in Mess-Config-File vorgenommen werden
* Die Anwendung soll nur gültige Parameterwerte akzeptieren und ungültige Eingaben mit defaults ersetzen und warnungen an den user geben
* Es soll möglich sein, Messparameter als Konfiguration zu speichern.
* Es soll möglich sein, gespeicherte Messprofile zu laden.
* Die aktuell gesetzten Parameter sollen vor Messstart angezeigt werden.

### Messung
* Eine Messreihe soll gestartet werden können.
* Eine laufende Messreihe soll gestoppt werden können.
* Eine Messreihe soll kontrolliert beendet werden können, sodass bereits empfangene Daten erhalten bleiben.
* Die Anwendung soll während einer Messung Messdaten kontinuierlich oder in Blöcken empfangen können.
* Empfangene Messdaten sollen mit Zeitstempeln versehen werden.
* Die Messung soll auch bei längeren Messreihen stabil laufen, ohne dass Daten verloren gehen.

### Echtzeitvisualisierung
* Die Anwendung soll eingehende Messdaten während der Messung live darstellen können.
* Der Live-Plot soll deaktivierbar sein, um Ressourcen zu sparen oder Messungen ohne Visualisierung durchzuführen.
* Es soll möglich sein, mindestens eine relevante Darstellung auszuwählen, z. B. Impedanz über Frequenz, Nyquist-Plot, Bode-Plot oder Zeitreihe.
* Der Live-Plot soll in sinnvollen Intervallen aktualisiert werden.
* Die Visualisierung darf die Datenerfassung nicht blockieren oder wesentlich verlangsamen.
* Die geplotteten Daten sollen nach Möglichkeit aus denselben Daten stammen, die auch gespeichert werden.

### Speicherung
* Messergebnisse sollen im HDF5-Format gespeichert werden können.
* Jede Messung soll in einer eigenen HDF5-Datei oder als eigene Gruppe innerhalb einer Datei gespeichert werden können.
* Die Speicherung soll automatisch während oder unmittelbar nach der Messung erfolgen.
* Metadaten zur Messung sollen mitgespeichert werden.
* Die gespeicherten Daten sollen für Menschen und Software nachvollziehbar strukturiert sein.
* Die Anwendung soll Dateinamen nach einem nachvollziehbaren Schema erzeugen können, z. B. Zeitstempel + Messname.
* Der Speicherpfad soll konfigurierbar sein.
* Bei einem Abbruch der Messung sollen bereits empfangene Daten möglichst gespeichert bleiben.

### Oberfläche
* Die Anwendung soll als Python-Anwendung ohne zwingende grafische Oberfläche nutzbar sein.
* Die Anwendung soll über eine Kommandozeilenschnittstelle oder eine einfache TUI bedienbar sein.
* Die wichtigsten Aktionen sollen über klare Befehle erreichbar sein, z. B. verbinden, konfigurieren, starten, stoppen, speichern.
* Die Anwendung soll Hilfetexte und Nutzungshinweise anzeigen können.
* Fehler sollen verständlich und nachvollziehbar ausgegeben werden.

### Nicht-funktionale Anforderungen
* Die Software soll in Python implementiert werden.
* Die Software soll unter Windows und Linux lauffähig sein.
* Die Software soll lokal ausgeführt werden.
* Die Software soll minimalistisch und erweiterbar gestaltet sein.
* Die Kernfunktionalität soll möglichst wenige externe Abhängigkeiten benötigen.
* Die Architektur soll eine klare Trennung zwischen Gerätekommunikation, Messlogik, Speicherung und Darstellung vorsehen.
* Die Anwendung soll so gestaltet sein, dass sie auch von Studierenden mit Grundkenntnissen in Python/Laborbetrieb nutzbar ist.
* Die Software soll dokumentiert werden, mindestens mit README, Installationsanleitung und Nutzungsbeispielen.
* Die Kernmodule sollen testbar gestaltet sein.
* Die Anwendung soll ohne spezielle Installation als Python-Projekt in einer virtuellen Umgebung lauffähig sein.
