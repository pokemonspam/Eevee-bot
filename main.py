import asyncio
import os
import random
import sqlite3
from io import BytesIO
from typing import Any, Optional

import aiohttp
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter

try:
    import streamlit as st
except ImportError:
    st = None


# ==============================================================================
# Configuration & Environment Loading
# ==============================================================================
PREFIX = "p!"
OWNER_IDS = {772797011899973633}
DB_PATH = os.getenv("BOT_DB_PATH", "poketwo_bot.db")

SHINY_EMOJI = "✨"
GMAX_EMOJI = "💥"

# Optional custom pixel emoji map keyed by slug (e.g. "eevee": "<:eevee:123456789012345678>")
PIXEL_SPRITE_EMOJIS: dict[str, str] = {}

NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky",
]

STAT_KEYS = ["hp", "atk", "def", "spa", "spd", "spe"]
STAT_LABELS = {
    "hp": "HP",
    "atk": "Attack",
    "def": "Defense",
    "spa": "Sp. Atk",
    "spd": "Sp. Def",
    "spe": "Speed",
}

TYPE_PALETTES = {
    "normal": ((124, 134, 128), (82, 92, 88), (195, 205, 198)),
    "fire": ((178, 72, 54), (92, 34, 28), (255, 175, 110)),
    "water": ((52, 108, 176), (26, 54, 102), (135, 215, 255)),
    "electric": ((186, 154, 42), (96, 76, 20), (255, 235, 120)),
    "grass": ((64, 138, 86), (32, 74, 48), (155, 235, 165)),
    "ice": ((84, 162, 186), (40, 88, 110), (185, 242, 255)),
    "fighting": ((156, 62, 56), (82, 30, 30), (245, 145, 130)),
    "poison": ((124, 68, 156), (62, 30, 86), (215, 150, 255)),
    "ground": ((164, 126, 68), (88, 64, 32), (242, 204, 132)),
    "flying": ((92, 128, 186), (48, 68, 108), (178, 212, 255)),
    "psychic": ((178, 68, 118), (92, 32, 62), (255, 155, 198)),
    "bug": ((108, 148, 52), (54, 80, 26), (196, 236, 124)),
    "rock": ((132, 116, 88), (68, 58, 44), (218, 198, 164)),
    "ghost": ((92, 74, 146), (44, 34, 78), (182, 160, 255)),
    "dragon": ((76, 84, 168), (38, 42, 96), (156, 172, 255)),
    "dark": ((78, 72, 84), (34, 30, 40), (168, 158, 184)),
    "steel": ((104, 122, 138), (54, 64, 76), (196, 216, 232)),
    "fairy": ((184, 102, 154), (96, 48, 80), (255, 186, 226)),
}


