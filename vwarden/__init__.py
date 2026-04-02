"""V-Warden RedBot Cog Package"""
from .vwarden import VWarden

async def setup(bot):
    """Lädt den V-Warden Cog."""
    from .vwarden import VWarden
    cog = VWarden()
    await bot.add_cog(cog)
