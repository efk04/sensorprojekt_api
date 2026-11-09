# Sensorprojekt – Sciospec ISX-3 Python API & Mess-Framework

## 1. Projektziel
Ziel ist eine lokal laufende, modulare Python-Anwendung und API (`isx3_api`) zur Steuerung, Systemdiagnose und automatisierten Datenerfassung von Sciospec ISX-3 Impedanzspektrometern (**Standard ISX-3 / ISX-3mini** sowie **Medical Research ISX-3**) im universitären Laborbetrieb.

Die Software ermöglicht es Studierenden und Forschenden:
- beide Gerätegenerationen (Standard & Medical Research) über die serielle USB-Schnittstelle (Virtual COM Port) anzusprechen,
- komplexe Messeinstellungen (inkl. Multi-Block-Frequenzsweeps und Multiplexer-Routing) über `.ini`-Profile, einen interaktiven Konsolen-Assistenten (CLI) oder eine grafische Oberfläche (Tkinter-GUI) vorzunehmen,
- vor Messbeginn einen automatisierten **System-Baseline-Drift-Check** am internen $2\,\text{k}\Omega$-Referenzwiderstand durchzuführen,
- Einzelpunkt-, Hardware-Sweep- und Mehrkanal-MUX-Messreihen kontrolliert zu starten und zu stoppen,
- Messdaten in Echtzeit (punkt- oder sweepweise) in verschiedenen elektrochemischen Diagrammen zu visualisieren,
- Messergebnisse samt kompletter Konfigurations-Metadaten reproduzierbar im **HDF5-Format** zu speichern.

Die Anwendung ist stand-alone, plattformübergreifend unter Windows und Linux lauffähig, kommt mit minimalen Standard-Abhängigkeiten aus und ist durch automatisierte Unit-Tests (ohne Hardware-Zwang via Mocking) abgesichert.

## 2. Projektstatus & Meilensteine
- **Basis-Architektur & Treiber (`commands.py`):** Vollständige Kapselung des Binärprotokolls (`0xB0` bis `0xB9`, `0x97`, `0xA1`) mit synchronem ACK/NACK-Handshake (`0x18`).
- **Dual-Hardware-Support:** Unterstützung für das klassische 4-Byte-Frontend (`0xB0` + `0xB2`) bei Standard-Geräten sowie das erweiterte 15-Byte-Frontend-Protokoll (`0xB0` mit 16-Bit-Kanaladressierung ohne `0xB2`) beim Medical Research ISX-3.
- **Gutachten-Revision & Bugfixes:** Vollständige Behebung aller im Gutachten identifizierten Altmängel (aktive HDF5-Speicherung, bytegenaues Frame-Parsing für 4-Byte-ms- und 5-Byte-$\mu\text{s}$-Zeitstempel sowie Current-Range-Byte, echter Hex-Software-Reset `0xA1 0x00 0xA1`, Bereinigung von Fremdimporten).
- **Qualitätssicherung:** Implementierung einer Mock-basierten Unit-Test-Suite (`tests/test_isx3_api.py`) für Konfigurations-Parser, MUX-Logik, Binärprotokoll und HDF5-Persistenz.

## 3. Funktionale Anforderungen (Aktueller Umsetzungsstand)

### Geräteverbindung & Hardware-Abstraktion
- **Automatische Port-Erkennung:** Die Anwendung erkennt über `serial.tools.list_ports` alle verfügbaren seriellen Schnittstellen unter Windows (`COMx`) und Linux (`/dev/ttyUSBx`, `/dev/ttyACMx`) und stellt bei Bedarf Fallback-Ports bereit.
- **Verbindungsaufbau:** Aufbau der USB-FS-Verbindung (`connect_device_fs`) mit konfigurierbarer Baudrate (Standard: `115200` Baud) und automatischem Puffer-Reset.
- **Modell-Umschaltung:** Nahtlose Unterstützung von `standard` (ISX-3 / ISX-3mini) und `medical` (Medical Research ISX-3) über den Konfigurationsparameter `device_version`.
- **Fehlerbehandlung:** Klare Prüfung auf Port-Verfügbarkeit, Verbindungsabbrüche und unvollständige Datenframes mit gezielten `TimeoutError`- und `ConnectionError`-Ausgaben.

