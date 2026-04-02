import discord
from redbot.core import commands, checks, Config
from redbot.core.bot import Red
import asyncio
import re
from typing import Optional

class VVardenBridge(commands.Cog):
    """
    Ein Cog, der mit dem VVarden-Bot interagiert, um gebannte Nutzer zu erkennen.
    Er sendet den Check-Befehl an VVarden und wertet die Antwort aus.
    Keine API-Keys oder Datenbanken erforderlich!
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=12345678901234567890, force_registration=True)
        
        default_guild = {
            "enabled": False,
            "log_channel": None,
            "punishment": "kick",  # kick, ban, warn
            "vwarden_id": None,    # Die User ID des VVarden Bots
            "check_command": "!check" # Der Befehl den VVarden nutzt (Standard: !check)
        }
        self.config.register_guild(**default_guild)
        
        # Muster zur Erkennung von Treffern in der Antwort
        self.hit_pattern = re.compile(r"(ban|banned|gebannt|verstoß|violation|hit|treffer|flag)", re.IGNORECASE)
        self.safe_pattern = re.compile(r"(clean|safe|keine|no record|found nothing|ok|frei)", re.IGNORECASE)

    async def get_vwarden_response(self, ctx, user: discord.Member) -> Optional[bool]:
        """
        Sendet einen Check-Befehl an VVarden und wartet auf die Antwort.
        Gibt True zurück, wenn der User gebannt ist, False wenn sicher, None bei Fehler.
        """
        vwarden_id = await self.config.guild(ctx.guild).vwarden_id()
        check_cmd = await self.config.guild(ctx.guild).check_command()
        log_chan_id = await self.config.guild(ctx.guild).log_channel()
        
        if not vwarden_id:
            if hasattr(ctx, 'send'):
                await ctx.send("❌ Fehler: VVarden-Bot-ID nicht konfiguriert. Nutze `[p]vwarden setvvid <ID>`.")
            return None
            
        if not log_chan_id:
            if hasattr(ctx, 'send'):
                await ctx.send("❌ Fehler: Kein Log-Kanal konfiguriert. Nutze `[p]vwarden logchannel`.")
            return None

        log_channel = ctx.guild.get_channel(log_chan_id)
        if not log_channel:
            if hasattr(ctx, 'send'):
                await ctx.send("❌ Fehler: Log-Kanal nicht gefunden.")
            return None

        # VVarden Bot finden
        vwarden_user = self.bot.get_user(vwarden_id)
        if not vwarden_user:
            try:
                vwarden_member = await ctx.guild.fetch_member(vwarden_id)
                vwarden_user = vwarden_member
            except:
                if hasattr(ctx, 'send'):
                    await ctx.send("❌ Fehler: VVarden-Bot wurde auf diesem Server nicht gefunden.")
                return None

        # Berechtigungen prüfen
        if not log_channel.permissions_for(ctx.guild.me).send_messages:
            if hasattr(ctx, 'send'):
                await ctx.send("❌ Fehler: Ich habe keine Rechte, im Log-Kanal zu schreiben.")
            return None
        if not log_channel.permissions_for(ctx.guild.me).read_message_history:
            if hasattr(ctx, 'send'):
                await ctx.send("❌ Fehler: Ich kann im Log-Kanal nicht lesen.")
            return None

        # Befehl senden
        try:
            check_msg = f"{check_cmd} {user.name}"
            sent_msg = await log_channel.send(check_msg)
        except Exception as e:
            if hasattr(ctx, 'send'):
                await ctx.send(f"❌ Konnte Check nicht senden: {e}")
            return None

        # Auf Antwort warten (max 10 Sekunden)
        try:
            def check_response(msg):
                # Prüfe ob Nachricht von VVarden kommt und im richtigen Kanal ist
                if msg.author.id != vwarden_id or msg.channel.id != log_channel.id:
                    return False
                # Entweder es ist eine Antwort auf unsere Nachricht (Reply)
                if msg.reference and getattr(msg.reference, 'message_id', None) == sent_msg.id:
                    return True
                # Oder sie enthält den Usernamen und kam kurz nach unserer Anfrage
                if user.name in msg.content and abs((msg.created_at - sent_msg.created_at).total_seconds()) < 10:
                    return True
                return False

            response_msg = await self.bot.wait_for('message', timeout=10.0, check=check_response)
            
            # Antwort auswerten
            content = response_msg.content
            if self.hit_pattern.search(content):
                return True  # Gebannt/Treffer
            elif self.safe_pattern.search(content):
                return False  # Sicher
            else:
                # Unklare Antwort - wir gehen im Zweifel von sicher aus, aber loggen es
                print(f"Unerwartete VVarden-Antwort für {user.name}: {content}")
                return None
                
        except asyncio.TimeoutError:
            if hasattr(ctx, 'send') and ctx.guild:
                try:
                    await ctx.send("⚠️ Timeout: VVarden hat nicht geantwortet. Ist der Bot online?")
                except:
                    pass
            return None
        except Exception as e:
            if hasattr(ctx, 'send'):
                await ctx.send(f"❌ Fehler: {e}")
            return None
        finally:
            # Aufräumen: Eigene Anfrage löschen
            try:
                await sent_msg.delete()
            except:
                pass

    async def handle_punishment(self, guild: discord.Guild, user: discord.Member, reason: str = "VVarden Hit"):
        """Führt die Bestrafung durch."""
        punishment = await self.config.guild(guild).punishment()
        
        try:
            if punishment == "ban":
                await guild.ban(user, reason=reason, delete_message_days=0)
                return "gebannt"
            elif punishment == "kick":
                await guild.kick(user, reason=reason)
                return "gekickt"
            elif punishment == "warn":
                return "markiert (Warn)"
            else:
                return "nicht bestraft (Konfigurationsfehler)"
        except Exception as e:
            raise e

    @commands.group(name="vwarden", aliases=["vv"])
    @commands.guild_only()
    async def vwarden_group(self, ctx):
        """Einstellungen für die VVarden-Integration."""
        pass

    @vwarden_group.command(name="einrichten")
    @checks.admin_or_permissions(manage_guild=True)
    async def cmd_enable(self, ctx):
        """Aktiviert den Schutz für diesen Server."""
        await self.config.guild(ctx.guild).enabled.set(True)
        await ctx.send("✅ VVarden-Schutz ist jetzt **aktiv**.\n\nWichtig: Stelle sicher, dass du folgende Einstellungen vornimmst:\n1. `[p]vwarden setvvid <ID>` - ID des VVarden-Bots\n2. `[p]vwarden logchannel <#kanal>` - Kanal für Checks")

    @vwarden_group.command(name="deaktivieren")
    @checks.admin_or_permissions(manage_guild=True)
    async def cmd_disable(self, ctx):
        """Deaktiviert den Schutz."""
        await self.config.guild(ctx.guild).enabled.set(False)
        await ctx.send("❌ VVarden-Schutz ist jetzt **inaktiv**.")

    @vwarden_group.command(name="setvvid")
    @checks.admin_or_permissions(manage_guild=True)
    async def cmd_set_vvid(self, ctx, vvid: int):
        """Setzt die User-ID des VVarden-Bots.
        
        Aktiviere den Entwicklermodus in Discord (Einstellungen -> Erweitert),
        dann Rechtsklick auf den VVarden-Bot -> ID kopieren.
        """
        await self.config.guild(ctx.guild).vwarden_id.set(vvid)
        await ctx.send(f"✅ VVarden-Bot-ID auf `{vvid}` gesetzt.")

    @vwarden_group.command(name="logchannel")
    @checks.admin_or_permissions(manage_guild=True)
    async def cmd_set_log(self, ctx, channel: discord.TextChannel):
        """Setzt den Kanal, in dem die Checks durchgeführt werden.
        
        Dies MUSS ein Kanal sein, in dem sowohl dein Bot als auch VVarden schreiben können.
        VVarden muss in diesem Kanal antworten können!
        """
        await self.config.guild(ctx.guild).log_channel.set(channel.id)
        await ctx.send(f"✅ Log-Kanal auf {channel.mention} gesetzt.\nStelle sicher, dass VVarden hier schreiben kann!")

    @vwarden_group.command(name="bestrafung")
    @checks.admin_or_permissions(manage_guild=True)
    async def cmd_set_punish(self, ctx, art: str):
        """Setzt die Bestrafung: `ban`, `kick` oder `warn`."""
        art = art.lower()
        if art not in ["ban", "kick", "warn"]:
            await ctx.send("❌ Ungültige Art. Wähle: ban, kick, warn")
            return
        await self.config.guild(ctx.guild).punishment.set(art)
        await ctx.send(f"✅ Bestrafung auf `{art}` gesetzt.")

    @vwarden_group.command(name="status")
    @checks.admin_or_permissions(manage_guild=True)
    async def cmd_status(self, ctx):
        """Zeigt den aktuellen Status der Konfiguration."""
        enabled = await self.config.guild(ctx.guild).enabled()
        vvid = await self.config.guild(ctx.guild).vwarden_id()
        log_id = await self.config.guild(ctx.guild).log_channel()
        punish = await self.config.guild(ctx.guild).punishment()
        check_cmd = await self.config.guild(ctx.guild).check_command()
        
        log_ch = ctx.guild.get_channel(log_id) if log_id else "Nicht gesetzt"
        vvid_str = f"<@{vvid}>" if vvid else "Nicht gesetzt"
        
        status_text = f"""**VVarden Bridge Status**
