import discord
from discord.ext import commands
from discord import app_commands


class Misc(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="aide", description="Affiche toutes les commandes du bot Five.")
    async def aide(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🤖 Aide du bot Five",
            description="Voici toutes les commandes disponibles :",
            color=discord.Color.teal()
        )

        # --- Gestion Joueurs ---
        embed.add_field(
            name="Joueurs",
            value=(
                "• **/set_joueur** — Créer / modifier un joueur et ses stats.\n"
                "• **/liste_joueurs** — Voir tous les joueurs enregistrés.\n"
                "• **/stats_joueur** — Voir la carte FUT + stats complètes.\n"
                "• **/personnaliser_carte** — Couleur, bordure, texte personnalisés.\n"
            ),
            inline=False
        )

        # --- Matchmaking ---
        embed.add_field(
            name="Matchs",
            value=(
                "• **/creer_match** — Créer un match 5v5 équilibré.\n"
                "• **/resultat_match** — Enregistrer le score.\n"
                "• **/ajouter_stats** — Ajouter buts/passes d’un match.\n"
                "• **/supprimer_match** — Supprimer un match via son ID.\n"
            ),
            inline=False
        )

        # --- MVP ---
        embed.add_field(
            name="MVP",
            value=(
                "• **/vote_mvp** — Voter pour le MVP d’un match.\n"
                "• **/fin_mvp** — Clôturer le MVP et afficher le résultat.\n"
            ),
            inline=False
        )

        # --- Classements ---
        embed.add_field(
            name="Classements",
            value=(
                "• **/classement** — Classement général (points, victoires…).\n"
                "• **/classement_buts** — Meilleurs buteurs.\n"
                "• **/classement_passes** — Meilleurs passeurs.\n"
                "• **/classement_stats** — Classement des notes (tir, passes, physique, influence, gardien, note globale).\n"
            ),
            inline=False
        )

        embed.set_footer(text="Bot Five — Le bot ultime pour organiser vos matchs ⚽🔥")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ping", description="Test de latence.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("🏓 Pong !", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))
