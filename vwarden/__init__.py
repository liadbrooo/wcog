from .vwarden import VVardenBridge

__red_end_user_data_statement__ = (
    "Dieser Cog speichert Konfigurationseinstellungen pro Server (VVarden-Bot-ID, Log-Kanal, Bestrafungsart). "
    "Der Cog selbst speichert keine persönlichen Daten von Benutzern dauerhaft. "
    "Bei der Prüfung wird nur der Benutzername temporär an den VVarden-Bot gesendet."
)

async def setup(bot):
    """Setup-Funktion für RedBot."""
    cog = VVardenBridge(bot)
    await bot.add_cog(cog)
