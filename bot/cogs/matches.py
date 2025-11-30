import re
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta


def balance_teams(players_with_rating: list[tuple[int, int]]):
    """
    players_with_rating: [(id, rating), ...] pour 10 joueurs.
    Retourne (team_a_ids, team_b_ids, sum_a, sum_b)
    id peut être un id Discord (int > 0) ou un id invité (int négatif).
    """
    sorted_players = sorted(players_with_rating, key=lambda x: x[1], reverse=True)

    team_a = []
    team_b = []
    sum_a = 0
    sum_b = 0

    for pid, rating in sorted_players:
        if len(team_a) < 5 and (sum_a <= sum_b or len(team_b) >= 5):
            team_a.append(pid)
            sum_a += rating
        else:
            team_b.append(pid)
            sum_b += rating

    return team_a, team_b, sum_a, sum_b


class Matches(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = bot.data_manager
        self._mention_re = re.compile(r"<@!?(\d+)>")
        # *** 7 ou ***7 → invité note 7
        self._guest_re = re.compile(r"^\*\*\*\s*(\d+)$")

    def _resolve_slot(self, token: str, players: dict, guest_id: int):
        """
        token : string tapé dans la commande (pseudo, mention, ou *** 7)
        players : dict des joueurs enregistrés
        guest_id : id négatif courant pour générer un invité

        Retourne:
          (player_id, name, rating, is_guest, new_guest_id)

        Règles :
        - token = '*** 7' ou '***7' -> invité note 7 (1–10)
        - @mention -> joueur existant, note venant du profil
        - pseudo exact d'un joueur -> joueur existant, note venant du profil
        - sinon -> erreur
        """
        token = token.strip()

        # 1) Cas invité *** 7
        m_guest = self._guest_re.fullmatch(token)
        if m_guest:
            note = int(m_guest.group(1))
            if note < 1 or note > 10:
                raise ValueError(f"La note pour l'invité doit être entre 1 et 10 (reçu: {note}).")
            name = "Invité"
            rating = note
            return guest_id, name, rating, True, guest_id - 1

        # 2) Cas mention <@123...>
        m_mention = self._mention_re.fullmatch(token)
        if m_mention:
            uid = int(m_mention.group(1))
            pdata = players.get(str(uid))
            if not pdata:
                raise ValueError(f"{token} n'a pas de profil (/set_joueur).")
            name = pdata["name"]
            rating = pdata["rating"]
            return uid, name, rating, False, guest_id

        # 3) Cas pseudo exact d'un joueur enregistré
        for p in players.values():
            if p["name"].lower() == token.lower():
                return p["id"], p["name"], p["rating"], False, guest_id

        # 4) Sinon -> erreur explicite
        raise ValueError(
            f"Le joueur `{token}` n'existe pas dans la base.\n"
            f"- Utilise `/set_joueur` pour l'enregistrer, ou\n"
            f"- utilise `*** 7` pour un invité (*** + note)."
        )

    # ---------------- CREER MATCH ----------------

    @app_commands.command(
        name="creer_match",
        description="Crée un match 5v5 équilibré. Utilise des pseudos/mentions, ou `*** 7` pour un invité."
    )
    @app_commands.describe(
        joueur1="Pseudo / mention / `*** 7` pour invité",
        joueur2="Pseudo / mention / `*** 7` pour invité",
        joueur3="Pseudo / mention / `*** 7` pour invité",
        joueur4="Pseudo / mention / `*** 7` pour invité",
        joueur5="Pseudo / mention / `*** 7` pour invité",
        joueur6="Pseudo / mention / `*** 7` pour invité",
        joueur7="Pseudo / mention / `*** 7` pour invité",
        joueur8="Pseudo / mention / `*** 7` pour invité",
        joueur9="Pseudo / mention / `*** 7` pour invité",
        joueur10="Pseudo / mention / `*** 7` pour invité",
    )
    async def creer_match(
        self,
        interaction: discord.Interaction,
        joueur1: str,
        joueur2: str,
        joueur3: str,
        joueur4: str,
        joueur5: str,
        joueur6: str,
        joueur7: str,
        joueur8: str,
        joueur9: str,
        joueur10: str,
    ):
        slots = [
            joueur1, joueur2, joueur3, joueur4, joueur5,
            joueur6, joueur7, joueur8, joueur9, joueur10
        ]

        players_data = self.data.get_players()
        guest_id = -1
        match_players = {}        # id -> {name, rating, is_guest}
        players_with_rating = []  # (id, rating)

        # Résolution de chaque pseudo / mention / *** 7
        try:
            for token in slots:
                pid, name, rating, is_guest, guest_id = self._resolve_slot(
                    token, players_data, guest_id
                )
                match_players[pid] = {
                    "name": name,
                    "rating": rating,
                    "is_guest": is_guest,
                }
                players_with_rating.append((pid, rating))
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return

        # Équilibrage des équipes (invités inclus)
        team_a_ids, team_b_ids, sum_a, sum_b = balance_teams(players_with_rating)

        # Enregistrement du match
        match = self.data.create_match(team_a_ids, team_b_ids, interaction.channel_id)

        total_a = sum(match_players[pid]["rating"] for pid in team_a_ids)
        total_b = sum(match_players[pid]["rating"] for pid in team_b_ids)

        if total_a > total_b:
            favorite = "Équipe A 🔴"
        elif total_b > total_a:
            favorite = "Équipe B 🔵"
        else:
            favorite = "Équipes à égalité ⚖️"

        # Tableau côte à côte
        # Tableau vertical lisible pour téléphone
        lines = []

        lines.append("🔴 ÉQUIPE A")
        for idx, pid in enumerate(team_a_ids, start=1):
            p = match_players[pid]
            lines.append(f"{idx}. {p['name']} ({p['rating']}/10)")

        lines.append("")  # espace

        lines.append("🔵 ÉQUIPE B")
        for idx, pid in enumerate(team_b_ids, start=1):
            p = match_players[pid]
            lines.append(f"{idx}. {p['name']} ({p['rating']}/10)")

        teams_table = "```txt\n" + "\n".join(lines) + "\n```"


        description = (
            f"**Match #{match['id']}** créé !\n\n"
            f"🔴 **Équipe A** (Total: **{total_a}**)\n"
            f"🔵 **Équipe B** (Total: **{total_b}**)\n\n"
            f"{teams_table}\n"
            f"**Équipe favorite** : {favorite}\n\n"
            f"➡️ Pensez à noter l'ID du match : **#{match['id']}** "
            f"(utile pour le résultat, le MVP et les stats)."
        )

        embed = discord.Embed(
            title=f"⚽ Match #{match['id']}",
            description=description,
            color=discord.Color.orange()
        )
        embed.set_footer(
            text="Utilise /resultat_match pour le score, puis /vote_mvp et /ajouter_stats (pour les joueurs du Discord)."
        )

        await interaction.response.send_message(embed=embed)

    # ---------------- RESULTAT MATCH ----------------

    @app_commands.command(name="resultat_match", description="Enregistre le résultat d'un match (score).")
    @app_commands.describe(
        match_id="ID du match (affiché lors de /creer_match)",
        score_equipe_a="Buts de l'équipe A",
        score_equipe_b="Buts de l'équipe B"
    )
    async def resultat_match(
        self,
        interaction: discord.Interaction,
        match_id: int,
        score_equipe_a: int,
        score_equipe_b: int
    ):
        match = self.data.get_match(match_id)
        if not match:
            await interaction.response.send_message("❌ Match introuvable.", ephemeral=True)
            return

        if match["result_recorded"]:
            await interaction.response.send_message("⚠️ Le résultat de ce match est déjà enregistré.", ephemeral=True)
            return

        match = self.data.update_match(
            match_id,
            score_a=score_equipe_a,
            score_b=score_equipe_b,
            result_recorded=True
        )

        # Tous les joueurs connus (id > 0) prennent un match joué
        for pid in match["team_a"] + match["team_b"]:
            if pid > 0:
                self.data.increment_player_stats(pid, matches=1)

        # Victoire / défaite / nul + points
        if score_equipe_a > score_equipe_b:
            winners = match["team_a"]
            losers = match["team_b"]
            msg_result = "Victoire de **l'équipe A 🔴**"
        elif score_equipe_b > score_equipe_a:
            winners = match["team_b"]
            losers = match["team_a"]
            msg_result = "Victoire de **l'équipe B 🔵**"
        else:
            winners = []
            losers = []
            msg_result = "Match **nul**."

        if winners:
            for pid in winners:
                if pid > 0:
                    self.data.increment_player_stats(pid, wins=1, points=1)
            for pid in losers:
                if pid > 0:
                    self.data.increment_player_stats(pid, losses=1)
        else:
            for pid in match["team_a"] + match["team_b"]:
                if pid > 0:
                    self.data.increment_player_stats(pid, draws=1)

        embed = discord.Embed(
            title=f"📌 Résultat du match #{match_id}",
            description=(
                f"{msg_result}\n\n"
                f"🔴 Équipe A : **{score_equipe_a}**\n"
                f"🔵 Équipe B : **{score_equipe_b}**\n\n"
                "Les joueurs peuvent maintenant utiliser `/vote_mvp` et `/ajouter_stats` avec l'ID du match."
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    # ---------------- MVP ----------------

    @app_commands.command(name="vote_mvp", description="Vote pour le MVP d'un match.")
    @app_commands.describe(
        match_id="ID du match",
        joueur="Joueur pour lequel tu votes MVP (doit avoir joué le match)"
    )
    async def vote_mvp(
        self,
        interaction: discord.Interaction,
        match_id: int,
        joueur: discord.Member
    ):
        match = self.data.get_match(match_id)
        if not match:
            await interaction.response.send_message("❌ Match introuvable.", ephemeral=True)
            return

        # Vérifier si le joueur a joué le match
        if joueur.id not in match["team_a"] and joueur.id not in match["team_b"]:
            await interaction.response.send_message(
                "❌ Ce joueur n'a pas participé à ce match (ou c'est un invité).",
                ephemeral=True
            )
            return

        # Vérifier si le vote est encore ouvert
        if not match.get("mvp_open", True):
            await interaction.response.send_message(
                f"⚠️ Le vote MVP est déjà clôturé pour le match #{match_id}.",
                ephemeral=True
            )
            return

        # Empêcher plusieurs votes pour le même match par la même personne
        mvp_votes = match.get("mvp_votes", {}) or {}
        voter_key = str(interaction.user.id)
        if voter_key in mvp_votes:
            await interaction.response.send_message(
                f"⚠️ Tu as déjà voté pour le MVP du match #{match_id}.",
                ephemeral=True
            )
            return

        # Enregistrer le vote
        self.data.add_mvp_vote(match_id, interaction.user.id, joueur.id)

        await interaction.response.send_message(
            f"✅ Ton vote pour **{joueur.display_name}** a été pris en compte pour le match #{match_id}.",
            ephemeral=True
        )

    #fin mvp

    @app_commands.command(
        name="fin_mvp",
        description="Clôture le vote MVP d'un match et affiche le résultat des votes."
    )
    @app_commands.describe(
        match_id="ID du match pour lequel tu veux clôturer/voir le MVP"
    )
    async def fin_mvp(
        self,
        interaction: discord.Interaction,
        match_id: int,
    ):
        match = self.data.get_match(match_id)
        if not match:
            await interaction.response.send_message("❌ Match introuvable.", ephemeral=True)
            return

        was_open = match.get("mvp_open", True)
        votes = match.get("mvp_votes", {}) or {}

        # Aucun vote → rien à attribuer
        if not votes:
            if was_open:
                # On ferme quand même le vote pour ce match
                self.data.update_match(match_id, mvp_open=False, mvp_winners=[])
                text = (
                    f"🕒 Vote MVP clôturé pour le match #{match_id}, "
                    f"mais aucun vote n'a été enregistré.\n"
                    f"Aucun MVP n'est attribué."
                )
            else:
                text = (
                    f"ℹ️ Le vote MVP pour le match #{match_id} était déjà clôturé, "
                    f"et aucun vote n'a été enregistré.\n"
                    f"Aucun MVP n'a été attribué."
                )
            await interaction.response.send_message(text)
            return

        # Tally des votes : target_id -> nb_votes (on cast en int)
        tally: dict[int, int] = {}
        for _voter_key, target in votes.items():
            try:
                pid = int(target)
            except (TypeError, ValueError):
                continue
            tally[pid] = tally.get(pid, 0) + 1

        if not tally:
            # Sécurité : votes illisibles
            await interaction.response.send_message(
                f"❌ Impossible de lire les votes MVP pour le match #{match_id}.",
                ephemeral=True
            )
            return

        max_votes = max(tally.values())
        top_candidates = [pid for pid, c in tally.items() if c == max_votes]

        winners = top_candidates  # ceux qui sont en tête (égalité possible)
        players_data = self.data.get_players()

        def name_for(pid: int) -> str:
            pdata = players_data.get(str(pid))
            if pdata and "name" in pdata:
                return pdata["name"]
            member = interaction.guild.get_member(pid) if interaction.guild else None
            if member:
                return member.display_name
            return f"<@{pid}>"

        # 👉 Attribution des points / MVP UNIQUEMENT si le vote était encore ouvert
        if was_open:
            total_points = 1.0
            share = total_points / len(winners)  # ex: 0.5 si 2, 0.33 si 3, etc.

            for pid in winners:
                # On ignore les invités (ids négatifs)
                if pid > 0:
                    self.data.increment_player_stats(pid, points=share, mvps=1)

            # On ferme définitivement le vote
            self.data.update_match(match_id, mvp_open=False, mvp_winners=winners)
            just_closed = True
        else:
            just_closed = False

        # On relit le match au cas où
        match = self.data.get_match(match_id) or match

        # Construction du détail des votes
        lines = []
        for pid, count in sorted(tally.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"• **{name_for(pid)}** — {count} vote(s)")

        # Texte selon le nb de gagnants
        if len(winners) == 1:
            mvp_name = name_for(winners[0])
            if just_closed:
                mvp_line = f"🏆 **MVP du match : {mvp_name}** (1 point & +1 MVP)."
                footer_info = "Le vote vient d'être clôturé. Les points MVP ont été attribués maintenant."
            else:
                mvp_line = f"🏆 **MVP du match : {mvp_name}** (points déjà attribués auparavant)."
                footer_info = "Le vote était déjà clôturé. Aucun nouveau point n'a été ajouté."
        else:
            winners_names = ", ".join(name_for(pid) for pid in winners)
            share = 1.0 / len(winners)
            share_str = f"{share:.2f}".rstrip("0").rstrip(".")  # 0.5 → '0.5', 0.33 → '0.33'
            if just_closed:
                mvp_line = (
                    f"🏆 **MVP ex æquo : {winners_names}**\n"
                    f"Ils se partagent 1 point, soit {share_str} pt chacun (+1 MVP chacun)."
                )
                footer_info = "Le vote vient d'être clôturé. Les points MVP ont été attribués maintenant."
            else:
                mvp_line = (
                    f"🏆 **MVP ex æquo : {winners_names}**\n"
                    f"Ils se sont partagés 1 point lors de la clôture précédente."
                )
                footer_info = "Le vote était déjà clôturé auparavant. Aucun nouveau point n'a été ajouté."

        headline = (
            f"🏁 Vote MVP clôturé pour le match #{match_id}"
            if just_closed
            else f"ℹ️ Résultat du vote MVP pour le match #{match_id}"
        )

        embed = discord.Embed(
            title=headline,
            description=(
                mvp_line
                + "\n\n**Détail des votes :**\n"
                + "\n".join(lines)
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text=footer_info)

        await interaction.response.send_message(embed=embed)

    # ---------------- AJOUTER STATS ----------------

    @app_commands.command(name="ajouter_stats", description="Ajoute les stats (buts / passes) d'un joueur pour un match.")
    @app_commands.describe(
        match_id="ID du match concerné",
        joueur="Joueur du Discord concerné",
        buts="Nombre de buts à ajouter pour ce match",
        passes="Nombre de passes décisives à ajouter pour ce match"
    )
    async def ajouter_stats(
        self,
        interaction: discord.Interaction,
        match_id: int,
        joueur: discord.Member,
        buts: int = 0,
        passes: int = 0
    ):
        match = self.data.get_match(match_id)
        if not match:
            await interaction.response.send_message("❌ Match introuvable.", ephemeral=True)
            return

        # Vérifier que le joueur a participé au match
        if joueur.id not in match["team_a"] and joueur.id not in match["team_b"]:
            await interaction.response.send_message(
                "❌ Ce joueur n'a pas participé à ce match (ou c'est un invité).",
                ephemeral=True
            )
            return

        player = self.data.get_player(joueur.id)
        if not player:
            await interaction.response.send_message(
                "❌ Ce joueur n'est pas encore enregistré (/set_joueur).",
                ephemeral=True
            )
            return

        # Vérifier si les stats ont déjà été saisies pour ce joueur sur ce match
        stats_entered = match.get("stats_entered", {})
        pid_str = str(joueur.id)
        if stats_entered.get(pid_str):
            await interaction.response.send_message(
                f"⚠️ Les stats de **{joueur.display_name}** ont déjà été renseignées pour le match #{match_id}.",
                ephemeral=True
            )
            return

        # Mise à jour des stats globales du joueur
        self.data.increment_player_stats(joueur.id, goals=buts, assists=passes)

        # Marquer les stats comme saisies pour ce match
        stats_entered[pid_str] = True
        self.data.update_match(match_id, stats_entered=stats_entered)

        updated = self.data.get_player(joueur.id)

        embed = discord.Embed(
            title=f"📈 Stats mises à jour — Match #{match_id}",
            description=f"Joueur : {joueur.mention}",
            color=discord.Color.blue()
        )
        if buts:
            embed.add_field(name="Buts ajoutés (pour ce match)", value=str(buts), inline=True)
        if passes:
            embed.add_field(name="Passes décisives ajoutées (pour ce match)", value=str(passes), inline=True)

        embed.add_field(name="Total buts (tous matchs)", value=str(updated["goals"]), inline=True)
        embed.add_field(name="Total passes (tous matchs)", value=str(updated["assists"]), inline=True)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Matches(bot))
