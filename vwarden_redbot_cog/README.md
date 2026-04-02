# V-Warden RedBot Cog

Ein Port des [V-Warden Discord Bots](https://github.com/V-Warden/discord) als RedBot Cog.

## Installation

1. Lade diesen Cog in deinen RedBot:
```
[pre]repo add vwarden <URL_zu_diesem_Repo>
[pre]install vwarden
```

2. Konfiguriere den Cog für deinen Server:
```
[p]vwarden config settings <#log-channel>
[p]vwarden config punishments owner ban
```

## Befehle

### Hauptbefehle

- `[p]vwarden checkuser <user>` - Überprüft ob ein Benutzer auf der Blacklist steht
- `[p]vwarden checkserver [server_id]` - Überprüft einen Server auf Blacklist-Status
- `[p]vwarden checkself` - Überprüft deinen eigenen Status (ephemeral)
- `[p]vwarden config` - Zeigt die Konfiguration an
- `[p]vwarden status` - Zeigt den Systemstatus
- `[p]vwarden about` - Informationen über V-Warden

### Konfiguration (Admin-only)

- `[p]vwarden config settings <#channel>` - Setzt den Log-Kanal
- `[p]vwarden config punishments <type> <action>` - Konfiguriert Strafen
  - Types: `owner`, `supporter`, `leaker`, `cheater`, `other`
  - Actions: `ban`, `kick`, `warn`, `role`

### Owner-Befehle

- `[p]vwarden adduser <user> <type> [reason]` - Fügt Benutzer zur Blacklist hinzu
- `[p]vwarden removeuser <user>` - Entfernt Benutzer von der Blacklist
- `[p]vwarden export <user>` - Exportiert Benutzerdaten als JSON

## Wichtige Hinweise

### Datenbank-Verbindung

Dieser Cog ist ein **Port der Bot-Logik** des originalen V-Warden Bots. Für die volle Funktionalität benötigst du:

1. **Zugang zur V-Warden Datenbank/API** - Der originale Bot verwendet Prisma mit PostgreSQL
2. **Oder eine eigene Implementierung** der Datenbank-Funktionen

Die folgenden Methoden im Cog müssen angepasst werden:
- `get_user_data()` - Ruft Benutzerdaten ab
- `get_user_imports()` - Ruft Import-Einträge ab
- `action_appeal()` - Führt Appeals durch

### Beispiel für API-Integration

```python
async def get_user_data(self, user_id: str) -> Optional[dict]:
    async with aiohttp.ClientSession() as session:
        api_url = await self.config.api_url()
        if api_url:
            async with session.get(f"{api_url}/users/{user_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._user_cache[user_id] = data
                    return data
    return None
```

## Features (vom Original übernommen)

- ✅ User Blacklist Checking
- ✅ Server Blacklist Checking  
- ✅ Automatic Moderation Actions (Ban/Kick/Warn/Role)
- ✅ Configurable Punishments per User Type
- ✅ Detailed Logging
- ✅ Appeal System Support
- ✅ Auto-Appeal Logic
- ✅ Member Join Monitoring
- ✅ Cache System

## Unterstützte Benutzertypen

- `OWNER` - Server Owner die TOS verletzt haben
- `SUPPORTER` - Supporter von Cheat/Discord Leak Communities
- `CHEATER` - Bekannte Cheater
- `LEAKER` - Personen die vertrauliche Informationen leaken
- `OTHER` - Andere Verstöße

## Benutzerstatus

- `WHITELISTED` - Benutzer ist whitelisted
- `BLACKLISTED` - Benutzer ist blacklisted
- `PERM_BLACKLISTED` - Permanent blacklisted
- `APPEALED` - Benutzer hat erfolgreich appealed

## Unterstützung

- Original Projekt: https://github.com/V-Warden/discord
- Support Discord: https://discord.gg/MVNZR73Ghf

## Lizenz

Basierend auf dem V-Warden Discord Bot Projekt. Bitte beachte die Lizenz des Originalprojekts.
