# Einstellungen für alle Rechner

## Lautstärke
* Auf das Lautstärkesymbol rechtsklick, Wiedergabegeräte, Reiter Kommunikation
-> Nichts unternehmen

## Taskleisteneinstellungen
* Nach Taskleisteneinstellungen suchen -> Unter der Überschrift Infobereich -> Symbole für die Anzeige auf der Taskleiste auswählen -> Immer alle Symbole im Benachrichtigungsfeld anzeigen -> Einschalten

## Energieoptionen
* Systemsteuerung\Hardware und Sound\Energieoptionen -> Auswählen, was beim Drücken von Netzschaltern geschenen soll -> Einstellungen des Administrators freigeben.
* Beim Drücken des Netzschalters -> Herunterfahren
* Beim Drücken der Energiespartaste -> Nichts unternehmen
* Beim Zuklappen -> Nichts unternehmen (für Laptops)

Zeitpunkt für das Ausschalten des Bildschirms auswählen
* Bildschirm ausschalten: Niemals
* Energiesparmodus nach: Niemals

## Windows Store
* Oben rechts auf das Personen-Icon -> Download und Updates -> Nach Updates suchen -> Alle aktualisieren
Scanner runter laden (startet implizit alle Updates aus dem Store)
* Windows-Scanner laden

## Windows Update Einstellungen
* Erweiterte Optionen -> Update für andere Microsoft Produkte bereitstellen, wenn ein Windows-Update ausgeführt wird [ja]

## autotuninglevel deaktivieren
* WindowsHelper\DisableAutotuninglevel.bat als Admin ausführen

## fast startup and hybernate (Hybrider Ruhezustand und Ruhezustand) deaktivieren
* WindowsHelper\TurnOffFastStartup.bat als Admin ausführen

## Systemwiederherstellung
* Systemsteuerung\System und Sicherheit\System
* Erweiterte Systemeinstellungen, Tab Computerschutz, für C: (System) aktivieren
* Konfigurieren: 10% und löschen

## Startmenü Einträge
* [Dieser PC] und [Systemsteuerung] ins Startmenü

## Gastbenutzer hinzufügen

## SysinternalsSuite
* Windows Programme Microsoft\SysinternalsSuite (Updated February 13, 2018) entpackt nach C:\SysinternalsSuite kopieren (und ggf. Verknüpfung nach Desktop)

## Windows Programme
### MD5 and CRC
* Windows Programme\MD5 and CRC nach C:\Windows\System32 kopieren
### 7zip
### Adobe
* Sumatra-PDF
* Flash plugin
* Adobe Reader
* __kein__ Schokwave oder Air
* Zum Schluss Reader starten und nach Updates suchen

### FileZilla
### Greenshot

### Java
#### Endanwender
* JRE x64
#### Entwickler
* JDK x64
* Windows Programme\Maven\apache-maven-3.3.9-bin.zip nach C:\apache-maven-3.3.9 kopieren
** Umgebungsvariablen setzen -> neu:
*** JAVA_HOME: C:\Program Files\Java\jdk-9.0.4
*** PATH -> Neu -> C:\apache-maven-3.5.3\bin

### Groovy

### KeePass

### LibreOffice
* Word auswählen
* Aus dem Startmenü Writer und Calc Verknüpfung auf den Desktop

### Mozilla
* Firefox
* Im Firefox unter Einstellungen -> Erweitert -> Datenübermittlung -> Telemetrie
* Nach Standardprogramme suchen und Firefox festlegen

### Notepad++

### Paint.NET
* Benutzerdefiniert und Dateierweiterungen raus nehmen

### Python
* Achtung, add to path aktivieren

### VeraCrypt
### VLC
### WinRAR