def get_secret_or_env(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(key)
    if val:
        return val.strip()
    if st is not None:
        try:
            if key in st.secrets:
                secret_val = str(st.secrets[key]).strip()
                if secret_val:
                    return secret_val
        except Exception:
            pass
    return default


def gmax_badge() -> str:
    return GMAX_EMOJI


def format_mon_header(mon: dict[str, Any]) -> str:
    prefixes = []
    if mon.get("shiny"):
        prefixes.append(SHINY_EMOJI)
    if mon.get("gmax"):
        prefixes.append(gmax_badge())
    if prefixes:
        return f"{' '.join(prefixes)} {mon['display_name']}"
    return mon["display_name"]


def format_gender_symbol(gender: Optional[str]) -> str:
    g = (gender or "").lower()
    if g in ("male", "m", "♂"):
        return "♂"
    if g in ("female", "f", "♀"):
        return "♀"
    return "?"


def calc_iv_percent(ivs: dict[str, int]) -> float:
    total = sum(int(ivs.get(k, 0)) for k in STAT_KEYS)
    return round((total / (31 * len(STAT_KEYS))) * 100.0, 2)


def make_embed(
    title: str,
    description: str = "",
    color_rgb: tuple[int, int, int] = (235, 135, 175),
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.from_rgb(*color_rgb),
    )


# ==============================================================================
# Database Layer
# ==============================================================================
class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                shards INTEGER DEFAULT 0,
                redeems INTEGER DEFAULT 0,
                selected_slot INTEGER,
                shiny_hunt_slug TEXT,
                shiny_chain INTEGER DEFAULT 0,
                incense_until REAL DEFAULT 0
            )
        """)
        cur.execute("PRAGMA table_info(users)")
        cols = {row["name"] for row in cur.fetchall()}
        if "shards" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN shards INTEGER DEFAULT 0")
        if "redeems" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN redeems INTEGER DEFAULT 0")
        if "selected_slot" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN selected_slot INTEGER")
        if "shiny_hunt_slug" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN shiny_hunt_slug TEXT")
        if "shiny_chain" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN shiny_chain INTEGER DEFAULT 0")
        if "incense_until" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN incense_until REAL DEFAULT 0")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS pokemon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                slot_num INTEGER NOT NULL,
                dex_id INTEGER NOT NULL,
                slug TEXT NOT NULL,
                display_name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                nature TEXT DEFAULT 'Hardy',
                gender TEXT DEFAULT 'genderless',
                shiny INTEGER DEFAULT 0,
                gmax INTEGER DEFAULT 0,
                iv_hp INTEGER DEFAULT 0,
                iv_atk INTEGER DEFAULT 0,
                iv_def INTEGER DEFAULT 0,
                iv_spa INTEGER DEFAULT 0,
                iv_spd INTEGER DEFAULT 0,
                iv_spe INTEGER DEFAULT 0,
                iv_percent REAL DEFAULT 0.0,
                artwork_url TEXT,
                shiny_artwork_url TEXT,
                types_json TEXT
            )
        """)
        cur.execute("PRAGMA table_info(pokemon)")
        pcols = {row["name"] for row in cur.fetchall()}
        if "gmax" not in pcols:
            cur.execute("ALTER TABLE pokemon ADD COLUMN gmax INTEGER DEFAULT 0")
        if "shiny_artwork_url" not in pcols:
            cur.execute("ALTER TABLE pokemon ADD COLUMN shiny_artwork_url TEXT")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS species_catches (
                user_id INTEGER NOT NULL,
                slug TEXT NOT NULL,
                catch_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, slug)
            )
        """)
        self.conn.commit()

    def ensure_user(self, user_id: int) -> sqlite3.Row:
        self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,),
        )
        self.conn.commit()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()

    def add_balance(self, user_id: int, amount: int):
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ?",
            (amount, user_id),
        )
        self.conn.commit()

    def add_shards(self, user_id: int, amount: int):
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET shards = MAX(0, shards + ?) WHERE user_id = ?",
            (amount, user_id),
        )
        self.conn.commit()

    def add_redeems(self, user_id: int, amount: int):
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET redeems = MAX(0, redeems + ?) WHERE user_id = ?",
            (amount, user_id),
        )
        self.conn.commit()

    def consume_redeem(self, user_id: int) -> bool:
        self.ensure_user(user_id)
        cur = self.conn.cursor()
        cur.execute("SELECT redeems FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        current = int(row["redeems"] or 0) if row else 0
        if current <= 0:
            return False
        self.conn.execute(
            "UPDATE users SET redeems = redeems - 1 WHERE user_id = ? AND redeems > 0",
            (user_id,),
        )
        self.conn.commit()
        return True

    def set_shiny_hunt(self, user_id: int, slug: Optional[str], reset_chain: bool = False):
        self.ensure_user(user_id)
        if reset_chain:
            self.conn.execute(
                "UPDATE users SET shiny_hunt_slug = ?, shiny_chain = 0 WHERE user_id = ?",
                (slug or None, user_id),
            )
        else:
            self.conn.execute(
                "UPDATE users SET shiny_hunt_slug = ? WHERE user_id = ?",
                (slug or None, user_id),
            )
        self.conn.commit()

    def increment_shiny_chain(self, user_id: int) -> int:
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET shiny_chain = COALESCE(shiny_chain, 0) + 1 WHERE user_id = ?",
            (user_id,),
        )
        self.conn.commit()
        cur = self.conn.cursor()
        cur.execute("SELECT shiny_chain FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return int(row["shiny_chain"] or 0) if row else 0

    def increment_species_catch(self, user_id: int, slug: str) -> int:
        self.ensure_user(user_id)
        self.conn.execute(
            """
            INSERT INTO species_catches (user_id, slug, catch_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, slug) DO UPDATE SET catch_count = catch_count + 1
            """,
            (user_id, slug),
        )
        self.conn.commit()
        cur = self.conn.cursor()
        cur.execute(
            "SELECT catch_count FROM species_catches WHERE user_id = ? AND slug = ?",
            (user_id, slug),
        )
        row = cur.fetchone()
        return int(row["catch_count"]) if row else 0

    def next_slot_num(self, user_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COALESCE(MAX(slot_num), 0) + 1 AS next_slot FROM pokemon WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return int(row["next_slot"] or 1) if row else 1

    def insert_pokemon(self, user_id: int, mon: dict[str, Any]) -> int:
        user = self.ensure_user(user_id)
        slot_num = self.next_slot_num(user_id)
        ivs = mon["ivs"]
        shiny_int = 1 if mon.get("shiny") else 0
        gmax_int = 1 if mon.get("gmax") else 0
        self.conn.execute(
            """
            INSERT INTO pokemon (
                user_id, slot_num, dex_id, slug, display_name, level, xp,
                nature, gender, shiny, gmax,
                iv_hp, iv_atk, iv_def, iv_spa, iv_spd, iv_spe,
                iv_percent, artwork_url, shiny_artwork_url, types_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                slot_num,
                mon["dex_id"],
                mon["slug"],
                mon["display_name"],
                mon["level"],
                mon.get("xp", 0),
                mon["nature"],
                mon["gender"],
                shiny_int,
                gmax_int,
                ivs["hp"],
                ivs["atk"],
                ivs["def"],
                ivs["spa"],
                ivs["spd"],
                ivs["spe"],
                mon["iv_percent"],
                mon.get("artwork_url"),
                mon.get("shiny_artwork_url"),
                ",".join(mon.get("types", [])),
            ),
        )
        if user["selected_slot"] is None:
            self.conn.execute(
                "UPDATE users SET selected_slot = ? WHERE user_id = ?",
                (slot_num, user_id),
            )
        self.conn.commit()
        return slot_num

    def get_all_pokemon(self, user_id: int) -> list[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM pokemon WHERE user_id = ? ORDER BY slot_num ASC",
            (user_id,),
        )
        return cur.fetchall()

    def get_pokemon_by_slot(self, user_id: int, slot_num: int) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM pokemon WHERE user_id = ? AND slot_num = ?",
            (user_id, slot_num),
        )
        return cur.fetchone()

    def get_selected_pokemon(self, user_id: int) -> Optional[sqlite3.Row]:
        user = self.ensure_user(user_id)
        sel = user["selected_slot"]
        if sel is not None:
            row = self.get_pokemon_by_slot(user_id, int(sel))
            if row:
                return row
        all_mons = self.get_all_pokemon(user_id)
        if all_mons:
            first_slot = int(all_mons[0]["slot_num"])
            self.conn.execute(
                "UPDATE users SET selected_slot = ? WHERE user_id = ?",
                (first_slot, user_id),
            )
            self.conn.commit()
            return all_mons[0]
        return None

    def select_pokemon(self, user_id: int, slot_num: int) -> bool:
        row = self.get_pokemon_by_slot(user_id, slot_num)
        if not row:
            return False
        self.ensure_user(user_id)
        self.conn.execute(
            "UPDATE users SET selected_slot = ? WHERE user_id = ?",
            (slot_num, user_id),
        )
        self.conn.commit()
        return True

    def release_pokemon(self, user_id: int, slot_num: int) -> Optional[sqlite3.Row]:
        row = self.get_pokemon_by_slot(user_id, slot_num)
        if not row:
            return None
        self.conn.execute(
            "DELETE FROM pokemon WHERE user_id = ? AND slot_num = ?",
            (user_id, slot_num),
        )
        user = self.ensure_user(user_id)
        if user["selected_slot"] == slot_num:
            remaining = self.get_all_pokemon(user_id)
            next_sel = int(remaining[0]["slot_num"]) if remaining else None
            self.conn.execute(
                "UPDATE users SET selected_slot = ? WHERE user_id = ?",
                (next_sel, user_id),
            )
        self.conn.commit()
        return row