━━━━━━━━━━━━━━━━━━━━━━━
🔹 Aktiv: {'✅ Ja' if enabled else '❌ Nein'}
🔹 VVarden Bot: {vvid_str}
🔹 Log Kanal: {log_ch.mention if isinstance(log_ch, discord.TextChannel) else log_ch}
🔹 Bestrafung: {punish}
🔹 Check-Befehl: `{check_cmd}`
━━━━━━━━━━━━━━━━━━━━━━━
"""
        await ctx.send(status_text)

    @vwarden_group.command(name="check")
    @checks.admin_or_permissions(manage_guild=True)
    async def cmd_manual_check(self, ctx, user: discord.Member):
        """Führt einen manuellen Check eines Benutzers durch."""
        await ctx.send(f"🔍 Prüfe {user.mention} über VVarden...")
        result = await self.get_vwarden_response(ctx, user)
        
        if result is True:
            try:
                action = await self.handle_punishment(ctx.guild, user, "Manueller VVarden Check")
                await ctx.send(f"🚨 **TREFFER!** {user.mention} ist in der VVarden-Datenbank!\n→ User wurde **{action}**.")
            except Exception as e:
                await ctx.send(f"🚨 **TREFFER!** {user.mention} ist gebannt, konnte aber nicht bestraft werden: {e}")
        elif result is False:
            await ctx.send(f"✅ {user.mention} ist sauber (kein Eintrag in VVarden).")
        else:
            await ctx.send("❓ Prüfung konnte nicht abgeschlossen werden. Überprüfe die Konfiguration.")

    @vwarden_group.command(name="setcmd")
    @checks.admin_or_permissions(manage_guild=True)
    async def cmd_set_checkcmd(self, ctx, command: str):
        """Setzt den Befehl, den VVarden verwendet (Standard: !check).
        
        Nur ändern, wenn VVarden einen anderen Befehl nutzt!
        """
        await self.config.guild(ctx.guild).check_command.set(command)
        await ctx.send(f"✅ Check-Befehl auf `{command}` gesetzt.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Automatischer Check beim Beitreten eines neuen Members."""
        if not member.guild or member.bot:
            return
            
        enabled = await self.config.guild(member.guild).enabled()
        if not enabled:
            return

        # Kurze Verzögerung damit alles bereit ist
        await asyncio.sleep(2)
        
        # Kanal zum Senden finden
        channel = member.guild.system_channel
        if not channel:
            for c in member.guild.text_channels:
                if c.permissions_for(member.guild.me).send_messages:
                    channel = c
                    break
        
        if not channel:
            return

        # Fake Context für die Helper-Funktion
        class FakeCtx:
            def __init__(self, guild, chan):
                self.guild = guild
                self.channel = chan
            async def send(self, msg):
                try:
                    await chan.send(msg)
                except:
                    pass

        fake_ctx = FakeCtx(member.guild, channel)

        # Prüfen
        is_banned = await self.get_vwarden_response(fake_ctx, member)
        
        if is_banned is True:
            log_chan_id = await self.config.guild(member.guild).log_channel()
            log_channel = member.guild.get_channel(log_chan_id) if log_chan_id else channel
            
            reason = "Automatischer VVarden Join-Check"
            
            try:
                action = await self.handle_punishment(member.guild, member, reason)
                
                if log_channel:
                    await log_channel.send(
                        f"🚨 **AUTOMATISCHER SCHUTZ**\n\n"
                        f"User: {member.mention} (`{member.id}`)\n"
                        f"Aktion: **{action}**\n"
                        f"Grund: In VVarden-Datenbank gelistet"
                    )
            except Exception as e:
                if log_channel:
                    await log_channel.send(f"❌ Fehler beim Bestrafen von {member.mention}: {e}")


def setup(bot: Red):
    """Lädt den Cog."""
    bot.add_cog(VVardenBridge(bot))
