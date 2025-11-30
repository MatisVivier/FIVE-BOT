import discord
from discord.ext import commands
from discord import app_commands


class Rankings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = bot.data_manager

    def _star_if_top_mvp(self, player, players):
        max_mvp = max((p["mvps"] for p in players.values()), default=0)
        if player["mvps"] == max_mvp and max_mvp > 0:
            return "⭐"
        return " "

    def _short_name(self, name: str, width: int = 10) -> str:
        # Garde width caractères max, avec "…" si coupé, sinon pad avec espaces
        if len(name) > width:
            return name[: width - 1] + "…"
        return name.ljust(width)

    # ============ CLASSEMENT GENERAL ============
    @app_commands.command(name="classement", description="Classement général (points, victoires, etc.).")
    async def classement(self, interaction: discord.Interaction):
        players = self.data.get_players()
        if not players:
            await interaction.response.send_message("Aucun joueur enregistré.", ephemeral=True)
            return

        sorted_players = sorted(
            players.values(),
            key=lambda p: (
                p.get("points", 0),                     # 1 : points
                p.get("goals", 0),                      # 2 : buts
                p.get("assists", 0),                    # 3 : passes
                p.get("wins", 0),                       # 4 : victoires
                p.get("wins", 0) - p.get("losses", 0),  # 5 : diff V-D
                p.get("mvps", 0),                       # 6 : nombre de MVP
                p.get("name", "").lower()               # 7 : ordre alphabétique
            ),
            reverse=True
        )

        embed = discord.Embed(
            title="🏆 Classement général",
            color=discord.Color.purple()
        )

        header_line = (
            f"{'Pos':^3}  "
            f"{'Nom':7}  "
            f"{'Pts':^3}  "
            f"{'Vic':^3}  "
            f"{'Def':^3}  "
            f"{'But':^3}  "
            f"{'Pds':^3}  "
            f"{'MVP':^3}  "
        )

        lines = [header_line]

        for i, p in enumerate(sorted_players, start=1):
            star = self._star_if_top_mvp(p, players)  # '⭐' ou ' '
            name_short = self._short_name(p.get("name", "?"), 7)

            line = (
                f"{i:^3}  "
                f"{name_short}  "
                f"{p.get('points', 0):^3}  "
                f"{p.get('wins', 0):^3}  "
                f"{p.get('losses', 0):^3}  "
                f"{p.get('goals', 0):^3}  "
                f"{p.get('assists', 0):^3}  "
                f"{p.get('mvps', 0):^3}  "
                f"{star:^3}"
            )
            lines.append(line)

        # Découpe en blocs Discord-safe
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 2 > 900:
                embed.add_field(name="\u200b", value=f"```txt\n{chunk}```", inline=False)
                chunk = ""
            chunk += line + "\n"

        if chunk:
            embed.add_field(name="\u200b", value=f"```txt\n{chunk}```", inline=False)

        await interaction.response.send_message(embed=embed)

    # ============ CLASSEMENT BUTEURS ============
    @app_commands.command(name="classement_buts", description="Classement des meilleurs buteurs.")
    async def classement_buts(self, interaction: discord.Interaction):
        players = self.data.get_players()
        if not players:
            await interaction.response.send_message("Aucun joueur enregistré.", ephemeral=True)
            return

        sorted_players = sorted(players.values(), key=lambda p: p.get("goals", 0), reverse=True)

        embed = discord.Embed(
            title="⚽ Classement buteurs",
            color=discord.Color.green()
        )

        header_line = (
            f"{'Pos':^3}  "
            f"{'Nom':7}  "
            f"{'But':^3}  "
        )

        lines = [header_line]

        for i, p in enumerate(sorted_players, start=1):
            name_short = self._short_name(p.get("name", "?"), 7)
            line = (
                f"{i:^3}  "
                f"{name_short}  "
                f"{p.get('goals', 0):^3}  "
            )
            lines.append(line)

        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 2 > 900:
                embed.add_field(name="\u200b", value=f"```txt\n{chunk}```", inline=False)
                chunk = ""
            chunk += line + "\n"

        if chunk:
            embed.add_field(name="\u200b", value=f"```txt\n{chunk}```", inline=False)

        await interaction.response.send_message(embed=embed)

    # ============ CLASSEMENT PASSEURS ============
    @app_commands.command(name="classement_passes", description="Classement des meilleurs passeurs.")
    async def classement_passes(self, interaction: discord.Interaction):
        players = self.data.get_players()
        if not players:
            await interaction.response.send_message("Aucun joueur enregistré.", ephemeral=True)
            return

        sorted_players = sorted(players.values(), key=lambda p: p.get("assists", 0), reverse=True)

        embed = discord.Embed(
            title="🎯 Classement passeurs",
            color=discord.Color.blue()
        )

        header_line = (
            f"{'Pos':^3}  "
            f"{'Nom':7}  "
            f"{'Pds':^3}  "
        )

        lines = [header_line]

        for i, p in enumerate(sorted_players, start=1):
            name_short = self._short_name(p.get("name", "?"), 7)
            line = (
                f"{i:^3}  "
                f"{name_short}  "
                f"{p.get('assists', 0):^3}  "
            )
            lines.append(line)

        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 2 > 900:
                embed.add_field(name="\u200b", value=f"```txt\n{chunk}```", inline=False)
                chunk = ""
            chunk += line + "\n"

        if chunk:
            embed.add_field(name="\u200b", value=f"```txt\n{chunk}```", inline=False)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Rankings(bot))
