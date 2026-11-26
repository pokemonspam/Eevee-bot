import os
import re
import io
import json
import math
import time
import random
import sqlite3
from typing import Optional, List, Dict, Any, Tuple

import aiohttp
from PIL import Image, ImageDraw, ImageFilter
import discord
from discord.ext import commands, tasks

# ==============================================================================
# CONFIGURATION & TOKEN LOADING
# ==============================================================================
def _load_bot_token() -> str:
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if token and token != "YOUR_BOT_TOKEN_HERE":
        return token
    try:
        import streamlit as st
        secret_token = str(st.secrets.get("DISCORD_BOT_TOKEN", "")).strip()
        if secret_token and secret_token != "YOUR_BOT_TOKEN_HERE":
            return secret_token
    except Exception:
        pass
    return token


BOT_TOKEN = _load_bot_token()
PREFIX = "p!"
DB_PATH = "pokebot.db"

# Bot owner Discord User ID(s) for owner-only commands (p!spawnmon)
OWNER_IDS = {772797011899973633}

# Optional custom emoji overrides for Shiny / Gigantamax / Gender badges
SHINY_EMOJI = "✨"
GMAX_EMOJI = "<:gmax:123456789012345678>"
USE_DEFAULT_GMAX_BADGE = True
DEFAULT_GMAX_TEXT = "🇬"

# Optional Gen VIII pixelated icon emoji map: {dex_id: "<:mon_001:123456789>"}
# If unavailable or upload fails, p!p leaves the icon slot blank (never 🔹 or random emojis).
CUSTOM_BOX_EMOJIS: Dict[int, str] = {}

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
]

NATURE_MODIFIERS: Dict[str, Tuple[Optional[str], Optional[str]]] = {
    "Hardy": (None, None), "Lonely": ("atk", "def"), "Brave": ("atk", "spd"),
    "Adamant": ("atk", "spatk"), "Naughty": ("atk", "spdef"),
    "Bold": ("def", "atk"), "Docile": (None, None), "Relaxed": ("def", "spd"),
    "Impish": ("def", "spatk"), "Lax": ("def", "spdef"),
    "Timid": ("spd", "atk"), "Hasty": ("spd", "def"), "Serious": (None, None),
    "Jolly": ("spd", "spatk"), "Naive": ("spd", "spdef"),
    "Modest": ("spatk", "atk"), "Mild": ("spatk", "def"), "Quiet": ("spatk", "spd"),
    "Bashful": (None, None), "Rash": ("spatk", "spdef"),
    "Calm": ("spdef", "atk"), "Gentle": ("spdef", "def"), "Sassy": ("spdef", "spd"),
    "Careful": ("spdef", "spatk"), "Quirky": (None, None),
}

EXTRA_ALIASES: Dict[str, List[str]] = {
    "eevee": ["ibui", "eievui", "evoli"],
    "pikachu": ["pika", "pikachuu"],
    "charizard": ["lizardon", "dracaufeu", "glurak"],
    "bulbasaur": ["fushigidane", "bulbizarre", "bisasam"],
    "squirtle": ["zenigame", "carapuce", "schiggy"],
    "mewtwo": ["myuutsuu"],
    "mew": ["myuu"],
    "gengar": ["gangar", "ectoplasma"],
    "lucario": ["rukario"],
    "greninja": ["gekkouga", "amphinobi"],
    "garchomp": ["gaburias", "carchacrok", "knakrack"],
    "rayquaza": ["rekkuuza"],
    "gardevoir": ["sirknight"],
    "umbreon": ["blacky", "noctali", "nachtara"],
    "sylveon": ["nymphia", "nymphali", "feelinara"],
    "mimikyu": ["mimikkyu"],
    "gimmighoul": ["collecurei"],
    "gholdengo": ["surfugo"],
    "tatsugiri": ["sharitatsu"],
}

STARTER_LIST = [
    "bulbasaur", "charmander", "squirtle",
    "chikorita", "cyndaquil", "totodile",
    "treecko", "torchic", "mudkip",
    "turtwig", "chimchar", "piplup",
    "snivy", "tepig", "oshawott",
    "chespin", "fennekin", "froakie",
    "rowlet", "litten", "popplio",
    "grookey", "scorbunny", "sobble",
    "sprigatito", "fuecoco", "quaxly",
    "pikachu", "eevee",
]

SHOP_ITEMS: Dict[str, Dict[str, Any]] = {
    "incense": {
        "name": "Incense",
        "price": 1000,
        "description": "Spawns 1 wild Pokémon every 20 seconds for 180 spawns in this channel.",
        "spawns": 180,
        "interval": 20,
    },
    "rare candy": {
        "name": "Rare Candy",
        "price": 75,
        "description": "Levels up your selected Pokémon by +1.",
    },
    "redeem": {
        "name": "Redeem",
        "price": 30000,
        "description": "Spawn any Pokémon of your choice immediately.",
    },
}


def make_embed(
    title: Optional[str] = None,
    description: Optional[str] = None,
    color: Tuple[int, int, int] = (104, 152, 178),
    footer: Optional[str] = None,
) -> discord.Embed:
    emb = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(*color),
    )
    if footer:
        emb.set_footer(text=footer)
    return emb


# ==============================================================================
# DATABASE LAYER
# ==============================================================================
class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 500,
                selected_pokemon_id INTEGER DEFAULT NULL,
                redeems INTEGER DEFAULT 0,
                shiny_hunt_slug TEXT DEFAULT NULL
            )
        """)
        # Safe migration if upgrading from an older users table
        cols = [r["name"] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
        if "shiny_hunt_slug" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN shiny_hunt_slug TEXT DEFAULT NULL")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pokemon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                dex_id INTEGER NOT NULL,
                slug TEXT NOT NULL,
                display_name TEXT NOT NULL,
                level INTEGER NOT NULL,
                xp INTEGER DEFAULT 0,
                shiny INTEGER DEFAULT 0,
                gmax INTEGER DEFAULT 0,
                gender TEXT NOT NULL,
                nature TEXT NOT NULL,
                hp_iv INTEGER NOT NULL,
                atk_iv INTEGER NOT NULL,
                def_iv INTEGER NOT NULL,
                spatk_iv INTEGER NOT NULL,
                spdef_iv INTEGER NOT NULL,
                spd_iv INTEGER NOT NULL,
                iv_percent REAL NOT NULL,
                types TEXT NOT NULL,
                caught_at REAL NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS channel_spawns (
                channel_id INTEGER PRIMARY KEY,
                spawn_json TEXT NOT NULL,
                spawned_at REAL NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS incense_channels (
                channel_id INTEGER PRIMARY KEY,
                remaining_spawns INTEGER NOT NULL,
                interval_sec INTEGER NOT NULL,
                paused INTEGER DEFAULT 0,
                last_spawn_at REAL DEFAULT 0
            )
        """)
        self.conn.commit()

    def ensure_user(self, user_id: int) -> sqlite3.Row:
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        self.conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()

    def add_balance(self, user_id: int, amount: int):
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ?",
            (amount, user_id),
        )
        self.conn.commit()

    def add_redeems(self, user_id: int, count: int):
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET redeems = MAX(0, redeems + ?) WHERE user_id = ?",
            (count, user_id),
        )
        self.conn.commit()

    def set_selected(self, user_id: int, pokemon_id: int):
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET selected_pokemon_id = ? WHERE user_id = ?",
            (pokemon_id, user_id),
        )
        self.conn.commit()

    def set_shiny_hunt(self, user_id: int, slug: str):
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET shiny_hunt_slug = ? WHERE user_id = ?",
            (slug, user_id),
        )
        self.conn.commit()

    def insert_pokemon(self, owner_id: int, mon: Dict[str, Any]) -> int:
        self.ensure_user(owner_id)
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO pokemon (
                owner_id, dex_id, slug, display_name, level, xp,
                shiny, gmax, gender, nature,
                hp_iv, atk_iv, def_iv, spatk_iv, spdef_iv, spd_iv,
                iv_percent, types, caught_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            owner_id,
            mon["dex_id"],
            mon["slug"],
            mon["display_name"],
            mon["level"],
            int(mon["shiny"]),
            int(mon["gmax"]),
            mon["gender"],
            mon["nature"],
            mon["ivs"]["hp"],
            mon["ivs"]["atk"],
            mon["ivs"]["def"],
            mon["ivs"]["spatk"],
            mon["ivs"]["spdef"],
            mon["ivs"]["spd"],
            mon["iv_percent"],
            json.dumps(mon["types"]),
            time.time(),
        ))
        new_id = cur.lastrowid
        user = self.ensure_user(owner_id)
        if user["selected_pokemon_id"] is None:
            cur.execute(
                "UPDATE users SET selected_pokemon_id = ? WHERE user_id = ?",
                (new_id, owner_id),
            )
        self.conn.commit()
        return new_id

    def get_user_pokemon(self, owner_id: int) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM pokemon WHERE owner_id = ? ORDER BY id ASC",
            (owner_id,),
        )
        rows = cur.fetchall()
        result = []
        for idx, row in enumerate(rows, start=1):
            d = dict(row)
            d["display_index"] = idx
            d["types"] = json.loads(d["types"])
            result.append(d)
        return result

    def delete_pokemon(self, pokemon_id: int, owner_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute(
            "DELETE FROM pokemon WHERE id = ? AND owner_id = ?",
            (pokemon_id, owner_id),
        )
        deleted = cur.rowcount > 0
        if deleted:
            user = self.ensure_user(owner_id)
            if user["selected_pokemon_id"] == pokemon_id:
                cur.execute(
                    "SELECT id FROM pokemon WHERE owner_id = ? ORDER BY id DESC LIMIT 1",
                    (owner_id,),
                )
                nxt = cur.fetchone()
                cur.execute(
                    "UPDATE users SET selected_pokemon_id = ? WHERE user_id = ?",
                    (nxt["id"] if nxt else None, owner_id),
                )
        self.conn.commit()
        return deleted

    def set_spawn(self, channel_id: int, mon: Dict[str, Any]):
        self.conn.execute(
            "INSERT OR REPLACE INTO channel_spawns (channel_id, spawn_json, spawned_at) VALUES (?, ?, ?)",
            (channel_id, json.dumps(mon), time.time()),
        )
        self.conn.commit()

    def get_spawn(self, channel_id: int) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT spawn_json FROM channel_spawns WHERE channel_id = ?",
            (channel_id,),
        )
        row = cur.fetchone()
        return json.loads(row["spawn_json"]) if row else None

    def clear_spawn(self, channel_id: int):
        self.conn.execute(
            "DELETE FROM channel_spawns WHERE channel_id = ?",
            (channel_id,),
        )
        self.conn.commit()

    def activate_or_add_incense(self, channel_id: int, spawns: int = 180, interval: int = 20):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM incense_channels WHERE channel_id = ?",
            (channel_id,),
        )
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE incense_channels
                SET remaining_spawns = remaining_spawns + ?,
                    interval_sec = ?,
                    paused = 0
                WHERE channel_id = ?
            """, (spawns, interval, channel_id))
        else:
            cur.execute("""
                INSERT INTO incense_channels (channel_id, remaining_spawns, interval_sec, paused, last_spawn_at)
                VALUES (?, ?, ?, 0, 0)
            """, (channel_id, spawns, interval))
        self.conn.commit()

    def set_incense_paused(self, channel_id: int, paused: bool) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM incense_channels WHERE channel_id = ?",
            (channel_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cur.execute(
            "UPDATE incense_channels SET paused = ? WHERE channel_id = ?",
            (1 if paused else 0, channel_id),
        )
        self.conn.commit()
        cur.execute(
            "SELECT * FROM incense_channels WHERE channel_id = ?",
            (channel_id,),
        )
        return cur.fetchone()

    def get_active_incenses(self) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM incense_channels WHERE paused = 0 AND remaining_spawns > 0"
        )
        return cur.fetchall()

    def decrement_incense(self, channel_id: int):
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE incense_channels
            SET remaining_spawns = remaining_spawns - 1,
                last_spawn_at = ?
            WHERE channel_id = ?
        """, (time.time(), channel_id))
        cur.execute(
            "DELETE FROM incense_channels WHERE channel_id = ? AND remaining_spawns <= 0",
            (channel_id,),
        )
        self.conn.commit()


