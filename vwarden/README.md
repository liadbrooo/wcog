# VVarden Bridge - RedBot Cog

Ein RedBot-Cog, der mit dem **VVarden-Bot** auf deinem Discord-Server interagiert, um gebannte Nutzer zu erkennen und automatisch zu bestrafen.

## ⚠️ Wichtig: Funktionsweise

Dieser Cog benötigt **KEINE API-Keys** und **KEINE eigene Datenbank**! Stattdessen:

1. Der VVarden-Bot muss sich **auf demselben Discord-Server** befinden
2. Der Cog sendet den Check-Befehl (z.B. `!check username`) an VVarden
3. Die Antwort von VVarden wird ausgewertet
4. Bei einem Treffer wird der Nutzer automatisch bestraft (Ban/Kick/Warn)

## 📋 Installation

### 1. Repo hinzufügen
```
[p]repo add vwarden https://github.com/DEIN_USERNAME/vwarden.git main
```

### 2. Cog installieren
```
[p]cog install vwarden vwarden
```

### 3. Cog laden
```
[p]load vwarden
```

## ⚙️ Einrichtung

### Schritt 1: VVarden-Bot ID setzen
Aktiviere in Discord den Entwicklermodus (Einstellungen → Erweitert → Entwicklermodus).
Rechtsklick auf den VVarden-Bot → "ID kopieren".

```
[p]vwarden setvvid 123456789012345678
```

### Schritt 2: Log-Kanal festlegen
Erstelle einen Kanal, in dem sowohl dein Bot als auch VVarden schreiben können.

```
[p]vwarden logchannel #kanal-name
```

### Schritt 3: Schutz aktivieren
```
[p]vwarden einrichten
```

### Schritt 4: Bestrafung einstellen (optional)
Standard ist Kick. Optionen: `ban`, `kick`, `warn`

```
[p]vwarden bestrafung ban
```

## 📖 Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `[p]vwarden einrichten` | Aktiviert den Schutz für diesen Server |
| `[p]vwarden deaktivieren` | Deaktiviert den Schutz |
| `[p]vwarden setvvid <ID>` | Setzt die VVarden-Bot-ID |
| `[p]vwarden logchannel <#kanal>` | Setzt den Kanal für Checks |
| `[p]vwarden bestrafung <art>` | Setzt Strafe: ban, kick, warn |
| `[p]vwarden status` | Zeigt aktuelle Konfiguration |
| `[p]vwarden check <@user>` | Manuelles Prüfen eines Users |
| `[p]vwarden setcmd <befehl>` | Ändert Check-Befehl (Standard: !check) |

## 🔍 Automatische Funktionen

- **Join-Schutz**: Jeder neue User wird automatisch bei VVarden geprüft
- **Automatische Bestrafung**: Bei Treffer sofort Ban/Kick/Warn
- **Logging**: Alle Aktionen werden im Log-Kanal dokumentiert

## ❗ Voraussetzungen

1. **VVarden-Bot** muss auf dem Server sein
2. Dein Bot braucht **Nachrichten senden & lesen**-Rechte im Log-Kanal
3. VVarden muss im Log-Kanal antworten dürfen
4. Dein Bot braucht **Ban/Kick**-Rechte für Bestrafungen

## 🔧 Fehlerbehebung

**"VVarden hat nicht geantwortet"**
- Ist der VVarden-Bot online?
- Hat er Schreibrechte im Log-Kanal?
- Nutzt VVarden einen anderen Check-Befehl? → `[p]vwarden setcmd`

**"Konnte nicht bestrafen"**
- Hat dein Bot Ban/Kick-Rechte?
- Ist die eigene Rolle höher als die des Users?

**"Timeout"**
- VVarden ist vielleicht überlastet
- Netzwerkprobleme prüfen

## 📄 Lizenz

Dieser Cog steht unter der gleichen Lizenz wie der originale VVarden-Bot.

---

**Hinweis**: Dieser Cog ist eine Bridge-Lösung und hängt von der Verfügbarkeit des VVarden-Bots ab. Für eine eigenständige Lösung müsste eine lokale Datenbank verwendet werden.
