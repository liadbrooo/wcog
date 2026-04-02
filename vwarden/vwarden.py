"""
V-Warden RedBot Cog - Vollständiger Port des V-Warden Discord Bots
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from enum import Enum

import discord
from redbot.core import commands, Config, checks
import aiohttp

log = logging.getLogger("red.vwarden")


class UserType(str, Enum):
    OWNER = "OWNER"
    SUPPORTER = "SUPPORTER"
    CHEATER = "CHEATER"
    LEAKER = "LEAKER"
    OTHER = "OTHER"
    BOT = "BOT"


class UserStatus(str, Enum):
    WHITELISTED = "WHITELISTED"
    BLACKLISTED = "BLACKLISTED"
    PERM_BLACKLISTED = "PERM_BLACKLISTED"
    APPEALED = "APPEALED"


class PunishType(str, Enum):
    WARN = "WARN"
    ROLE = "ROLE"
    KICK = "KICK"
    BAN = "BAN"


COLOURS = {
    "YELLOW": 0xFFFF00,
    "RED": 0x800000,
    "GREEN": 0x008000,
    "BLUE": 0x0000FF,
}


class VWarden(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=58294671235, force_registration=True)

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
            "ignored_roles": [],
            "ignored_channels": [],
        }

        self.config.register_guild(**default_guild)

        default_global = {
            "api_url": "https://api.v-warden.com",
            "api_key": None,
            "cache_time": 300,
        }

        self.config.register_global(**default_global)

        self.user_cache: Dict[int, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[int, float] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def cog_unload(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def red_get_data_for_user(self, user_id: int):
        return {"message": "Keine persönlichen Daten gespeichert."}

    async def red_delete_data_for_user(self, user_id: int):
        pass

    def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def get_api_key(self) -> Optional[str]:
        return await self.config.api_key()

    async def check_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        now = datetime.now().timestamp()
        if user_id in self.user_cache:
            cache_time = self.cache_timestamps.get(user_id, 0)
            cache_duration = await self.config.cache_time()
            if now - cache_time < cache_duration:
                log.debug(f"Verwende gecachte Daten für User {user_id}")
                return self.user_cache[user_id]

        api_key = await self.get_api_key()
        if not api_key:
            log.warning("Kein API-Key konfiguriert!")
            return None

        api_url = await self.config.api_url()
        url = f"{api_url}/users/{user_id}"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            session = self.get_session()
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.user_cache[user_id] = data
                    self.cache_timestamps[user_id] = now
                    log.info(f"User {user_id} wurde als {data.get('type', 'UNKNOWN')} identifiziert")
                    return data
                elif resp.status == 404:
                    log.debug(f"User {user_id} nicht in Datenbank gefunden")
                    return None
                else:
                    log.error(f"API Fehler: {resp.status}")
                    return None
        except asyncio.TimeoutError:
            log.error(f"Timeout bei API Anfrage für User {user_id}")
            return None
        except Exception as e:
            log.error(f"Fehler bei API Anfrage: {e}", exc_info=True)
            return None

    async def punish_user(self, guild: discord.Guild, member: discord.Member, user_data: Dict[str, Any], reason: str):
        punishments = await self.config.guild(guild).punishments()
        user_type = user_data.get("type", "OTHER").upper()

        if not punishments.get("enabled", True):
            return

        punish_map = {
            "OWNER": punishments.get("owner", PunishType.BAN.value),
            "SUPPORTER": punishments.get("supporter", PunishType.BAN.value),
            "LEAKER": punishments.get("leaker", PunishType.BAN.value),
            "CHEATER": punishments.get("cheater", PunishType.KICK.value),
            "OTHER": punishments.get("other", PunishType.ROLE.value),
        }

        punish_type = punish_map.get(user_type, PunishType.ROLE.value)

        try:
            if punish_type == PunishType.BAN.value:
                unban_setting = f"unban_{user_type.lower()}"
                should_unban = punishments.get(unban_setting, False)

                await member.ban(reason=reason, delete_message_days=0)
                
                if should_unban:
                    await asyncio.sleep(5)
                    await guild.unban(member.user, reason="V-Warden: Automatischer Unban nach Ban")
                    log.info(f"User {member.id} wurde gebannt und sofort entbannt")

            elif punish_type == PunishType.KICK.value:
                await member.kick(reason=reason)

            elif punish_type == PunishType.ROLE.value:
                role_id = await self.config.guild(guild).punishment_role()
                if role_id:
                    role = guild.get_role(role_id)
                    if role:
                        await member.add_roles(role, reason=reason)
                        log.info(f"User {member.id} erhielt Strafrrolle {role.name}")

            elif punish_type == PunishType.WARN.value:
                log.info(f"User {member.id} wurde verwarnt (nur Log)")

        except discord.Forbidden:
            log.error(f"Keine Berechtigung um {member.id} zu bestrafen")
        except discord.HTTPException as e:
            log.error(f"HTTP Fehler bei Bestrafung: {e}")
        except Exception as e:
            log.error(f"Unbekannter Fehler bei Bestrafung: {e}", exc_info=True)

    async def log_action(self, guild: discord.Guild, action: str, user: Union[discord.User, discord.Member], user_data: Optional[Dict[str, Any]] = None, additional_info: Optional[str] = None):
        log_channel_id = await self.config.guild(guild).log_channel()
        if not log_channel_id:
            return

        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        embed = discord.Embed(
            title="🛡️ V-Warden Alarm",
            description=f"**Aktion:** {action}",
            color=COLOURS["RED"],
            timestamp=datetime.now()
        )

        embed.add_field(name="Benutzer", value=f"{user.mention} ({user.id})", inline=False)
        embed.add_field(name="Name", value=str(user), inline=True)

        if user_data:
            embed.add_field(name="Typ", value=user_data.get("type", "UNKNOWN"), inline=True)
            embed.add_field(name="Status", value=user_data.get("status", "UNKNOWN"), inline=True)
            
            proof_url = user_data.get("proof_url")
            if proof_url:
                embed.add_field(name="Beweis", value=f"[Link]({proof_url})", inline=False)

        if additional_info:
            embed.add_field(name="Zusatzinfo", value=additional_info, inline=False)

        embed.set_footer(text="V-Warden Protection System")
        embed.set_thumbnail(url=user.display_avatar.url)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            log.error(f"Keine Berechtigung zum Senden in Log-Kanal {log_channel_id}")
        except Exception as e:
            log.error(f"Fehler beim Senden des Log-Eintrags: {e}")

    @commands.group(name="vwarden", aliases=["vw"])
    @commands.guild_only()
    async def vwarden_group(self, ctx: commands.Context):
        pass

    @vwarden_group.command(name="enable")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_enable(self, ctx: commands.Context):
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send("✅ V-Warden wurde für diesen Server **aktiviert**.")
        log.info(f"V-Warden wurde in Guild {ctx.guild.name} aktiviert")

    @vwarden_group.command(name="disable")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_disable(self, ctx: commands.Context):
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("❌ V-Warden wurde für diesen Server **deaktiviert**.")
        log.info(f"V-Warden wurde in Guild {ctx.guild.name} deaktiviert")

    @vwarden_group.command(name="logchannel")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_logchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        if channel is None:
            channel = ctx.channel

        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"✅ Log-Kanal wurde auf {channel.mention} gesetzt.")
        log.info(f"Log-Kanal für {ctx.guild.name} wurde auf {channel.name} gesetzt")

    @vwarden_group.command(name="punishrole")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_punishrole(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        if role is None:
            await self.config.guild(ctx.guild).punishment_role.set(None)
            await ctx.send("✅ Strafrrolle wurde entfernt.")
        else:
            await self.config.guild(ctx.guild).punishment_role.set(role.id)
            await ctx.send(f"✅ Strafrrolle wurde auf {role.mention} gesetzt.")
        log.info(f"Strafrrolle für {ctx.guild.name} wurde {'gesetzt' if role else 'entfernt'}")

    @vwarden_group.command(name="config")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_config(self, ctx: commands.Context):
        enabled = await self.config.guild(ctx.guild).enabled()
        log_channel_id = await self.config.guild(ctx.guild).log_channel()
        punish_role_id = await self.config.guild(ctx.guild).punishment_role()
        punishments = await self.config.guild(ctx.guild).punishments()

        log_channel = ctx.guild.get_channel(log_channel_id) if log_channel_id else None
        punish_role = ctx.guild.get_role(punish_role_id) if punish_role_id else None

        embed = discord.Embed(
            title="⚙️ V-Warden Konfiguration",
            color=COLOURS["BLUE"],
            timestamp=datetime.now()
        )

        status = "✅ Aktiviert" if enabled else "❌ Deaktiviert"
        embed.add_field(name="Status", value=status, inline=True)

        log_info = log_channel.mention if log_channel else "Nicht gesetzt"
        embed.add_field(name="Log-Kanal", value=log_info, inline=True)

        role_info = punish_role.mention if punish_role else "Nicht gesetzt"
        embed.add_field(name="Strafrrolle", value=role_info, inline=True)

        punish_enabled = "✅" if punishments.get("enabled", True) else "❌"
        embed.add_field(name="Bestrafungen", value=f"{punish_enabled} Aktiviert", inline=False)

        punish_text = ""
        for utype in ["owner", "supporter", "leaker", "cheater", "other"]:
            ptype = punishments.get(utype, "BAN")
            emoji = "🔨" if ptype == "BAN" else "👢" if ptype == "KICK" else "🎭" if ptype == "ROLE" else "⚠️"
            punish_text += f"{emoji} **{utype.upper()}:** {ptype}\n"

        embed.add_field(name="Straf-Typen", value=punish_text or "Keine Einstellungen", inline=False)
        embed.set_footer(text=f"Guild ID: {ctx.guild.id}")
        await ctx.send(embed=embed)

    @vwarden_group.command(name="check")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def vwarden_check(self, ctx: commands.Context, user: Optional[discord.User] = None):
        if user is None:
            user = ctx.author

        enabled = await self.config.guild(ctx.guild).enabled()
        
        await ctx.trigger_typing()
        
        user_data = await self.check_user(user.id)

        if user_data is None:
            embed = discord.Embed(
                title="🔍 Benutzerüberprüfung",
                description=f"**{user}** wurde **nicht** in der V-Warden Datenbank gefunden.",
                color=COLOURS["GREEN"]
            )
            embed.add_field(name="Status", value="✅ Sauber", inline=False)
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text="V-Warden Protection System")
            await ctx.send(embed=embed)
            return

        user_type = user_data.get("type", "UNKNOWN")
        status = user_data.get("status", "UNKNOWN")
        proof_url = user_data.get("proof_url")

        color = COLOURS["RED"] if status in ["BLACKLISTED", "PERM_BLACKLISTED"] else COLOURS["YELLOW"]

        embed = discord.Embed(
            title="⚠️ V-Warden Warnung!",
            description=f"**{user}** wurde in der V-Warden Datenbank gefunden!",
            color=color
        )

        embed.add_field(name="Typ", value=user_type, inline=True)
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)

        if proof_url:
            embed.add_field(name="Beweis", value=f"[Hier klicken]({proof_url})", inline=False)

        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="V-Warden Protection System")

        await ctx.send(embed=embed)

        if enabled and isinstance(user, discord.Member):
            await self.log_action(ctx.guild, "Manuelle Überprüfung - Treffer", user, user_data)
            
            punishments = await self.config.guild(ctx.guild).punishments()
            if punishments.get("enabled", True):
                reason = f"V-Warden: Benutzer als {user_type} identifiziert"
                await self.punish_user(ctx.guild, user, user_data, reason)

    @vwarden_group.command(name="scan")
    @checks.admin_or_permissions(manage_guild=True)
    @commands.cooldown(1, 300, commands.BucketType.guild)
    async def vwarden_scan(self, ctx: commands.Context):
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send("❌ V-Warden ist für diesen Server nicht aktiviert.")
            return

        await ctx.send("🔄 Starte Server-Scan... Dies kann einige Zeit dauern.")
        
        members = ctx.guild.members
        found_count = 0
        punished_count = 0

        for i, member in enumerate(members):
            if member.bot:
                continue

            ignored_roles = await self.config.guild(ctx.guild).ignored_roles()
            if any(role.id in ignored_roles for role in member.roles):
                continue

            await ctx.trigger_typing()
            
            user_data = await self.check_user(member.id)

            if user_data:
                found_count += 1
                user_type = user_data.get("type", "UNKNOWN")
                
                await self.log_action(ctx.guild, "Automatischer Scan - Treffer", member, user_data, f"Scan Fortschritt: {i+1}/{len(members)}")

                punishments = await self.config.guild(ctx.guild).punishments()
                if punishments.get("enabled", True):
                    reason = f"V-Warden Auto-Scan: Benutzer als {user_type} identifiziert"
                    await self.punish_user(ctx.guild, member, user_data, reason)
                    punished_count += 1

                await asyncio.sleep(0.5)

        summary_embed = discord.Embed(
            title="📊 Scan abgeschlossen",
            description="Der Server-Scan wurde erfolgreich abgeschlossen.",
            color=COLOURS["GREEN"],
            timestamp=datetime.now()
        )

        summary_embed.add_field(name="Geprüfte Mitglieder", value=len(members), inline=True)
        summary_embed.add_field(name="Treffer", value=found_count, inline=True)
        summary_embed.add_field(name="Bestraft", value=punished_count, inline=True)
        summary_embed.set_footer(text="V-Warden Protection System")

        await ctx.send(embed=summary_embed)
        log.info(f"Scan in {ctx.guild.name} abgeschlossen: {found_count} Treffer, {punished_count} bestraft")

    @vwarden_group.command(name="setpunish")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_setpunish(self, ctx: commands.Context, user_type: str, punishment: str):
        valid_types = ["owner", "supporter", "leaker", "cheater", "other"]
        valid_punishments = ["ban", "kick", "role", "warn", "none"]

        user_type = user_type.lower()
        punishment = punishment.lower()

        if user_type not in valid_types:
            await ctx.send(f"❌ Ungültiger Typ. Gültige Typen: {', '.join(valid_types)}")
            return

        if punishment not in valid_punishments:
            await ctx.send(f"❌ Ungültige Strafe. Gültige Strafen: {', '.join(valid_punishments)}")
            return

        if punishment == "none":
            punishment_value = None
        else:
            punishment_value = punishment.upper()

        punishments = await self.config.guild(ctx.guild).punishments()
        punishments[user_type] = punishment_value
        await self.config.guild(ctx.guild).punishments.set(punishments)

        await ctx.send(f"✅ Strafe für **{user_type.upper()}** wurde auf **{punishment.upper()}** gesetzt.")
        log.info(f"Strafe für {user_type} in {ctx.guild.name} wurde auf {punishment} gesetzt")

    @vwarden_group.command(name="togglepunishments")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_togglepunishments(self, ctx: commands.Context):
        punishments = await self.config.guild(ctx.guild).punishments()
        current = punishments.get("enabled", True)
        punishments["enabled"] = not current
        await self.config.guild(ctx.guild).punishments.set(punishments)

        status = "aktiviert" if not current else "deaktiviert"
        await ctx.send(f"✅ Automatische Bestrafungen wurden **{status}**.")

    @vwarden_group.command(name="ignore")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_ignore(self, ctx: commands.Context, role_or_channel: Union[discord.Role, discord.TextChannel]):
        if isinstance(role_or_channel, discord.Role):
            ignored = await self.config.guild(ctx.guild).ignored_roles()
            if role_or_channel.id not in ignored:
                ignored.append(role_or_channel.id)
                await self.config.guild(ctx.guild).ignored_roles.set(ignored)
                await ctx.send(f"✅ Rolle {role_or_channel.mention} wird jetzt ignoriert.")
        else:
            ignored = await self.config.guild(ctx.guild).ignored_channels()
            if role_or_channel.id not in ignored:
                ignored.append(role_or_channel.id)
                await self.config.guild(ctx.guild).ignored_channels.set(ignored)
                await ctx.send(f"✅ Kanal {role_or_channel.mention} wird jetzt ignoriert.")

    @vwarden_group.command(name="unignore")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_unignore(self, ctx: commands.Context, role_or_channel: Union[discord.Role, discord.TextChannel]):
        if isinstance(role_or_channel, discord.Role):
            ignored = await self.config.guild(ctx.guild).ignored_roles()
            if role_or_channel.id in ignored:
                ignored.remove(role_or_channel.id)
                await self.config.guild(ctx.guild).ignored_roles.set(ignored)
                await ctx.send(f"✅ Rolle {role_or_channel.mention} wird nicht mehr ignoriert.")
            else:
                await ctx.send("ℹ️ Diese Rolle war nicht auf der Ignorier-Liste.")
        else:
            ignored = await self.config.guild(ctx.guild).ignored_channels()
            if role_or_channel.id in ignored:
                ignored.remove(role_or_channel.id)
                await self.config.guild(ctx.guild).ignored_channels.set(ignored)
                await ctx.send(f"✅ Kanal {role_or_channel.mention} wird nicht mehr ignoriert.")
            else:
                await ctx.send("ℹ️ Dieser Kanal war nicht auf der Ignorier-Liste.")

    @vwarden_group.command(name="apikey")
    @checks.is_owner()
    async def vwarden_apikey(self, ctx: commands.Context, api_key: Optional[str] = None):
        if api_key is None:
            current_key = await self.get_api_key()
            if current_key:
                masked = current_key[:4] + "..." + current_key[-4:] if len(current_key) > 8 else "***"
                await ctx.send(f"🔑 Aktueller API-Key: `{masked}`")
            else:
                await ctx.send("❌ Kein API-Key konfiguriert.")
        else:
            await self.config.api_key.set(api_key)
            await ctx.send("✅ API-Key wurde aktualisiert.")
            self.user_cache.clear()
            self.cache_timestamps.clear()

    @vwarden_group.command(name="clearcache")
    @checks.admin_or_permissions(manage_guild=True)
    async def vwarden_clearcache(self, ctx: commands.Context):
        self.user_cache.clear()
        self.cache_timestamps.clear()
        await ctx.send("✅ Cache wurde geleert.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        enabled = await self.config.guild(member.guild).enabled()
        if not enabled:
            return

        if member.bot:
            return

        ignored_roles = await self.config.guild(member.guild).ignored_roles()
        if any(role.id in ignored_roles for role in member.roles):
            return

        await asyncio.sleep(2)
        
        user_data = await self.check_user(member.id)

        if user_data:
            user_type = user_data.get("type", "UNKNOWN")
            
            await self.log_action(member.guild, "Mitglied beigetreten - Treffer", member, user_data)

            punishments = await self.config.guild(member.guild).punishments()
            if punishments.get("enabled", True):
                reason = f"V-Warden: Benutzer als {user_type} identifiziert (Beitritt)"
                await self.punish_user(member.guild, member, user_data, reason)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        enabled = await self.config.guild(message.guild).enabled()
        if not enabled:
            return

        if message.author.bot:
            return

        ignored_channels = await self.config.guild(message.guild).ignored_channels()
        if message.channel.id in ignored_channels:
            return
        
        user_data = await self.check_user(message.author.id)
        
        if user_data and user_data.get("status") in ["BLACKLISTED", "PERM_BLACKLISTED"]:
            await self.log_action(message.guild, "Nachricht gesendet - Treffer", message.author, user_data, f"Kanal: {message.channel.mention}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        log_channel = None
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                log_channel = channel
                break

        if log_channel:
            await self.config.guild(guild).log_channel.set(log_channel.id)

            prefixes = await self.bot.get_prefix(message=None) if hasattr(self.bot, 'get_prefix') else ["!"]
            prefix = prefixes[0] if isinstance(prefixes, list) and prefixes else "!"

            embed = discord.Embed(
                title="🛡️ V-Warden installiert",
                description="Danke dass du V-Warden installiert hast!\n\nUm den Bot zu konfigurieren:",
                color=COLOURS["BLUE"]
            )
            embed.add_field(
                name="Erste Schritte",
                value=(
                    f"`{prefix}vwarden enable` - Aktiviere den Bot\n"
                    f"`{prefix}vwarden config` - Zeige Konfiguration\n"
                    f"`{prefix}vwarden help` - Hilfe anzeigen"
                ),
                inline=False
            )

            try:
                await log_channel.send(embed=embed)
            except Exception:
                pass

        log.info(f"V-Warden wurde Guild {guild.name} ({guild.id}) hinzugefügt")


async def setup(bot):
    cog = VWarden(bot)
    await bot.add_cog(cog)
    log.info("V-Warden Cog wurde erfolgreich geladen.")
