import discord
from discord.ext import commands
from data_manager import DataManager
from dotenv import load_dotenv
import os

# Charge le .env
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("❌ ERREUR : Le token Discord n'a pas été trouvé dans le fichier .env")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

GUILD_ID = 1020352225811386449  # ton serveur

class FiveBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
        )
        self.data_manager = DataManager()

    async def setup_hook(self):
        # Charge les cogs
        await self.load_extension("cogs.players")
        await self.load_extension("cogs.matches")
        await self.load_extension("cogs.rankings")
        await self.load_extension("cogs.misc")

        guild = discord.Object(id=GUILD_ID)

        # Sync les commandes instant local guild
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        print(f"Slash commands synchro pour la guild {GUILD_ID} : {len(synced)} commandes.")

    async def on_ready(self):
        print(f"Connecté en tant que {self.user} (id: {self.user.id})")


if __name__ == "__main__":
    bot = FiveBot()

    print("TOKEN lu depuis .env :", TOKEN[:5] + "********")  # Affiche juste le début pour debug propre
    bot.run(TOKEN)