# ==============================================================================
# POKEAPI CLIENT & ALIAS RESOLVER
# ==============================================================================
class PokeAPIClient:
    BASE_URL = "https://pokeapi.co/api/v2"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.pokemon_cache: Dict[str, Dict[str, Any]] = {}
        self.species_cache: Dict[str, Dict[str, Any]] = {}
        self.all_pokemon_names: List[str] = []
        self.alias_to_slug: Dict[str, str] = {}
        self.slug_to_aliases: Dict[str, set] = {}
        self.box_icon_cache: Dict[int, str] = dict(CUSTOM_BOX_EMOJIS)

    async def start(self):
        self.session = aiohttp.ClientSession()
        await self._bootstrap_index()

    async def close(self):
        if self.session:
            await self.session.close()

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = text.replace("♀", "-f").replace("♂", "-m")
        text = re.sub(r"[^a-z0-9\s\-]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def _register_alias(self, alias: str, slug: str):
        norm = self._normalize(alias)
        if not norm:
            return
        self.alias_to_slug[norm] = slug
        self.alias_to_slug[norm.replace(" ", "-")] = slug
        self.alias_to_slug[norm.replace("-", " ")] = slug
        self.slug_to_aliases.setdefault(slug, set()).update({
            norm,
            norm.replace(" ", "-"),
            norm.replace("-", " "),
        })

    async def _bootstrap_index(self):
        try:
            async with self.session.get(f"{self.BASE_URL}/pokemon?limit=1500") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data.get("results", []):
                        slug = item["name"]
                        self.all_pokemon_names.append(slug)
                        self._register_alias(slug, slug)
                        if slug.endswith("-alola"):
                            base = slug[:-6]
                            self._register_alias(f"alolan {base}", slug)
                            self._register_alias(f"alola {base}", slug)
                        elif slug.endswith("-galar"):
                            base = slug[:-6]
                            self._register_alias(f"galarian {base}", slug)
                            self._register_alias(f"galar {base}", slug)
                        elif slug.endswith("-hisui"):
                            base = slug[:-6]
                            self._register_alias(f"hisuian {base}", slug)
                            self._register_alias(f"hisui {base}", slug)
                        elif slug.endswith("-paldea"):
                            base = slug[:-7]
                            self._register_alias(f"paldean {base}", slug)
                            self._register_alias(f"paldea {base}", slug)
                        elif slug.endswith("-gmax"):
                            base = slug[:-5]
                            self._register_alias(f"gigantamax {base}", slug)
                            self._register_alias(f"gmax {base}", slug)

            for base_slug, aliases in EXTRA_ALIASES.items():
                for al in aliases:
                    self._register_alias(al, base_slug)
        except Exception as e:
            print(f"[PokeAPI] Bootstrap warning: {e}")

    def resolve_slug(self, query: str) -> Optional[str]:
        norm = self._normalize(query)
        if not norm:
            return None
        if norm in self.alias_to_slug:
            return self.alias_to_slug[norm]
        hyphen = norm.replace(" ", "-")
        if hyphen in self.alias_to_slug:
            return self.alias_to_slug[hyphen]
        for prefix, suffix in [
            ("alolan ", "-alola"), ("alola ", "-alola"),
            ("galarian ", "-galar"), ("galar ", "-galar"),
            ("hisuian ", "-hisui"), ("hisui ", "-hisui"),
            ("paldean ", "-paldea"), ("paldea ", "-paldea"),
            ("gigantamax ", "-gmax"), ("gmax ", "-gmax"),
        ]:
            if norm.startswith(prefix):
                candidate = norm[len(prefix):].replace(" ", "-") + suffix
                if candidate in self.alias_to_slug:
                    return self.alias_to_slug[candidate]
        return None

    def format_display_name(self, slug: str) -> str:
        parts = slug.split("-")
        if len(parts) >= 2:
            suffix = parts[-1]
            base = " ".join(p.capitalize() for p in parts[:-1])
            region_map = {
                "alola": f"Alolan {base}",
                "galar": f"Galarian {base}",
                "hisui": f"Hisuian {base}",
                "paldea": f"Paldean {base}",
                "gmax": f"Gigantamax {base}",
            }
            if suffix in region_map:
                return region_map[suffix]
        return " ".join(p.capitalize() for p in parts)

    async def get_pokemon_data(self, identifier: str) -> Optional[Dict[str, Any]]:
        slug = self.resolve_slug(str(identifier)) or self._normalize(str(identifier)).replace(" ", "-")
        if slug in self.pokemon_cache:
            return self.pokemon_cache[slug]

        async with self.session.get(f"{self.BASE_URL}/pokemon/{slug}") as resp:
            if resp.status != 200:
                return None
            raw = await resp.json()

        species_name = raw["species"]["name"]
        species_data = await self.get_species_data(species_name)

        valid_names = set(self.slug_to_aliases.get(slug, set()))
        valid_names.update({
            self._normalize(slug),
            self._normalize(slug.replace("-", " ")),
            self._normalize(species_name),
            self._normalize(species_name.replace("-", " ")),
            self._normalize(self.format_display_name(slug)),
        })
        for al in EXTRA_ALIASES.get(species_name, []):
            valid_names.add(self._normalize(al))
        if species_data:
            for entry in species_data.get("names", []):
                loc_name = self._normalize(entry.get("name", ""))
                if loc_name:
                    valid_names.add(loc_name)
                    self._register_alias(loc_name, species_name)

        base_stats = {s["stat"]["name"]: s["base_stat"] for s in raw["stats"]}
        sprites = raw.get("sprites", {})
        other = sprites.get("other", {})
        official = other.get("official-artwork", {})
        home = other.get("home", {})
        gen8_icon = (
            sprites.get("versions", {})
            .get("generation-viii", {})
            .get("icons", {})
            .get("front_default")
        )

        parsed = {
            "dex_id": raw["id"],
            "species_id": species_data["id"] if species_data else raw["id"],
            "species_name": species_name,
            "slug": raw["name"],
            "display_name": self.format_display_name(raw["name"]),
            "types": [t["type"]["name"] for t in sorted(raw["types"], key=lambda x: x["slot"])],
            "base_stats": {
                "hp": base_stats.get("hp", 50),
                "atk": base_stats.get("attack", 50),
                "def": base_stats.get("defense", 50),
                "spatk": base_stats.get("special-attack", 50),
                "spdef": base_stats.get("special-defense", 50),
                "spd": base_stats.get("speed", 50),
            },
            "artwork_default": official.get("front_default") or home.get("front_default") or sprites.get("front_default"),
            "artwork_shiny": official.get("front_shiny") or home.get("front_shiny") or sprites.get("front_shiny"),
            "box_icon_url": gen8_icon,
            "gender_rate": species_data.get("gender_rate", 4) if species_data else 4,
            "valid_catch_names": sorted(valid_names),
        }
        self.pokemon_cache[raw["name"]] = parsed
        self.pokemon_cache[slug] = parsed
        return parsed

    async def get_species_data(self, species_name: str) -> Optional[Dict[str, Any]]:
        if species_name in self.species_cache:
            return self.species_cache[species_name]
        async with self.session.get(f"{self.BASE_URL}/pokemon-species/{species_name}") as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            self.species_cache[species_name] = data
            return data

    async def ensure_box_icon_emoji(self, bot: commands.Bot, dex_id: int, icon_url: Optional[str]) -> str:
        if dex_id in self.box_icon_cache:
            return self.box_icon_cache[dex_id]
        if not icon_url or not self.session:
            self.box_icon_cache[dex_id] = ""
            return ""
        try:
            app_emojis = await bot.fetch_application_emojis()
            target_name = f"pkmn_{dex_id}"
            for em in app_emojis:
                if em.name == target_name:
                    val = str(em)
                    self.box_icon_cache[dex_id] = val
                    return val

            async with self.session.get(icon_url) as resp:
                if resp.status != 200:
                    self.box_icon_cache[dex_id] = ""
                    return ""
                img_bytes = await resp.read()

            created = await bot.create_application_emoji(name=target_name, image=img_bytes)
            val = str(created)
            self.box_icon_cache[dex_id] = val
            return val
        except Exception:
            self.box_icon_cache[dex_id] = ""
            return ""


# ==============================================================================
# MUTED, NATURAL ENVIRONMENT BACKGROUND COMPOSITOR (PIL)
# ==============================================================================
class SceneRenderer:
    WIDTH = 640
    HEIGHT = 400

    TYPE_PALETTES: Dict[str, Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = {
        "normal":   ((198, 196, 186), (168, 165, 152)),
        "fire":     ((186, 134, 112), (142, 94, 78)),
        "water":    ((96, 146, 176),  (54, 102, 136)),
        "electric": ((118, 136, 114), (82, 102, 84)),
        "grass":    ((148, 178, 142), (112, 146, 110)),
        "ice":      ((182, 206, 218), (146, 178, 194)),
        "fighting": ((178, 140, 126), (142, 106, 94)),
        "poison":   ((150, 132, 166), (114, 96, 132)),
        "ground":   ((188, 168, 138), (154, 132, 102)),
        "flying":   ((168, 196, 218), (198, 214, 226)),
        "psychic":  ((184, 148, 172), (146, 112, 138)),
        "bug":      ((162, 180, 132), (128, 148, 98)),
        "rock":     ((168, 160, 146), (132, 124, 112)),
        "ghost":    ((116, 112, 136), (84, 80, 106)),
        "dragon":   ((124, 136, 172), (92, 104, 142)),
        "dark":     ((106, 104, 114), (76, 74, 84)),
        "steel":    ((166, 174, 182), (132, 142, 152)),
        "fairy":    ((204, 178, 192), (174, 146, 164)),
    }

    @classmethod
    def _vertical_gradient(
        cls,
        top_rgb: Tuple[int, int, int],
        bot_rgb: Tuple[int, int, int],
    ) -> Image.Image:
        img = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT))
        draw = ImageDraw.Draw(img)
        for y in range(cls.HEIGHT):
            t = y / max(1, cls.HEIGHT - 1)
            r = int(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * t)
            g = int(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * t)
            b = int(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * t)
            draw.line([(0, y), (cls.WIDTH, y)], fill=(r, g, b, 255))
        return img

    @classmethod
    def _draw_flying_sky(cls, canvas: Image.Image):
        overlay = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        clouds = [
            (70, 75, 195, 122),
            (130, 62, 240, 118),
            (410, 95, 555, 142),
            (465, 82, 585, 135),
            (215, 165, 345, 202),
        ]
        for box in clouds:
            draw.ellipse(box, fill=(235, 242, 248, 95))
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=10))
        canvas.alpha_composite(overlay)

    @classmethod
    def _draw_electric_forest(cls, canvas: Image.Image):
        overlay = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([0, 315, cls.WIDTH, cls.HEIGHT], fill=(68, 86, 68, 170))
        tree_positions = [55, 125, 515, 585]
        for tx in tree_positions:
            draw.rectangle([tx - 6, 235, tx + 6, 325], fill=(64, 78, 62, 150))
            draw.polygon([(tx, 145), (tx - 38, 245), (tx + 38, 245)], fill=(74, 94, 74, 155))
            draw.polygon([(tx, 180), (tx - 44, 275), (tx + 44, 275)], fill=(66, 86, 66, 160))
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=3))
        canvas.alpha_composite(overlay)

        bolt_layer = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(bolt_layer)
        bolts = [
            [(165, 65), (153, 95), (166, 95), (154, 126)],
            [(475, 55), (464, 82), (476, 82), (465, 110)],
        ]
        for pts in bolts:
            bdraw.line(pts, fill=(224, 206, 122, 130), width=3)
        bolt_layer = bolt_layer.filter(ImageFilter.GaussianBlur(radius=1.2))
        canvas.alpha_composite(bolt_layer)

    @classmethod
    def _draw_water_ocean(cls, canvas: Image.Image):
        overlay = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        rays = [
            [(220, 0), (275, 0), (195, 340), (110, 340)],
            [(295, 0), (355, 0), (345, 360), (255, 360)],
            [(375, 0), (425, 0), (495, 330), (415, 330)],
        ]
        for poly in rays:
            draw.polygon(poly, fill=(186, 222, 238, 42))
        draw.ellipse([-60, 335, cls.WIDTH + 60, 440], fill=(42, 82, 112, 140))
        for bx, by, br in [(140, 260, 4), (152, 225, 3), (490, 245, 4), (502, 205, 3)]:
            draw.ellipse([bx - br, by - br, bx + br, by + br], outline=(195, 228, 242, 75), width=1)
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=6))
        canvas.alpha_composite(overlay)

    @classmethod
    def _draw_grass_meadow(cls, canvas: Image.Image):
        overlay = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.ellipse([-80, 295, 440, 430], fill=(96, 130, 94, 145))
        draw.ellipse([220, 305, cls.WIDTH + 80, 440], fill=(86, 120, 86, 155))
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=6))
        canvas.alpha_composite(overlay)

    @classmethod
    def _draw_subtle_ground_shadow(cls, canvas: Image.Image):
        shadow = Image.new("RGBA", (cls.WIDTH, cls.HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shadow)
        draw.ellipse([215, 325, 425, 355], fill=(25, 30, 35, 55))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))
        canvas.alpha_composite(shadow)

    @classmethod
    async def render_card(
        cls,
        session: Optional[aiohttp.ClientSession],
        sprite_url: Optional[str],
        types: List[str],
    ) -> Optional[discord.File]:
        primary = types[0].lower() if types else "normal"
        top_rgb, bot_rgb = cls.TYPE_PALETTES.get(primary, cls.TYPE_PALETTES["normal"])
        canvas = cls._vertical_gradient(top_rgb, bot_rgb)

        if primary == "flying":
            cls._draw_flying_sky(canvas)
        elif primary == "electric":
            cls._draw_electric_forest(canvas)
        elif primary == "water":
            cls._draw_water_ocean(canvas)
        elif primary in ("grass", "bug"):
            cls._draw_grass_meadow(canvas)

        cls._draw_subtle_ground_shadow(canvas)

        if sprite_url and session:
            try:
                async with session.get(sprite_url) as resp:
                    if resp.status == 200:
                        raw_bytes = await resp.read()
                        sprite = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
                        target_h = 265
                        ratio = target_h / max(1, sprite.height)
                        target_w = int(sprite.width * ratio)
                        sprite = sprite.resize((target_w, target_h), Image.Resampling.LANCZOS)
                        x = (cls.WIDTH - target_w) // 2
                        y = (cls.HEIGHT - target_h) // 2 + 12
                        canvas.alpha_composite(sprite, (x, y))
            except Exception:
                pass

        buf = io.BytesIO()
        canvas.convert("RGB").save(buf, format="PNG")
        buf.seek(0)
        return discord.File(buf, filename="pokemon.png")