# ==============================================================================
# PokéAPI Client & Payload Builders
# ==============================================================================
class PokeAPIClient:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        self._external_session = session is not None
        self.session = session
        self._cache: dict[str, dict[str, Any]] = {}
        self._max_dex = 1025

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            )
        return self.session

    async def close(self):
        if self.session and not self.session.closed and not self._external_session:
            await self.session.close()

    async def get_pokemon_data(self, name_or_id: str | int) -> Optional[dict[str, Any]]:
        key = str(name_or_id).strip().lower().replace(" ", "-")
        if not key:
            return None
        if key in self._cache:
            return self._cache[key]

        session = await self._get_session()
        url = f"https://pokeapi.co/api/v2/pokemon/{key}"
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        except Exception:
            return None

        dex_id = int(data.get("id", 0))
        slug = str(data.get("name", key)).lower()
        display_name = slug.replace("-", " ").title()
        types = [
            t["type"]["name"].lower()
            for t in sorted(data.get("types", []), key=lambda x: x.get("slot", 0))
        ]
        other = data.get("sprites", {}).get("other", {})
        official = other.get("official-artwork", {})
        home = other.get("home", {})

        artwork_url = (
            official.get("front_default")
            or home.get("front_default")
            or data.get("sprites", {}).get("front_default")
        )
        shiny_artwork_url = (
            official.get("front_shiny")
            or home.get("front_shiny")
            or data.get("sprites", {}).get("front_shiny")
            or artwork_url
        )

        gender_rate = 4
        try:
            species_url = data.get("species", {}).get("url")
            if species_url:
                async with session.get(species_url) as sresp:
                    if sresp.status == 200:
                        sdata = await sresp.json()
                        gender_rate = int(sdata.get("gender_rate", 4))
                        for name_entry in sdata.get("names", []):
                            if name_entry.get("language", {}).get("name") == "en":
                                base_en = name_entry.get("name")
                                if base_en and slug == str(sdata.get("name", "")).lower():
                                    display_name = base_en
                                break
        except Exception:
            pass

        payload = {
            "dex_id": dex_id,
            "slug": slug,
            "display_name": display_name,
            "types": types,
            "artwork_url": artwork_url,
            "shiny_artwork_url": shiny_artwork_url,
            "gender_rate": gender_rate,
        }
        self._cache[key] = payload
        self._cache[slug] = payload
        if dex_id:
            self._cache[str(dex_id)] = payload
        return payload

    async def get_random_pokemon(self) -> Optional[dict[str, Any]]:
        for _ in range(5):
            dex = random.randint(1, self._max_dex)
            pdata = await self.get_pokemon_data(dex)
            if pdata:
                return pdata
        return await self.get_pokemon_data("eevee")

    async def fetch_image(self, url: Optional[str]) -> Optional[Image.Image]:
        if not url:
            return None
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                raw = await resp.read()
            img = Image.open(BytesIO(raw)).convert("RGBA")
            return img
        except Exception:
            return None


def roll_gender(gender_rate: int) -> str:
    if gender_rate < 0:
        return "genderless"
    if gender_rate == 0:
        return "male"
    if gender_rate == 8:
        return "female"
    female_threshold = (gender_rate / 8.0) * 100.0
    return "female" if random.uniform(0, 100) < female_threshold else "male"


def build_pokemon_payload(
    pdata: dict[str, Any],
    force_shiny: bool = False,
    force_gmax: bool = False,
    shiny_chain: int = 0,
) -> dict[str, Any]:
    ivs = {k: random.randint(0, 31) for k in STAT_KEYS}
    iv_percent = calc_iv_percent(ivs)
    level = random.randint(1, 50)
    nature = random.choice(NATURES)
    gender = roll_gender(int(pdata.get("gender_rate", 4)))

    chain_bonus = min(shiny_chain * 0.0005, 0.05)
    base_shiny_chance = 1.0 / 512.0 + chain_bonus
    is_shiny = True if force_shiny else (random.random() < base_shiny_chance)
    is_gmax = True if force_gmax else (random.random() < 0.02)

    artwork = (
        pdata.get("shiny_artwork_url")
        if is_shiny
        else pdata.get("artwork_url")
    )

    return {
        "dex_id": pdata["dex_id"],
        "slug": pdata["slug"],
        "display_name": pdata["display_name"],
        "types": pdata.get("types", []),
        "level": level,
        "xp": 0,
        "nature": nature,
        "gender": gender,
        "shiny": is_shiny,
        "gmax": is_gmax,
        "ivs": ivs,
        "iv_percent": iv_percent,
        "artwork_url": pdata.get("artwork_url"),
        "shiny_artwork_url": pdata.get("shiny_artwork_url"),
        "active_artwork_url": artwork,
    }


