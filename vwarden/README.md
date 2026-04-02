# V-Warden RedBot Cog

Ein mächtiges Tool zum Schutz deines Discord-Servers vor bekannten Cheatern, Leaks und anderen Bedrohungen aus der FiveM-Community.

## Installation

1. Füge das Repository zu deinem RedBot hinzu:
   ```
   [p]repo add vwarden https://github.com/YOUR_USERNAME/vwarden main
   ```

2. Installiere den Cog:
   ```
   [p]cog install vwarden vwarden
   ```

3. Lade den Cog:
   ```
   [p]load vwarden
   ```

## WICHTIG: API-Key einrichten

Bevor du V-Warden verwenden kannst, musst du einen API-Key konfigurieren. Nur der Bot-Besitzer kann dies tun:

```
!vwarden apikey DEIN_API_KEY
```

Du erhältst deinen API-Key von V-Warden. Besuche https://discord.gg/MVNZR73Ghf für mehr Informationen.

## Einrichtung

1. Aktiviere den Bot für deinen Server:
   ```
   !vwarden enable
   ```

2. Konfiguriere den Log-Kanal:
   ```
   !vwarden logchannel #channel-name
   ```

3. Überprüfe die Konfiguration:
   ```
   !vwarden config
   ```

## Befehle

### Basis-Befehle
- `!vwarden enable` - Aktiviert V-Warden für diesen Server
- `!vwarden disable` - Deaktiviert V-Warden
- `!vwarden logchannel` - Setzt den Log-Kanal
- `!vwarden punishrole @Rolle` - Setzt die Strafrrolle
- `!vwarden config` - Zeigt die aktuelle Konfiguration

### Überprüfung
- `!vwarden check @user` - Überprüft einen Benutzer in der Datenbank
- `!vwarden scan` - Scannt alle Mitglieder des Servers (nur Admins)

### Bestrafungen konfigurieren
- `!vwarden setpunish <typ> <strafe>` - Setzt Strafe für Benutzertyp
  - Typen: owner, supporter, leaker, cheater, other
  - Strafen: ban, kick, role, warn, none
- `!vwarden togglepunishments` - Aktiviert/Deaktiviert automatische Bestrafungen

### Ignore-Listen
- `!vwarden ignore @Rolle` oder `!vwarden ignore #Kanal` - Ignoriert Rolle/Kanal
- `!vwarden unignore @Rolle` oder `!vwarden unignore #Kanal` - Entfernt von Ignore-Liste

### Admin-Befehle (nur Bot-Besitzer)
- `!vwarden apikey <KEY>` - Setzt den API-Key
- `!vwarden apikey` - Zeigt den aktuellen API-Key (maskiert)
- `!vwarden clearcache` - Leert den Benutzer-Cache

## Funktionsweise

- **Automatischer Schutz**: Wenn ein neuer Benutzer den Server betritt, wird er automatisch überprüft
- **Nachrichten-Überwachung**: Auch beim Senden von Nachrichten können Benutzer geprüft werden
- **Bestrafungen**: Automatische Bestrafung basierend auf dem Benutzertyp (Ban, Kick, Rolle, Warnung)
- **Logging**: Alle Vorfälle werden im konfigurierten Log-Kanal dokumentiert
- **Caching**: Ergebnisse werden gecacht um API-Aufrufe zu minimieren

## Unterstützung

Für Support und weitere Informationen besuche: https://discord.gg/MVNZR73Ghf

## Original Projekt

https://github.com/V-Warden/discord