# ==============================================================================
# STAT CALCULATIONS & SPAWN / IV HELPERS
# ==============================================================================
STAT_KEYS = ["hp", "atk", "def", "spatk", "spdef", "spd"]
STAT_LABELS = {
    "hp": "HP",
    "atk": "Attack",
    "def": "Defense",
    "spatk": "Sp. Atk",
    "spdef": "Sp. Def",
    "spd": "Speed",
}

STAT_ALIASES = {
    "hp": "hp", "hpiv": "hp",
    "atk": "atk", "attack": "atk", "atkiv": "atk", "attackiv": "atk",
    "def": "def", "defense": "def", "defence": "def", "defiv": "def",
    "spatk": "spatk", "spa": "spatk", "specialattack": "spatk", "spatkiv": "spatk",
    "spdef": "spdef", "spd_def": "spdef", "specialdefense": "spdef", "spdiv": "spdef", "spdefiv": "spdef",
    "spd": "spd", "spe": "spd", "speed": "spd", "spdiv_speed": "spd", "speediv": "spd",
}


def compute_battle_stats(base_stats: Dict[str, int], ivs: Dict[str, int], level: int, nature: str) -> Dict[str, int]:
    inc_stat, dec_stat = NATURE_MODIFIERS.get(nature, (None, None))
    out: Dict[str, int] = {}
    for key in STAT_KEYS:
        base = base_stats.get(key, 50)
        iv = ivs.get(key, 0)
        if key == "hp":
            out[key] = math.floor(((2 * base + iv) * level) / 100) + level + 10
        else:
            raw = math.floor(((2 * base + iv) * level) / 100) + 5
            mult = 1.1 if inc_stat == key else (0.9 if dec_stat == key else 1.0)
            out[key] = math.floor(raw * mult)
    return out