# ==============================================================================
# Wild Spawn Scene Renderer
# ==============================================================================
class SceneRenderer:
    def __init__(self, width: int = 640, height: int = 360):
        self.width = width
        self.height = height

    def render_spawn_card(
        self,
        sprite: Optional[Image.Image],
        types: list[str],
        is_shiny: bool = False,
        is_gmax: bool = False,
    ) -> BytesIO:
        w, h = self.width, self.height
        primary_type = types[0] if types else "normal"
        secondary_type = types[1] if len(types) > 1 else primary_type

        c1_top, c1_bot, c1_glow = TYPE_PALETTES.get(
            primary_type, TYPE_PALETTES["normal"]
        )
        c2_top, c2_bot, c2_glow = TYPE_PALETTES.get(
            secondary_type, TYPE_PALETTES["normal"]
        )

        # Base vertical gradient blending primary & secondary type tones
        base = Image.new("RGBA", (w, h), (20, 22, 30, 255))
        px = base.load()
        for y in range(h):
            t = y / max(1, h - 1)
            r = int((c1_top[0] * (1 - t) + c1_bot[0] * t) * 0.65 + (c2_top[0] * (1 - t) + c2_bot[0] * t) * 0.35)
            g = int((c1_top[1] * (1 - t) + c1_bot[1] * t) * 0.65 + (c2_top[1] * (1 - t) + c2_bot[1] * t) * 0.35)
            b = int((c1_top[2] * (1 - t) + c1_bot[2] * t) * 0.65 + (c2_top[2] * (1 - t) + c2_bot[2] * t) * 0.35)
            for x in range(w):
                px[x, y] = (
                    max(0, min(255, r)),
                    max(0, min(255, g)),
                    max(0, min(255, b)),
                    255,
                )

        # Radial spotlight behind the Pokémon
        glow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow_layer)
        cx, cy = w // 2, h // 2 - 8
        glow_color = (255, 225, 130) if is_shiny else c1_glow
        for radius, alpha in [(165, 26), (120, 46), (78, 72), (44, 96)]:
            gdraw.ellipse(
                (cx - radius, cy - radius, cx + radius, cy + radius),
                fill=(glow_color[0], glow_color[1], glow_color[2], alpha),
            )
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=18))
        base = Image.alpha_composite(base, glow_layer)

        # Soft ambient bokeh accents
        bokeh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(bokeh)
        rng = random.Random(f"{primary_type}-{secondary_type}-{is_shiny}-{is_gmax}")
        for _ in range(14):
            bx = rng.randint(40, w - 40)
            by = rng.randint(30, h - 50)
            br = rng.randint(8, 26)
            ba = rng.randint(12, 32)
            accent = c2_glow if rng.random() > 0.5 else c1_glow
            bdraw.ellipse(
                (bx - br, by - br, bx + br, by + br),
                fill=(accent[0], accent[1], accent[2], ba),
            )
        bokeh = bokeh.filter(ImageFilter.GaussianBlur(radius=5))
        base = Image.alpha_composite(base, bokeh)

        # Ground shadow oval under Pokémon
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_layer)
        sdraw.ellipse(
            (cx - 95, h - 78, cx + 95, h - 42),
            fill=(0, 0, 0, 115),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=10))
        base = Image.alpha_composite(base, shadow_layer)

        # Subtle edge vignette & clean inner frame
        vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        vdraw = ImageDraw.Draw(vignette)
        vdraw.rectangle((0, 0, w, h), outline=(10, 12, 18, 120), width=14)
        vdraw.rectangle((10, 10, w - 10, h - 10), outline=(255, 255, 255, 36), width=2)
        vignette = vignette.filter(ImageFilter.GaussianBlur(radius=4))
        base = Image.alpha_composite(base, vignette)

        # Place centered Pokémon artwork with drop shadow
        if sprite is not None:
            max_side = 235 if is_gmax else 205
            sp = sprite.copy()
            sp.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

            sp_shadow = Image.new("RGBA", sp.size, (0, 0, 0, 0))
            alpha_mask = sp.split()[3]
            dark_fill = Image.new("RGBA", sp.size, (0, 0, 0, 130))
            sp_shadow.paste(dark_fill, (0, 0), mask=alpha_mask)
            sp_shadow = sp_shadow.filter(ImageFilter.GaussianBlur(radius=6))

            px_x = (w - sp.width) // 2
            px_y = (h - sp.height) // 2 - 4
            base.paste(sp_shadow, (px_x, px_y + 8), mask=sp_shadow)
            base.paste(sp, (px_x, px_y), mask=sp)

        out = BytesIO()
        base.convert("RGB").save(out, format="PNG")
        out.seek(0)
        return out


