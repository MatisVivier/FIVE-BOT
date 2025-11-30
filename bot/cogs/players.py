import discord
from discord.ext import commands
from discord import app_commands

class Players(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = bot.data_manager

    def _rating_embed(self, member: discord.Member, player_data: dict) -> discord.Embed:
        embed = discord.Embed(
            title="Profil joueur mis à jour",
            description=f"Joueur : {member.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Note", value=f"**{player_data['rating']}/10**", inline=True)
        embed.add_field(name="Points", value=str(player_data['points']), inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        return embed

    @app_commands.command(name="set_joueur", description="Créer ou modifier un joueur avec une note sur 10.")
    @app_commands.describe(
        joueur="Le joueur (mention) à créer ou mettre à jour",
        note="Note de 1 à 10 (entier)"
    )
    async def set_joueur(self, interaction: discord.Interaction, joueur: discord.Member, note: int):
        if note < 1 or note > 10:
            await interaction.response.send_message(
                "❌ La note doit être comprise entre **1** et **10**.",
                ephemeral=True
            )
            return

        player = self.data.upsert_player(joueur.id, joueur.display_name, note)
        embed = self._rating_embed(joueur, player)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="liste_joueurs", description="Affiche la liste de tous les joueurs enregistrés.")
    async def liste_joueurs(self, interaction: discord.Interaction):
        players = self.data.get_players()
        if not players:
            await interaction.response.send_message("Aucun joueur enregistré pour le moment.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Liste des joueurs",
            color=discord.Color.blurple()
        )

        # tri par note décroissante
        sorted_players = sorted(players.values(), key=lambda p: p["rating"], reverse=True)
        lines = []
        for p in sorted_players:
            lines.append(f"**{p['name']}**  —  {p['rating']}/10  —  {p['points']} pts")

        # Discord a une limite de longueur, on split si besoin
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 1000:
                embed.add_field(name="\u200b", value=chunk, inline=False)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            embed.add_field(name="\u200b", value=chunk, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="stats_joueur", description="Affiche les stats complètes d'un joueur.")
    async def stats_joueur(self, interaction: discord.Interaction, joueur: discord.Member):
        player = self.data.get_player(joueur.id)
        if not player:
            await interaction.response.send_message("❌ Ce joueur n'est pas encore enregistré.", ephemeral=True)
            return

        # Classement général (par points)
        players = self.data.get_players()
        sorted_by_points = sorted(
            players.values(),
            key=lambda p: (p["points"], p["wins"], p["goals"], p["assists"]),
            reverse=True
        )
        rank = next((i + 1 for i, p in enumerate(sorted_by_points) if p["id"] == joueur.id), None)

        embed = discord.Embed(
            title=f"Stats de {joueur.display_name}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=joueur.display_avatar.url)
        embed.add_field(name="Note", value=f"{player['rating']}/10", inline=True)
        embed.add_field(name="Points", value=str(player["points"]), inline=True)
        embed.add_field(name="Matches joués", value=str(player["matches"]), inline=True)

        embed.add_field(name="Victoires", value=str(player["wins"]), inline=True)
        embed.add_field(name="Défaites", value=str(player["losses"]), inline=True)
        embed.add_field(name="Buts", value=str(player["goals"]), inline=True)
        embed.add_field(name="Passes décisives", value=str(player["assists"]), inline=True)
        embed.add_field(name="MVP", value=str(player["mvps"]), inline=True)

        if rank is not None:
            embed.add_field(name="Position au classement général", value=f"#{rank}", inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Players(bot))
