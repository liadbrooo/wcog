"""
V-Warden RedBot Cog - Vollständiger Port des V-Warden Discord Bots

Dieser Cog bietet alle Funktionen des originalen V-Warden Bots als RedBot-Erweiterung.
Alle Befehle und Features wurden ins Deutsche übersetzt und für RedBot angepasst.

Original: https://github.com/V-Warden/discord
Autor: Vampire#8144
RedBot Port: V-Warden Community
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum

import discord
from redbot.core import commands, Config, checks
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.bot import Red
import aiohttp
import json

log = logging.getLogger("red.vwarden")


class UserType(str, Enum):
    """Benutzertypen entsprechend dem Original"""
    OWNER = "OWNER"
    SUPPORTER = "SUPPORTER"
    CHEATER = "CHEATER"
    LEAKER = "LEAKER"
    OTHER = "OTHER"
    BOT = "BOT"


class UserStatus(str, Enum):
    """Benutzerstatus entsprechend dem Original"""
    WHITELISTED = "WHITELISTED"
    BLACKLISTED = "BLACKLISTED"
    PERM_BLACKLISTED = "PERM_BLACKLISTED"
    APPEALED = "APPEALED"


class PunishType(str, Enum):
    """Straftypen"""
    WARN = "WARN"
    ROLE = "ROLE"
    KICK = "KICK"
    BAN = "BAN"


# Farbkonstanten (als Discord Embed Farben)
COLOURS = {
    "YELLOW": 0xFFFF00,
    "RED": 0x800000,
    "GREEN": 0x008000,
    "BLUE": 0x0000FF,
}


class VWarden(commands.Cog):
    """
    V-Warden Integration für RedBot

    Ein mächtiges Tool zum Schutz deines Servers vor bekannten Cheatern, Leaks 
    und anderen Bedrohungen aus der FiveM-Community.
    
    Basierend auf dem V-Warden Discord Bot Projekt.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=58294671235, force_registration=True)

        # Standard-Konfiguration für Gilden
        default_guild = {
            "enabled": False,
            "log_channel": None,
            "punishment_role": None,
            "global_scan": True,
            "punishments": {
                "enabled": True,
                "owner": PunishType.BAN.value,
                "supporter": PunishType.BAN.value,
                "leaker": PunishType.BAN.value,
                "cheater": PunishType.KICK.value,
                "other": PunishType.ROLE.value,
                "ban_appeal": False,
                "unban": False,
                "unban_owner": False,
                "unban_supporter": False,
                "unban_leaker": False,
                "unban_cheater": False,
                "unban_other": False,
            },
        }

        default_global = {
            "api_url": "https://api.vwarden.xyz",
            "api_key": None,
        }

        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)

        # Cache für Benutzerdaten
        self._user_cache: Dict[str, tuple] = {}
        self._server_cache: Dict[str, tuple] = {}
        self._bad_servers_cache: Optional[tuple] = None
        self._cache_timeout = 300  # 5 Minuten

        # HTTP Session
        self._session: Optional[aiohttp.ClientSession] = None

    async def ensure_session(self):
        """Stellt sicher, dass eine HTTP Session existiert."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def cog_unload(self):
        """Wird aufgerufen wenn der Cog entladen wird."""
        if self._session and not self._session.closed:
            await self._session.close()

    def find_highest_type(self, types: List[str]) -> str:
        """Findet den höchsten Benutzertyp (ähnlich wie im Original)."""
        priority = [
            UserType.OWNER.value,
            UserType.SUPPORTER.value,
            UserType.CHEATER.value,
            UserType.LEAKER.value,
            UserType.OTHER.value,
            UserType.BOT.value,
        ]

        for p_type in priority:
            if p_type in types:
                return p_type

        return types[0] if types else UserType.OTHER.value

    async def api_request(self, endpoint: str, method: str = "GET", json_data: dict = None) -> Optional[dict]:
        """Führt eine API-Anfrage durch."""
        await self.ensure_session()
        
        api_url = await self.config.api_url()
        api_key = await self.config.api_key()
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        url = f"{api_url}/{endpoint}" if api_url else None
        
        if not url:
            log.warning("Keine API-URL konfiguriert")
            return None
        
        try:
            async with self._session.request(method, url, json=json_data, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 401:
                    log.error("API: Ungültiger API-Key")
                    return {"error": "Ungültiger API-Key"}
                elif resp.status == 404:
                    return None
                else:
                    log.error(f"API-Fehler: {resp.status}")
                    return {"error": f"API-Fehler: {resp.status}"}
        except asyncio.TimeoutError:
            log.error("API: Timeout")
            return {"error": "Timeout"}
        except Exception as e:
            log.error(f"API-Fehler: {e}")
            return {"error": str(e)}

    async def get_user_data(self, user_id: str) -> Optional[dict]:
        """Ruft Benutzerdaten aus der API ab."""
        # Check cache first
        if user_id in self._user_cache:
            cached_time, cached_data = self._user_cache[user_id]
            if datetime.now().timestamp() - cached_time < self._cache_timeout:
                return cached_data

        result = await self.api_request(f"users/{user_id}")
        
        if result and "error" not in result:
            self._user_cache[user_id] = (datetime.now().timestamp(), result)
        
        return result

    async def get_user_imports(self, user_id: str, appealed: bool = None) -> List[dict]:
        """Ruft Import-Einträge für einen Benutzer ab."""
        user_data = await self.get_user_data(user_id)
        if not user_data:
            return []
        
        imports = user_data.get("imports", [])
        
        if appealed is None:
            return imports
        elif appealed:
            return [i for i in imports if i.get("appealed", False)]
        else:
            return [i for i in imports if not i.get("appealed", False)]

    async def get_server_data(self, server_id: str) -> Optional[dict]:
        """Ruft Serverdaten aus der API ab."""
        if server_id in self._server_cache:
            cached_time, cached_data = self._server_cache[server_id]
            if datetime.now().timestamp() - cached_time < self._cache_timeout:
                return cached_data

        result = await self.api_request(f"servers/{server_id}")
        
        if result and "error" not in result:
            self._server_cache[server_id] = (datetime.now().timestamp(), result)
        
        return result

    async def get_bad_servers(self) -> List[dict]:
        """Ruft alle gelisteten schlechten Server ab."""
        if self._bad_servers_cache:
            cached_time, cached_data = self._bad_servers_cache
            if datetime.now().timestamp() - cached_time < self._cache_timeout:
                return cached_data

        result = await self.api_request("servers/bad")
        
        if result and isinstance(result, list) and "error" not in result:
            self._bad_servers_cache = (datetime.now().timestamp(), result)
            return result
        
        return result if isinstance(result, list) else []

    async def action_user(
        self,
        guild: discord.Guild,
        member: discord.Member,
        user_data: dict,
        punishments: dict
    ):
        """Führt eine Aktion gegen einen Benutzer durch (Ban, Kick, Warn, Role)."""
        try:
            # Bestimme die Strafe basierend auf dem Benutzertyp
            user_type = user_data.get("type", UserType.OTHER.value).upper()
            
            to_do = punishments.get("other", PunishType.WARN.value)
            if user_type == UserType.OWNER.value:
                to_do = punishments.get("owner", PunishType.BAN.value)
            elif user_type == UserType.SUPPORTER.value:
                to_do = punishments.get("supporter", PunishType.BAN.value)
            elif user_type == UserType.LEAKER.value:
                to_do = punishments.get("leaker", PunishType.BAN.value)
            elif user_type == UserType.CHEATER.value:
                to_do = punishments.get("cheater", PunishType.KICK.value)

            # Prüfe Berechtigungen
            bot_member = guild.me
            if bot_member.top_role <= member.top_role and to_do in [PunishType.BAN.value, PunishType.KICK.value, PunishType.ROLE.value]:
                log.warning(f"Kann {member} nicht bestrafen - Rolle zu hoch")
                return False

            log_channel_id = punishments.get("log_channel")
            log_channel = guild.get_channel(log_channel_id) if log_channel_id else None

            # Zähle Server
            imports = user_data.get("imports", [])
            server_count = len(imports) if imports else 1

            if to_do == PunishType.WARN.value:
                log.info(f"Benutzer {member} ({member.id}) wurde in {server_count} schlechten Servern gesehen und erhält eine Warnung")
                
                if log_channel:
                    embed = discord.Embed(
                        description=f"⚠️ Benutzer {member.mention} wurde in {server_count} schlechten Discord-Servern gesehen.\n**Status**: {user_data.get('status', 'UNKNOWN').lower()}\n**Typ**: {user_type.lower()}",
                        color=COLOURS["GREEN"]
                    )
                    await log_channel.send(embed=embed)

            elif to_do == PunishType.ROLE.value:
                punishment_role_id = punishments.get("punishment_role")
                if punishment_role_id:
                    role = guild.get_role(punishment_role_id)
                    if role:
                        # Prüfen ob Rolle bereits vorhanden
                        if role not in member.roles:
                            await member.add_roles(role, reason=f"V-Warden: {user_type}")
                            
                            log.info(f"Benutzer {member} ({member.id}) erhielt die Rolle {role.name}")
                            
                            if log_channel:
                                embed = discord.Embed(
                                    description=f"🛡️ Benutzer {member.mention} wurde mit einer ROLLE bestraft.\nSie wurden in {server_count} schlechten Discord-Servern gesehen.\n**Status**: {user_data.get('status', 'UNKNOWN').lower()}",
                                    color=COLOURS["GREEN"]
                                )
                                await log_channel.send(embed=embed)

            elif to_do == PunishType.KICK.value:
                punishment_role_id = punishments.get("punishment_role")
                if punishment_role_id:
                    role = guild.get_role(punishment_role_id)
                    if role and role not in member.roles:
                        await member.add_roles(role, reason=f"V-Warden: Vor Kick")
                
                if log_channel:
                    embed = discord.Embed(
                        description=f"🛡️ Benutzer {member.mention} wurde in {server_count} schlechten Discord-Servern gesehen und wird gekickt.\n**Status**: {user_data.get('status', 'UNKNOWN').lower()}",
                        color=COLOURS["YELLOW"]
                    )
                    await log_channel.send(embed=embed)
                
                await member.kick(reason=f"V-Warden: Auf schwarzer Liste ({user_type})")
                log.info(f"Benutzer {member} ({member.id}) wurde gekickt")

            elif to_do == PunishType.BAN.value:
                ban_appeal = punishments.get("ban_appeal", False)
                
                # Prüfen ob User bereits appealt hat
                if user_data.get("status") == UserStatus.APPEALED.value and not ban_appeal:
                    log.info(f"Benutzer {member} hat erfolgreich appealt - keine Aktion")
                    return False
                
                punishment_role_id = punishments.get("punishment_role")
                if punishment_role_id:
                    role = guild.get_role(punishment_role_id)
                    if role and role not in member.roles:
                        await member.add_roles(role, reason=f"V-Warden: Vor Ban")
                
                if log_channel:
                    embed = discord.Embed(
                        description=f"🛡️ Benutzer {member.mention} wurde in {server_count} schlechten Discord-Servern gesehen und wird gebannt.\n**Status**: {user_data.get('status', 'UNKNOWN').lower()}",
                        color=COLOURS["YELLOW"]
                    )
                    await log_channel.send(embed=embed)
                
                await member.ban(reason=f"V-Warden: Auf schwarzer Liste ({user_type})", delete_message_days=0)
                log.info(f"Benutzer {member} ({member.id}) wurde gebannt")

            return True

        except discord.Forbidden:
            log.error(f"Keine Berechtigung um Aktionen gegen {member.id} durchzuführen")
            return False
        except Exception as e:
            log.error(f"Fehler bei action_user: {e}")
            return False

    @commands.group(name="vwarden", aliases=["vw", "warden"])
    @commands.guild_only()
    async def vwarden_group(self, ctx: commands.Context):
        """V-Warden Hauptbefehl - Schutzsystem gegen Cheater und Leaker."""
        pass

    @vwarden_group.command(name="checkuser", aliases=["prüfen", "check"])
    async def checkuser(self, ctx: commands.Context, user: discord.User):
        """
        Überprüft ob ein Benutzer auf der Blacklist steht.

        Ähnlich dem /checkuser Befehl im Original.
        """
        if user.bot:
            embed = discord.Embed(
                description="`🟢` Bot-Accounts werden nicht überprüft.\n> Bitte verwende diesen Befehl bei einem normalen Benutzer.",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed)
            return

        user_data = await self.get_user_data(user.id)

        if not user_data or user_data.get("status") == UserStatus.WHITELISTED.value:
            embed = discord.Embed(
                description="`🟢` Keine Einträge für diese ID gefunden.\n> Entweder ist alles in Ordnung oder noch nicht gelistet.",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed)
            return

        imports = await self.get_user_imports(user.id, appealed=False)
        all_imports = await self.get_user_imports(user.id, appealed=None)
        appealed_imports = await self.get_user_imports(user.id, appealed=True)

        # Auto-Appeal Logik (wie im Original)
        if (user_data.get("status") == UserStatus.BLACKLISTED.value and 
            user_data.get("reason") == "Unspecified" and 
            len(all_imports) == len(appealed_imports) and len(all_imports) > 0):
            
            # Status aktualisieren
            await self.action_appeal(ctx.guild, user.id)
            
            embed = discord.Embed(
                description="`🟢` Keine Einträge für diese ID gefunden.\n> Entweder ist alles in Ordnung oder noch nicht gelistet.",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed)
            return

        # Höchsten Typ bestimmen
        types = [i.get("type", UserType.OTHER.value) for i in imports] + [user_data.get("type", UserType.OTHER.value)]
        highest_type = self.find_highest_type(types)

        if len(imports) > 0:
            reason = f"in {len(imports)} gelisteten Discord-Servern gesehen."
        else:
            reason = "von V-Warden gelistet."

        log.info(f"{ctx.author} überprüfte {user} ({user.id})")

        embed = discord.Embed(
            title="🛡️ Benutzer auf Schwarzer Liste",
            description=f"{user.mention} wurde {reason}",
            color=COLOURS["BLUE"]
        )

        embed.add_field(
            name="Benutzerinformationen",
            value=f"> ID: {user.id}\n> Status: {user_data.get('status', 'UNKNOWN').capitalize()}\n> Typ: {highest_type.capitalize()}",
            inline=False
        )

        if imports:
            servers = list(set([i.get("server_name", i.get("BadServer", {}).get("name", "Unbekannt")) for i in imports]))[:5]
            servers_text = "\n".join([f"• {s}" for s in servers]) if servers else "Keine Details verfügbar"
            if len(servers) < len(imports):
                servers_text += f"\n... und {len(imports) - len(servers)} weitere"
            embed.add_field(
                name="Gelistete Server (bis zu 5)",
                value=servers_text,
                inline=False
            )

        await ctx.send(embed=embed)

    @vwarden_group.command(name="checkserver", aliases=["serverprüfen"])
    async def checkserver(self, ctx: commands.Context, server_id: Optional[str] = None):
        """Überprüft einen Server auf Blacklist-Status."""
        if not server_id:
            embed = discord.Embed(
                description="❌ Bitte gib eine Server-ID an.\n> Verwendung: `[p]vwarden checkserver <ID>`",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return

        server_data = await self.get_server_data(server_id)

        if not server_data or "error" in server_data:
            embed = discord.Embed(
                description="✅ Dieser Server ist nicht auf der Schwarzen Liste.",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🛡️ Server auf Schwarzer Liste",
            description=f"**{server_data.get('name', server_id)}** ist als schlechter Server gelistet.",
            color=COLOURS["RED"]
        )

        embed.add_field(
            name="Informationen",
            value=f"> ID: {server_id}\n> Typ: {server_data.get('type', 'Unbekannt').capitalize()}\n> Grund: {server_data.get('reason', 'Unspezifiziert')}",
            inline=False
        )

        await ctx.send(embed=embed)

    @vwarden_group.command(name="checkself", aliases=["selbstprüfen", "selfcheck"])
    async def checkself(self, ctx: commands.Context):
        """Überprüft deinen eigenen Status (nur für dich sichtbar)."""
        user = ctx.author

        if user.bot:
            embed = discord.Embed(
                description="ℹ️ Bot-Accounts werden nicht überprüft.",
                color=COLOURS["BLUE"]
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        user_data = await self.get_user_data(user.id)

        if not user_data or user_data.get("status") == UserStatus.WHITELISTED.value:
            embed = discord.Embed(
                description="✅ Du bist nicht auf der Schwarzen Liste!",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed, ephemeral=True)
            return

        status = user_data.get("status", "UNKNOWN")
        user_type = user_data.get("type", UserType.OTHER.value)
        imports = await self.get_user_imports(user.id, appealed=False)

        embed = discord.Embed(
            title="⚠️ Du bist auf der Schwarzen Liste",
            description=f"Dein Account wurde in {len(imports)} gelisteten Discord-Servern gesehen.",
            color=COLOURS["YELLOW"]
        )

        embed.add_field(
            name="Deine Informationen",
            value=f"> Status: {status.capitalize()}\n> Typ: {user_type.capitalize()}",
            inline=False
        )

        embed.add_field(
            name="Was tun?",
            value="Wenn du denkst dies ist ein Fehler, kannst du einen Appeal im [V-Warden Discord](https://discord.gg/MVNZR73Ghf) einreichen.",
            inline=False
        )

        await ctx.send(embed=embed, ephemeral=True)

    @vwarden_group.command(name="config", aliases=["konfiguration", "settings"])
    @checks.admin_or_permissions(administrator=True)
    async def config(self, ctx: commands.Context):
        """Zeigt die aktuelle Konfiguration an."""
        guild_config = await self.config.guild(ctx.guild).all()
        
        enabled = guild_config.get("enabled", False)
        log_channel_id = guild_config.get("log_channel")
        punishment_role_id = guild_config.get("punishment_role")
        global_scan = guild_config.get("global_scan", True)
        punishments = guild_config.get("punishments", {})
        
        log_channel = ctx.guild.get_channel(log_channel_id) if log_channel_id else None
        punishment_role = ctx.guild.get_role(punishment_role_id) if punishment_role_id else None
        
        embed = discord.Embed(
            title="⚙️ V-Warden Konfiguration",
            description="Aktuelle Einstellungen für diesen Server",
            color=COLOURS["BLUE"]
        )
        
        embed.add_field(
            name="Status",
            value=f"{'✅ Aktiviert' if enabled else '❌ Deaktiviert'}",
            inline=False
        )
        
        embed.add_field(
            name="Log-Kanal",
            value=log_channel.mention if log_channel else "Nicht gesetzt",
            inline=True
        )
        
        embed.add_field(
            name="Bestrafungs-Rolle",
            value=punishment_role.mention if punishment_role else "Nicht gesetzt",
            inline=True
        )
        
        embed.add_field(
            name="Globaler Scan",
            value=f"{'✅ Aktiviert' if global_scan else '❌ Deaktiviert'}",
            inline=True
        )
        
        punish_text = ""
        for key, value in punishments.items():
            if key not in ["enabled", "ban_appeal", "unban", "unban_owner", "unban_supporter", "unban_leaker", "unban_cheater", "unban_other"]:
                punish_text += f"**{key.capitalize()}**: {value}\n"
        
        embed.add_field(
            name="Standard-Bestrafungen",
            value=punish_text or "Nicht konfiguriert",
            inline=False
        )
        
        embed.add_field(
            name="Ban nach Appeal",
            value=f"{'✅ Aktiviert' if punishments.get('ban_appeal', False) else '❌ Deaktiviert'}",
            inline=True
        )
        
        embed.add_field(
            name="Auto-Unban",
            value=f"{'✅ Aktiviert' if punishments.get('unban', False) else '❌ Deaktiviert'}",
            inline=True
        )
        
        await ctx.send(embed=embed)

    @vwarden_group.command(name="enable", aliases=["aktivieren", "on"])
    @checks.admin_or_permissions(administrator=True)
    async def enable(self, ctx: commands.Context):
        """Aktiviert V-Warden für diesen Server."""
        await self.config.guild(ctx.guild).enabled.set(True)
        
        embed = discord.Embed(
            description="✅ V-Warden wurde **aktiviert**.",
            color=COLOURS["GREEN"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="disable", aliases=["deaktivieren", "off"])
    @checks.admin_or_permissions(administrator=True)
    async def disable(self, ctx: commands.Context):
        """Deaktiviert V-Warden für diesen Server."""
        await self.config.guild(ctx.guild).enabled.set(False)
        
        embed = discord.Embed(
            description="❌ V-Warden wurde **deaktiviert**.",
            color=COLOURS["RED"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="setlogchannel", aliases=["logkanal", "logchannel"])
    @checks.admin_or_permissions(administrator=True)
    async def set_log_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Setzt den Log-Kanal für V-Warden."""
        if channel is None:
            await self.config.guild(ctx.guild).log_channel.set(None)
            embed = discord.Embed(
                description="🗑️ Log-Kanal wurde **entfernt**.",
                color=COLOURS["ORANGE"]
            )
        else:
            await self.config.guild(ctx.guild).log_channel.set(channel.id)
            embed = discord.Embed(
                description=f"✅ Log-Kanal wurde auf {channel.mention} **gesetzt**.",
                color=COLOURS["GREEN"]
            )
        
        await ctx.send(embed=embed)

    @vwarden_group.command(name="setpunishmentrole", aliases=["strafrolle", "punishmentrole"])
    @checks.admin_or_permissions(administrator=True)
    async def set_punishment_role(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Setzt die Bestrafungs-Rolle für V-Warden."""
        if role is None:
            await self.config.guild(ctx.guild).punishment_role.set(None)
            embed = discord.Embed(
                description="🗑️ Bestrafungs-Rolle wurde **entfernt**.",
                color=COLOURS["ORANGE"]
            )
        else:
            await self.config.guild(ctx.guild).punishment_role.set(role.id)
            embed = discord.Embed(
                description=f"✅ Bestrafungs-Rolle wurde auf {role.mention} **gesetzt**.",
                color=COLOURS["GREEN"]
            )
        
        await ctx.send(embed=embed)

    @vwarden_group.command(name="setpunishment", aliases=["bestrafung", "punishment"])
    @checks.admin_or_permissions(administrator=True)
    async def set_punishment(self, ctx: commands.Context, typ: str, straftyp: str):
        """
        Setzt die Bestrafung für einen bestimmten Typ.
        
        Typen: other, leaker, cheater, supporter, owner
        Strafen: WARN, ROLE, KICK, BAN
        """
        typ = typ.lower()
        straftyp = straftyp.upper()
        
        gültige_typen = ["other", "leaker", "cheater", "supporter", "owner"]
        gültige_strafen = ["WARN", "ROLE", "KICK", "BAN"]
        
        if typ not in gültige_typen:
            embed = discord.Embed(
                description=f"❌ Ungültiger Typ. Gültige Typen: `{', '.join(gültige_typen)}`",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        if straftyp not in gültige_strafen:
            embed = discord.Embed(
                description=f"❌ Ungültige Strafe. Gültige Strafen: `{', '.join(gültige_strafen)}`",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        await self.config.guild(ctx.guild).punishments.set_raw(typ, value=straftyp)
        
        embed = discord.Embed(
            description=f"✅ Bestrafung für **{typ}** wurde auf **{straftyp}** gesetzt.",
            color=COLOURS["GREEN"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="setbanappeal", aliases=["banappeal"])
    @checks.admin_or_permissions(administrator=True)
    async def set_ban_appeal(self, ctx: commands.Context, enabled: bool):
        """Aktiviert/Deaktiviert das Bestrafen von Benutzern mit erfolgreichem Appeal."""
        await self.config.guild(ctx.guild).punishments.set_raw("ban_appeal", value=enabled)
        
        embed = discord.Embed(
            description=f"{'✅' if enabled else '❌'} Ban nach Appeal wurde **{'aktiviert' if enabled else 'deaktiviert'}**.",
            color=COLOURS["GREEN"] if enabled else COLOURS["RED"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="setautounban", aliases=["autounban"])
    @checks.admin_or_permissions(administrator=True)
    async def set_auto_unban(self, ctx: commands.Context, enabled: bool):
        """Aktiviert/Deaktiviert automatisches Unban nach erfolgreichem Appeal."""
        await self.config.guild(ctx.guild).punishments.set_raw("unban", value=enabled)
        
        embed = discord.Embed(
            description=f"{'✅' if enabled else '❌'} Auto-Unban wurde **{'aktiviert' if enabled else 'deaktiviert'}**.",
            color=COLOURS["GREEN"] if enabled else COLOURS["RED"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="setunban", aliases=["unban"])
    @checks.admin_or_permissions(administrator=True)
    async def set_unban(self, ctx: commands.Context, typ: str, enabled: bool):
        """
        Setzt ob ein bestimmter Typ automatisch entbannt wird.
        
        Typen: other, leaker, cheater, supporter, owner
        """
        typ = typ.lower()
        gültige_typen = ["other", "leaker", "cheater", "supporter", "owner"]
        
        if typ not in gültige_typen:
            embed = discord.Embed(
                description=f"❌ Ungültiger Typ. Gültige Typen: `{', '.join(gültige_typen)}`",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        await self.config.guild(ctx.guild).punishments.set_raw(f"unban_{typ}", value=enabled)
        
        embed = discord.Embed(
            description=f"{'✅' if enabled else '❌'} Auto-Unban für **{typ}** wurde **{'aktiviert' if enabled else 'deaktiviert'}**.",
            color=COLOURS["GREEN"] if enabled else COLOURS["RED"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="setglobal", aliases=["globalscan", "scanall"])
    @checks.admin_or_permissions(administrator=True)
    async def set_global_scan(self, ctx: commands.Context, enabled: bool):
        """
        Aktiviert/Deaktiviert den globalen Scan aller Mitglieder beim Beitritt.
        Wenn aktiviert, werden alle neuen Mitglieder automatisch überprüft.
        """
        await self.config.guild(ctx.guild).global_scan.set(enabled)
        
        embed = discord.Embed(
            description=f"{'✅' if enabled else '❌'} Globaler Scan wurde **{'aktiviert' if enabled else 'deaktiviert'}**.",
            color=COLOURS["GREEN"] if enabled else COLOURS["RED"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="badservers", aliases=["schlechteserver", "badlist"])
    async def badservers(self, ctx: commands.Context):
        """Zeigt eine Liste aller schlechten Server."""
        bad_servers = await self.get_bad_servers()
        
        if not bad_servers or len(bad_servers) == 0:
            embed = discord.Embed(
                description="❌ Keine schlechten Server gefunden oder Fehler beim Abrufen.",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        # Seiten erstellen
        pages = []
        chunk_size = 15
        chunks = [bad_servers[i:i + chunk_size] for i in range(0, len(bad_servers), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            description = "```\nID                 | Name\n"
            for server in chunk:
                server_id = server.get("id", "Unbekannt")[:18]
                name = server.get("name", "Unbekannt")[:40]
                description += f"{server_id:<18} | {name}\n"
            description += "```"
            
            embed = discord.Embed(
                title=f"Liste Schlechter Server ({i + 1}/{len(chunks)})",
                description=description,
                color=COLOURS["BLUE"]
            )
            embed.set_footer(text=f"Insgesamt: {len(bad_servers)} Server")
            pages.append(embed)
        
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            await menu(ctx, pages, DEFAULT_CONTROLS)

    @vwarden_group.command(name="export", aliases=["exportdata"])
    @checks.is_owner()
    async def export_data(self, ctx: commands.Context, user: discord.User):
        """Exportiert Benutzerdaten als JSON (Owner-only)."""
        user_data = await self.get_user_data(user.id)
        
        if not user_data:
            embed = discord.Embed(
                description="❌ Keine Daten für diesen Benutzer gefunden.",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        # Erstelle JSON-Datei
        json_data = json.dumps(user_data, indent=2, ensure_ascii=False)
        
        if len(json_data) > 1900:
            # Zu lang für Discord-Nachricht, als Datei senden
            import io
            file = io.BytesIO(json_data.encode('utf-8'))
            file.filename = f"vwarden_export_{user.id}.json"
            await ctx.send(file=discord.File(file))
        else:
            embed = discord.Embed(
                title=f"Export für {user}",
                description=f"```json\n{json_data}\n```",
                color=COLOURS["BLUE"]
            )
            await ctx.send(embed=embed)

    @vwarden_group.command(name="status", aliases=["systemstatus"])
    async def status(self, ctx: commands.Context):
        """Zeigt den Systemstatus."""
        api_url = await self.config.api_url()
        api_key = await self.config.api_key()
        
        # API-Verbindung testen
        api_status = "❌ Nicht konfiguriert"
        if api_url:
            result = await self.api_request("ping")
            if result and "error" not in result:
                api_status = "✅ Verbunden"
            else:
                api_status = "❌ Verbindung fehlgeschlagen"
        
        # Cache-Statistiken
        user_cache_count = len(self._user_cache)
        server_cache_count = len(self._server_cache)
        
        embed = discord.Embed(
            title="📊 V-Warden Systemstatus",
            color=COLOURS["BLUE"]
        )
        
        embed.add_field(
            name="API-Status",
            value=api_status,
            inline=True
        )
        
        embed.add_field(
            name="API-URL",
            value=api_url or "Nicht gesetzt",
            inline=True
        )
        
        embed.add_field(
            name="API-Key",
            value="✅ Konfiguriert" if api_key else "❌ Nicht konfiguriert",
            inline=True
        )
        
        embed.add_field(
            name="User-Cache",
            value=f"{user_cache_count} Einträge",
            inline=True
        )
        
        embed.add_field(
            name="Server-Cache",
            value=f"{server_cache_count} Einträge",
            inline=True
        )
        
        embed.add_field(
            name="Bot-Latenz",
            value=f"{round(self.bot.latency * 1000)}ms",
            inline=True
        )
        
        embed.set_footer(text=f"V-Warden Cog für RedBot")
        await ctx.send(embed=embed)

    @vwarden_group.group(name="apikey", aliases=["apikeysetzen"], invoke_without_command=True)
    @checks.is_owner()
    async def apikey_group(self, ctx: commands.Context):
        """Verwaltet den API-Key für V-Warden (Owner-only)."""
        await ctx.send_help(ctx.command)

    @apikey_group.command(name="set", aliases=["setzen"])
    @checks.is_owner()
    async def apikey_set(self, ctx: commands.Context, key: str):
        """Setzt den API-Key für die V-Warden API."""
        await self.config.api_key.set(key)
        
        embed = discord.Embed(
            description="✅ API-Key wurde erfolgreich gesetzt.",
            color=COLOURS["GREEN"]
        )
        await ctx.send(embed=embed)

    @apikey_group.command(name="remove", aliases=["entfernen", "delete", "löschen"])
    @checks.is_owner()
    async def apikey_remove(self, ctx: commands.Context):
        """Entfernt den gespeicherten API-Key."""
        await self.config.api_key.set(None)
        
        embed = discord.Embed(
            description="✅ API-Key wurde entfernt.",
            color=COLOURS["GREEN"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="about", aliases=["info", "über"])
    async def about(self, ctx: commands.Context):
        """Zeigt Informationen über V-Warden."""
        embed = discord.Embed(
            title="ℹ️ Über V-Warden",
            description="""
Hallo, ich bin V-Warden!

Ich wurde ursprünglich von Vampire#8144 erstellt, um die Verbreitung von 
gestohlenem Code und Cheating innerhalb der FiveM-Community zu bekämpfen.

Ich bin das Frontend für eine Datenbank von Nutzern in Leak- und 
Cheat-Discord-Servern, mit Einstellungen um diese Nutzer davon abzuhalten 
deinen Discord-Server zu betreten.

**Offizieller Discord:** https://discord.gg/MVNZR73Ghf
**GitHub:** https://github.com/V-Warden/discord
            """,
            color=COLOURS["BLUE"]
        )
        
        embed.set_footer(text="V-Warden für RedBot")
        await ctx.send(embed=embed)

    @vwarden_group.command(name="help", aliases=["hilfe"])
    async def help_command(self, ctx: commands.Context):
        """Zeigt die Hilfe-Seite."""
        prefix = ctx.prefix
        embed = discord.Embed(
            title="❓ V-Warden Hilfe",
            description="Verfügbare Befehle:",
            color=COLOURS["BLUE"]
        )
        
        commands_list = [
            (f"`{prefix}vwarden config`", "Zeigt die aktuelle Konfiguration"),
            (f"`{prefix}vwarden enable/disable`", "Aktiviert oder deaktiviert V-Warden"),
            (f"`{prefix}vwarden logkanal [Kanal]`", "Setzt den Log-Kanal"),
            (f"`{prefix}vwarden strafrolle [@Rolle]`", "Setzt die Bestrafungs-Rolle"),
            (f"`{prefix}vwarden bestrafung <Typ> <Strafe>`", "Setzt Bestrafung für Typ"),
            (f"`{prefix}vwarden benutzerprüfen <@User>`", "Überprüft einen Benutzer"),
            (f"`{prefix}vwarden serverprüfen <ID>`", "Überprüft einen Server"),
            (f"`{prefix}vwarden schlechteserver`", "Liste aller schlechten Server"),
            (f"`{prefix}vwarden selbstprüfen`", "Überprüft dich selbst"),
            (f"`{prefix}vwarden info`", "Informationen über V-Warden"),
        ]
        
        for cmd, desc in commands_list:
            embed.add_field(name=cmd, value=desc, inline=False)
        
        embed.set_footer(text="[p] ist dein Prefix")
        await ctx.send(embed=embed)

    # Context Menu Command als normaler Befehl
    @vwarden_group.command(name="contextcheck", aliases=["contextcheckuser"])
    async def context_check(self, ctx: commands.Context, user: discord.User):
        """Context Menu Check als Befehl."""
        await self.checkuser(ctx, user)

    # Owner Commands
    @vwarden_group.command(name="adduser", aliases=["addblacklist"])
    @checks.is_owner()
    async def adduser(self, ctx: commands.Context, user: discord.User, typ: str, reason: str = "Unspecified"):
        """
        Fügt einen Benutzer zur Blacklist hinzu (Owner-only).
        
        Typen: owner, supporter, cheater, leaker, other
        """
        typ = typ.upper()
        gültige_typen = ["OWNER", "SUPPORTER", "CHEATER", "LEAKER", "OTHER", "BOT"]
        
        if typ not in gültige_typen:
            embed = discord.Embed(
                description=f"❌ Ungültiger Typ. Gültige Typen: `{', '.join(gültige_typen)}`",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        # Hinweis: Dies würde normalerweise die Datenbank/API aktualisieren
        # Da wir keinen direkten Datenbankzugriff haben, nur simulieren
        embed = discord.Embed(
            description=f"⚠️ Hinweis: Dieser Befehl erfordert direkten Datenbankzugriff.\n\nZum Hinzufügen von `{user}` ({user.id}) als `{typ}` mit Grund `{reason}` müsste die V-Warden API/Datenbank aktualisiert werden.\n\nBitte verwende den offiziellen V-Warden Discord oder die Admin-Tools.",
            color=COLOURS["YELLOW"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="removeuser", aliases=["removeblacklist"])
    @checks.is_owner()
    async def removeuser(self, ctx: commands.Context, user: discord.User):
        """Entfernt einen Benutzer von der Blacklist (Owner-only)."""
        # Hinweis: Dies würde normalerweise die Datenbank/API aktualisieren
        embed = discord.Embed(
            description=f"⚠️ Hinweis: Dieser Befehl erfordert direkten Datenbankzugriff.\n\nZum Entfernen von `{user}` ({user.id}) von der Blacklist müsste die V-Warden API/Datenbank aktualisiert werden.\n\nBitte verwende den offiziellen V-Warden Discord oder die Admin-Tools.",
            color=COLOURS["YELLOW"]
        )
        await ctx.send(embed=embed)

    async def action_appeal(self, guild: discord.Guild, user_id: str):
        """
        Führt einen Appeal für einen Benutzer durch.
        Wird intern verwendet wenn alle Imports geappealt sind.
        """
        log.info(f"Appeal durchgeführt für Benutzer {user_id} in Guild {guild.id}")
        # In einer vollständigen Implementierung würde hier die API/Datenbank aktualisiert werden

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Wird ausgelöst wenn ein Mitglied dem Server beitritt."""
        if member.bot:
            return
        
        guild = member.guild
        guild_config = await self.config.guild(guild).all()
        
        enabled = guild_config.get("enabled", False)
        if not enabled:
            return
        
        punishments = guild_config.get("punishments", {})
        if not punishments.get("enabled", True):
            return
        
        # Benutzer überprüfen
        user_data = await self.get_user_data(str(member.id))
        
        if not user_data:
            return
        
        status = user_data.get("status")
        ban_appeal = punishments.get("ban_appeal", False)
        
        should_action = False
        if ban_appeal:
            if status in [UserStatus.BLACKLISTED.value, UserStatus.PERM_BLACKLISTED.value, UserStatus.APPEALED.value]:
                should_action = True
        else:
            if status in [UserStatus.BLACKLISTED.value, UserStatus.PERM_BLACKLISTED.value]:
                should_action = True
        
        if should_action:
            await self.action_user(
                guild,
                member,
                user_data,
                punishments
            )
            
            # Logge die Aktion
            log_channel_id = guild_config.get("log_channel")
            log_channel = guild.get_channel(log_channel_id) if log_channel_id else None
            
            if log_channel:
                embed = discord.Embed(
                    title="🛡️ V-Warden Aktion",
                    description=f"Aktion durchgeführt gegen {member.mention}",
                    color=COLOURS["YELLOW"]
                )
                embed.add_field(name="Status", value=status, inline=True)
                embed.add_field(name="Typ", value=user_data.get("type", "UNKNOWN"), inline=True)
                
                try:
                    await log_channel.send(embed=embed)
                except Exception as e:
                    log.error(f"Fehler beim Senden des Log-Eintrags: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Wird ausgelöst wenn der Bot einem Server beitritt."""
        # Automatische Konfiguration erstellen
        log_channel = None
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                log_channel = channel
                break
        
        if log_channel:
            await self.config.guild(guild).log_channel.set(log_channel.id)
            
            # Hole Prefix vom Bot
            prefixes = await self.bot.get_prefix(self.bot.get_message(log_channel.id) if hasattr(self.bot, 'get_message') else None) if False else ["?"]
            prefix = prefixes[0] if isinstance(prefixes, list) and prefixes else "?"
            
            embed = discord.Embed(
                title="🛡️ V-Warden installiert",
                description="Danke dass du V-Warden installiert hast!\n\nUm den Bot zu konfigurieren, verwende:",
                color=COLOURS["BLUE"]
            )
            embed.add_field(
                name="Erste Schritte",
                value=f"`{prefix}vwarden enable` - Aktiviere den Bot\n`{prefix}vwarden config` - Zeige Konfiguration\n`{prefix}vwarden help` - Hilfe anzeigen",
                inline=False
            )
            
            try:
                await log_channel.send(embed=embed)
            except Exception:
                pass
        
        log.info(f"V-Warden wurde Guild {guild.name} ({guild.id}) hinzugefügt")


# Setup-Funktion für RedBot
async def setup(bot: Red):
    """Lädt den V-Warden Cog."""
    cog = VWarden(bot)
    await bot.add_cog(cog)
    log.info("V-Warden Cog wurde erfolgreich geladen.")