# ==============================================================================
# Embed & UI Builders
# ==============================================================================
def build_info_embed(row: sqlite3.Row, user: discord.User | discord.Member) -> tuple[discord.Embed, Optional[str]]:
    mon = {
        "display_name": row["display_name"],
        "shiny": bool(row["shiny"]),
        "gmax": bool(row["gmax"]),
    }
    header = format_mon_header(mon)
    gender_sym = format_gender_symbol(row["gender"])

    ivs = {
        "hp": int(row["iv_hp"] or 0),
        "atk": int(row["iv_atk"] or 0),
        "def": int(row["iv_def"] or 0),
        "spa": int(row["iv_spa"] or 0),
        "spd": int(row["iv_spd"] or 0),
        "spe": int(row["iv_spe"] or 0),
    }
    total_iv_sum = sum(ivs.values())
    iv_pct = float(row["iv_percent"] or calc_iv_percent(ivs))

    embed = discord.Embed(
        title=f"Level {row['level']} {header} {gender_sym}",
        color=discord.Color.from_rgb(235, 135, 175),
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    details_text = (
        f"**XP:** {int(row['xp'] or 0)}\n"
        f"**Nature:** {row['nature'] or 'Hardy'}\n"
        f"**Gender:** {(row['gender'] or 'Genderless').capitalize()}"
    )
    embed.add_field(name="Details", value=details_text, inline=False)

    stats_text = (
        f"**HP:** {ivs['hp']} — IV: {ivs['hp']}/31\n"
        f"**Attack:** {ivs['atk']} — IV: {ivs['atk']}/31\n"
        f"**Defense:** {ivs['def']} — IV: {ivs['def']}/31\n"
        f"**Sp. Atk:** {ivs['spa']} — IV: {ivs['spa']}/31\n"
        f"**Sp. Def:** {ivs['spd']} — IV: {ivs['spd']}/31\n"
        f"**Speed:** {ivs['spe']} — IV: {ivs['spe']}/31\n"
        f"**Total IV:** {total_iv_sum}/186 ({iv_pct:.2f}%)"
    )
    embed.add_field(name="Stats", value=stats_text, inline=False)

    artwork_url = (
        row["shiny_artwork_url"]
        if row["shiny"] and row["shiny_artwork_url"]
        else row["artwork_url"]
    )
    if artwork_url:
        embed.set_image(url=artwork_url)

    embed.set_footer(text=f"Displaying pokémon {row['slot_num']}.")
    return embed, artwork_url


def format_pokemon_row_line(row: sqlite3.Row) -> str:
    slug = str(row["slug"] or "").lower()
    pixel_prefix = PIXEL_SPRITE_EMOJIS.get(slug, "")
    mon_badges = []
    if row["shiny"]:
        mon_badges.append(SHINY_EMOJI)
    if row["gmax"]:
        mon_badges.append(gmax_badge())
    badges_str = f" {' '.join(mon_badges)}" if mon_badges else ""
    gender_sym = format_gender_symbol(row["gender"])
    iv_pct = float(row["iv_percent"] or 0.0)
    left_icons = f"{pixel_prefix}{badges_str}".strip()
    name_part = f"{left_icons} {row['display_name']} {gender_sym}".strip() if left_icons else f"{row['display_name']} {gender_sym}".strip()
    return f"`{row['slot_num']}` {name_part} • Lvl. {row['level']} • {iv_pct:.2f}%"


def build_pokemon_list_embed(
    rows: list[sqlite3.Row],
    page: int = 0,
    per_page: int = 20,
) -> discord.Embed:
    total = len(rows)
    if total == 0:
        embed = discord.Embed(
            title="Your pokémon",
            description="You don't have any pokémon yet! Catch wild pokémon with `p!c <name>`.",
            color=discord.Color.from_rgb(235, 135, 175),
        )
        embed.set_footer(text="Showing entries 0–0 out of 0.")
        return embed

    total_pages = max(1, (total + per_page - 1) // per_page)
    safe_page = max(0, min(page, total_pages - 1))
    start_idx = safe_page * per_page
    end_idx = min(total, start_idx + per_page)
    page_rows = rows[start_idx:end_idx]

    lines = [format_pokemon_row_line(r) for r in page_rows]
    embed = discord.Embed(
        title="Your pokémon",
        description="\n".join(lines),
        color=discord.Color.from_rgb(235, 135, 175),
    )
    embed.set_footer(text=f"Showing entries {start_idx + 1}–{end_idx} out of {total}.")
    return embed


class PokemonListView(discord.ui.View):
    def __init__(self, ctx: commands.Context, rows: list[sqlite3.Row], per_page: int = 20):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.rows = rows
        self.per_page = per_page
        self.page = 0
        self.total_pages = max(1, (len(rows) + per_page - 1) // per_page)
        self.message: Optional[discord.Message] = None
        self._sync_buttons()

    def _sync_buttons(self):
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.total_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command author can flip through this pokémon list.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        self._sync_buttons()
        embed = build_pokemon_list_embed(self.rows, self.page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
        self._sync_buttons()
        embed = build_pokemon_list_embed(self.rows, self.page, self.per_page)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class HuntConfirmView(discord.ui.View):
    def __init__(
        self,
        author_id: int,
        target_slug: str,
        target_name: str,
        current_chain: int,
        db: Database,
    ):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.target_slug = target_slug
        self.target_name = target_name
        self.current_chain = current_chain
        self.db = db

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the command author can confirm or cancel this hunt change.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.db.set_shiny_hunt(self.author_id, self.target_slug, reset_chain=True)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=make_embed(
                "Shiny Hunt Updated",
                f"Now shiny hunting **{self.target_name}**. Your previous chain of **{self.current_chain}** was reset.",
                (112, 186, 134),
            ),
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=make_embed(
                "Hunt Change Cancelled",
                f"Kept your current shiny hunt and preserved your chain of **{self.current_chain}**.",
                (148, 163, 184),
            ),
            view=self,
        )
        self.stop()


class ChangeHuntModal(discord.ui.Modal, title="Change Shiny Hunt"):
    pokemon_input = discord.ui.TextInput(
        label="Pokémon Name",
        placeholder="e.g. eevee",
        required=True,
        max_length=50,
    )

    def __init__(self, ctx: commands.Context, bot_instance: "PokeBot"):
        super().__init__()
        self.ctx = ctx
        self.bot = bot_instance

    async def on_submit(self, interaction: discord.Interaction):
        query = self.pokemon_input.value.strip()
        pdata = await self.bot.pokeapi.get_pokemon_data(query)
        if not pdata:
            await interaction.response.send_message(
                f"Could not find a pokémon matching `{query}`.",
                ephemeral=True,
            )
            return

        user_row = self.bot.db.ensure_user(self.ctx.author.id)
        old_chain = int(user_row["shiny_chain"] or 0)
        target_slug = pdata["slug"]
        target_name = pdata["display_name"]

        if old_chain > 0:
            view = HuntConfirmView(
                author_id=self.ctx.author.id,
                target_slug=target_slug,
                target_name=target_name,
                current_chain=old_chain,
                db=self.bot.db,
            )
            await interaction.response.send_message(
                embed=make_embed(
                    "Confirm Shiny Hunt Change",
                    (
                        f"Do you want to change your shiny hunt to **{target_name}**? "
                        f"This will reset your current hunt chain (**{old_chain}**)."
                    ),
                    (235, 135, 175),
                ),
                view=view,
            )
        else:
            self.bot.db.set_shiny_hunt(self.ctx.author.id, target_slug, reset_chain=True)
            await interaction.response.send_message(
                embed=make_embed(
                    "Shiny Hunt Updated",
                    f"Now shiny hunting **{target_name}**!",
                    (112, 186, 134),
                )
            )


class ShinyHuntView(discord.ui.View):
    def __init__(self, ctx: commands.Context, bot_instance: "PokeBot"):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.bot = bot_instance

    @discord.ui.button(label="Change hunt", style=discord.ButtonStyle.primary)
    async def change_hunt_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command author can change their shiny hunt here.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(ChangeHuntModal(self.ctx, self.bot))


async def build_shiny_hunt_embed(bot_instance: "PokeBot", user_id: int) -> discord.Embed:
    user_row = bot_instance.db.ensure_user(user_id)
    hunt_slug = user_row["shiny_hunt_slug"]
    chain = int(user_row["shiny_chain"] or 0)

    if hunt_slug:
        pdata = await bot_instance.pokeapi.get_pokemon_data(hunt_slug)
        hunt_label = pdata["display_name"] if pdata else hunt_slug.replace("-", " ").title()
    else:
        hunt_label = "None"

    embed = discord.Embed(
        title="Shiny Hunt ✨",
        description=(
            "You can select a specific pokémon to shiny hunt. "
            "Each time you catch that pokémon, your chain will increase. "
            "The longer your chain, the higher your chance of catching a shiny one!"
        ),
        color=discord.Color.from_rgb(235, 135, 175),
    )
    embed.add_field(name="Currently Hunting", value=hunt_label, inline=False)
    embed.add_field(name="Chain", value=str(chain), inline=False)
    return embed


# ==============================================================================
# Bot Class & Spawn Mechanics
# ==============================================================================
class PokeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            owner_ids=OWNER_IDS,
        )
        self.db = Database(DB_PATH)
        self.pokeapi = PokeAPIClient()
        self.renderer = SceneRenderer()
        self.active_spawns: dict[int, dict[str, Any]] = {}
        self.channel_msg_counts: dict[int, int] = {}

    async def close(self):
        await self.pokeapi.close()
        await super().close()

    async def trigger_random_spawn(
        self,
        channel: discord.abc.Messageable,
        custom_mon: Optional[dict[str, Any]] = None,
        force_shiny: bool = False,
        force_gmax: bool = False,
    ) -> Optional[dict[str, Any]]:
        if custom_mon is not None:
            spawn = dict(custom_mon)
        else:
            pdata = await self.pokeapi.get_random_pokemon()
            if not pdata:
                return None
            spawn = build_pokemon_payload(
                pdata,
                force_shiny=force_shiny,
                force_gmax=force_gmax,
            )

        art_url = (
            spawn.get("shiny_artwork_url")
            if spawn.get("shiny")
            else spawn.get("artwork_url")
        )
        sprite = await self.pokeapi.fetch_image(art_url)
        card_buf = self.renderer.render_spawn_card(
            sprite=sprite,
            types=spawn.get("types", []),
            is_shiny=bool(spawn.get("shiny")),
            is_gmax=bool(spawn.get("gmax")),
        )

        channel_id = getattr(channel, "id", 0)
        self.active_spawns[channel_id] = spawn

        embed = discord.Embed(
            title="A wild pokémon has appeared!",
            description=f"Guess the pokémon and type `{PREFIX}c <pokémon>` to catch it!",
            color=discord.Color.from_rgb(120, 195, 145),
        )
        file = discord.File(fp=card_buf, filename="spawn.png")
        embed.set_image(url="attachment://spawn.png")
        await channel.send(embed=embed, file=file)
        return spawn


bot = PokeBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id if bot.user else 'N/A'})")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if not message.content.startswith(PREFIX) and message.channel is not None:
        ch_id = message.channel.id
        count = bot.channel_msg_counts.get(ch_id, 0) + 1
        if count >= 12:
            bot.channel_msg_counts[ch_id] = 0
            asyncio.create_task(bot.trigger_random_spawn(message.channel))
        else:
            bot.channel_msg_counts[ch_id] = count

    await bot.process_commands(message)


