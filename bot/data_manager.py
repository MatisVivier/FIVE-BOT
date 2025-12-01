import json
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone


class DataManager:
    def __init__(self, path: str = "data/data.json"):
        self.path = Path(path)
        self.lock = Lock()
        self._ensure_file()

    def _ensure_file(self):
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            # Fichier inexistant → on crée une structure propre
            self._write({
                "players": {},
                "matches": {},
                "last_match_id": 0
            })
        else:
            # Fichier existant → on vérifie que la structure a bien toutes les clés
            data = self._read()
            changed = False

            if "players" not in data or not isinstance(data["players"], dict):
                data["players"] = {}
                changed = True

            if "matches" not in data or not isinstance(data["matches"], dict):
                data["matches"] = {}
                changed = True

            if "last_match_id" not in data or not isinstance(data["last_match_id"], int):
                data["last_match_id"] = 0
                changed = True

            if changed:
                self._write(data)

    def _read(self):
        with self.lock:
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)

    def _write(self, data):
        with self.lock:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    # ---------- PLAYERS ----------

    def get_players(self):
        data = self._read()
        players = data["players"]

        # modèle de base pour forcer tous les champs à exister
        base_template = {
            "id": None,
            "name": "",
            # Note globale sur 10 (moyenne des 5 stats)
            "rating": 0,

            # 🔢 Nouvelles stats détaillées
            "tir": 0,
            "passes": 0,
            "physique": 0,
            "influence": 0,
            "gardien": 0,

            # Stats de matchs
            "points": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "matches": 0,
            "goals": 0,
            "assists": 0,
            "mvps": 0,

            "card_color": "#1E1E46",   # bleu/violet par défaut
            "card_tagline": "",
            "card_border": "#D4AF37",
        }

        changed = False
        for pid, player in players.items():
            for key, default_value in base_template.items():
                if key not in player:
                    # pour 'id', on met l'id de la clé si absent
                    if key == "id":
                        player[key] = int(pid)
                    else:
                        player[key] = default_value
                    changed = True

        if changed:
            # on réécrit le fichier une fois pour tout remettre propre
            self._write(data)

        return players

    def get_player(self, user_id: int):
        players = self.get_players()
        return players.get(str(user_id))

    def upsert_player(
        self,
        user_id: int,
        name: str,
        tir: int,
        passes: int,
        physique: int,
        influence: int,
        gardien: int,
    ):
        """
        Crée ou met à jour un joueur avec 5 stats.
        La note globale `rating` = moyenne des 5 stats.
        """
        data = self._read()
        pid = str(user_id)

        # sécurité : clamp entre 0 et 10
        def clamp_stat(value: int) -> int:
            try:
                v = int(value)
            except ValueError:
                v = 0
            return max(0, min(10, v))

        tir = clamp_stat(tir)
        passes = clamp_stat(passes)
        physique = clamp_stat(physique)
        influence = clamp_stat(influence)
        gardien = clamp_stat(gardien)

        # moyenne des 5 stats
        rating = (tir + passes + physique + influence + gardien) / 5
        rating = round(rating, 1)

        # modèle de base pour être sûr que tous les champs existent
        base_template = {
            "id": user_id,
            "name": name,
            "rating": rating,

            "tir": tir,
            "passes": passes,
            "physique": physique,
            "influence": influence,
            "gardien": gardien,

            "points": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "matches": 0,
            "goals": 0,
            "assists": 0,
            "mvps": 0,
            "card_color": "#1E1E46",
            "card_tagline": "",
            "card_border": "#D4AF37",
        }

        if pid not in data["players"]:
            # Nouveau joueur → on prend le template complet
            data["players"][pid] = base_template
        else:
            # Joueur existant → on met à jour nom + stats + rating
            player = data["players"][pid]
            player["name"] = name
            player["rating"] = rating
            player["tir"] = tir
            player["passes"] = passes
            player["physique"] = physique
            player["influence"] = influence
            player["gardien"] = gardien

            # On complète les clés manquantes (cas vieux data.json)
            for key, default_value in base_template.items():
                if key not in player:
                    player[key] = default_value

        self._write(data)
        return data["players"][pid]

    def update_player_stats(self, user_id: int, **kwargs):
        data = self._read()
        pid = str(user_id)
        if pid not in data["players"]:
            return None
        player = data["players"][pid]
        for key, value in kwargs.items():
            if key in player:
                player[key] = value
        self._write(data)
        return player

    def increment_player_stats(self, user_id: int, **kwargs):
        data = self._read()
        pid = str(user_id)
        if pid not in data["players"]:
            return None
        player = data["players"][pid]
        for key, delta in kwargs.items():
            if key in player and isinstance(delta, (int, float)):
                player[key] += delta
        self._write(data)
        return player

    # ---------- MATCHES ----------

    def create_match(self, team_a_ids, team_b_ids, channel_id: int):
        data = self._read()

        # Sécurité au cas où last_match_id n'existe toujours pas pour une raison quelconque
        if "last_match_id" not in data or not isinstance(data["last_match_id"], int):
            data["last_match_id"] = 0

        data["last_match_id"] += 1
        match_id = data["last_match_id"]

        now = datetime.now(timezone.utc).isoformat()

        if "matches" not in data or not isinstance(data["matches"], dict):
            data["matches"] = {}

        data["matches"][str(match_id)] = {
            "id": match_id,
            "channel_id": channel_id,
            "created_at": now,
            "team_a": team_a_ids,
            "team_b": team_b_ids,
            "score_a": None,
            "score_b": None,
            "result_recorded": False,
            "mvp_open": True,
            "mvp_votes": {},      # voter_id -> target_player_id
            "stats_entered": {}   # player_id -> True (stats déjà ajoutées pour ce match)
        }

        self._write(data)
        return data["matches"][str(match_id)]

    def delete_match(self, match_id: int | str):
        """Supprime un match du fichier data.json. Retourne le match supprimé ou None."""
        data = self._read()
        mid = str(match_id)

        if "matches" not in data or mid not in data["matches"]:
            return None

        removed = data["matches"].pop(mid)
        self._write(data)
        return removed

    def get_match(self, match_id: int | str):
        data = self._read()
        return data["matches"].get(str(match_id))

    def update_match(self, match_id: int | str, **kwargs):
        data = self._read()
        mid = str(match_id)
        if mid not in data["matches"]:
            return None
        match = data["matches"][mid]
        for key, value in kwargs.items():
            match[key] = value
        self._write(data)
        return match

    def add_mvp_vote(self, match_id: int | str, voter_id: int, target_player_id: int):
        data = self._read()
        mid = str(match_id)
        if mid not in data["matches"]:
            return None
        data["matches"][mid]["mvp_votes"][str(voter_id)] = str(target_player_id)
        self._write(data)
        return data["matches"][mid]

    def finalize_mvp(self, match_id: int):
        """Clôture le vote MVP, attribue les points et renvoie (match, winners_ids)."""
        data = self._read()
        match = data["matches"].get(str(match_id))
        if not match:
            raise ValueError(f"Match {match_id} introuvable.")

        # Si déjà clôturé, on ne ré-attribue pas les points
        if not match.get("mvp_open", True):
            winners = match.get("mvp_winners", [])
            return match, winners

        votes = match.get("mvp_votes", {}) or {}
        winners: list[int] = []

        if votes:
            # Tally des votes : on force les IDs en int
            tally: dict[int, int] = {}
            for _voter_str, target_str in votes.items():
                try:
                    pid = int(target_str)
                except (TypeError, ValueError):
                    continue
                tally[pid] = tally.get(pid, 0) + 1

            if tally:
                max_votes = max(tally.values())
                winners = [pid for pid, c in tally.items() if c == max_votes]

                # Partage de 1 point entre tous les gagnants (égalité possible)
                total_points = 1.0
                share = total_points / len(winners)

                for pid in winners:
                    # On ignore les invités (ids négatifs)
                    if pid > 0:
                        self.increment_player_stats(pid, points=share, mvps=1)

        # On marque le vote comme clôturé et on stocke les gagnants
        match["mvp_open"] = False
        match["mvp_winners"] = winners

        data["matches"][str(match_id)] = match
        self._write(data)
        return match, winners