def roll_gender(gender_rate: int) -> str:
    if gender_rate == -1:
        return "Genderless"
    if gender_rate == 0:
        return "Male"
    if gender_rate == 8:
        return "Female"
    female_chance = gender_rate / 8.0
    return "Female" if random.random() < female_chance else "Male"


def gender_symbol(gender: str) -> str:
    if gender == "Male":
        return "♂"
    if gender == "Female":
        return "♀"
    return "⚪"


def gmax_badge() -> str:
    if USE_DEFAULT_GMAX_BADGE and GMAX_EMOJI.endswith("123456789012345678>"):
        return DEFAULT_GMAX_TEXT
    return GMAX_EMOJI


def distribute_iv_total(target_total: int, pinned: Dict[str, int]) -> Optional[Dict[str, int]]:
    remaining_keys = [k for k in STAT_KEYS if k not in pinned]
    pinned_sum = sum(pinned.values())
    rem_points = target_total - pinned_sum

    if rem_points < 0 or rem_points > 31 * len(remaining_keys):
        return None

    alloc = {k: 0 for k in remaining_keys}
    pool = list(remaining_keys)
    for _ in range(rem_points):
        valid_choices = [k for k in pool if alloc[k] < 31]
        if not valid_choices:
            return None
        chosen = random.choice(valid_choices)
        alloc[chosen] += 1

    result = dict(pinned)
    result.update(alloc)
    return result


def build_pokemon_payload(
    pdata: Dict[str, Any],
    level: Optional[int] = None,
    ivs: Optional[Dict[str, int]] = None,
    shiny: Optional[bool] = None,
    gmax: Optional[bool] = None,
) -> Dict[str, Any]:
    lvl = level if level is not None else random.randint(1, 45)
    is_shiny = shiny if shiny is not None else (random.random() < (1 / 4096))
    is_gmax = gmax if gmax is not None else False
    if ivs is None:
        ivs = {k: random.randint(0, 31) for k in STAT_KEYS}
    iv_pct = round((sum(ivs.values()) / 186.0) * 100.0, 2)

    return {
        "dex_id": pdata["dex_id"],
        "slug": pdata["slug"],
        "display_name": pdata["display_name"],
        "level": lvl,
        "shiny": is_shiny,
        "gmax": is_gmax,
        "gender": roll_gender(pdata["gender_rate"]),
        "nature": random.choice(NATURES),
        "ivs": ivs,
        "iv_percent": iv_pct,
        "types": pdata["types"],
        "artwork_default": pdata["artwork_default"],
        "artwork_shiny": pdata["artwork_shiny"],
        "box_icon_url": pdata["box_icon_url"],
        "valid_catch_names": pdata["valid_catch_names"],
    }