# ==============================================================================
# Commands
# ==============================================================================
@bot.command(name="start")
async def start_cmd(ctx: commands.Context):
    bot.db.ensure_user(ctx.author.id)
    embed = make_embed(
        "Welcome to PokéBot!",
        (
            f"Use `{PREFIX}pick <pokémon>` to claim your starter pokémon, "
            f"`{PREFIX}p` to view your collection, `{PREFIX}i` to inspect your selected pokémon, "
            f"and `{PREFIX}c <name>` whenever a wild pokémon spawns!"
        ),
        (235, 135, 175),
    )
    await ctx.send(embed=embed)


@bot.command(name="pick")
async def pick_cmd(ctx: commands.Context, *, mon_name: str = "eevee"):
    pdata = await bot.pokeapi.get_pokemon_data(mon_name.strip())
    if not pdata:
        await ctx.send(
            embed=make_embed(
                "Not Found",
                f"Could not find a pokémon matching `{mon_name}`.",
                (186, 108, 108),
            )
        )
        return

    mon = build_pokemon_payload(pdata)
    mon["level"] = 5
    slot = bot.db.insert_pokemon(ctx.author.id, mon)
    bot.db.select_pokemon(ctx.author.id, slot)

    header = format_mon_header(mon)
    embed = make_embed(
        "Starter Chosen!",
        f"You received a Level **{mon['level']}** **{header}** (`{mon['iv_percent']:.2f}%` IV) in slot `#{slot}`!",
        (112, 186, 134),
    )
    await ctx.send(embed=embed)


