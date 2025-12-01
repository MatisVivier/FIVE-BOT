import discord
from discord.ext import commands
from discord import app_commands

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

class Players(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data = bot.data_manager

    # -------------------------------------------------
    # Embed pour confirmation mise à jour joueur
    # -------------------------------------------------
    def _rating_embed(self, member: discord.Member, player_data: dict) -> discord.Embed:
        embed = discord.Embed(
            title="Profil joueur mis à jour",
            description=f"Joueur : {member.mention}",
            color=discord.Color.green()
        )

        # 🟢 Résumé
        resume_value = (
            f"**Note globale :** {player_data['rating']}/10\n"
            f"**Points :** {player_data['points']}\n"
            f"**Matches joués :** {player_data.get('matches', 0)}"
        )
        embed.add_field(name="----- Résumé -----", value=resume_value, inline=False)

        # ⚙️ Notes techniques
        techniques_value = (
            f"**Tir :** {player_data['tir']}/10\n"
            f"**Passes :** {player_data['passes']}/10\n"
            f"**Physique :** {player_data['physique']}/10\n"
            f"**Influence :** {player_data['influence']}/10\n"
            f"**Gardien :** {player_data['gardien']}/10"
        )
        embed.add_field(name="----- Notes techniques -----", value=techniques_value, inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)
        return embed
    
    # -------------------------------------------------
    # /set_joueur — Définir les 5 stats
    # -------------------------------------------------
    @app_commands.command(
        name="set_joueur",
        description="Créer ou modifier un joueur avec 5 stats (tir, passes, physique, influence, gardien)."
    )
    @app_commands.describe(
        joueur="Le joueur à créer ou mettre à jour",
        tir="Note en tir (0-10)",
        passes="Note en passes (0-10)",
        physique="Note en physique (0-10)",
        influence="Influence sur le jeu (0-10)",
        gardien="Note en gardien (0-10, 0 si joueur de champ)"
    )
    async def set_joueur(
        self,
        interaction: discord.Interaction,
        joueur: discord.Member,
        tir: app_commands.Range[int, 0, 10],
        passes: app_commands.Range[int, 0, 10],
        physique: app_commands.Range[int, 0, 10],
        influence: app_commands.Range[int, 0, 10],
        gardien: app_commands.Range[int, 0, 10],
    ):
        # Mise à jour via DataManager
        player = self.data.upsert_player(
            user_id=joueur.id,
            name=joueur.display_name,
            tir=tir,
            passes=passes,
            physique=physique,
            influence=influence,
            gardien=gardien,
        )

        embed = self._rating_embed(joueur, player)
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------
    # /liste_joueurs — Tri par rating global
    # -------------------------------------------------
    @app_commands.command(name="liste_joueurs", description="Affiche la liste de tous les joueurs.")
    async def liste_joueurs(self, interaction: discord.Interaction):
        players = self.data.get_players()

        if not players:
            await interaction.response.send_message("Aucun joueur enregistré pour le moment.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Liste des joueurs",
            color=discord.Color.blurple()
        )

        # tri par note globale décroissante
        sorted_players = sorted(players.values(), key=lambda p: p["rating"], reverse=True)

        lines = []
        for p in sorted_players:
            lines.append(
                f"**{p['name']}** — {p['rating']}/10 — {p['points']} pts"
            )

        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 1000:
                embed.add_field(name="\u200b", value=chunk, inline=False)
                chunk = ""
            chunk += line + "\n"

        if chunk:
            embed.add_field(name="\u200b", value=chunk, inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
    name="personnaliser_carte",
    description="Personnalise ta carte (couleur fond, bordure et texte)."
    )
    @app_commands.describe(
        couleur="Couleur de fond (#FF8800, bleu, violet, etc.)",
        bordure="Couleur de bordure (#FFD700, or, rouge, etc.)",
        texte="Petit texte perso (optionnel)."
    )
    async def personnaliser_carte(
        self,
        interaction: discord.Interaction,
        couleur: str,
        bordure: str = None,
        texte: str | None = None
    ):
        user = interaction.user
        player = self.data.get_player(user.id)

        if not player:
            await interaction.response.send_message(
                "❌ Tu n'es pas encore enregistré. Utilise `/set_joueur`.",
                ephemeral=True
            )
            return

        updates = {"card_color": couleur}

        if bordure:
            updates["card_border"] = bordure

        if texte is not None:
            if len(texte) > 40:
                await interaction.response.send_message(
                    "❌ Ton texte est trop long (max 40 caractères).",
                    ephemeral=True
                )
                return
            updates["card_tagline"] = texte.strip()

        self.data.update_player_stats(user.id, **updates)

        desc = f"🎨 **Ta carte a été personnalisée !**\n\n• Fond : `{couleur}`"
        if bordure:
            desc += f"\n• Bordure : `{bordure}`"
        if texte is not None:
            desc += f"\n• Texte : `{texte or '(supprimé)'}`"

        embed = discord.Embed(title="Personnalisation mise à jour", description=desc, color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _build_fut_card(self, member: discord.Member, player: dict, avatar_bytes: bytes) -> BytesIO:
        """Génère une carte style FUT et renvoie un buffer PNG prêt à être envoyé."""
        from PIL import Image, ImageDraw, ImageFont

        # ---------- Petites fonctions utilitaires ----------

        def text_size(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
            try:
                bbox = font.getbbox(text)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                return w, h
            except Exception:
                return font.getlength(text), font.size

        def parse_color(color_str: str, default=(30, 30, 70)):
            """
            Attend un #RRGGBB, sinon quelques noms FR simples,
            sinon fallback sur default.
            """
            if not isinstance(color_str, str):
                return default

            color_str = color_str.strip().lower()

            # noms de couleurs simples
            named = {
                "rouge": (200, 40, 40),
                "bleu": (40, 80, 200),
                "vert": (40, 160, 80),
                "violet": (120, 60, 180),
                "or": (212, 175, 55),
                "gold": (212, 175, 55),
                "noir": (10, 10, 10),
                "blanc": (230, 230, 230),
            }
            if color_str in named:
                return named[color_str]

            # hex
            if color_str.startswith("#") and len(color_str) == 7:
                try:
                    r = int(color_str[1:3], 16)
                    g = int(color_str[3:5], 16)
                    b = int(color_str[5:7], 16)
                    return (r, g, b)
                except ValueError:
                    pass

            return default

        # ---------- Dimensions et image de base ----------

        width, height = 400, 600
        img = Image.new("RGBA", (width, height), (15, 15, 35, 255))
        draw = ImageDraw.Draw(img)

        # Couleur personnalisée de base
        base_color = parse_color(player.get("card_color", "#1E1E46"))
        br, bg, bb = base_color

        # Dégradé vertical à partir de la couleur choisie
        for y in range(height):
            ratio = y / height
            r = int(br + (10 - br) * ratio * 0.5)
            g = int(bg + (10 - bg) * ratio * 0.5)
            b = int(bb + (10 - bb) * ratio * 0.5)
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

        # Bordure dorée
        # Couleur de bordure personnalisée
        border_hex = player.get("card_border", "#D4AF37")

        def hex_to_rgb(h):
            h = h.strip().lstrip("#")
            if len(h) != 6:
                return (212, 175, 55)  # fallback or
            try:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            except:
                return (212, 175, 55)

        border_rgb = hex_to_rgb(border_hex)
        border_color = (*border_rgb, 255)

        border_width = 8
        draw.rectangle(
            [border_width // 2, border_width // 2, width - border_width // 2, height - border_width // 2],
            outline=border_color,
            width=border_width
        )

        # Fonts
        try:
            title_font = ImageFont.truetype("arial.ttf", 40)
            big_font = ImageFont.truetype("arial.ttf", 72)
            stat_font = ImageFont.truetype("arial.ttf", 28)
            name_font = ImageFont.truetype("arial.ttf", 32)
            tagline_font = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            title_font = ImageFont.load_default()
            big_font = ImageFont.load_default()
            stat_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            tagline_font = ImageFont.load_default()

        # ---------- Note + nom + tagline ----------

        rating = player.get("rating", 0)
        rating_text = f"{rating:.1f}" if isinstance(rating, float) and not rating.is_integer() else str(int(rating))
        draw.text((30, 40), rating_text, font=big_font, fill=(255, 255, 255, 255))

        draw.text((35, 120), "", font=title_font, fill=(230, 230, 230, 255))

        name = player.get("name", member.display_name)
        name = name.upper()
        name_w, name_h = text_size(name, name_font)
        draw.text(((width - name_w) / 2, 20), name, font=name_font, fill=(255, 255, 255, 255))

        # Texte perso sous le nom
        tagline = player.get("card_tagline") or ""
        if tagline:
            tagline = tagline.strip()
            tag_w, tag_h = text_size(tagline, tagline_font)
            draw.text(((width - tag_w) / 2, 60), tagline, font=tagline_font, fill=(240, 240, 240, 230))

        # ---------- Avatar ----------

        try:
            avatar_img = Image.open(BytesIO(avatar_bytes)).convert("RGBA")
            min_side = min(avatar_img.width, avatar_img.height)
            left = (avatar_img.width - min_side) // 2
            top = (avatar_img.height - min_side) // 2
            avatar_img = avatar_img.crop((left, top, left + min_side, top + min_side))
            avatar_img = avatar_img.resize((200, 200), Image.LANCZOS)

            avatar_x = (width - 200) // 2
            avatar_y = 150

            draw.rounded_rectangle(
                [avatar_x - 8, avatar_y - 8, avatar_x + 200 + 8, avatar_y + 200 + 8],
                radius=30,
                outline=(255, 255, 255, 130),
                width=3
            )

            img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)
        except Exception:
            pass

        # ---------- Stats ----------

        tir = player.get("tir", 0)
        pas = player.get("passes", 0)
        phy = player.get("physique", 0)
        inf = player.get("influence", 0)
        gar = player.get("gardien", 0)

        def fmt(v):
            if isinstance(v, float) and not v.is_integer():
                return f"{v:.1f}"
            return str(int(v))

        stats_left = [
            ("TIR", fmt(tir)),
            ("PAS", fmt(pas)),
            ("PHY", fmt(phy)),
        ]
        stats_right = [
            ("INF", fmt(inf)),
            ("GAR", fmt(gar)),
        ]

        draw.text((width // 2 - 40, 380), "STATS", font=title_font, fill=(255, 255, 255, 255))

        left_x = 60
        right_x = width - 60 - 80
        start_y = 430
        line_h = 40

        for i, (label, val) in enumerate(stats_left):
            y = start_y + i * line_h
            draw.text((left_x, y), f"{val}", font=stat_font, fill=(255, 255, 255, 255))
            draw.text((left_x + 50, y), label, font=stat_font, fill=(220, 220, 220, 255))

        for i, (label, val) in enumerate(stats_right):
            y = start_y + i * line_h
            draw.text((right_x, y), f"{val}", font=stat_font, fill=(255, 255, 255, 255))
            draw.text((right_x + 50, y), label, font=stat_font, fill=(220, 220, 220, 255))

        # Footer
        footer_text = ""
        ft_w, ft_h = text_size(footer_text, stat_font)
        draw.text((width - ft_w - 15, height - ft_h - 10), footer_text, font=stat_font, fill=(230, 230, 230, 200))

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    # -------------------------------------------------
    # /stats_joueur — Stats complètes bien séparées
    # -------------------------------------------------
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

        # Embed texte
        embed = discord.Embed(
            title=f"Stats de {joueur.display_name}",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=joueur.display_avatar.url)

        # Bloc notes profil
        embed.add_field(
            name="Profil joueur",
            value=(
                f"• Note globale : **{player.get('rating', 0)}/10**\n"
                f"• Tir : **{player.get('tir', 0)}/10**\n"
                f"• Passes : **{player.get('passes', 0)}/10**\n"
                f"• Physique : **{player.get('physique', 0)}/10**\n"
                f"• Influence : **{player.get('influence', 0)}/10**\n"
                f"• Gardien : **{player.get('gardien', 0)}/10**"
            ),
            inline=False
        )

        # Bloc stats globales
        embed.add_field(
            name="Stats globales",
            value=(
                f"• Points classement : **{player['points']}**\n"
                f"• Matches joués : **{player['matches']}**\n"
                f"• Victoires : **{player['wins']}**\n"
                f"• Défaites : **{player['losses']}**\n"
                f"• Nuls : **{player['draws']}**"
            ),
            inline=False
        )

        # Bloc contributions
        embed.add_field(
            name="Contributions",
            value=(
                f"• Buts : **{player['goals']}**\n"
                f"• Passes décisives : **{player['assists']}**\n"
                f"• MVP : **{player['mvps']}**"
            ),
            inline=False
        )

        if rank is not None:
            embed.add_field(
                name="🏆 Position au classement général",
                value=f"**#{rank}**",
                inline=False
            )

        # Génération de la carte style FUT
        avatar_bytes = await joueur.display_avatar.read()
        card_buffer = self._build_fut_card(joueur, player, avatar_bytes)
        file = discord.File(fp=card_buffer, filename=f"carte_{joueur.id}.png")

        # On envoie embed + image en même temps
        await interaction.response.send_message(embed=embed, file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(Players(bot))