### Gerätesteuerung, Multiplexer-Routing & Diagnose
- **Synchrones Befehls-Framing:** Jeder Befehl wird im Format `[Tag] [Länge] [Payload] [Tag]` gesendet und wartet auf die Hardware-Quittierung (`0x18 0x01 0x83 0x18`).
- **Klartext-Statusmeldungen:** Hardware-Antwortcodes (`MSG_DICT`, z. B. `0x81` Syntaxfehler, `0x82` unbekanntes Tag, `0x90` Überstrom, `0x91` Überspannung) werden in menschenlesbare deutsche Meldungen übersetzt.
- **Universelles MUX32/64-Pin-Routing (`route_mux_sensor`):**
  - Automatische Kanalberechnung für **4-Leiter-Messungen** ($4n-3$ bis $4n$, z. B. Sensor 1 $\rightarrow$ Pins `1, 2, 3, 4`; Sensor 2 $\rightarrow$ Pins `5, 6, 7, 8`) und **2-Leiter-Messungen** ($2n-1$ und $2n$) für beide Geräteversionen.
  - Unterstützung für Kanalbereiche (`1-8`), Komma-Listen (`1, 3, 5`) sowie freie **Custom-Pin-Belegungen über Doppelpunkt-Syntax** (z. B. `1: 2,5,8,6` oder `22: 22,22,23,23`) via Regex-Parser.
  - Automatischer Relais-Stack-Reset (`0xB0 0x03 FF FF FF 0xB0`) vor jedem Kanalwechsel und beim Beenden der Messung (`clear_mux_routing`).
- **Firmware-Schutz für Medical-Geräte:** Optionale Frame-Erweiterungen (`0x97`) und nicht unterstützte Befehle werden im Medical-Modus abgefangen, um ACK-Timeouts zu verhindern.
- **System-Baseline-Drift-Check (`run_baseline_drift_check`):** Automatisierte Stabilitätsprüfung über 5 Messzyklen bei $1\,\text{kHz}$ auf dem internen $2\,\text{k}\Omega$-Präzisionswiderstand (MUX-Port 3, Pins `22, 22, 23, 23`) mit Berechnung von Mittelwert und relativer Drift (Toleranzgrenze $\le 0{,}2\,\%$).

### Messeinstellungen & Messparameter (`config_handler.py`)
- **Strukturierte `.ini`-Konfiguration:** Verwaltung über 11 standardisierte Sektionen (`Connection`, `MUX`, `Frontend`, `ExtensionPort`, `FrequencySetup`, `FrequencyBlocks`, `DCBias`, `SyncTime`, `Options`, `Measurement`, `ApiSettings`) mittels typisierter Python-`dataclass`-Strukturen.
- **Intelligentes Einheiten- & SI-Präfix-Parsing:** Eingaben wie `100u`, `100uA`, `100mVpp`, `1.5k` oder `1M` werden automatisch in Gleitkommazahlen konvertiert.
- **Automatische Amplituden-Skalierung ($A_{pp}$ vs. $A_p$):**
  - Im **Standard-Modus** werden Amplituden als echte Spitzenwerte ($A_p$ / $V_p$) eingegeben und 1:1 an die Hardware übertragen.
  - Im **Medical-Modus** erfolgt die Eingabe analog zur Sciospec-PC-Software als Spitze-Spitze-Wert ($A_{pp}$ / $V_{pp}$). Die API halbiert diesen Wert vor dem Packen in den `0xB6`-Befehl automatisch (`* 0.5`), um die Peak-Vorgabe der Firmware zu erfüllen.
- **Multi-Block-Frequenzsweeps:** Unterstützung beliebig vieler verketteter Frequenzblöcke mit jeweils eigener Start-/Stoppfrequenz, Punktanzahl, Skalierung (`logarithmic` / `linear`), `precision`, Anregungsart (`Voltage` / `Current`) und Amplitude.
- **Parameter-Validierung & Fallbacks:** Ungültige Eingaben (z. B. nicht unterstützte `voltage_range`- oder `current_range`-Codes) werden automatisch auf sichere Hardware-Defaults korrigiert und mit einer Warnung protokolliert.

### Messung (`measurement.py`)
- **Zwei Ausführungsmodi:**
  - **Hardware-Sweep (`0xB6` Sub `0x03`):** Übertragung kompletter Frequenzblöcke in den Gerätespeicher und Einlesen des gesamten Spektrums in einem schnellen Block-Transfer.
  - **Single-Step-Modus (`0xB6` Sub `0x02`):** Diskrete Punkt-für-Punkt-Konfiguration und Messung.
- **Mehrkanal-Sequenzierung:** Automatisches Durchschalten aller aktiven MUX-Sensoren inklusive konfigurierbarer Einschwingzeit (`switch_delay_s` und `point_delay_ms`).
- **Erweiterte Datenframe-Auswertung (`read_measurement_data`):** Dynamisches Byte-Parsing für Realteil, Imaginärteil, Frequenz-ID sowie optionale 4-Byte-ms-Zeitstempel, 5-Byte-$\mu\text{s}$-Zeitstempel und den aktiven Strommessbereich (`current_range`).
- **Kontrollierter Abbruch:** Sauberes Abfangen von `KeyboardInterrupt` (`Strg+C`) in einem `try...finally`-Block; bereits gemessene Punkte bleiben in der HDF5-Datei erhalten, das MUX-Routing wird zurückgesetzt und der serielle Port sicher geschlossen.

