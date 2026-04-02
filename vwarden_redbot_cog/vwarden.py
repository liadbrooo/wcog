"""
V-Warden RedBot Cog
Ein Port des V-Warden Discord Bots als RedBot Cog.
Dieser Cog bietet Funktionen zum Überprüfen von Benutzern auf Blacklist-Status,
Server-Konfiguration und automatische Moderation.

Hinweis: Dieser Cog erfordert eine externe Datenbank und Konfiguration.
Die Original-Implementierung verwendet Prisma/PostgreSQL.
Für diesen Cog muss eine kompatible API oder Datenbank-Schnittstelle bereitgestellt werden.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Union

import discord
from redbot.core import commands, Config, checks
from redbot.core.utils import chat_formatting as cf
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.bot import Red

log = logging.getLogger("red.vwarden")

# Farbkonstanten (als Discord Embed Farben)
COLOURS = {
    "YELLOW": 0xFFFF00,
    "RED": 0x800000,
    "GREEN": 0x008000,
    "BLUE": 0x0000FF,
}


class UserType:
    """Benutzertypen entsprechend dem Original"""
    OWNER = "OWNER"
    SUPPORTER = "SUPPORTER"
    CHEATER = "CHEATER"
    LEAKER = "LEAKER"
    OTHER = "OTHER"
    BOT = "BOT"


class UserStatus:
    """Benutzerstatus entsprechend dem Original"""
    WHITELISTED = "WHITELISTED"
    BLACKLISTED = "BLACKLISTED"
    PERM_BLACKLISTED = "PERM_BLACKLISTED"
    APPEALED = "APPEALED"


class PunishType:
    """Straftypen"""
    WARN = "WARN"
    ROLE = "ROLE"
    KICK = "KICK"
    BAN = "BAN"


class VWarden(commands.Cog):
    """
    V-Warden Integration für RedBot
    
    Ein mächtiges Tool zum Schutz deines Servers vor bekannten Cheatern, Leaks und anderen Bedrohungen.
    Basierend auf dem V-Warden Discord Bot Projekt.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=58294671235, force_registration=True)
        
        # Standard-Konfiguration für Gilden
        default_guild = {
            "enabled": False,
            "log_channel": None,
            "punishments": {
                "enabled": True,
                "owner": PunishType.BAN,
                "supporter": PunishType.BAN,
                "leaker": PunishType.BAN,
                "cheater": PunishType.KICK,
                "other": PunishType.WARN,
                "ban_appeal": True,
                "unban_owner": False,
                "unban_supporter": False,
                "unban_leaker": False,
                "unban_cheater": False,
                "unban_other": False,
            },
        }
        
        default_global = {
            "api_url": None,  # URL zur V-Warden API (falls verfügbar)
            "database_url": None,  # Datenbank-Verbindungsstring
        }
        
        self.config.register_guild(**default_guild)
        self.config.register_global(**default_global)
        
        # Cache für Benutzerdaten (ähnlich wie LRU im Original)
        self._user_cache: Dict[str, dict] = {}
        self._cache_timeout = 3600  # 1 Stunde
        
        # Initialisiere den Hintergrundtask für Member-Checks
        self.member_check_task = bot.loop.create_task(self._member_check_loop())

    def cog_unload(self):
        """Wird aufgerufen wenn der Cog entladen wird"""
        self.member_check_task.cancel()

    async def _member_check_loop(self):
        """Hintergrundtask zum Überprüfen neuer Member"""
        while True:
            try:
                await asyncio.sleep(10)  # Alle 10 Sekunden prüfen
                # Diese Logik würde neue Member überprüfen
                # Implementierung hängt von der Datenbank/API ab
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Fehler im Member-Check-Loop: {e}")

    def find_highest_type(self, types: List[str]) -> str:
        """Findet den höchsten Benutzertyp (ähnlich wie im Original)"""
        priority = [
            UserType.OWNER,
            UserType.SUPPORTER,
            UserType.CHEATER,
            UserType.LEAKER,
            UserType.OTHER,
            UserType.BOT,
        ]
        
        for p_type in priority:
            if p_type in types:
                return p_type
        
        return types[0] if types else UserType.OTHER

    async def get_user_data(self, user_id: str) -> Optional[dict]:
        """
        Ruft Benutzerdaten aus der Datenbank/API ab.
        Dies ist ein Platzhalter - muss an deine Infrastruktur angepasst werden.
        """
        # Check cache first
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        
        # Hier würde der eigentliche Datenbank/API-Aufruf stehen
        # Beispielhafte Struktur (muss angepasst werden):
        """
        async with aiohttp.ClientSession() as session:
            api_url = await self.config.api_url()
            if api_url:
                async with session.get(f"{api_url}/users/{user_id}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._user_cache[user_id] = data
                        return data
        """
        
        return None

    async def get_user_imports(self, user_id: str, appealed: bool = False) -> List[dict]:
        """
        Ruft Import-Einträge für einen Benutzer ab.
        """
        # Platzhalter-Implementierung
        return []

    async def action_user(
        self,
        guild: discord.Guild,
        member: discord.Member,
        user_data: dict,
        punishments: dict
    ):
        """
        Führt eine Aktion gegen einen Benutzer durch (Ban, Kick, Warn, Role).
        """
        try:
            to_do = punishments.get("other", PunishType.WARN)
            
            # Bestimme die Strafe basierend auf dem Benutzertyp
            user_type = user_data.get("type", UserType.OTHER)
            if user_type == UserType.OWNER:
                to_do = punishments.get("owner", PunishType.BAN)
            elif user_type == UserType.SUPPORTER:
                to_do = punishments.get("supporter", PunishType.BAN)
            elif user_type == UserType.LEAKER:
                to_do = punishments.get("leaker", PunishType.BAN)
            elif user_type == UserType.CHEATER:
                to_do = punishments.get("cheater", PunishType.KICK)
            
            bot_member = guild.me
            if bot_member.top_role <= member.top_role:
                log.warning(f"Kann {member} nicht bestrafen - Rolle zu hoch")
                return
            
            if to_do == PunishType.BAN:
                await guild.ban(member, reason=f"V-Warden: {user_type}")
            elif to_do == PunishType.KICK:
                await guild.kick(member, reason=f"V-Warden: {user_type}")
            elif to_do == PunishType.WARN:
                # Warning kann als DM oder Notiz implementiert werden
                pass
            elif to_do == PunishType.ROLE:
                # Rolle entfernen/zuteilen - muss konfiguriert werden
                pass
                
            log.info(f"Aktion {to_do} gegen {member} in {guild} durchgeführt")
            
        except Exception as e:
            log.error(f"Fehler bei action_user: {e}")

    @commands.group(name="vwarden", aliases=["vw", "warden"])
    async def vwarden_group(self, ctx: commands.Context):
        """V-Warden Hauptbefehl"""
        pass

    @vwarden_group.command(name="checkuser")
    async def checkuser(self, ctx: commands.Context, user: discord.User):
        """
        Überprüft ob ein Benutzer auf der Blacklist steht.
        
        Ähnlich dem /checkuser Befehl im Original.
        """
        if user.bot:
            embed = discord.Embed(
                description="`🟢` No results are provided to bot accounts.\n> Please access this command as a standard user.",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed)
            return
        
        user_data = await self.get_user_data(user.id)
        
        if not user_data or user_data.get("status") == UserStatus.WHITELISTED:
            embed = discord.Embed(
                description="`🟢` No results found for this ID.\n> They are either fine or not yet listed.",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed)
            return
        
        imports = await self.get_user_imports(user.id, appealed=False)
        all_imports = await self.get_user_imports(user.id, appealed=None)
        appealed_imports = await self.get_user_imports(user.id, appealed=True)
        
        if len(imports) == 0 and user_data.get("status") == UserStatus.APPEALED:
            embed = discord.Embed(
                description="`🟢` No results found for this ID.\n> They are either fine or not yet listed.",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed)
            return
        
        # Auto-Appeal Logik (wie im Original)
        if (
            user_data.get("status") == UserStatus.BLACKLISTED
            and user_data.get("reason") == "Unspecified"
            and len(all_imports) == len(appealed_imports)
        ):
            # Status aktualisieren und Appeal durchführen
            await self.action_appeal(ctx.guild, user.id)
            embed = discord.Embed(
                description="`🟢` No results found for this ID.\n> They are either fine or not yet listed.",
                color=COLOURS["GREEN"]
            )
            await ctx.send(embed=embed)
            return
        
        # Typen sammeln
        types = [imp.get("type") for imp in imports]
        types.append(user_data.get("type", UserType.OTHER))
        highest = self.find_highest_type(types)
        
        if len(imports) > 0:
            reason = f"seen in {len(imports)} blacklisted Discords."
        else:
            reason = "blacklisted by Warden."
        
        status_display = user_data.get("status", "UNKNOWN").capitalize()
        type_display = highest.capitalize()
        
        embed = discord.Embed(
            title=":shield: User Blacklisted",
            description=f"<@{user.id}> has been {reason}",
            color=COLOURS["BLUE"]
        )
        embed.add_field(
            name="User Information",
            value=f"> ID: {user.id}\n> Status: {status_display}\n> Type: {type_display}",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @vwarden_group.command(name="checkserver")
    async def checkserver(self, ctx: commands.Context, server_id: Optional[str] = None):
        """
        Überprüft einen Server auf Blacklist-Status.
        """
        if not server_id:
            server_id = str(ctx.guild.id)
        
        # Platzhalter - muss an Datenbank/API angepasst werden
        embed = discord.Embed(
            title=":shield: Server Check",
            description=f"Checking server `{server_id}`...",
            color=COLOURS["BLUE"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="checkself")
    async def checkself(self, ctx: commands.Context):
        """
        Überprüft den eigenen Blacklist-Status.
        """
        user_data = await self.get_user_data(str(ctx.author.id))
        
        if not user_data or user_data.get("status") == UserStatus.WHITELISTED:
            embed = discord.Embed(
                description="`🟢` You are not on any blacklist. You're good to go!",
                color=COLOURS["GREEN"]
            )
        else:
            embed = discord.Embed(
                description="`🔴` You are currently blacklisted.",
                color=COLOURS["RED"]
            )
            embed.add_field(
                name="Status",
                value=user_data.get("status", "UNKNOWN"),
                inline=False
            )
            embed.add_field(
                name="Type",
                value=user_data.get("type", "UNKNOWN"),
                inline=False
            )
        
        await ctx.send(embed=embed, ephemeral=True)

    @vwarden_group.command(name="config")
    @commands.admin_or_permissions(administrator=True)
    async def config(self, ctx: commands.Context):
        """
        Konfiguriert V-Warden Einstellungen für diesen Server.
        """
        guild_config = await self.config.guild(ctx.guild).all()
        
        embed = discord.Embed(
            title="Warden Configuration",
            description="Welcome to the Warden Configuration. Please select a subcommand to view or configure settings.",
            color=COLOURS["BLUE"]
        )
        
        enabled_status = "✅ Enabled" if guild_config["enabled"] else "❌ Disabled"
        log_channel = guild_config["log_channel"]
        log_channel_mention = f"<#{log_channel}>" if log_channel else "Not set"
        
        embed.add_field(
            name="Current Settings",
            value=(
                f"> Status: {enabled_status}\n"
                f"> Log Channel: {log_channel_mention}\n"
                f"> Punishments: {'Enabled' if guild_config['punishments']['enabled'] else 'Disabled'}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Subcommands",
            value=(
                "`/vwarden config settings` - Configure the bot settings\n"
                "`/vwarden config punishments` - Configure the punishments\n"
                "`/vwarden config bans` - Configure the bans\n"
                "`/vwarden config unbans` - Configure the unbans"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @vwarden_group.group(name="config", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    async def config_subgroup(self, ctx: commands.Context):
        """Konfigurations-Untergruppe"""
        await ctx.invoke(self.config)

    @config_subgroup.command(name="settings")
    @commands.admin_or_permissions(administrator=True)
    async def config_settings(
        self,
        ctx: commands.Context,
        log_channel: Optional[discord.TextChannel] = None
    ):
        """
        Konfiguriert die Grundeinstellungen.
        """
        if log_channel:
            await self.config.guild(ctx.guild).log_channel.set(log_channel.id)
            embed = discord.Embed(
                description=f"`🟢` Log channel set to {log_channel.mention}",
                color=COLOURS["GREEN"]
            )
        else:
            current = await self.config.guild(ctx.guild).log_channel()
            if current:
                embed = discord.Embed(
                    description=f"`🟡` Current log channel: <#{current}>",
                    color=COLOURS["YELLOW"]
                )
            else:
                embed = discord.Embed(
                    description="`🔴` No log channel configured.",
                    color=COLOURS["RED"]
                )
        
        await ctx.send(embed=embed)

    @config_subgroup.command(name="punishments")
    @commands.admin_or_permissions(administrator=True)
    async def config_punishments(
        self,
        ctx: commands.Context,
        punishment_type: Optional[str] = None,
        action: Optional[str] = None
    ):
        """
        Konfiguriert die Strafen für verschiedene Benutzertypen.
        
        punishment_type: owner, supporter, leaker, cheater, other
        action: ban, kick, warn, role
        """
        if not punishment_type or not action:
            # Zeige aktuelle Konfiguration
            punishes = await self.config.guild(ctx.guild).punishments()
            
            embed = discord.Embed(
                title="Punishment Configuration",
                description="Current punishment settings:",
                color=COLOURS["BLUE"]
            )
            
            for p_type, p_action in punishes.items():
                if p_type in ["owner", "supporter", "leaker", "cheater", "other"]:
                    embed.add_field(
                        name=p_type.capitalize(),
                        value=p_action,
                        inline=True
                    )
            
            embed.add_field(
                name="Usage",
                value="`/vwarden config punishments <type> <action>`\nTypes: owner, supporter, leaker, cheater, other\nActions: ban, kick, warn, role",
                inline=False
            )
            
            await ctx.send(embed=embed)
            return
        
        # Aktualisiere Strafe
        valid_types = ["owner", "supporter", "leaker", "cheater", "other"]
        valid_actions = ["ban", "kick", "warn", "role"]
        
        if punishment_type.lower() not in valid_types:
            embed = discord.Embed(
                description=f"`🔴` Invalid type. Valid types: {', '.join(valid_types)}",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        if action.lower() not in valid_actions:
            embed = discord.Embed(
                description=f"`🔴` Invalid action. Valid actions: {', '.join(valid_actions)}",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        current_punishes = await self.config.guild(ctx.guild).punishments()
        current_punishes[punishment_type.lower()] = action.upper()
        await self.config.guild(ctx.guild).punishments.set(current_punishes)
        
        embed = discord.Embed(
            description=f"`🟢` Punishment for {punishment_type} set to {action.upper()}",
            color=COLOURS["GREEN"]
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="badservers")
    async def badservers(self, ctx: commands.Context):
        """
        Zeigt Informationen über bekannte schlechte Server.
        """
        # Platzhalter - müsste Datenbank abfragen
        embed = discord.Embed(
            title="Bad Servers Database",
            description="Information about blacklisted servers.",
            color=COLOURS["BLUE"]
        )
        embed.add_field(
            name="Note",
            value="This feature requires database connectivity.",
            inline=False
        )
        await ctx.send(embed=embed)

    @vwarden_group.command(name="export")
    @commands.is_owner()
    async def export_data(self, ctx: commands.Context, user: discord.User):
        """
        Exportiert alle Daten eines Benutzers (Owner-only).
        """
        user_data = await self.get_user_data(str(user.id))
        imports = await self.get_user_imports(str(user.id))
        
        if not user_data:
            embed = discord.Embed(
                description="`🔴` No data found for this user.",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        # Erstelle JSON-Export
        import json
        export_data = {
            "user": user_data,
            "imports": imports,
            "exported_at": datetime.utcnow().isoformat()
        }
        
        export_json = json.dumps(export_data, indent=2)
        
        # Als Datei senden wenn zu lang
        if len(export_json) > 1900:
            from io import BytesIO
            file = BytesIO(export_json.encode('utf-8'))
            file.name = f"vwarden_export_{user.id}.json"
            await ctx.send(
                content=f"Export for {user.mention}:",
                file=discord.File(file, filename=file.name)
            )
        else:
            await ctx.send(cf.box(export_json, lang="json"))

    @vwarden_group.command(name="status")
    async def status(self, ctx: commands.Context):
        """
        Zeigt den Status des V-Warden Systems.
        """
        embed = discord.Embed(
            title=":shield: V-Warden Status",
            color=COLOURS["BLUE"]
        )
        
        # Bot-Statistiken
        total_guilds = len(self.bot.guilds)
        enabled_guilds = 0
        
        for guild in self.bot.guilds:
            if await self.config.guild(guild).enabled():
                enabled_guilds += 1
        
        embed.add_field(
            name="Bot Statistics",
            value=(
                f"> Total Guilds: {total_guilds}\n"
                f"> Enabled Guilds: {enabled_guilds}"
            ),
            inline=True
        )
        
        # System-Status
        embed.add_field(
            name="System",
            value=(
                f"> Version: 1.0.0 (RedBot Port)\n"
                f"> Cache Size: {len(self._user_cache)}\n"
                f"> Status: Online"
            ),
            inline=True
        )
        
        embed.set_footer(text="Based on V-Warden Discord Bot")
        
        await ctx.send(embed=embed)

    @vwarden_group.command(name="about")
    async def about(self, ctx: commands.Context):
        """
        Informationen über V-Warden.
        """
        embed = discord.Embed(
            title=":shield: About V-Warden",
            description=(
                "V-Warden is a powerful tool designed to protect your Discord server "
                "from known cheaters, leakers, and other malicious actors.\n\n"
                "This is a port of the original V-Warden Discord Bot for use with RedBot."
            ),
            color=COLOURS["BLUE"]
        )
        
        embed.add_field(
            name="Features",
            value=(
                "• User blacklist checking\n"
                "• Server blacklist checking\n"
                "• Automatic moderation actions\n"
                "• Configurable punishments\n"
                "• Detailed logging\n"
                "• Appeal system support"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Links",
            value=(
                "[Original Project](https://github.com/V-Warden/discord)\n"
                "[Support Discord](https://discord.gg/MVNZR73Ghf)"
            ),
            inline=False
        )
        
        embed.set_footer(text="Protecting communities since 2023")
        
        await ctx.send(embed=embed)

    # Context Menu Commands (als normale Commands da RedBot keine nativen Context Menus hat)
    @vwarden_group.command(name="contextcheck")
    async def context_check(self, ctx: commands.Context, user: discord.User):
        """
        Kontextmenü-Äquivalent: Check User Status
        """
        await ctx.invoke(self.checkuser, user=user)

    @checks.is_owner()
    @vwarden_group.command(name="adduser")
    async def adduser(
        self,
        ctx: commands.Context,
        user: discord.User,
        user_type: str,
        *,
        reason: str = "Unspecified"
    ):
        """
        Fügt einen Benutzer zur Blacklist hinzu (Owner-only).
        
        user_type: owner, supporter, cheater, leaker, other
        """
        valid_types = ["owner", "supporter", "cheater", "leaker", "other"]
        
        if user_type.lower() not in valid_types:
            embed = discord.Embed(
                description=f"`🔴` Invalid type. Valid types: {', '.join(valid_types)}",
                color=COLOURS["RED"]
            )
            await ctx.send(embed=embed)
            return
        
        # Platzhalter - würde Datenbank aktualisieren
        embed = discord.Embed(
            description=f"`🟢` User {user.mention} would be added as {user_type.upper()}\nReason: {reason}",
            color=COLOURS["GREEN"]
        )
        embed.add_field(
            name="Note",
            value="This requires database connectivity to function.",
            inline=False
        )
        await ctx.send(embed=embed)

    @checks.is_owner()
    @vwarden_group.command(name="removeuser")
    async def removeuser(self, ctx: commands.Context, user: discord.User):
        """
        Entfernt einen Benutzer von der Blacklist (Owner-only).
        """
        # Platzhalter - würde Datenbank aktualisieren
        embed = discord.Embed(
            description=f"`🟢` User {user.mention} would be removed from the blacklist.",
            color=COLOURS["GREEN"]
        )
        embed.add_field(
            name="Note",
            value="This requires database connectivity to function.",
            inline=False
        )
        await ctx.send(embed=embed)

    async def action_appeal(self, guild: discord.Guild, user_id: str):
        """
        Führt einen Appeal für einen Benutzer durch.
        Entfernt Bans und Rollen entsprechend der Konfiguration.
        """
        try:
            # Versuche Ban zu entfernen
            try:
                ban = await guild.fetch_ban(discord.Object(id=user_id))
                await guild.unban(ban.user, reason="V-Warden: Auto-appeal")
                log.info(f"Unbanned {user_id} in {guild.id} via auto-appeal")
            except discord.NotFound:
                pass  # Nicht gebannt
            except Exception as e:
                log.error(f"Fehler beim Unban: {e}")
            
            # Weitere Appeal-Logik hier...
            
        except Exception as e:
            log.error(f"Fehler bei action_appeal: {e}")

    # Event-Handler für Member-Joins (muss anders registriert werden in RedBot)
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Überprüft neue Member beim Joinen.
        Entspricht dem guildMemberAdd Event im Original.
        """
        if member.bot:
            return
        
        guild = member.guild
        guild_config = await self.config.guild(guild).all()
        
        # Prüfe ob V-Warden für diese Gilde aktiviert ist
        if not guild_config.get("enabled", False):
            return
        
        # Prüfe ob Punishments aktiviert sind
        if not guild_config.get("punishments", {}).get("enabled", True):
            return
        
        # Hole Log-Channel
        log_channel_id = guild_config.get("log_channel")
        if not log_channel_id:
            return
        
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        # Überprüfe Benutzer in Datenbank
        user_data = await self.get_user_data(str(member.id))
        
        if not user_data:
            return
        
        status = user_data.get("status")
        ban_appeal = guild_config["punishments"].get("ban_appeal", True)
        
        should_action = False
        if ban_appeal:
            if status in [UserStatus.BLACKLISTED, UserStatus.PERM_BLACKLISTED, UserStatus.APPEALED]:
                should_action = True
        else:
            if status in [UserStatus.BLACKLISTED, UserStatus.PERM_BLACKLISTED]:
                should_action = True
        
        if should_action:
            await self.action_user(
                guild,
                member,
                user_data,
                guild_config["punishments"]
            )
            
            # Logge die Aktion
            embed = discord.Embed(
                title=":shield: V-Warden Action",
                description=f"Action taken against {member.mention}",
                color=COLOURS["YELLOW"]
            )
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Type", value=user_data.get("type", "UNKNOWN"), inline=True)
            
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                log.error(f"Fehler beim Senden des Log-Eintrags: {e}")


# Setup-Funktion für RedBot
async def setup(bot: Red):
    """Lädt den V-Warden Cog"""
    await bot.add_cog(VWarden(bot))
    log.info("V-Warden Cog loaded successfully")
