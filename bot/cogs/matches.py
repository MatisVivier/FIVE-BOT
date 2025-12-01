import re
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from itertools import combinations

# Poids des stats pour l'équilibrage
STAT_WEIGHTS = {
    "tir": 5.0,
    "passes": 5.0,
    "influence": 4.5,
    "physique": 2.5,
    "gardien": 2.0,
}

# Clés de stats qu'on calcule comme moyennes par équipe (affichage)
STAT_AVG_KEYS = ("tir", "passes", "physique", "influence", "gardien", "rating")


def _compute_team_avgs(team_ids: list[int], players_stats: dict[int, dict[str, float]]):
    """Calcule les moyennes de stats pour une équipe."""
    n = len(team_ids)
    if n == 0:
        return {k: 0.0 for k in STAT_AVG_KEYS}

    sums = {k: 0.0 for k in STAT_AVG_KEYS}
    for pid in team_ids:
        stats = players_stats[pid]
        for k in STAT_AVG_KEYS:
            sums[k] += float(stats.get(k, 0.0))

    return {k: sums[k] / n for k in STAT_AVG_KEYS}


def balance_teams(players_stats: dict[int, dict[str, float]]):
    """
    players_stats : {id: {tir, passes, physique, influence, gardien, rating}, ...}
    Retourne (team_a_ids, team_b_ids, avgs_a, avgs_b)

    On teste toutes les combinaisons possibles (C(10,5)=252),
    et on prend celle qui minimise la différence de stats pondérée
    avec les poids définis dans STAT_WEIGHTS.
    """
    ids = list(players_stats.keys())
    n = len(ids)
    if n % 2 != 0:
        raise ValueError("Le nombre de joueurs doit être pair pour créer 2 équipes.")

    half = n // 2
    best = None
    best_cost = None

    for combo in combinations(ids, half):
        team_a = list(combo)
        team_b = [pid for pid in ids if pid not in combo]

        avgs_a = _compute_team_avgs(team_a, players_stats)
        avgs_b = _compute_team_avgs(team_b, players_stats)

        # coût = somme des écarts au carré sur chaque stat, pondéré
        cost = 0.0
        for key, weight in STAT_WEIGHTS.items():
            diff = avgs_a[key] - avgs_b[key]
            cost += weight * (diff ** 2)

        # On choisit la combinaison avec le coût minimal
        if best is None or cost < best_cost:
            best_cost = cost
            best = (team_a, team_b, avgs_a, avgs_b)

    if best is None:
        raise RuntimeError("Impossible de calculer un équilibrage d'équipes.")

    return best  # team_a_ids, team_b_ids, avgs_a, avgs_b


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
          (player_id, name, rating, is_guest, stats_dict, new_guest_id)

        stats_dict contient :
          tir, passes, physique, influence, gardien, rating
        """
        token = token.strip()

        # 1) Cas invité *** 7
        m_guest = self._guest_re.fullmatch(token)
        if m_guest:
            note = int(m_guest.group(1))
            if note < 1 or note > 10:
                raise ValueError(f"La note pour l'invité doit être entre 1 et 10 (reçu: {note}).")

            name = "Invité"
            rating = float(note)
            # Pour un invité, on met toutes les stats à la même valeur
            stats = {
                "rating": rating,
                "tir": rating,
                "passes": rating,
                "physique": rating,
                "influence": rating,
                "gardien": rating,
            }
            return guest_id, name, rating, True, stats, guest_id - 1

        # 2) Cas mention <@123...>
        m_mention = self._mention_re.fullmatch(token)
        if m_mention:
            uid = int(m_mention.group(1))
            pdata = players.get(str(uid))
            if not pdata:
                raise ValueError(f"{token} n'a pas de profil (/set_joueur).")

            name = pdata["name"]
            rating = float(pdata["rating"])
            stats = {
                "rating": rating,
                "tir": float(pdata.get("tir", rating)),
                "passes": float(pdata.get("passes", rating)),
                "physique": float(pdata.get("physique", rating)),
                "influence": float(pdata.get("influence", rating)),
                "gardien": float(pdata.get("gardien", rating)),
            }
            return uid, name, rating, False, stats, guest_id

        # 3) Cas pseudo exact d'un joueur enregistré
        for p in players.values():
            if p["name"].lower() == token.lower():
                rating = float(p["rating"])
                stats = {
                    "rating": rating,
                    "tir": float(p.get("tir", rating)),
                    "passes": float(p.get("passes", rating)),
                    "physique": float(p.get("physique", rating)),
                    "influence": float(p.get("influence", rating)),
                    "gardien": float(p.get("gardien", rating)),
                }
                return p["id"], p["name"], rating, False, stats, guest_id

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
        match_players = {}        # id -> {name, rating, is_guest, stats}
        players_stats = {}        # id -> stats dict (tir, passes, ...)

        # Résolution de chaque pseudo / mention / *** 7
        try:
            for token in slots:
                pid, name, rating, is_guest, stats, guest_id = self._resolve_slot(
                    token, players_data, guest_id
                )
                match_players[pid] = {
                    "name": name,
                    "rating": rating,
                    "is_guest": is_guest,
                    "stats": stats,
                }
                players_stats[pid] = stats
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
            return

        # Équilibrage multi-stats pondéré
        team_a_ids, team_b_ids, avgs_a, avgs_b = balance_teams(players_stats)

        # Enregistrement du match
        match = self.data.create_match(team_a_ids, team_b_ids, interaction.channel_id)

        avg_rating_a = avgs_a["rating"]
        avg_rating_b = avgs_b["rating"]

        if avg_rating_a > avg_rating_b:
            favorite = "Équipe A 🔴"
        elif avg_rating_b > avg_rating_a:
            favorite = "Équipe B 🔵"
        else:
            favorite = "Équipes à égalité ⚖️"

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

        # Résumé des moyennes de stats par équipe
        def fmt_avgs(label: str, avgs: dict[str, float]) -> str:
            return (
                f"{label} — moyennes :\n"
                f"- Tir : **{avgs['tir']:.1f}**\n"
                f"- Passes : **{avgs['passes']:.1f}**\n"
                f"- Physique : **{avgs['physique']:.1f}**\n"
                f"- Influence : **{avgs['influence']:.1f}**\n"
                f"- Gardien : **{avgs['gardien']:.1f}**\n"
                f"- Note globale : **{avgs['rating']:.1f}**"
            )

        description = (
            f"**Match #{match['id']}** créé !\n\n"
            f"{fmt_avgs('🔴 Équipe A', avgs_a)}\n\n"
            f"{fmt_avgs('🔵 Équipe B', avgs_b)}\n\n"
            f"{teams_table}\n"
            f"**Équipe favorite** (sur la note globale moyenne) : {favorite}\n\n"
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

    # ---------------- FIN MVP ----------------

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
            share_str = f"{share:.2f}".rstrip("0").rstrip(".")
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

    @app_commands.command(
        name="supprimer_match",
        description="Supprime définitivement un match à partir de son ID."
    )
    @app_commands.describe(
        match_id="ID du match à supprimer (affiché lors de /creer_match)."
    )
    async def supprimer_match(
        self,
        interaction: discord.Interaction,
        match_id: int
    ):
        # On vérifie d'abord s'il existe
        match = self.data.get_match(match_id)
        if not match:
            await interaction.response.send_message(
                f"❌ Aucun match trouvé avec l'ID **#{match_id}**.",
                ephemeral=True
            )
            return

        # Optionnel : tu peux protéger la commande pour que seuls les admins l'utilisent
        # if not interaction.user.guild_permissions.administrator:
        #     await interaction.response.send_message(
        #         "❌ Tu n'as pas la permission de supprimer des matchs.",
        #         ephemeral=True
        #     )
        #     return

        removed = self.data.delete_match(match_id)
        if not removed:
            await interaction.response.send_message(
                f"❌ Impossible de supprimer le match **#{match_id}** (erreur interne).",
                ephemeral=True
            )
            return

        # Petit récap dans l'embed
        score_a = removed.get("score_a")
        score_b = removed.get("score_b")

        if score_a is not None and score_b is not None:
            score_txt = f"Score enregistré : 🔴 {score_a} - {score_b} 🔵"
        else:
            score_txt = "Aucun score n'avait encore été enregistré pour ce match."

        embed = discord.Embed(
            title=f"🗑️ Match #{match_id} supprimé",
            description=(
                "Le match a été retiré de l'historique.\n\n"
                f"{score_txt}\n\n"
                "_Les stats déjà ajoutées aux joueurs **ne sont pas modifiées**._"
            ),
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Matches(bot))
