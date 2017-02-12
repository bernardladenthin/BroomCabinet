# Einstellungen für alle Rechner
## Laufwerke defragmentieren und optimieren
Bei Festplatten: Automatische Defragmentierung (Optimierung) ausstellen

## Lautstärke
Auf das Lautstärkesymbol rechtsklick, Wiedergabegeräte, Reiter Kommunikation
-> Nichts unternehmen

## Taskleisteneinstellungen
Nach Taskleisteneinstellungen suchen -> Unter der Überschrift Infobereich -> Symbole für die Anzeige auf der Taskleiste auswählen -> Immer alle Symbole im Benachrichtigungsfeld anzeigen -> Einschalten

## Energieoptionen
Systemsteuerung\Hardware und Sound\Energieoptionen -> Auswählen, was beim Drücken von Netzschaltern geschenen soll -> Einstellungen des Administrators freigeben.
-> Beim Drücken des Netzschalters -> Herunterfahren
-> Beim Drücken der Energiespartaste -> Nichts unternehmen
-> Beim Zuklappen -> Nichts unternehmen (für Laptops)
-> Schnellstart deaktivieren (sehr wichtig).
-> Ruhezustand deaktivieren (sehr wichtig).

Zeitpunkt für das Ausschalten des Bildschirms auswählen
-> Bildschirm ausschalten: Niemals
-> Energiesparmodus nach: Niemals

## Windows Store
-> Oben rechts auf das Personen-Icon -> Download und Updates -> Nach Updates suchen -> Alle aktualisieren
Scanner runter laden (startet implizit alle Updates aus dem Store)
-> Windows-Scanner laden

## Windows Update Einstellungen
Erweiterte Optionen -> Update für andere Microsoft Produkte bereitstellen [ja], Featureupdates Zurückstellen [ja]

## autotuninglevel deaktivieren
Windows Hilfreiches \ DisableAutotuninglevel.bat als Admin ausführen

## fast startup deaktivieren
Windows Hilfreiches \ TurnOffFastStartup.bat als Admin ausführen

## Systemwiederherstellung bereinigen
* Systemsteuerung\System und Sicherheit\System
* Erweiterte Systemeinstellungen, Tab Computerschutz, für C: (System) aktivieren
* Konfigurieren: 10% und löschen

## Startmenü Einträge
[Dieser PC] und [Systemsteuerung] ins Startmenü

## SysinternalsSuite
Windows Programme Microsoft\SysinternalsSuite (Updated November 18, 2016) entpackt nach C:\SysinternalsSuite kopieren (und ggf. Verknüpfung nach Desktop)

## MD5 and CRC
Windows Programme\MD5 and CRC nach C:\Windows\System32 kopieren

## Sync
Windows Programme Microsoft\Sync 2.0 nach C:\Windows\System32 kopieren
Eigenschaften -> Kompatibilität -> Programm als Administrator ausführen
(ggf. Verknüpfung nach Desktop)

## Windows Programme
### 7zip
### Adobe
* Sumatra-PDF
* Flash plugin
* Adobe Reader
* __kein__ Schokwave oder Air
Zum Schluss Reader starten und nach Updates suchen

### Greenshot

### Java
#### Endanwender
* JRE x64
#### Entwickler
* JDK x64
* Windows Programme\Maven\apache-maven-3.3.9-bin.zip nach C:\apache-maven-3.3.9 kopieren
Umgebungsvariablen setzen:
-> neu:
JAVA_HOME: C:\Program Files\Java\jdk1.8.0_121
PATH -> Neu -> C:\apache-maven-3.3.9\bin

### LibreOffice
* Word auswählen
* Aus dem Startmenü Writer und Calc Verknüpfung auf den Desktop

### Mozilla
* Firefox
** about:config und dann browser.sessionstore.interval auf 90000
* wmpfirefoxplugin
* Im Firefox unter Einstellungen -> Erweitert -> Datenübermittlung -> Telemetrie
* Nach Standardprogramme suchen und Firefox festlegen

### MozBackup

### Notepad++

### Paint.NET
* Benutzerdefiniert und Dateierweiterungen raus nehmen

### Python
Achtung, add to path aktivieren

### Skype
* More options, beide Bing Buttons / MSN entfernen

### VLC