@bot.command(name="catch", aliases=["c"])
async def catch_cmd(ctx: commands.Context, *, guess: str = ""):
    spawn = bot.active_spawns.get(ctx.channel.id)
    if not spawn:
        await ctx.send("There is no wild pokémon to catch right now!")
        return

    clean_guess = guess.strip().lower().replace(" ", "-")
    valid_names = {
        str(spawn["slug"]).lower(),
        str(spawn["display_name"]).lower(),
        str(spawn["display_name"]).lower().replace(" ", "-"),
    }
    if not clean_guess or clean_guess not in valid_names:
        await ctx.send("That is not the right pokémon! Try again.")
        return

    del bot.active_spawns[ctx.channel.id]
    slot = bot.db.insert_pokemon(ctx.author.id, spawn)
    gender_sym = format_gender_symbol(spawn.get("gender"))
    iv_pct = float(spawn.get("iv_percent", 0.0))

    msg = (
        f"Congratulations {ctx.author.mention}! You caught a Level {spawn['level']} "
        f"{spawn['display_name']} {gender_sym} ({iv_pct:.2f}%)!"
    )

    if spawn.get("gmax"):
        msg += f"\n\nWoah! It seems that this pokémon has the Gigantamax Factor... {gmax_badge()}"

    user_row = bot.db.ensure_user(ctx.author.id)
    hunt_slug = user_row["shiny_hunt_slug"]
    old_chain = int(user_row["shiny_chain"] or 0)

    if hunt_slug and spawn["slug"] == hunt_slug:
        new_chain = bot.db.increment_shiny_chain(ctx.author.id)
        msg += f"\n\n+1 Shiny chain! ({new_chain})"
    elif spawn.get("shiny") and old_chain > 0:
        bot.db.set_shiny_hunt(ctx.author.id, hunt_slug or "", reset_chain=True)

    if spawn.get("shiny"):
        msg += f"\n\nThese colors seem unusual... {SHINY_EMOJI}"

    species_total = bot.db.increment_species_catch(ctx.author.id, spawn["slug"])
    if species_total > 0 and species_total % 10 == 0:
        reward_pc = 35 * (species_total // 10)
        bot.db.add_balance(ctx.author.id, reward_pc)
        msg += (
            f"\n\nYou have caught {species_total} {spawn['display_name']}! "
            f"You receive **{reward_pc:,} pc**!"
        )

    await ctx.send(msg)


@bot.command(name="info", aliases=["i"])
async def info_cmd(ctx: commands.Context, slot: Optional[int] = None):
    if slot is not None:
        row = bot.db.get_pokemon_by_slot(ctx.author.id, slot)
        if not row:
            await ctx.send(
                embed=make_embed(
                    "Not Found",
                    f"You don't have a pokémon in slot `#{slot}`.",
                    (186, 108, 108),
                )
            )
            return
    else:
        row = bot.db.get_selected_pokemon(ctx.author.id)
        if not row:
            await ctx.send(
                embed=make_embed(
                    "No Pokémon",
                    f"You don't have any pokémon yet! Use `{PREFIX}pick <pokémon>` to start.",
                    (186, 108, 108),
                )
            )
            return

    embed, _ = build_info_embed(row, ctx.author)
    await ctx.send(embed=embed)


@bot.command(name="pokemon", aliases=["p"])
async def pokemon_cmd(ctx: commands.Context, page: int = 1):
    rows = bot.db.get_all_pokemon(ctx.author.id)
    per_page = 20
    view = PokemonListView(ctx, rows, per_page=per_page)
    start_page = max(0, min(page - 1, view.total_pages - 1))
    view.page = start_page
    view._sync_buttons()

    embed = build_pokemon_list_embed(rows, page=start_page, per_page=per_page)
    msg = await ctx.send(embed=embed, view=view)
    view.message = msg


@bot.command(name="select", aliases=["s"])
async def select_cmd(ctx: commands.Context, slot: int):
    ok = bot.db.select_pokemon(ctx.author.id, slot)
    if not ok:
        await ctx.send(
            embed=make_embed(
                "Not Found",
                f"You don't have a pokémon in slot `#{slot}`.",
                (186, 108, 108),
            )
        )
        return
    row = bot.db.get_pokemon_by_slot(ctx.author.id, slot)
    header = format_mon_header(dict(row)) if row else f"#{slot}"
    await ctx.send(
        embed=make_embed(
            "Pokémon Selected",
            f"Selected **{header}** (`#{slot}`).",
            (112, 186, 134),
        )
    )


@bot.command(name="release", aliases=["r"])
async def release_cmd(ctx: commands.Context, slot: int):
    row = bot.db.release_pokemon(ctx.author.id, slot)
    if not row:
        await ctx.send(
            embed=make_embed(
                "Not Found",
                f"You don't have a pokémon in slot `#{slot}`.",
                (186, 108, 108),
            )
        )
        return
    header = format_mon_header(dict(row))
    await ctx.send(
        embed=make_embed(
            "Pokémon Released",
            f"Released **{header}** (`#{slot}`).",
            (235, 135, 175),
        )
    )


@bot.command(name="shinyhunt", aliases=["sh"])
async def shinyhunt_cmd(ctx: commands.Context, *, mon_name: str = ""):
    if not mon_name.strip():
        embed = await build_shiny_hunt_embed(bot, ctx.author.id)
        await ctx.send(embed=embed, view=ShinyHuntView(ctx, bot))
        return

    pdata = await bot.pokeapi.get_pokemon_data(mon_name.strip())
    if not pdata:
        await ctx.send(
            embed=make_embed(
                "Not Found",
                f"Could not find a pokémon matching `{mon_name}`.",
                (186, 108, 108),
            )
        )
        return

    user_row = bot.db.ensure_user(ctx.author.id)
    old_chain = int(user_row["shiny_chain"] or 0)
    target_slug = pdata["slug"]
    target_name = pdata["display_name"]

    if old_chain > 0:
        view = HuntConfirmView(
            author_id=ctx.author.id,
            target_slug=target_slug,
            target_name=target_name,
            current_chain=old_chain,
            db=bot.db,
        )
        await ctx.send(
            embed=make_embed(
                "Confirm Shiny Hunt Change",
                (
                    f"Do you want to change your shiny hunt to **{target_name}**? "
                    f"This will reset your current hunt chain (**{old_chain}**)."
                ),
                (235, 135, 175),
            ),
            view=view,
        )
        return

    bot.db.set_shiny_hunt(ctx.author.id, target_slug, reset_chain=True)
    await ctx.send(
        embed=make_embed(
            "Shiny Hunt Updated",
            f"Now shiny hunting **{target_name}**!",
            (112, 186, 134),
        )
    )


@bot.command(name="redeemspawn", aliases=["rs"])
async def redeemspawn_cmd(ctx: commands.Context, *, mon_name: str = ""):
    user = bot.db.ensure_user(ctx.author.id)
    redeems_val = int(user["redeems"] or 0)

    if not mon_name.strip():
        bot_mention_label = f"@{bot.user.name}" if bot.user else "@Bot"
        embed = discord.Embed(
            title=f"Your Redeems: {redeems_val}",
            description=(
                "You can use redeems to receive any pokémon of your choice. "
                "You can receive redeems by purchasing them with shards or through voting rewards."
            ),
            color=discord.Color.from_rgb(235, 135, 175),
        )
        embed.add_field(
            name=f"`{bot_mention_label} redeemspawn <pokémon>`",
            value=(
                "Use a redeem to spawn a pokémon of your choice in the current channel "
                "(*careful, if something else spawns, it'll be overridden*)."
            ),
            inline=False,
        )
        await ctx.send(embed=embed)
        return

    if redeems_val <= 0:
        await ctx.send(
            embed=make_embed(
                "No Redeems",
                f"You don't have any redeems! Use `{PREFIX}rs` to check how to get redeems.",
                (186, 108, 108),
            )
        )
        return

    pdata = await bot.pokeapi.get_pokemon_data(mon_name.strip())
    if not pdata:
        await ctx.send(
            embed=make_embed(
                "Not Found",
                f"Could not find a pokémon matching `{mon_name}`.",
                (186, 108, 108),
            )
        )
        return

    if not bot.db.consume_redeem(ctx.author.id):
        await ctx.send(
            embed=make_embed(
                "No Redeems",
                "You don't have any redeems left!",
                (186, 108, 108),
            )
        )
        return

    mon = build_pokemon_payload(pdata)
    await bot.trigger_random_spawn(ctx.channel, custom_mon=mon)


@bot.command(name="bal", aliases=["balance", "pc"])
async def balance_cmd(ctx: commands.Context):
    user = bot.db.ensure_user(ctx.author.id)
    bal_val = int(user["balance"] or 0)
    shards_val = int(user["shards"] or 0)
    embed = discord.Embed(
        title=f"{ctx.author.display_name}'s balance",
        color=discord.Color.from_rgb(235, 135, 175),
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="Pokécoins", value=f"{bal_val:,}", inline=False)
    embed.add_field(name="Shards", value=f"{shards_val:,}", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="shop")
async def shop_cmd(ctx: commands.Context):
    embed = discord.Embed(
        title="PokéShop",
        description=f"Use `{PREFIX}buy <item>` to purchase an item.",
        color=discord.Color.from_rgb(235, 135, 175),
    )
    embed.add_field(
        name="1. Redeem — 100 Shards",
        value=f"Grants `1` redeem for `{PREFIX}rs <pokémon>`.",
        inline=False,
    )
    embed.add_field(
        name="2. Incense — 500 pc",
        value="Boosts wild spawns in this channel.",
        inline=False,
    )
    await ctx.send(embed=embed)


@bot.command(name="buy")
async def buy_cmd(ctx: commands.Context, *, item_name: str = ""):
    key = item_name.strip().lower()
    user = bot.db.ensure_user(ctx.author.id)
    if key in ("redeem", "rs", "1"):
        cost = 100
        if int(user["shards"] or 0) < cost:
            await ctx.send(
                embed=make_embed(
                    "Insufficient Shards",
                    f"You need **{cost}** shards to buy a Redeem.",
                    (186, 108, 108),
                )
            )
            return
        bot.db.add_shards(ctx.author.id, -cost)
        bot.db.add_redeems(ctx.author.id, 1)
        await ctx.send(
            embed=make_embed(
                "Purchase Successful",
                f"Bought **1 Redeem** for **{cost}** shards!",
                (112, 186, 134),
            )
        )
    elif key in ("incense", "inc", "2"):
        cost = 500
        if int(user["balance"] or 0) < cost:
            await ctx.send(
                embed=make_embed(
                    "Insufficient Pokécoins",
                    f"You need **{cost:,} pc** to buy Incense.",
                    (186, 108, 108),
                )
            )
            return
        bot.db.add_balance(ctx.author.id, -cost)
        await bot.trigger_random_spawn(ctx.channel)
        await ctx.send(
            embed=make_embed(
                "Incense Activated",
                f"Spent **{cost:,} pc** and summoned a wild pokémon!",
                (112, 186, 134),
            )
        )
    else:
        await ctx.send(
            embed=make_embed(
                "Unknown Item",
                f"Available items: `redeem` (100 shards), `incense` (500 pc). Check `{PREFIX}shop`.",
                (186, 108, 108),
            )
        )


@bot.command(name="inc")
async def inc_cmd(ctx: commands.Context):
    await buy_cmd(ctx, item_name="incense")


@bot.command(name="spawnmon")
@commands.is_owner()
async def spawnmon_cmd(ctx: commands.Context, *, mon_name: str = ""):
    if not mon_name.strip():
        await bot.trigger_random_spawn(ctx.channel)
        return
    pdata = await bot.pokeapi.get_pokemon_data(mon_name.strip())
    if not pdata:
        await ctx.send(
            embed=make_embed(
                "Not Found",
                f"Could not find a pokémon matching `{mon_name}`.",
                (186, 108, 108),
            )
        )
        return
    mon = build_pokemon_payload(pdata)
    await bot.trigger_random_spawn(ctx.channel, custom_mon=mon)


@bot.command(name="fshine")
@commands.is_owner()
async def fshine_cmd(ctx: commands.Context, *, args: str = ""):
    tokens = args.strip().split()
    force_gmax = any(t.lower() == "gmax" for t in tokens)
    name_tokens = [t for t in tokens if t.lower() != "gmax"]
    mon_query = " ".join(name_tokens).strip()

    if not mon_query:
        existing = bot.active_spawns.get(ctx.channel.id)
        if existing:
            pdata = await bot.pokeapi.get_pokemon_data(existing["slug"])
            if pdata:
                mon = build_pokemon_payload(
                    pdata,
                    force_shiny=True,
                    force_gmax=force_gmax or bool(existing.get("gmax")),
                )
                await bot.trigger_random_spawn(ctx.channel, custom_mon=mon)
                return
        pdata = await bot.pokeapi.get_random_pokemon()
        if pdata:
            mon = build_pokemon_payload(pdata, force_shiny=True, force_gmax=force_gmax)
            await bot.trigger_random_spawn(ctx.channel, custom_mon=mon)
        return

    pdata = await bot.pokeapi.get_pokemon_data(mon_query)
    if not pdata:
        await ctx.send(
            embed=make_embed(
                "Not Found",
                f"Could not find a pokémon matching `{mon_query}`.",
                (186, 108, 108),
            )
        )
        return
    mon = build_pokemon_payload(pdata, force_shiny=True, force_gmax=force_gmax)
    await bot.trigger_random_spawn(ctx.channel, custom_mon=mon)


# ==============================================================================
# Entrypoint
# ==============================================================================
def main():
    token = get_secret_or_env("DISCORD_TOKEN") or get_secret_or_env("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing bot token! Set DISCORD_TOKEN (or BOT_TOKEN) in environment variables or Streamlit secrets."
        )
    bot.run(token)


if __name__ == "__main__":
    main()
