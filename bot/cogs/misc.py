import discord
from discord.ext import commands
from discord import app_commands


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="aide", description="Affiche l'aide du bot et les commandes disponibles.")
    async def aide(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 Aide du bot Five",
            description=(
                "Voici les principales commandes disponibles :\n\n"
                "• `/set_joueur` — Créer / modifier un joueur avec une note sur 10.\n"
                "• `/liste_joueurs` — Liste de tous les joueurs enregistrés.\n"
                "• `/creer_match` — Créer un match 5v5 avec équipes équilibrées.\n"
                "• `/resultat_match` — Enregistrer le résultat d'un match.\n"
                "• `/vote_mvp` — Voter pour le MVP d'un match (24h).\n"
                "• `/ajouter_stats` — Ajouter buts/passes à un joueur.\n"
                "• `/classement` — Classement général.\n"
                "• `/classement_buts` — Meilleurs buteurs.\n"
                "• `/classement_passes` — Meilleurs passeurs.\n"
                "• `/stats_joueur` — Stats détaillées d'un joueur.\n"
            ),
            color=discord.Color.teal()
        )
        embed.set_footer(text="Bot Five — crée ton classement perso entre potes ⚽")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="Test de latence.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("🏓 Pong !", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))