# ==============================================================================
# INTERACTIVE VIEWS
# ==============================================================================
class InfoPaginatorView(discord.ui.View):
    def __init__(self, bot: "PokeBot", user: discord.abc.User, collection: List[Dict[str, Any]], start_idx: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user
        self.collection = collection
        self.idx = start_idx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                embed=make_embed("Not Allowed", "Only the command invoker can use these buttons.", (186, 108, 108)),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.idx = (self.idx - 1) % len(self.collection)
        embed, file = await self.bot.build_info_embed(self.user, self.collection[self.idx], len(self.collection))
        attachments = [file] if file else []
        await interaction.response.edit_message(embed=embed, attachments=attachments, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.idx = (self.idx + 1) % len(self.collection)
        embed, file = await self.bot.build_info_embed(self.user, self.collection[self.idx], len(self.collection))
        attachments = [file] if file else []
        await interaction.response.edit_message(embed=embed, attachments=attachments, view=self)


class ListPaginatorView(discord.ui.View):
    def __init__(self, user: discord.abc.User, pages: List[discord.Embed]):
        super().__init__(timeout=120)
        self.user = user
        self.pages = pages
        self.page_idx = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                embed=make_embed("Not Allowed", "Only the command invoker can browse this list.", (186, 108, 108)),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page_idx = (self.page_idx - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.page_idx], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page_idx = (self.page_idx + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.page_idx], view=self)


class ReleaseConfirmView(discord.ui.View):
    def __init__(self, db: Database, user: discord.abc.User, mon: Dict[str, Any], reward_pc: int):
        super().__init__(timeout=45)
        self.db = db
        self.user = user
        self.mon = mon
        self.reward_pc = reward_pc
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                embed=make_embed("Not Allowed", "This confirmation isn't for you.", (186, 108, 108)),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved:
            return
        self.resolved = True
        deleted = self.db.delete_pokemon(self.mon["id"], self.user.id)
        for child in self.children:
            child.disabled = True
        if deleted:
            self.db.add_balance(self.user.id, self.reward_pc)
            emb = make_embed(
                "Pokémon Released",
                (
                    f"Released your Level {self.mon['level']} {self.mon['display_name']} "
                    f"({self.mon['iv_percent']:.2f}%) and received **{self.reward_pc:,} pc**!"
                ),
                (88, 166, 132),
            )
            await interaction.response.edit_message(content=None, embed=emb, view=self)
        else:
            emb = make_embed("Not Found", "That Pokémon is no longer in your collection.", (186, 108, 108))
            await interaction.response.edit_message(content=None, embed=emb, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved:
            return
        self.resolved = True
        for child in self.children:
            child.disabled = True
        emb = make_embed("Release Cancelled", "Your Pokémon was kept.", (130, 140, 150))
        await interaction.response.edit_message(content=None, embed=emb, view=self)


class BuyConfirmView(discord.ui.View):
    def __init__(
        self,
        bot: "PokeBot",
        user: discord.abc.User,
        channel_id: int,
        item_key: str,
        quantity: int,
        total_cost: int,
    ):
        super().__init__(timeout=45)
        self.bot = bot
        self.user = user
        self.channel_id = channel_id
        self.item_key = item_key
        self.quantity = quantity
        self.total_cost = total_cost
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                embed=make_embed("Not Allowed", "This purchase prompt isn't for you.", (186, 108, 108)),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved:
            return
        self.resolved = True
        for child in self.children:
            child.disabled = True

        user_row = self.bot.db.ensure_user(self.user.id)
        if user_row["balance"] < self.total_cost:
            emb = make_embed("Insufficient Balance", "You no longer have enough Pokécoins for this purchase.", (186, 108, 108))
            await interaction.response.edit_message(content=None, embed=emb, view=self)
            return

        self.bot.db.add_balance(self.user.id, -self.total_cost)
        item = SHOP_ITEMS[self.item_key]

        if self.item_key == "incense":
            total_spawns = item["spawns"] * self.quantity
            self.bot.db.activate_or_add_incense(self.channel_id, spawns=total_spawns, interval=item["interval"])
            emb = make_embed(
                "Purchase Complete",
                (
                    f"Purchased **{self.quantity}x {item['name']}** for **{self.total_cost:,} pc**!\n"
                    f"Incense is now **active and running** in this channel (**{total_spawns}** spawns remaining)."
                ),
                (88, 166, 132),
            )
            await interaction.response.edit_message(content=None, embed=emb, view=self)
        elif self.item_key == "rare candy":
            sel_id = user_row["selected_pokemon_id"]
            if not sel_id:
                self.bot.db.add_balance(self.user.id, self.total_cost)
                emb = make_embed("Purchase Refunded", "You don't have a selected Pokémon to level up. Purchase refunded.", (186, 108, 108))
                await interaction.response.edit_message(content=None, embed=emb, view=self)
                return
            self.bot.db.conn.execute(
                "UPDATE pokemon SET level = MIN(100, level + ?) WHERE id = ? AND owner_id = ?",
                (self.quantity, sel_id, self.user.id),
            )
            self.bot.db.conn.commit()
            emb = make_embed(
                "Purchase Complete",
                f"Purchased **{self.quantity}x Rare Candy** for **{self.total_cost:,} pc**! Your selected Pokémon leveled up!",
                (88, 166, 132),
            )
            await interaction.response.edit_message(content=None, embed=emb, view=self)
        elif self.item_key == "redeem":
            self.bot.db.add_redeems(self.user.id, self.quantity)
            emb = make_embed(
                "Purchase Complete",
                f"Purchased **{self.quantity}x Redeem** for **{self.total_cost:,} pc**!",
                (88, 166, 132),
            )
            await interaction.response.edit_message(content=None, embed=emb, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.resolved:
            return
        self.resolved = True
        for child in self.children:
            child.disabled = True
        emb = make_embed("Purchase Cancelled", "No Pokécoins were spent.", (130, 140, 150))
        await interaction.response.edit_message(content=None, embed=emb, view=self)


# ==============================================================================
# MAIN BOT CLASS
# ==============================================================================
class PokeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or(PREFIX, PREFIX.upper()),
            intents=intents,
            case_insensitive=True,
            help_command=None,
        )
        self.db = Database(DB_PATH)
        self.pokeapi = PokeAPIClient()
        self.channel_activity: Dict[int, int] = {}

    async def setup_hook(self):
        await self.pokeapi.start()
        self.incense_loop.start()

    async def close(self):
        self.incense_loop.cancel()
        await self.pokeapi.close()
        await super().close()

    @tasks.loop(seconds=5)
    async def incense_loop(self):
        now = time.time()
        active = self.db.get_active_incenses()
        for row in active:
            ch_id = row["channel_id"]
            interval = row["interval_sec"]
            last_at = row["last_spawn_at"]
            if now - last_at >= interval:
                channel = self.get_channel(ch_id)
                if isinstance(channel, discord.TextChannel):
                    await self.trigger_random_spawn(channel)
                    self.db.decrement_incense(ch_id)

    @incense_loop.before_loop
    async def before_incense(self):
        await self.wait_until_ready()

    async def trigger_random_spawn(
        self,
        channel: discord.TextChannel,
        custom_mon: Optional[Dict[str, Any]] = None,
    ):
        if custom_mon is None:
            if not self.pokeapi.all_pokemon_names:
                return
            rand_id = random.randint(1, 1025)
            pdata = await self.pokeapi.get_pokemon_data(str(rand_id))
            if not pdata:
                return
            mon = build_pokemon_payload(pdata)
        else:
            mon = custom_mon

        self.db.set_spawn(channel.id, mon)

        sprite_url = mon["artwork_shiny"] if mon["shiny"] else mon["artwork_default"]
        file = await SceneRenderer.render_card(self.pokeapi.session, sprite_url, mon["types"])

        embed = discord.Embed(
            title="A wild pokémon has appeared!",
            description=f"Guess the pokémon and type `{PREFIX}catch <pokémon>` to catch it!",
            color=discord.Color.from_rgb(88, 166, 132),
        )
        if file:
            embed.set_image(url="attachment://pokemon.png")
            await channel.send(embed=embed, file=file)
        else:
            await channel.send(embed=embed)

    async def build_info_embed(
        self,
        user: discord.abc.User,
        mon: Dict[str, Any],
        total_count: int,
    ) -> Tuple[discord.Embed, Optional[discord.File]]:
        prefixes = []
        if mon["shiny"]:
            prefixes.append(SHINY_EMOJI)
        if mon["gmax"]:
            prefixes.append(gmax_badge())
        prefix_str = f"{' '.join(prefixes)} " if prefixes else ""

        title = f"{prefix_str}Level {mon['level']} {mon['display_name']}"

        pdata = await self.pokeapi.get_pokemon_data(mon["slug"])
        base_stats = pdata["base_stats"] if pdata else {k: 50 for k in STAT_KEYS}
        ivs = {
            "hp": mon["hp_iv"],
            "atk": mon["atk_iv"],
            "def": mon["def_iv"],
            "spatk": mon["spatk_iv"],
            "spdef": mon["spdef_iv"],
            "spd": mon["spd_iv"],
        }
        calc = compute_battle_stats(base_stats, ivs, mon["level"], mon["nature"])

        types_str = " | ".join(t.capitalize() for t in mon["types"])
        details_block = (
            f"**XP:** {mon['xp']}/{mon['level'] * 25 + 250}\n"
            f"**Nature:** {mon['nature']}\n"
            f"**Gender:** {mon['gender']} {gender_symbol(mon['gender'])}\n"
            f"**Types:** {types_str}"
        )

        # Unbolded "IV:" across all 6 stats
        stats_lines = []
        for k in STAT_KEYS:
            stats_lines.append(f"**{STAT_LABELS[k]}:** {calc[k]} – IV: {ivs[k]}/31")
        stats_lines.append(f"**Total IV:** {mon['iv_percent']:.2f}%")

        embed = discord.Embed(
            title=title,
            color=discord.Color.from_rgb(104, 152, 178),
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.add_field(name="Details", value=details_block, inline=False)
        embed.add_field(name="Stats", value="\n".join(stats_lines), inline=False)
        embed.set_footer(text=f"Displaying Pokémon: {mon['display_index']}/{total_count}")

        sprite_url = None
        if pdata:
            sprite_url = pdata["artwork_shiny"] if mon["shiny"] else pdata["artwork_default"]

        file = await SceneRenderer.render_card(self.pokeapi.session, sprite_url, mon["types"])
        if file:
            embed.set_image(url="attachment://pokemon.png")
        return embed, file


bot = PokeBot()


# ==============================================================================
# MESSAGE LISTENER FOR NATURAL ACTIVITY SPAWNS
# ==============================================================================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    if not message.content.lower().startswith(PREFIX):
        ch_id = message.channel.id
        bot.channel_activity[ch_id] = bot.channel_activity.get(ch_id, 0) + 1
        if bot.channel_activity[ch_id] >= 18:
            bot.channel_activity[ch_id] = 0
            await bot.trigger_random_spawn(message.channel)

    await bot.process_commands(message)


# ==============================================================================
# STARTER, REDEEM SPAWN & SHINY HUNT COMMANDS (p!start, p!pick, p!rs, p!sh)
# ==============================================================================
@bot.command(name="start")
async def start_cmd(ctx: commands.Context):
    collection = bot.db.get_user_pokemon(ctx.author.id)
    if collection:
        await ctx.send(embed=make_embed("Already Started", "You have already started your journey!", (186, 108, 108)))
        return
    emb = make_embed(
        "Welcome to the Pokémon World!",
        (
            f"Choose your starter pokémon using `{PREFIX}pick <pokémon>`!\n\n"
            "**Available Starters:**\n"
            + ", ".join(s.capitalize() for s in STARTER_LIST)
        ),
        (88, 166, 132),
    )
    await ctx.send(embed=emb)


@bot.command(name="pick")
async def pick_cmd(ctx: commands.Context, *, starter_name: str = ""):
    collection = bot.db.get_user_pokemon(ctx.author.id)
    if collection:
        await ctx.send(embed=make_embed("Already Started", "You already picked your starter pokémon!", (186, 108, 108)))
        return
    choice = starter_name.strip().lower()
    if choice not in STARTER_LIST:
        await ctx.send(embed=make_embed("Invalid Starter", f"Use `{PREFIX}start` to see the valid starter list.", (186, 108, 108)))
        return
    pdata = await bot.pokeapi.get_pokemon_data(choice)
    if not pdata:
        await ctx.send(embed=make_embed("Error", "Could not load starter data. Try again in a moment.", (186, 108, 108)))
        return
    mon = build_pokemon_payload(pdata, level=5)
    bot.db.insert_pokemon(ctx.author.id, mon)
    await ctx.send(
        embed=make_embed(
            "Starter Chosen!",
            (
                f"Congratulations {ctx.author.mention}! You chose **Level 5 {mon['display_name']}** "
                f"({mon['iv_percent']:.2f}%) as your starter!"
            ),
            (88, 166, 132),
        )
    )


@bot.command(name="redeemspawn", aliases=["rs"])
async def redeemspawn_cmd(ctx: commands.Context, *, mon_name: str = ""):
    user = bot.db.ensure_user(ctx.author.id)
    if user["redeems"] <= 0 and ctx.author.id not in OWNER_IDS:
        await ctx.send(embed=make_embed("No Redeems", f"You don't have any redeems! Buy one from `{PREFIX}shop`.", (186, 108, 108)))
        return
    if not mon_name.strip():
        await ctx.send(embed=make_embed("Usage", f"`{PREFIX}rs <pokémon name>`", (104, 152, 178)))
        return
    pdata = await bot.pokeapi.get_pokemon_data(mon_name.strip())
    if not pdata:
        await ctx.send(embed=make_embed("Not Found", f"Could not find a pokémon matching `{mon_name}`.", (186, 108, 108)))
        return
    if ctx.author.id not in OWNER_IDS:
        bot.db.add_redeems(ctx.author.id, -1)
    mon = build_pokemon_payload(pdata)
    await bot.trigger_random_spawn(ctx.channel, custom_mon=mon)


@bot.command(name="shinyhunt", aliases=["sh"])
async def shinyhunt_cmd(ctx: commands.Context, *, mon_name: str = ""):
    if not mon_name.strip():
        await ctx.send(embed=make_embed("Usage", f"`{PREFIX}sh <pokémon name>`", (104, 152, 178)))
        return
    pdata = await bot.pokeapi.get_pokemon_data(mon_name.strip())
    if not pdata:
        await ctx.send(embed=make_embed("Not Found", f"Could not find a pokémon matching `{mon_name}`.", (186, 108, 108)))
        return
    bot.db.set_shiny_hunt(ctx.author.id, pdata["slug"])
    await ctx.send(embed=make_embed("Shiny Hunt Set", f"Now shiny hunting **{pdata['display_name']}**!", (88, 166, 132)))


# ==============================================================================
# CATCH COMMAND (p!c / p!catch)
# ==============================================================================
@bot.command(name="catch", aliases=["c"])
async def catch_cmd(ctx: commands.Context, *, guess: str = ""):
    if not guess.strip():
        await ctx.send(embed=make_embed("Usage", f"`{PREFIX}catch <pokémon name>`", (104, 152, 178)))
        return

    spawn = bot.db.get_spawn(ctx.channel.id)
    if not spawn:
        await ctx.send(embed=make_embed("No Wild Pokémon", "There is no wild pokémon in this channel right now!", (186, 108, 108)))
        return

    norm_guess = bot.pokeapi._normalize(guess)
    valid_names = set(spawn.get("valid_catch_names", []))
    valid_names.add(bot.pokeapi._normalize(spawn["display_name"]))
    valid_names.add(bot.pokeapi._normalize(spawn["slug"]))

    base_species = spawn["slug"].split("-")[0]
    valid_names.add(bot.pokeapi._normalize(base_species))

    if norm_guess not in valid_names:
        await ctx.send(embed=make_embed("Wrong Pokémon", "That is the wrong pokémon!", (186, 108, 108)))
        return

    bot.db.clear_spawn(ctx.channel.id)
    bot.db.insert_pokemon(ctx.author.id, spawn)

    shiny_tag = f" {SHINY_EMOJI}" if spawn["shiny"] else ""
    gmax_tag = f" {gmax_badge()}" if spawn["gmax"] else ""
    await ctx.send(
        embed=make_embed(
            "Pokémon Caught!",
            (
                f"Congratulations {ctx.author.mention}! You caught a Level {spawn['level']} "
                f"**{spawn['display_name']}**{shiny_tag}{gmax_tag} ({spawn['iv_percent']:.2f}%)!"
            ),
            (88, 166, 132),
        )
    )


# ==============================================================================
# INFO COMMAND (p!i / p!info)
# ==============================================================================
@bot.command(name="info", aliases=["i"])
async def info_cmd(ctx: commands.Context, target: str = ""):
    collection = bot.db.get_user_pokemon(ctx.author.id)
    if not collection:
        await ctx.send(embed=make_embed("Empty Collection", "You haven't caught any pokémon yet!", (186, 108, 108)))
        return

    user_row = bot.db.ensure_user(ctx.author.id)
    idx = len(collection) - 1

    t = target.strip().lower()
    if t in ("latest", "l", ""):
        if t == "" and user_row["selected_pokemon_id"] is not None:
            for i, m in enumerate(collection):
                if m["id"] == user_row["selected_pokemon_id"]:
                    idx = i
                    break
        else:
            idx = len(collection) - 1
    elif t.isdigit():
        num = int(t)
        if 1 <= num <= len(collection):
            idx = num - 1
        else:
            await ctx.send(embed=make_embed("Invalid Number", f"Invalid pokémon number. You have **{len(collection)}** pokémon.", (186, 108, 108)))
            return
    else:
        await ctx.send(embed=make_embed("Usage", f"`{PREFIX}info [number | latest]`", (104, 152, 178)))
        return

    embed, file = await bot.build_info_embed(ctx.author, collection[idx], len(collection))
    view = InfoPaginatorView(bot, ctx.author, collection, idx)
    if file:
        await ctx.send(embed=embed, file=file, view=view)
    else:
        await ctx.send(embed=embed, view=view)


# ==============================================================================
# POKÉMON COLLECTION LIST (p!p / p!pokemon)
# ==============================================================================
def _parse_numeric_filter(tokens: List[str], start_i: int) -> Tuple[Optional[str], Optional[int], int, Optional[str]]:
    if start_i >= len(tokens):
        return None, None, start_i, "Expected a number after flag."
    tok = tokens[start_i]
    if tok in (">", "<"):
        if start_i + 1 < len(tokens) and tokens[start_i + 1].isdigit():
            return tok, int(tokens[start_i + 1]), start_i + 2, None
        return None, None, start_i + 1, f"Expected a number after `{tok}`."
    if tok.startswith(">"):
        rest = tok[1:]
        if rest.isdigit():
            return ">", int(rest), start_i + 1, None
        return None, None, start_i + 1, f"Invalid comparison `{tok}`."
    if tok.startswith("<"):
        rest = tok[1:]
        if rest.isdigit():
            return "<", int(rest), start_i + 1, None
        return None, None, start_i + 1, f"Invalid comparison `{tok}`."
    if tok.isdigit():
        return "==", int(tok), start_i + 1, None
    return None, None, start_i + 1, f"Invalid filter value `{tok}`. Use a number, `> <num>`, or `< <num>`."


def _match_op(actual: int, op: str, target: int) -> bool:
    if op == "==":
        return actual == target
    if op == ">":
        return actual > target
    if op == "<":
        return actual < target
    return True


@bot.command(name="pokemon", aliases=["p"])
async def pokemon_list_cmd(ctx: commands.Context, *, args: str = ""):
    collection = bot.db.get_user_pokemon(ctx.author.id)
    if not collection:
        await ctx.send(embed=make_embed("Empty Collection", "You don't have any pokémon yet!", (186, 108, 108)))
        return

    tokens = args.split()
    only_shiny = False
    only_gmax = False
    name_filter: Optional[str] = None
    limit_count: Optional[int] = None
    order_by: Optional[str] = None
    numeric_filters: List[Tuple[str, str, int]] = []

    stat_flag_map = {
        "--lvl": "level",
        "--level": "level",
        "--hp": "hp_iv",
        "--hpiv": "hp_iv",
        "--atkiv": "atk_iv",
        "--defiv": "def_iv",
        "--spatkiv": "spatk_iv",
        "--spdiv": "spdef_iv",
        "--spdefiv": "spdef_iv",
        "--spd": "spd_iv",
        "--spdiv_speed": "spd_iv",
    }

    i = 0
    while i < len(tokens):
        tok = tokens[i].lower()
        if tok in ("--sh", "--shiny"):
            only_shiny = True
            i += 1
        elif tok == "--gmax":
            only_gmax = True
            i += 1
        elif tok in ("--n", "--name"):
            i += 1
            name_parts = []
            while i < len(tokens) and not tokens[i].startswith("--"):
                name_parts.append(tokens[i])
                i += 1
            if name_parts:
                name_filter = " ".join(name_parts).lower().strip()
        elif tok in ("--lim", "--limit"):
            if i + 1 < len(tokens) and tokens[i + 1].isdigit():
                limit_count = max(1, int(tokens[i + 1]))
                i += 2
            else:
                await ctx.send(embed=make_embed("Invalid Filter", "Invalid `--lim` value. Provide a positive number like `--lim 10`.", (186, 108, 108)))
                return
        elif tok in ("--o", "--order"):
            if i + 1 < len(tokens):
                order_by = tokens[i + 1].lower()
                i += 2
            else:
                await ctx.send(embed=make_embed("Invalid Filter", "Invalid `--o` value. Use `iv`, `iv+`, `iv-`, `lvl`, `lvl+`, or `lvl-`.", (186, 108, 108)))
                return
        elif tok in stat_flag_map:
            field = stat_flag_map[tok]
            op, val, nxt, err = _parse_numeric_filter(tokens, i + 1)
            if err:
                await ctx.send(embed=make_embed("Invalid Filter", f"Filter `{tok}`: {err}", (186, 108, 108)))
                return
            if op is not None and val is not None:
                numeric_filters.append((field, op, val))
            i = nxt
        else:
            i += 1

    filtered = []
    for mon in collection:
        if only_shiny and not mon["shiny"]:
            continue
        if only_gmax and not mon["gmax"]:
            continue
        if name_filter:
            dname = mon["display_name"].lower()
            slug = mon["slug"].lower().replace("-", " ")
            if name_filter not in dname and name_filter not in slug:
                continue
        passed_num = True
        for field, op, val in numeric_filters:
            if not _match_op(int(mon[field]), op, val):
                passed_num = False
                break
        if not passed_num:
            continue
        filtered.append(mon)

    if not filtered:
        await ctx.send(embed=make_embed("No Matches", "No pokémon matched your filters.", (186, 108, 108)))
        return

    if order_by in ("iv", "iv-"):
        filtered.sort(key=lambda m: m["iv_percent"], reverse=True)
    elif order_by == "iv+":
        filtered.sort(key=lambda m: m["iv_percent"], reverse=False)
    elif order_by in ("lvl", "lvl-"):
        filtered.sort(key=lambda m: m["level"], reverse=True)
    elif order_by == "lvl+":
        filtered.sort(key=lambda m: m["level"], reverse=False)

    if limit_count is not None:
        filtered = filtered[:limit_count]

    unique_dex = {m["dex_id"] for m in filtered[:60]}
    for did in unique_dex:
        if did not in bot.pokeapi.box_icon_cache:
            pdata = await bot.pokeapi.get_pokemon_data(str(did))
            icon_url = pdata["box_icon_url"] if pdata else None
            await bot.pokeapi.ensure_box_icon_emoji(bot, did, icon_url)

    per_page = 20
    pages: List[discord.Embed] = []
    total_filtered = len(filtered)
    total_pages = math.ceil(total_filtered / per_page)
    pad_width = len(str(max(m["display_index"] for m in filtered)))

    for p_idx in range(total_pages):
        chunk = filtered[p_idx * per_page : (p_idx + 1) * per_page]
        lines = []
        for mon in chunk:
            num_str = f"`{str(mon['display_index']).rjust(pad_width)}`"
            box_em = bot.pokeapi.box_icon_cache.get(mon["dex_id"], "")
            box_part = f"{box_em} " if box_em else ""
            sh_part = f"{SHINY_EMOJI} " if mon["shiny"] else ""
            gm_part = f"{gmax_badge()} " if mon["gmax"] else ""
            gen_sym = gender_symbol(mon["gender"])

            line = (
                f"{num_str} {box_part}{sh_part}{gm_part}**{mon['display_name']}** {gen_sym} "
                f"• Lvl. {mon['level']} • {mon['iv_percent']:.2f}%"
            )
            lines.append(line)

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Pokémon",
            description="\n".join(lines),
            color=discord.Color.from_rgb(104, 152, 178),
        )
        start_num = p_idx * per_page + 1
        end_num = min((p_idx + 1) * per_page, total_filtered)
        embed.set_footer(text=f"Showing {start_num}–{end_num} of {total_filtered} pokémon • Page {p_idx + 1}/{total_pages}")
        pages.append(embed)

    if len(pages) == 1:
        await ctx.send(embed=pages[0])
    else:
        await ctx.send(embed=pages[0], view=ListPaginatorView(ctx.author, pages))


# ==============================================================================
# SELECT & RELEASE COMMANDS (p!s / p!select, p!r / p!release)
# ==============================================================================
@bot.command(name="select", aliases=["s"])
async def select_cmd(ctx: commands.Context, number: str = ""):
    collection = bot.db.get_user_pokemon(ctx.author.id)
    if not collection:
        await ctx.send(embed=make_embed("Empty Collection", "You don't have any pokémon to select.", (186, 108, 108)))
        return
    if not number.isdigit():
        await ctx.send(embed=make_embed("Usage", f"`{PREFIX}select <number>`", (104, 152, 178)))
        return
    num = int(number)
    if not (1 <= num <= len(collection)):
        await ctx.send(embed=make_embed("Invalid Number", f"Invalid pokémon number. Choose between `1` and `{len(collection)}`.", (186, 108, 108)))
        return
    mon = collection[num - 1]
    bot.db.set_selected(ctx.author.id, mon["id"])
    await ctx.send(embed=make_embed("Pokémon Selected", f"You selected your Level {mon['level']} **{mon['display_name']}** (No. {num}).", (88, 166, 132)))


@bot.command(name="release", aliases=["r"])
async def release_cmd(ctx: commands.Context, number: str = ""):
    collection = bot.db.get_user_pokemon(ctx.author.id)
    if not collection:
        await ctx.send(embed=make_embed("Empty Collection", "You don't have any pokémon to release.", (186, 108, 108)))
        return
    if not number.isdigit():
        await ctx.send(embed=make_embed("Usage", f"`{PREFIX}release <number>`", (104, 152, 178)))
        return
    num = int(number)
    if not (1 <= num <= len(collection)):
        await ctx.send(embed=make_embed("Invalid Number", f"Invalid pokémon number. Choose between `1` and `{len(collection)}`.", (186, 108, 108)))
        return

    mon = collection[num - 1]
    reward_pc = 2 if not mon["shiny"] else 50
    gen_sym = gender_symbol(mon["gender"])
    prompt = (
        f"Are you sure you want to release your Level {mon['level']} "
        f"{mon['display_name']} {gen_sym} ({mon['iv_percent']:.2f}%) No. {num} for {reward_pc} pc?"
    )
    view = ReleaseConfirmView(bot.db, ctx.author, mon, reward_pc)
    await ctx.send(embed=make_embed("Confirm Release", prompt, (204, 146, 82)), view=view)


# ==============================================================================
# SHOP & BUY WITH CONFIRMATION (p!shop, p!buy, p!bal)
# ==============================================================================
@bot.command(name="bal", aliases=["balance", "pc"])
async def balance_cmd(ctx: commands.Context):
    user = bot.db.ensure_user(ctx.author.id)
    await ctx.send(
        embed=make_embed(
            f"{ctx.author.display_name}'s Balance",
            f"**{user['balance']:,} Pokécoins** • **{user['redeems']}** Redeems",
            (104, 152, 178),
        )
    )


@bot.command(name="shop")
async def shop_cmd(ctx: commands.Context):
    user = bot.db.ensure_user(ctx.author.id)
    embed = discord.Embed(
        title="Poké Shop",
        description=f"Your Balance: **{user['balance']:,} pc**\nUse `{PREFIX}buy <item> [amount]` to purchase.",
        color=discord.Color.from_rgb(104, 152, 178),
    )
    for item in SHOP_ITEMS.values():
        embed.add_field(
            name=f"{item['name']} — {item['price']:,} pc",
            value=item["description"],
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.command(name="buy")
async def buy_cmd(ctx: commands.Context, *, raw_args: str = ""):
    raw_args = raw_args.strip().lower()
    if not raw_args:
        await ctx.send(embed=make_embed("Usage", f"`{PREFIX}buy <item name> [quantity]`", (104, 152, 178)))
        return

    parts = raw_args.split()
    qty = 1
    if len(parts) > 1 and parts[-1].isdigit():
        qty = max(1, int(parts[-1]))
        item_query = " ".join(parts[:-1])
    else:
        item_query = raw_args

    if item_query not in SHOP_ITEMS:
        await ctx.send(embed=make_embed("Unknown Item", f"Unknown shop item `{item_query}`. Check `{PREFIX}shop` for available items.", (186, 108, 108)))
        return

    item = SHOP_ITEMS[item_query]
    total_cost = item["price"] * qty
    user = bot.db.ensure_user(ctx.author.id)

    if user["balance"] < total_cost:
        await ctx.send(
            embed=make_embed(
                "Insufficient Balance",
                (
                    f"You need **{total_cost:,} pc** to buy {qty}x **{item['name']}**, "
                    f"but you only have **{user['balance']:,} pc**."
                ),
                (186, 108, 108),
            )
        )
        return

    view = BuyConfirmView(bot, ctx.author, ctx.channel.id, item_query, qty, total_cost)
    await ctx.send(
        embed=make_embed("Confirm Purchase", f"Are you sure you want to buy **{qty}x {item['name']}** for **{total_cost:,} pc**?", (104, 152, 178)),
        view=view,
    )


# ==============================================================================
# INCENSE CONTROL (p!inc r / p!inc p)
# ==============================================================================
@bot.command(name="incense", aliases=["inc"])
async def incense_cmd(ctx: commands.Context, action: str = ""):
    act = action.strip().lower()
    if act in ("r", "resume"):
        row = bot.db.set_incense_paused(ctx.channel.id, paused=False)
        if not row:
            await ctx.send(embed=make_embed("No Incense", "There is no active incense in this channel.", (186, 108, 108)))
        else:
            await ctx.send(
                embed=make_embed(
                    "Incense Resumed",
                    f"Incense **resumed** in this channel! (**{row['remaining_spawns']}** spawns remaining).",
                    (88, 166, 132),
                )
            )
    elif act in ("p", "pause"):
        row = bot.db.set_incense_paused(ctx.channel.id, paused=True)
        if not row:
            await ctx.send(embed=make_embed("No Incense", "There is no active incense in this channel.", (186, 108, 108)))
        else:
            await ctx.send(
                embed=make_embed(
                    "Incense Paused",
                    (
                        f"Incense **paused** in this channel. (**{row['remaining_spawns']}** spawns remaining).\n"
                        f"Use `{PREFIX}inc r` to resume."
                    ),
                    (204, 146, 82),
                )
            )
    else:
        cur = bot.db.conn.cursor()
        cur.execute("SELECT * FROM incense_channels WHERE channel_id = ?", (ctx.channel.id,))
        row = cur.fetchone()
        if not row:
            await ctx.send(embed=make_embed("No Incense", f"No active incense in this channel. Buy one with `{PREFIX}buy incense`.", (104, 152, 178)))
        else:
            state = "Paused" if row["paused"] else "Running"
            await ctx.send(
                embed=make_embed(
                    "Channel Incense",
                    (
                        f"**Status:** {state} • **{row['remaining_spawns']}** spawns left (every {row['interval_sec']}s).\n"
                        f"Use `{PREFIX}inc r` to resume or `{PREFIX}inc p` to pause."
                    ),
                    (104, 152, 178),
                )
            )


# ==============================================================================
# OWNER-ONLY CUSTOM SPAWNER (p!spawnmon)
# ==============================================================================
def _parse_spawnmon_args(
    raw: str,
) -> Tuple[Optional[str], Optional[int], Optional[float], Dict[str, int], Optional[bool], Optional[bool], Optional[str]]:
    text = raw.strip()
    if not text:
        return (
            None,
            None,
            None,
            {},
            None,
            None,
            f"Usage: `{PREFIX}spawnmon <mon> [level] [iv%] [(stat val, ...)] [shiny] [gmax]`",
        )

    pinned_raw: Dict[str, int] = {}
    bracket_match = re.search(r"\(([^)]+)\)", text)
    if bracket_match:
        inside = bracket_match.group(1)
        text = (text[: bracket_match.start()] + " " + text[bracket_match.end() :]).strip()
        for entry in inside.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split()
            if len(parts) != 2 or not parts[1].isdigit():
                return (
                    None,
                    None,
                    None,
                    {},
                    None,
                    None,
                    f"Invalid stat override `{entry}`. Use format like `(attack 31, spdiv 31)`.",
                )
            stat_token = re.sub(r"[^a-z]", "", parts[0].lower())
            if stat_token not in STAT_ALIASES:
                return (
                    None,
                    None,
                    None,
                    {},
                    None,
                    None,
                    f"Unknown stat `{parts[0]}`. Valid stats: `hp`, `attack`, `defense`, `spatk`, `spdiv`, `spd`.",
                )
            canon_key = STAT_ALIASES[stat_token]
            val = int(parts[1])
            if not (0 <= val <= 31):
                return (
                    None,
                    None,
                    None,
                    {},
                    None,
                    None,
                    f"Stat `{STAT_LABELS[canon_key]}` must be between `0` and `31` (got `{val}`).",
                )
            pinned_raw[canon_key] = val

    tokens = text.split()
    shiny_flag: Optional[bool] = None
    gmax_flag: Optional[bool] = None
    iv_pct: Optional[float] = None
    level: Optional[int] = None
    name_tokens: List[str] = []

    for tok in tokens:
        low = tok.lower()
        if low in ("shiny", "sh"):
            shiny_flag = True
        elif low in ("nonshiny", "normal"):
            shiny_flag = False
        elif low in ("gmax", "gigantamax"):
            gmax_flag = True
        elif low.endswith("%"):
            num_part = low[:-1]
            try:
                val = float(num_part)
                if not (0.0 <= val <= 100.0):
                    return None, None, None, {}, None, None, "IV percentage must be between `0%` and `100%`."
                iv_pct = val
            except ValueError:
                name_tokens.append(tok)
        elif tok.isdigit() and level is None:
            lvl_val = int(tok)
            if not (1 <= lvl_val <= 100):
                return None, None, None, {}, None, None, "Level must be between `1` and `100`."
            level = lvl_val
        else:
            name_tokens.append(tok)

    if not name_tokens:
        return None, None, None, {}, None, None, "Please specify a pokémon name."

    mon_name = " ".join(name_tokens)
    return mon_name, level, iv_pct, pinned_raw, shiny_flag, gmax_flag, None


@bot.command(name="spawnmon")
async def spawnmon_cmd(ctx: commands.Context, *, raw_args: str = ""):
    if ctx.author.id not in OWNER_IDS:
        await ctx.send(embed=make_embed("Owner Only", "Only the bot owner can use this command.", (186, 108, 108)))
        return

    mon_name, level, iv_pct, pinned_raw, shiny_flag, gmax_flag, err = _parse_spawnmon_args(raw_args)
    if err:
        await ctx.send(embed=make_embed("Invalid Arguments", err, (186, 108, 108)))
        return

    pdata = await bot.pokeapi.get_pokemon_data(mon_name)
    if not pdata:
        await ctx.send(embed=make_embed("Not Found", f"Could not find a pokémon matching `{mon_name}`.", (186, 108, 108)))
        return

    ivs: Optional[Dict[str, int]] = None
    note_msg = ""

    if iv_pct is not None:
        target_total = round((iv_pct / 100.0) * 186)

        if not pinned_raw:
            ivs = distribute_iv_total(target_total, {})
        else:
            accepted: Dict[str, int] = {}
            rejected_notes: List[str] = []
            items = list(pinned_raw.items())

            for k, val in items:
                remaining_slots_after = 6 - (len(accepted) + 1)
                new_sum = sum(accepted.values()) + val
                rem_needed = target_total - new_sum

                if rem_needed < 0:
                    max_allowed = max(0, target_total - sum(accepted.values()))
                    rejected_notes.append(
                        f"`{STAT_LABELS[k]} {val}` exceeded **{iv_pct:.2f}%** (target sum `{target_total}/186`) — "
                        f"it should have been **≤ {max_allowed}** to match `{iv_pct:.2f}%`."
                    )
                    break
                if rem_needed > 31 * remaining_slots_after:
                    min_needed = target_total - sum(accepted.values()) - (31 * remaining_slots_after)
                    rejected_notes.append(
                        f"`{STAT_LABELS[k]} {val}` is too low to reach **{iv_pct:.2f}%** across the remaining stats — "
                        f"it should have been **≥ {min_needed}**."
                    )
                    break
                accepted[k] = val

            if not accepted and rejected_notes:
                await ctx.send(embed=make_embed("IV Mismatch", f"IV doesn't match stats! {rejected_notes[0]}", (186, 108, 108)))
                return

            ivs = distribute_iv_total(target_total, accepted)
            if ivs is None:
                await ctx.send(
                    embed=make_embed("IV Mismatch", f"IV doesn't match stats! Target `{iv_pct:.2f}%` requires a total of `{target_total}/186` IV points.", (186, 108, 108))
                )
                return

            if rejected_notes or len(accepted) < len(items):
                kept_str = ", ".join(f"{STAT_LABELS[k]} {v}" for k, v in accepted.items())
                extra_msg = rejected_notes[0] if rejected_notes else (
                    f"Only the first **{len(accepted)}** stat(s) ({kept_str}) were locked in so the remaining stats could match **{iv_pct:.2f}%**."
                )
                note_msg = (
                    f"IV doesn't match all given stats — kept `{kept_str}` and randomized the rest to hit exact "
                    f"**{iv_pct:.2f}%**. Suggestion: {extra_msg}"
                )
    elif pinned_raw:
        ivs = {k: pinned_raw.get(k, random.randint(0, 31)) for k in STAT_KEYS}

    mon = build_pokemon_payload(
        pdata=pdata,
        level=level,
        ivs=ivs,
        shiny=shiny_flag,
        gmax=gmax_flag,
    )

    if note_msg:
        await ctx.send(embed=make_embed("IV Adjustment", note_msg, (204, 146, 82)))

    await bot.trigger_random_spawn(ctx.channel, custom_mon=mon)


if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise RuntimeError(
            "Missing DISCORD_BOT_TOKEN. Set it in your environment variables or Streamlit Secrets before starting the bot."
        )
    bot.run(BOT_TOKEN)