### Echtzeitvisualisierung (`plot_templates.py`)
- **Vier Diagramm-Vorlagen:**
  - `bode`: Klassisches Bode-Diagramm ($|Z|$ logarithmisch und Phase $\varphi$ in Grad über logarithmischer Frequenz).
  - `bode_lin`: Bode-Diagramm mit linearer Betragsachse.
  - `nyquist`: Ortskurve ($Z_{\mathrm{imag}}$ über $Z_{\mathrm{real}}$) mit quadratischer Achsenskalierung.
  - `impedance_frequency`: Getrennte Darstellung von $Z_{\mathrm{real}}$ und $Z_{\mathrm{imag}}$ über der Frequenz.
- **Sweep-Historie:** Vergangene Durchläufe (bis zu 5 Sweeps) werden als dezente graue Referenzkurven im Hintergrund mitgeführt.
- **Ressourcen-Steuerung:** Der Live-Plot kann komplett deaktiviert (`live_plot_enabled = False`) oder zwischen Punkt-Update (`point`) und Komplett-Sweep-Update (`sweep`) umgeschaltet werden.

### Speicherung im HDF5-Format
- **Automatische Dateierzeugung:** Jede Messkampagne erzeugt im Ordner `measurements/` eine Datei nach dem Schema `measurement_<MAIN|MUX>_<YYYYMMDD-HHMMSS>.h5`.
- **Vollständige Reproduzierbarkeit:** Die gesamte `.ini`-Konfiguration sowie `device_version` und `measurement_type` werden vor Messbeginn in der HDF5-Gruppe `Configuration` als Attribute gesichert.
- **Hierarchische Datenablage:**
  - Am Hauptport unter `/Measurement_<Zyklus>.<PunktID>`
  - Im MUX-Betrieb getrennt nach Kanälen unter `/Sensor_<Nr>/Measurement_<Zyklus>.<PunktID>` inklusive realer Kanal-Messdauer (`measurement_duration_ms`).
  - Gespeicherte Datasets pro Messpunkt: `frequency`, `frequency_id`, `real_part`, `imaginary_part`, `timestamp` sowie optional `hw_timestamp` (inkl. Einheiten-Attribut `ms`/`us`) und `current_range`.

### Oberfläche & Bedienkonzept (`main.py` & `config_gui.py`)
Über den zentralen Einstiegspunkt `tests/main.py` stehen drei gleichwertige Arbeitsweisen zur Verfügung:
1. **Grafische Benutzeroberfläche (Tkinter-GUI):** Komfortabler Profil-Manager mit dynamischer Einheiten-Umschaltung ($A$/$V$ Peak vs. $A_{pp}$/$V_{pp}$), interaktiver Frequenzblock-Tabelle, MUX-Pin-Hilfe, integriertem Baseline-Drift-Check und Live-Log-Konsole.
2. **Direktes Laden einer `.ini`-Datei:** Schneller Start bestehender Messprofile über Pfadeingabe für automatisierte Serienmessungen.
3. **Interaktiver Konsolen-Assistent (CLI):** Schrittweise Abfrage aller Parameter direkt im Terminal für Headless-Systeme (z. B. Raspberry Pi oder Linux-Laborrechner über SSH) ohne grafische Oberfläche.

### Nicht-funktionale Anforderungen & Architektur
- **Klare Schichtenarchitektur (`src/isx3_api/`):**
  - `commands.py`: Hardware-Treiber, Binärprotokoll & Selbsttest.
  - `config_handler.py`: INI-Parser, Dataclasses, Einheiten-Konverter & Queue-Generator.
  - `measurement.py`: Mess-Orchestrator, MUX-Parsing & HDF5-Datenpersistenz.
  - `plot_templates.py`: Matplotlib-Visualisierungsvorlagen.
  - `config_gui.py`: Grafische Tkinter-Oberfläche.
- **Minimale Abhängigkeiten:** Beschränkt auf `pyserial`, `numpy`, `matplotlib` und `h5py` (sowie Standardbibliotheken `tkinter`, `struct`, `configparser`, `unittest`).
- **Testbarkeit:** Vollständige Abdeckung der Kernlogik durch `tests/test_isx3_api.py` (13 Unit-Tests mit Hardware-Mocking).
