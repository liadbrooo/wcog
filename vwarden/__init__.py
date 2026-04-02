"""V-Warden RedBot Cog Package"""
from .vwarden import VWarden

async def setup(bot):
    """Lädt den V-Warden Cog."""
    cog = VWarden(bot)
    await bot.add_cog(cog)
