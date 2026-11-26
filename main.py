import asyncio
import os
import random
import re
import sqlite3
import time
from datetime import datetime
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
BOT_ID = 1558161013273133137
OWNER_ID = 772797011899973633
OWNER_IDS = {OWNER_ID}
DB_PATH = os.getenv("BOT_DB_PATH", "poketwo_bot.db")

SHINY_EMOJI = "✨"
GMAX_EMOJI = "<:Gmax:1575503911932919948>"
MALE_EMOJI = "<:male:1566169579300851852>"
FEMALE_EMOJI = "<:Female:1566169649249263627>"

# Optional custom pixel emoji map keyed by slug (e.g. "eevee": "<:eevee:123456789012345678>")
PIXEL_SPRITE_EMOJIS: dict[str, str] = {}

REGIONAL_PREFIX_MAP: dict[str, str] = {
    "alolan": "alola",
    "alola": "alola",
    "galarian": "galar",
    "galar": "galar",
    "hisuian": "hisui",
    "hisui": "hisui",
    "paldean": "paldea",
    "paldea": "paldea",
}

REGIONAL_SUFFIX_TO_LABEL: dict[str, str] = {
    "alola": "Alolan",
    "galar": "Galarian",
    "hisui": "Hisuian",
    "paldea": "Paldean",
}

GMAX_ELIGIBLE_SLUGS: set[str] = {
    "venusaur",
    "charizard",
    "blastoise",
    "butterfree",
    "pikachu",
    "meowth",
    "machamp",
    "gengar",
    "kingler",
    "lapras",
    "eevee",
    "snorlax",
    "garbodor",
    "melmetal",
    "rillaboom",
    "cinderace",
    "inteleon",
    "corviknight",
    "orbeetle",
    "drednaw",
    "coalossal",
    "flapple",
    "appletun",
    "sandaconda",
    "toxtricity-amped",
    "toxtricity-low-key",
    "centiskorch",
    "hatterene",
    "grimmsnarl",
    "alcremie",
    "copperajah",
    "duraludon",
    "urshifu-single-strike",
    "urshifu-rapid-strike",
}

STARTERS_BY_REGION: dict[str, list[str]] = {
    "Kanto": ["Bulbasaur", "Charmander", "Squirtle"],
    "Johto": ["Chikorita", "Cyndaquil", "Totodile"],
    "Hoenn": ["Treecko", "Torchic", "Mudkip"],
    "Sinnoh": ["Turtwig", "Chimchar", "Piplup"],
    "Unova": ["Snivy", "Tepig", "Oshawott"],
    "Kalos": ["Chespin", "Fennekin", "Froakie"],
    "Alola": ["Rowlet", "Litten", "Popplio"],
    "Galar": ["Grookey", "Scorbunny", "Sobble"],
    "Paldea": ["Sprigatito", "Fuecoco", "Quaxly"],
}

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

STAT_ALIASES = {
    "hp": "hp",
    "atk": "atk",
    "attack": "atk",
    "def": "def",
    "defense": "def",
    "spa": "spa",
    "spatk": "spa",
    "sp.atk": "spa",
    "sp_atk": "spa",
    "special-attack": "spa",
    "spd": "spd",
    "spdef": "spd",
    "sp.def": "spd",
    "sp_def": "spd",
    "special-defense": "spd",
    "spe": "spe",
    "speed": "spe",
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


def _mention_prefixes() -> list[str]:
    return [f"<@{BOT_ID}>", f"<@!{BOT_ID}>"]


def get_prefix(bot_instance: commands.Bot, message: discord.Message) -> list[str]:
    return ["p!", "P!", *_mention_prefixes()]


def normalize_prefix_text(content: str) -> str:
    stripped = content.lstrip()
    for m_prefix in (f"<@!{BOT_ID}>", f"<@{BOT_ID}>"):
        if stripped.startswith(m_prefix):
            rest = stripped[len(m_prefix):].lstrip()
            return PREFIX + rest
    if len(content) >= 2 and content[:2].lower() == "p!":
        return PREFIX + content[2:]
    return content


def normalize_pokemon_query(name_or_id: str | int) -> list[str]:
    raw = str(name_or_id).strip().lower()
    if not raw:
        return []
    if raw.isdigit():
        return [raw]

    tokens = [t for t in re.split(r"[\s-]+", raw) if t]
    candidates: list[str] = []

    def _add(c: str):
        if c and c not in candidates:
            candidates.append(c)

    _add("-".join(tokens))

    if tokens and tokens[0] in REGIONAL_PREFIX_MAP:
        reg_slug = REGIONAL_PREFIX_MAP[tokens[0]]
        rest = "-".join(tokens[1:])
        if rest:
            _add(f"{rest}-{reg_slug}")

    if len(tokens) >= 2 and tokens[-1] in REGIONAL_PREFIX_MAP:
        reg_slug = REGIONAL_PREFIX_MAP[tokens[-1]]
        base = "-".join(tokens[:-1])
        _add(f"{base}-{reg_slug}")

    return candidates


def format_regional_display_name(slug: str) -> str:
    clean = slug.strip().lower()
    for suffix, label in REGIONAL_SUFFIX_TO_LABEL.items():
        marker = f"-{suffix}"
        if clean.endswith(marker):
            base = clean[: -len(marker)].replace("-", " ").title()
            return f"{label} {base}".strip()
    return clean.replace("-", " ").title()


def has_gmax_factor(slug: str) -> bool:
    clean = (slug or "").strip().lower()
    if clean in GMAX_ELIGIBLE_SLUGS:
        return True
    for base in GMAX_ELIGIBLE_SLUGS:
        if clean.startswith(f"{base}-"):
            return True
    return False


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
        return MALE_EMOJI
    if g in ("female", "f", "♀"):
        return FEMALE_EMOJI
    return "?"


def calc_iv_percent(ivs: dict[str, int]) -> float:
    total = sum(int(ivs.get(k, 0)) for k in STAT_KEYS)
    return round((total / (31 * len(STAT_KEYS))) * 100.0, 2)


def xp_cap_for_level(level: int) -> int:
    return max(250, int(level) * 250)


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
                incense_until REAL DEFAULT 0,
                incense_remaining REAL DEFAULT 0,
                incense_channel_id INTEGER,
                incense_spawns_left INTEGER DEFAULT 0,
                incense_interval INTEGER DEFAULT 20,
                started_at REAL DEFAULT 0,
                total_caught INTEGER DEFAULT 0,
                shiny_caught INTEGER DEFAULT 0,
                gmax_caught INTEGER DEFAULT 0
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
        if "incense_remaining" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN incense_remaining REAL DEFAULT 0")
        if "incense_channel_id" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN incense_channel_id INTEGER")
        if "incense_spawns_left" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN incense_spawns_left INTEGER DEFAULT 0")
        if "incense_interval" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN incense_interval INTEGER DEFAULT 20")
        if "started_at" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN started_at REAL DEFAULT 0")
        if "total_caught" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN total_caught INTEGER DEFAULT 0")
        if "shiny_caught" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN shiny_caught INTEGER DEFAULT 0")
        if "gmax_caught" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN gmax_caught INTEGER DEFAULT 0")

        with self.conn:
            self.conn.execute(
                "UPDATE users SET started_at = ? WHERE started_at IS NULL OR started_at <= 0",
                (time.time(),),
            )

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
                types_json TEXT,
                UNIQUE(user_id, slot_num)
            )
        """)
        cur.execute("PRAGMA table_info(pokemon)")
        pcols = {row["name"] for row in cur.fetchall()}
        if "gmax" not in pcols:
            cur.execute("ALTER TABLE pokemon ADD COLUMN gmax INTEGER DEFAULT 0")
        if "shiny_artwork_url" not in pcols:
            cur.execute("ALTER TABLE pokemon ADD COLUMN shiny_artwork_url TEXT")
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_pokemon_user_slot ON pokemon(user_id, slot_num)"
        )

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
        now = time.time()
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO users (user_id, started_at) VALUES (?, ?)",
                (user_id, now),
            )
            self.conn.execute(
                "UPDATE users SET started_at = ? WHERE user_id = ? AND (started_at IS NULL OR started_at <= 0)",
                (now, user_id),
            )
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()

    def record_catch_stats(self, user_id: int, is_shiny: bool = False, is_gmax: bool = False):
        self.ensure_user(user_id)
        with self.conn:
            self.conn.execute(
                """
                UPDATE users
                SET total_caught = COALESCE(total_caught, 0) + 1,
                    shiny_caught = COALESCE(shiny_caught, 0) + ?,
                    gmax_caught = COALESCE(gmax_caught, 0) + ?
                WHERE user_id = ?
                """,
                (1 if is_shiny else 0, 1 if is_gmax else 0, user_id),
            )

    def get_unique_dex_count(self, user_id: int) -> int:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(DISTINCT dex_id) AS cnt FROM pokemon WHERE user_id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        return int(row["cnt"] or 0) if row else 0

    def add_balance(self, user_id: int, amount: int):
        self.ensure_user(user_id)
        with self.conn:
            self.conn.execute(
                "UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ?",
                (amount, user_id),
            )

    def add_shards(self, user_id: int, amount: int):
        self.ensure_user(user_id)
        with self.conn:
            self.conn.execute(
                "UPDATE users SET shards = MAX(0, shards + ?) WHERE user_id = ?",
                (amount, user_id),
            )

    def add_redeems(self, user_id: int, amount: int):
        self.ensure_user(user_id)
        with self.conn:
            self.conn.execute(
                "UPDATE users SET redeems = MAX(0, redeems + ?) WHERE user_id = ?",
                (amount, user_id),
            )

    def consume_redeem(self, user_id: int) -> bool:
        self.ensure_user(user_id)
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT redeems FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            current = int(row["redeems"] or 0) if row else 0
            if current <= 0:
                return False
            cur.execute(
                "UPDATE users SET redeems = redeems - 1 WHERE user_id = ? AND redeems > 0",
                (user_id,),
            )
            return True

    def set_shiny_hunt(self, user_id: int, slug: Optional[str], reset_chain: bool = False):
        self.ensure_user(user_id)
        with self.conn:
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

    def increment_shiny_chain(self, user_id: int) -> int:
        self.ensure_user(user_id)
        with self.conn:
            self.conn.execute(
                "UPDATE users SET shiny_chain = COALESCE(shiny_chain, 0) + 1 WHERE user_id = ?",
                (user_id,),
            )
            cur = self.conn.cursor()
            cur.execute("SELECT shiny_chain FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return int(row["shiny_chain"] or 0) if row else 0

    def start_incense(
        self,
        user_id: int,
        channel_id: int,
        duration_sec: int = 900,
        spawns_count: int = 45,
        interval_sec: int = 20,
    ):
        self.ensure_user(user_id)
        until_ts = time.time() + duration_sec
        with self.conn:
            self.conn.execute(
                """
                UPDATE users
                SET incense_until = ?,
                    incense_remaining = 0,
                    incense_channel_id = ?,
                    incense_spawns_left = ?,
                    incense_interval = ?
                WHERE user_id = ?
                """,
                (until_ts, channel_id, spawns_count, interval_sec, user_id),
            )

    def pause_incense(self, user_id: int) -> tuple[bool, float]:
        row = self.ensure_user(user_id)
        now = time.time()
        until_ts = float(row["incense_until"] or 0.0)
        rem = float(row["incense_remaining"] or 0.0)
        spawns_left = int(row["incense_spawns_left"] or 0)
        if until_ts > now and spawns_left > 0:
            left = max(0.0, until_ts - now)
            with self.conn:
                self.conn.execute(
                    """
                    UPDATE users
                    SET incense_until = 0,
                        incense_remaining = ?
                    WHERE user_id = ?
                    """,
                    (left, user_id),
                )
            return True, left
        if rem > 0 and spawns_left > 0:
            return False, rem
        return False, 0.0

    def resume_incense(self, user_id: int, channel_id: Optional[int] = None) -> tuple[bool, float]:
        row = self.ensure_user(user_id)
        now = time.time()
        until_ts = float(row["incense_until"] or 0.0)
        rem = float(row["incense_remaining"] or 0.0)
        spawns_left = int(row["incense_spawns_left"] or 0)
        if rem > 0 and spawns_left > 0:
            new_until = now + rem
            with self.conn:
                if channel_id is not None:
                    self.conn.execute(
                        """
                        UPDATE users
                        SET incense_until = ?,
                            incense_remaining = 0,
                            incense_channel_id = ?
                        WHERE user_id = ?
                        """,
                        (new_until, channel_id, user_id),
                    )
                else:
                    self.conn.execute(
                        """
                        UPDATE users
                        SET incense_until = ?,
                            incense_remaining = 0
                        WHERE user_id = ?
                        """,
                        (new_until, user_id),
                    )
            return True, rem
        if until_ts > now and spawns_left > 0:
            return False, max(0.0, until_ts - now)
        return False, 0.0

    def get_active_incense_users(self) -> list[sqlite3.Row]:
        now = time.time()
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM users
            WHERE incense_until > ?
              AND COALESCE(incense_spawns_left, 0) > 0
              AND incense_channel_id IS NOT NULL
            """,
            (now,),
        )
        return cur.fetchall()

    def decrement_incense_spawn(self, user_id: int) -> int:
        with self.conn:
            self.conn.execute(
                """
                UPDATE users
                SET incense_spawns_left = MAX(0, COALESCE(incense_spawns_left, 0) - 1)
                WHERE user_id = ?
                """,
                (user_id,),
            )
            cur = self.conn.cursor()
            cur.execute("SELECT incense_spawns_left FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            left = int(row["incense_spawns_left"] or 0) if row else 0
            if left <= 0:
                self.conn.execute(
                    "UPDATE users SET incense_until = 0, incense_remaining = 0 WHERE user_id = ?",
                    (user_id,),
                )
            return left

    def increment_species_catch(self, user_id: int, slug: str) -> int:
        self.ensure_user(user_id)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO species_catches (user_id, slug, catch_count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, slug) DO UPDATE SET catch_count = catch_count + 1
                """,
                (user_id, slug),
            )
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
        ivs = mon["ivs"]
        shiny_int = 1 if mon.get("shiny") else 0
        gmax_int = 1 if mon.get("gmax") else 0

        with self.conn:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT COALESCE(MAX(slot_num), 0) + 1 AS next_slot FROM pokemon WHERE user_id = ?",
                (user_id,),
            )
            row = cur.fetchone()
            slot_num = int(row["next_slot"] or 1) if row else 1

            cur.execute(
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
                cur.execute(
                    "UPDATE users SET selected_slot = ? WHERE user_id = ?",
                    (slot_num, user_id),
                )
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
            with self.conn:
                self.conn.execute(
                    "UPDATE users SET selected_slot = ? WHERE user_id = ?",
                    (first_slot, user_id),
                )
            return all_mons[0]
        return None

    def select_pokemon(self, user_id: int, slot_num: int) -> bool:
        row = self.get_pokemon_by_slot(user_id, slot_num)
        if not row:
            return False
        self.ensure_user(user_id)
        with self.conn:
            self.conn.execute(
                "UPDATE users SET selected_slot = ? WHERE user_id = ?",
                (slot_num, user_id),
            )
        return True

    def release_pokemon(self, user_id: int, slot_num: int) -> Optional[sqlite3.Row]:
        row = self.get_pokemon_by_slot(user_id, slot_num)
        if not row:
            return None
        user = self.ensure_user(user_id)
        with self.conn:
            self.conn.execute(
                "DELETE FROM pokemon WHERE user_id = ? AND slot_num = ?",
                (user_id, slot_num),
            )
            if user["selected_slot"] == slot_num:
                remaining = self.get_all_pokemon(user_id)
                next_sel = int(remaining[0]["slot_num"]) if remaining else None
                self.conn.execute(
                    "UPDATE users SET selected_slot = ? WHERE user_id = ?",
                    (next_sel, user_id),
                )
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

    async def _fetch_json(self, url: str) -> Optional[dict[str, Any]]:
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except Exception:
            return None

    async def get_pokemon_data(self, name_or_id: str | int) -> Optional[dict[str, Any]]:
        candidates = normalize_pokemon_query(name_or_id)
        if not candidates:
            return None

        for key in candidates:
            if key in self._cache:
                return self._cache[key]

        data: Optional[dict[str, Any]] = None
        matched_key = candidates[0]
        for key in candidates:
            fetched = await self._fetch_json(f"https://pokeapi.co/api/v2/pokemon/{key}")
            if fetched:
                data = fetched
                matched_key = key
                break

        if not data:
            return None

        dex_id = int(data.get("id", 0))
        slug = str(data.get("name", matched_key)).lower()
        display_name = format_regional_display_name(slug)
        types = [
            t["type"]["name"].lower()
            for t in sorted(data.get("types", []), key=lambda x: x.get("slot", 0))
        ]
        sprites = data.get("sprites", {})
        other = sprites.get("other", {})
        official = other.get("official-artwork", {})
        home = other.get("home", {})

        artwork_url = (
            official.get("front_default")
            or home.get("front_default")
            or sprites.get("front_default")
        )
        shiny_artwork_url = (
            official.get("front_shiny")
            or home.get("front_shiny")
            or sprites.get("front_shiny")
        )

        gender_rate = 4
        species_dex_id = dex_id
        try:
            species_url = data.get("species", {}).get("url")
            if species_url:
                sdata = await self._fetch_json(species_url)
                if sdata:
                    gender_rate = int(sdata.get("gender_rate", 4))
                    species_dex_id = int(sdata.get("id", dex_id) or dex_id)
                    if not shiny_artwork_url and slug != str(sdata.get("name", "")).lower():
                        for var in sdata.get("varieties", []):
                            if var.get("is_default"):
                                def_url = var.get("pokemon", {}).get("url")
                                if def_url:
                                    def_p = await self._fetch_json(def_url)
                                    if def_p:
                                        dspr = def_p.get("sprites", {})
                                        doth = dspr.get("other", {})
                                        shiny_artwork_url = (
                                            doth.get("official-artwork", {}).get("front_shiny")
                                            or doth.get("home", {}).get("front_shiny")
                                            or dspr.get("front_shiny")
                                        )
                                break
        except Exception:
            pass

        if not shiny_artwork_url:
            shiny_artwork_url = artwork_url

        payload = {
            "dex_id": species_dex_id or dex_id,
            "slug": slug,
            "display_name": display_name,
            "types": types,
            "artwork_url": artwork_url,
            "shiny_artwork_url": shiny_artwork_url,
            "gender_rate": gender_rate,
        }
        for c in candidates:
            self._cache[c] = payload
        self._cache[matched_key] = payload
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


def parse_iv_spec(spec_text: str) -> tuple[float, list[tuple[str, int]]]:
    """
    Parses strings like:
      - "80%" or "80"
      - "80%(atk-31,spd-31)" or "75.5% (hp-31, spe-28)"
    Returns (iv_percent, ordered_pinned_stats).
    """
    raw = spec_text.strip()
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*%?\s*(?:\(([^)]*)\))?\s*$", raw, re.IGNORECASE)
    if not match:
        raise ValueError("Invalid IV format.")

    iv_pct = max(0.0, min(100.0, float(match.group(1))))
    pinned: list[tuple[str, int]] = []
    inner = match.group(2)
    if inner:
        for chunk in inner.split(","):
            part = chunk.strip().lower()
            if not part:
                continue
            m = re.match(r"^([a-z0-9_.-]+)\s*[-:=]\s*([0-9]{1,2})$", part)
            if not m:
                continue
            stat_key = STAT_ALIASES.get(m.group(1))
            val = max(0, min(31, int(m.group(2))))
            if stat_key:
                pinned.append((stat_key, val))
    return round(iv_pct, 2), pinned


def generate_ivs_with_target(
    target_iv_pct: float,
    pinned: Optional[list[tuple[str, int]]] = None,
) -> tuple[dict[str, int], float]:
    """
    Generates 6 IVs (0..31) aiming for target_iv_pct.
    - If pinned stats are provided:
      * Checks if applying all pinned stats still allows the remaining stats (0..31)
        to reach target_sum = round((target_iv_pct / 100.0) * 186).
      * If not all fit within budget/bounds, applies valid pinned entries in order
        only while feasible, and rolls remaining stats with RNG.
    """
    max_total = 31 * len(STAT_KEYS)  # 186
    target_sum = max(0, min(max_total, round((target_iv_pct / 100.0) * max_total)))

    ivs: dict[str, int] = {k: random.randint(0, 31) for k in STAT_KEYS}
    locked: set[str] = set()

    if pinned:
        seen_stats: set[str] = set()
        deduped_pinned: list[tuple[str, int]] = []
        for stat_key, val in pinned:
            if stat_key not in seen_stats:
                seen_stats.add(stat_key)
                deduped_pinned.append((stat_key, max(0, min(31, int(val)))))

        all_pinned_sum = sum(v for _, v in deduped_pinned)
        remaining_after_all = len(STAT_KEYS) - len(deduped_pinned)
        min_possible_after_all = all_pinned_sum
        max_possible_after_all = all_pinned_sum + (remaining_after_all * 31)

        if min_possible_after_all <= target_sum <= max_possible_after_all:
            for stat_key, val in deduped_pinned:
                ivs[stat_key] = val
                locked.add(stat_key)
        else:
            running_sum = 0
            for idx, (stat_key, val) in enumerate(deduped_pinned):
                rem_slots = len(STAT_KEYS) - (idx + 1)
                tentative_sum = running_sum + val
                if tentative_sum <= target_sum <= tentative_sum + (rem_slots * 31):
                    ivs[stat_key] = val
                    locked.add(stat_key)
                    running_sum = tentative_sum
                else:
                    if idx == 0 and val <= max_total:
                        ivs[stat_key] = val
                        locked.add(stat_key)
                    break

    unlocked = [k for k in STAT_KEYS if k not in locked]
    if not unlocked:
        actual_pct = round((sum(ivs.values()) / max_total) * 100.0, 2)
        return ivs, actual_pct

    locked_sum = sum(ivs[k] for k in locked)
    desired_unlocked_sum = max(0, min(len(unlocked) * 31, target_sum - locked_sum))

    base_share = desired_unlocked_sum // len(unlocked)
    remainder = desired_unlocked_sum % len(unlocked)
    for idx, k in enumerate(unlocked):
        ivs[k] = max(0, min(31, base_share + (1 if idx < remainder else 0)))

    for _ in range(12):
        a, b = random.sample(unlocked, 2) if len(unlocked) >= 2 else (unlocked[0], unlocked[0])
        if a == b:
            break
        delta = random.randint(1, 5)
        if ivs[a] - delta >= 0 and ivs[b] + delta <= 31:
            ivs[a] -= delta
            ivs[b] += delta

    return ivs, round(target_iv_pct, 2)


def build_pokemon_payload(
    pdata: dict[str, Any],
    force_shiny: bool = False,
    force_gmax: bool = False,
    shiny_chain: int = 0,
    custom_level: Optional[int] = None,
    custom_iv_pct: Optional[float] = None,
    pinned_ivs: Optional[list[tuple[str, int]]] = None,
    exact_forced_flags: bool = False,
) -> dict[str, Any]:
    if custom_iv_pct is not None:
        ivs, iv_percent = generate_ivs_with_target(custom_iv_pct, pinned=pinned_ivs)
    else:
        ivs, iv_percent = generate_ivs_with_target(
            target_iv_pct=calc_iv_percent({k: random.randint(0, 31) for k in STAT_KEYS}),
            pinned=pinned_ivs,
        )
        if pinned_ivs is None:
            ivs = {k: random.randint(0, 31) for k in STAT_KEYS}
            iv_percent = calc_iv_percent(ivs)

    level = custom_level if custom_level is not None else random.randint(1, 50)
    nature = random.choice(NATURES)
    gender = roll_gender(int(pdata.get("gender_rate", 4)))
    slug = str(pdata.get("slug", "")).lower()
    eligible_gmax = has_gmax_factor(slug)

    if exact_forced_flags:
        is_shiny = bool(force_shiny)
        is_gmax = bool(force_gmax) and eligible_gmax
    else:
        chain_bonus = min(shiny_chain * 0.0005, 0.05)
        base_shiny_chance = 1.0 / 512.0 + chain_bonus
        is_shiny = True if force_shiny else (random.random() < base_shiny_chance)
        is_gmax = (True if force_gmax else (random.random() < 0.02)) and eligible_gmax

    shiny_art = pdata.get("shiny_artwork_url") or pdata.get("artwork_url")
    normal_art = pdata.get("artwork_url")
    artwork = shiny_art if is_shiny else normal_art

    return {
        "dex_id": pdata["dex_id"],
        "slug": slug,
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
        "artwork_url": normal_art,
        "shiny_artwork_url": shiny_art,
        "active_artwork_url": artwork,
    }


# ==============================================================================
# Wild Spawn Scene Renderer
# ==============================================================================
class SceneRenderer:
    def __init__(self, width: int = 640, height: int = 360):
        self.width = width
        self.height = height

    def _draw_nature_scene(
        self,
        base: Image.Image,
        primary_type: str,
        secondary_type: str,
        c1_top: tuple[int, int, int],
        c1_bot: tuple[int, int, int],
        c1_glow: tuple[int, int, int],
        c2_glow: tuple[int, int, int],
        rng: random.Random,
    ) -> Image.Image:
        w, h = self.width, self.height
        horizon_y = int(h * 0.64)

        scene = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(scene)

        far_tree = (
            max(0, min(255, int(c1_bot[0] * 0.58 + 12))),
            max(0, min(255, int(c1_bot[1] * 0.72 + 24))),
            max(0, min(255, int(c1_bot[2] * 0.68 + 18))),
            150,
        )
        mid_tree = (
            max(0, min(255, int(c1_bot[0] * 0.42 + 8))),
            max(0, min(255, int(c1_bot[1] * 0.56 + 18))),
            max(0, min(255, int(c1_bot[2] * 0.52 + 12))),
            195,
        )

        if primary_type in ("grass", "bug", "normal"):
            # Soft woodland trees & grassy ground
            for tx in range(20, w, 56):
                th = rng.randint(44, 86)
                tw = rng.randint(22, 36)
                sdraw.rectangle((tx - 3, horizon_y - th // 2, tx + 3, horizon_y + 4), fill=mid_tree)
                sdraw.ellipse((tx - tw, horizon_y - th, tx + tw, horizon_y - th // 3 + 12), fill=far_tree)
            for tx in range(42, w, 68):
                th = rng.randint(32, 64)
                tw = rng.randint(18, 28)
                sdraw.ellipse((tx - tw, horizon_y - th + 6, tx + tw, horizon_y + 6), fill=mid_tree)
        elif primary_type in ("water", "ice"):
            # Calm water bands & soft shore
            for wy in range(horizon_y - 24, h, 16):
                sdraw.line([(0, wy), (w, wy)], fill=(c1_glow[0], c1_glow[1], c1_glow[2], 42), width=3)
            sdraw.polygon([(80, horizon_y), (140, horizon_y - 44), (200, horizon_y)], fill=far_tree)
            sdraw.polygon([(440, horizon_y), (505, horizon_y - 52), (565, horizon_y)], fill=far_tree)
        elif primary_type in ("flying",):
            # Open sky with soft clouds & gentle horizon
            for cx_cloud, cy_cloud, cr in [(120, 82, 26), (144, 78, 32), (170, 84, 24), (480, 74, 28), (506, 70, 34), (532, 76, 24)]:
                sdraw.ellipse((cx_cloud - cr, cy_cloud - cr // 2, cx_cloud + cr, cy_cloud + cr // 2), fill=(255, 255, 255, 48))
        elif primary_type in ("fire",):
            # Warm dusk & subtle ember glow above ground
            for ex in range(45, w - 45, 75):
                ey = rng.randint(horizon_y - 24, horizon_y + 10)
                sdraw.ellipse((ex - 10, ey - 14, ex + 10, ey + 6), fill=(255, 155, 75, 55))
        elif primary_type in ("ground", "rock"):
            # Earthy ground mounds & stones
            for rx, ry, rw, rh in [(95, horizon_y - 12, 36, 18), (520, horizon_y - 16, 44, 22), (240, horizon_y + 26, 24, 12), (410, horizon_y + 34, 28, 14)]:
                sdraw.ellipse((rx - rw, ry - rh, rx + rw, ry + rh), fill=mid_tree)
        elif primary_type in ("ghost", "dark"):
            # Night sky with soft moon & dark silhouettes
            sdraw.ellipse((510, 48, 554, 92), fill=(235, 240, 255, 65))
            for tx in range(28, w, 64):
                th = rng.randint(40, 76)
                tw = rng.randint(18, 28)
                sdraw.ellipse((tx - tw, horizon_y - th, tx + tw, horizon_y + 6), fill=mid_tree)
        elif primary_type in ("fairy",):
            # Soft pastel meadow & gentle sparkles
            for spx, spy in [(115, 95), (210, 72), (430, 84), (525, 108), (165, 145), (475, 140)]:
                sdraw.ellipse((spx - 5, spy - 5, spx + 5, spy + 5), fill=(255, 215, 240, 65))
        else:
            for tx in range(24, w, 60):
                th = rng.randint(36, 70)
                tw = rng.randint(18, 28)
                sdraw.ellipse((tx - tw, horizon_y - th, tx + tw, horizon_y + 6), fill=far_tree)

        ground_top = (
            max(0, min(255, int(c1_bot[0] * 0.52 + 8))),
            max(0, min(255, int(c1_bot[1] * 0.68 + 20))),
            max(0, min(255, int(c1_bot[2] * 0.60 + 14))),
            225,
        )
        ground_bot = (
            max(0, min(255, int(c1_bot[0] * 0.32))),
            max(0, min(255, int(c1_bot[1] * 0.45))),
            max(0, min(255, int(c1_bot[2] * 0.38))),
            245,
        )
        sdraw.rectangle((0, horizon_y, w, h), fill=ground_top)
        sdraw.rectangle((0, int(h * 0.84), w, h), fill=ground_bot)

        scene = scene.filter(ImageFilter.GaussianBlur(radius=4))
        return Image.alpha_composite(base, scene)

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

        base = Image.new("RGBA", (w, h), (20, 22, 30, 255))
        px = base.load()
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(
                (c1_top[0] * (1 - t) + c1_bot[0] * t) * 0.65
                + (c2_top[0] * (1 - t) + c2_bot[0] * t) * 0.35
            )
            g = int(
                (c1_top[1] * (1 - t) + c1_bot[1] * t) * 0.65
                + (c2_top[1] * (1 - t) + c2_bot[1] * t) * 0.35
            )
            b = int(
                (c1_top[2] * (1 - t) + c1_bot[2] * t) * 0.65
                + (c2_top[2] * (1 - t) + c2_bot[2] * t) * 0.35
            )
            for x in range(w):
                px[x, y] = (
                    max(0, min(255, r)),
                    max(0, min(255, g)),
                    max(0, min(255, b)),
                    255,
                )

        # Keep wild spawn image clean without shiny/gmax overlays during spawning
        rng = random.Random(f"{primary_type}-{secondary_type}")
        base = self._draw_nature_scene(
            base=base,
            primary_type=primary_type,
            secondary_type=secondary_type,
            c1_top=c1_top,
            c1_bot=c1_bot,
            c1_glow=c1_glow,
            c2_glow=c2_glow,
            rng=rng,
        )

        cx, cy = w // 2, h // 2 - 8
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_layer)
        sdraw.ellipse(
            (cx - 95, h - 76, cx + 95, h - 42),
            fill=(0, 0, 0, 120),
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=9))
        base = Image.alpha_composite(base, shadow_layer)

        if sprite is not None:
            max_side = 285 if is_gmax else 260
            sp = sprite.copy()
            sp.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

            sp_shadow = Image.new("RGBA", sp.size, (0, 0, 0, 0))
            alpha_mask = sp.split()[3]
            dark_fill = Image.new("RGBA", sp.size, (0, 0, 0, 130))
            sp_shadow.paste(dark_fill, (0, 0), mask=alpha_mask)
            sp_shadow = sp_shadow.filter(ImageFilter.GaussianBlur(radius=6))

            px_x = (w - sp.width) // 2
            px_y = max(10, (h - sp.height) // 2 - 8)
            base.paste(sp_shadow, (px_x, px_y + 8), mask=sp_shadow)
            base.paste(sp, (px_x, px_y), mask=sp)

        out = BytesIO()
        base.convert("RGB").save(out, format="PNG")
        out.seek(0)
        return out


# ==============================================================================
# Embed & UI Builders
# ==============================================================================
def build_info_embed(
    row: sqlite3.Row,
    user: discord.User | discord.Member,
) -> tuple[discord.Embed, Optional[str]]:
    mon = {
        "display_name": row["display_name"],
        "shiny": bool(row["shiny"]),
        "gmax": bool(row["gmax"]),
    }
    header = format_mon_header(mon)
    level = int(row["level"] or 1)
    xp_val = int(row["xp"] or 0)
    xp_cap = xp_cap_for_level(level)

    ivs = {
        "hp": int(row["iv_hp"] or 0),
        "atk": int(row["iv_atk"] or 0),
        "def": int(row["iv_def"] or 0),
        "spa": int(row["iv_spa"] or 0),
        "spd": int(row["iv_spd"] or 0),
        "spe": int(row["iv_spe"] or 0),
    }
    iv_pct = float(row["iv_percent"] if row["iv_percent"] is not None else calc_iv_percent(ivs))

    embed = discord.Embed(
        title=f"{header} Level {level}" if (mon["shiny"] or mon["gmax"]) else f"Level {level} {row['display_name']}",
        color=discord.Color.from_rgb(235, 135, 175),
    )
    embed.set_thumbnail(url=user.display_avatar.url)

    details_text = (
        f"**XP:** {xp_val}/{xp_cap}\n"
        f"**Nature:** {row['nature'] or 'Hardy'}\n"
        f"**Gender:** {(row['gender'] or 'Genderless').capitalize()}"
    )
    embed.add_field(name="Details", value=details_text, inline=False)

    stats_text = (
        f"**HP:** {ivs['hp']} - IV: {ivs['hp']}/31\n"
        f"**Attack:** {ivs['atk']} - IV: {ivs['atk']}/31\n"
        f"**Defense:** {ivs['def']} - IV: {ivs['def']}/31\n"
        f"**Sp. Atk:** {ivs['spa']} - IV: {ivs['spa']}/31\n"
        f"**Sp. Def:** {ivs['spd']} - IV: {ivs['spd']}/31\n"
        f"**Speed:** {ivs['spe']} - IV: {ivs['spe']}/31\n"
        f"**Total IV:** {iv_pct:.2f}%"
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


def _resolve_pixel_sprite_emoji(slug: str) -> str:
    clean = (slug or "").strip().lower()
    if clean in PIXEL_SPRITE_EMOJIS and PIXEL_SPRITE_EMOJIS[clean]:
        return PIXEL_SPRITE_EMOJIS[clean]
    base_slug = clean.split("-", 1)[0]
    if base_slug in PIXEL_SPRITE_EMOJIS and PIXEL_SPRITE_EMOJIS[base_slug]:
        return PIXEL_SPRITE_EMOJIS[base_slug]
    return ""


def format_pokemon_row_line(row: sqlite3.Row) -> str:
    slug = str(row["slug"] or "").lower()
    sprite_emoji = _resolve_pixel_sprite_emoji(slug)

    badges: list[str] = []
    if sprite_emoji:
        badges.append(sprite_emoji)
    if row["shiny"]:
        badges.append(SHINY_EMOJI)
    if row["gmax"]:
        badges.append(gmax_badge())

    gender_sym = format_gender_symbol(row["gender"])
    iv_pct = float(row["iv_percent"] or 0.0)
    prefix_str = f"{'  '.join(badges)}  " if badges else "  "
    return f"`{row['slot_num']}`{prefix_str}{row['display_name']}  {gender_sym}  •  Lvl. {row['level']}  •  {iv_pct:.2f}%"


def build_pokemon_list_embed(
    rows: list[sqlite3.Row],
    page: int = 0,
    per_page: int = 20,
) -> discord.Embed:
    total = len(rows)
    if total == 0:
        embed = discord.Embed(
            title="Your pokémon",
            description=f"You don't have any pokémon yet! Catch wild pokémon with `{PREFIX}c <name>`.",
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


def _format_relative_duration(started_ts: float) -> str:
    elapsed = max(0, int(time.time() - started_ts))
    years = elapsed // (365 * 24 * 3600)
    if years >= 1:
        return f"{years} year{'s' if years != 1 else ''} ago"
    days = elapsed // (24 * 3600)
    if days >= 1:
        return f"{days} day{'s' if days != 1 else ''} ago"
    hours = elapsed // 3600
    if hours >= 1:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    minutes = max(1, elapsed // 60)
    return f"{minutes} minute{'s' if minutes != 1 else ''} ago"


def build_profile_embed(
    user_row: sqlite3.Row,
    target_user: discord.User | discord.Member,
    unique_dex: int,
    max_dex: int = 1025,
) -> discord.Embed:
    started_ts = float(user_row["started_at"] or time.time())
    started_str = datetime.fromtimestamp(started_ts).strftime("%d %B %Y %H:%M")
    rel_str = _format_relative_duration(started_ts)

    total_caught = int(user_row["total_caught"] or 0)
    shiny_caught = int(user_row["shiny_caught"] or 0)
    gmax_caught = int(user_row["gmax_caught"] or 0)
    dex_pct = round((unique_dex / max(1, max_dex)) * 100.0)

    desc = (
        f"**Trainer Profile**\n"
        f"Started at {started_str} ({rel_str})!\n\n"
        f"**Pokémon Caught**\n"
        f"Total: {total_caught}\n"
        f"Pokédex: {unique_dex}/{max_dex} ({dex_pct}%)\n"
        f"Gigantamax: {gmax_caught}\n"
        f"Shiny: {shiny_caught}"
    )

    embed = discord.Embed(
        description=desc,
        color=discord.Color.from_rgb(235, 195, 75),
    )
    embed.set_author(name=target_user.display_name, icon_url=target_user.display_avatar.url)
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


class ShinyResetConfirmView(discord.ui.View):
    def __init__(self, author_id: int, current_chain: int, db: Database):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.current_chain = current_chain
        self.db = db

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the command author can confirm or cancel this reset.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = self.db.ensure_user(self.author_id)
        self.db.set_shiny_hunt(self.author_id, row["shiny_hunt_slug"], reset_chain=True)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=make_embed(
                "Shiny Hunt Reset",
                f"Your shiny hunt chain has been reset from **{self.current_chain}** to **0**.",
                (112, 186, 134),
            ),
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=make_embed(
                "Reset Cancelled",
                f"Kept your shiny hunt chain at **{self.current_chain}**.",
                (148, 163, 184),
            ),
            view=self,
        )
        self.stop()


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
        hunt_label = pdata["display_name"] if pdata else format_regional_display_name(hunt_slug)
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
    embed.add_field(name="Chain", value=f"**{chain}**", inline=False)
    return embed


def _format_incense_footer(user_row: sqlite3.Row) -> str:
    now = time.time()
    until_ts = float(user_row["incense_until"] or 0.0)
    rem = float(user_row["incense_remaining"] or 0.0)
    spawns_left = int(user_row["incense_spawns_left"] or 0)
    interval = int(user_row["incense_interval"] or 20)

    if until_ts > now and spawns_left > 0:
        status = "Active"
        sec_left = max(0.0, until_ts - now)
        end_dt = datetime.fromtimestamp(until_ts).strftime("%d/%m/%Y %H:%M")
    elif rem > 0 and spawns_left > 0:
        status = "Paused"
        sec_left = rem
        end_dt = datetime.fromtimestamp(now + rem).strftime("%d/%m/%Y %H:%M")
    else:
        status = "Inactive"
        sec_left = 0.0
        end_dt = datetime.fromtimestamp(now).strftime("%d/%m/%Y %H:%M")

    mins_left = max(0, int(sec_left // 60))
    return (
        f"Incense: {status}.\n"
        f"Spawns Remaining: {spawns_left}.\n"
        f"Spawn Interval: {interval}s.\n"
        f"Ends in {mins_left}m at | {end_dt}"
    )


# ==============================================================================
# Bot Class & Spawn Mechanics
# ==============================================================================
class PokeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            owner_ids=OWNER_IDS,
        )
        self.db = Database(DB_PATH)
        self.pokeapi = PokeAPIClient()
        self.renderer = SceneRenderer()
        self.active_spawns: dict[int, dict[str, Any]] = {}
        self.channel_msg_counts: dict[int, int] = {}
        self._incense_task: Optional[asyncio.Task] = None

    async def setup_hook(self):
        self._incense_task = asyncio.create_task(self._incense_loop())

    async def close(self):
        if self._incense_task and not self._incense_task.done():
            self._incense_task.cancel()
        await self.pokeapi.close()
        await super().close()

    async def _incense_loop(self):
        while not self.is_closed():
            try:
                await asyncio.sleep(5)
                now = time.time()
                active_rows = self.db.get_active_incense_users()
                for urow in active_rows:
                    uid = int(urow["user_id"])
                    ch_id = int(urow["incense_channel_id"])
                    interval = int(urow["incense_interval"] or 20)
                    until_ts = float(urow["incense_until"] or 0.0)
                    last_spawn = float(self.active_spawns.get(ch_id, {}).get("_incense_last_ts", 0.0))
                    if until_ts > now and (now - last_spawn) >= interval:
                        channel = self.get_channel(ch_id) or await self.fetch_channel(ch_id)
                        if channel:
                            left = self.db.decrement_incense_spawn(uid)
                            updated_row = self.db.ensure_user(uid)
                            footer_txt = _format_incense_footer(updated_row)
                            await self.trigger_random_spawn(
                                channel,
                                incense_footer=footer_txt if left > 0 else None,
                                incense_last_ts=now,
                            )
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    async def trigger_random_spawn(
        self,
        channel: discord.abc.Messageable,
        custom_mon: Optional[dict[str, Any]] = None,
        force_shiny: bool = False,
        force_gmax: bool = False,
        incense_footer: Optional[str] = None,
        incense_last_ts: Optional[float] = None,
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

        # Render normal artwork during wild spawn; reveal shiny/gmax only after catch
        art_url = spawn.get("artwork_url") or spawn.get("shiny_artwork_url")
        sprite = await self.pokeapi.fetch_image(art_url)
        card_buf = self.renderer.render_spawn_card(
            sprite=sprite,
            types=spawn.get("types", []),
            is_shiny=False,
            is_gmax=False,
        )

        channel_id = getattr(channel, "id", 0)
        spawn_record = dict(spawn)
        if incense_last_ts is not None:
            spawn_record["_incense_last_ts"] = incense_last_ts
        self.active_spawns[channel_id] = spawn_record

        desc = f"Guess the pokémon and type `{PREFIX}c <pokémon>` to catch it!"
        if incense_footer:
            desc = f"{desc}\n\n{incense_footer}"

        embed = discord.Embed(
            title="A wild pokémon has appeared!",
            description=desc,
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

    normalized_content = normalize_prefix_text(message.content)
    if normalized_content != message.content:
        message.content = normalized_content

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
    for region_name, starters in STARTERS_BY_REGION.items():
        embed.add_field(
            name=f"{region_name} region starters",
            value=", ".join(starters),
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.command(name="profile", aliases=["pf"])
async def profile_cmd(ctx: commands.Context, *, raw_args: str = ""):
    tokens = raw_args.strip().split()
    target = _extract_target_user(ctx, tokens) if tokens else ctx.author
    if target is None:
        target = ctx.author

    user_row = bot.db.ensure_user(target.id)
    unique_dex = bot.db.get_unique_dex_count(target.id)
    discord_user: discord.User | discord.Member
    if isinstance(target, (discord.Member, discord.User)):
        discord_user = target
    else:
        fetched = bot.get_user(target.id)
        discord_user = fetched if fetched is not None else ctx.author

    embed = build_profile_embed(
        user_row=user_row,
        target_user=discord_user,
        unique_dex=unique_dex,
        max_dex=bot.pokeapi._max_dex,
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

    clean_guess = guess.strip().lower()
    clean_slug_guess = clean_guess.replace(" ", "-")
    valid_names = {
        str(spawn["slug"]).lower(),
        str(spawn["display_name"]).lower(),
        str(spawn["display_name"]).lower().replace(" ", "-"),
    }
    if not clean_guess or (clean_guess not in valid_names and clean_slug_guess not in valid_names):
        await ctx.send("That is not the right pokémon! Try again.")
        return

    del bot.active_spawns[ctx.channel.id]
    slot = bot.db.insert_pokemon(ctx.author.id, spawn)
    bot.db.record_catch_stats(
        ctx.author.id,
        is_shiny=bool(spawn.get("shiny")),
        is_gmax=bool(spawn.get("gmax")),
    )
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
        msg += f"\n\n+1 Shiny chain! (**{new_chain}**)"
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
    cleaned_arg = mon_name.strip()
    if cleaned_arg.lower() == "reset":
        user_row = bot.db.ensure_user(ctx.author.id)
        old_chain = int(user_row["shiny_chain"] or 0)
        view = ShinyResetConfirmView(
            author_id=ctx.author.id,
            current_chain=old_chain,
            db=bot.db,
        )
        await ctx.send(
            embed=make_embed(
                "Confirm Shiny Hunt Reset",
                f"Are you sure you want to reset your shiny hunt chain (**{old_chain}**)?",
                (235, 135, 175),
            ),
            view=view,
        )
        return

    if not cleaned_arg:
        embed = await build_shiny_hunt_embed(bot, ctx.author.id)
        await ctx.send(embed=embed, view=ShinyHuntView(ctx, bot))
        return

    pdata = await bot.pokeapi.get_pokemon_data(cleaned_arg)
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
        bot.db.start_incense(
            ctx.author.id,
            ctx.channel.id,
            duration_sec=900,
            spawns_count=45,
            interval_sec=20,
        )
        updated_row = bot.db.ensure_user(ctx.author.id)
        footer_txt = _format_incense_footer(updated_row)
        await bot.trigger_random_spawn(ctx.channel, incense_footer=footer_txt)
        await ctx.send(
            embed=make_embed(
                "Incense Activated",
                f"Spent **{cost:,} pc** and activated Incense in this channel!",
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
async def inc_cmd(ctx: commands.Context, action: str = ""):
    act = action.strip().lower()
    if act in ("p", "pause"):
        ok, rem_sec = bot.db.pause_incense(ctx.author.id)
        mins = int(rem_sec // 60)
        secs = int(rem_sec % 60)
        if ok:
            await ctx.send(
                embed=make_embed(
                    "Incense Paused",
                    f"Paused your incense with **{mins}m {secs}s** remaining. Use `{PREFIX}inc r` to resume.",
                    (235, 135, 175),
                )
            )
        else:
            await ctx.send(
                embed=make_embed(
                    "Cannot Pause Incense",
                    "You don't have an active incense timer running right now.",
                    (186, 108, 108),
                )
            )
        return

    if act in ("r", "resume"):
        ok, rem_sec = bot.db.resume_incense(ctx.author.id, channel_id=ctx.channel.id)
        mins = int(rem_sec // 60)
        secs = int(rem_sec % 60)
        if ok:
            await ctx.send(
                embed=make_embed(
                    "Incense Resumed",
                    f"Resumed your incense in this channel with **{mins}m {secs}s** remaining.",
                    (112, 186, 134),
                )
            )
        else:
            await ctx.send(
                embed=make_embed(
                    "Cannot Resume Incense",
                    "You don't have a paused incense timer to resume.",
                    (186, 108, 108),
                )
            )
        return

    await buy_cmd(ctx, item_name="incense")


# ==============================================================================
# Owner-Only Commands
# ==============================================================================
def _extract_target_user(ctx: commands.Context, tokens: list[str]) -> Optional[discord.Member | discord.User]:
    if ctx.message.mentions:
        return ctx.message.mentions[0]
    for tok in tokens:
        cleaned = re.sub(r"[<@!>]", "", tok)
        if cleaned.isdigit():
            uid = int(cleaned)
            member = ctx.guild.get_member(uid) if ctx.guild else None
            if member:
                return member
            user = bot.get_user(uid)
            if user:
                return user
            return discord.Object(id=uid)  # type: ignore[return-value]
    return None


def _parse_signed_amount(tokens: list[str]) -> Optional[int]:
    for tok in tokens:
        t = tok.strip().replace(",", "")
        if re.match(r"^[+-]?\d+$", t):
            return int(t)
    return None


@bot.command(name="owner")
async def owner_cmd(ctx: commands.Context, *, raw_args: str = ""):
    tokens = raw_args.strip().split()
    if not tokens:
        await ctx.send(
            embed=make_embed(
                "Bot Owner",
                f"Configured bot owner: <@{OWNER_ID}> (`{OWNER_ID}`).",
                (235, 135, 175),
            )
        )
        return

    target = _extract_target_user(ctx, tokens)
    if target is None:
        cleaned = re.sub(r"[<@!>]", "", tokens[0])
        if cleaned.isdigit():
            target_id = int(cleaned)
        else:
            await ctx.send(
                embed=make_embed(
                    "Invalid User",
                    f"Usage: `{PREFIX}owner [@user | user_id]`",
                    (186, 108, 108),
                )
            )
            return
    else:
        target_id = target.id

    is_own = target_id == OWNER_ID
    await ctx.send(
        embed=make_embed(
            "Owner Check",
            f"<@{target_id}> (`{target_id}`) is {'the configured bot owner.' if is_own else 'not the configured bot owner.'}",
            (112, 186, 134) if is_own else (186, 108, 108),
        )
    )


@bot.command(name="addbal")
@commands.is_owner()
async def addbal_cmd(ctx: commands.Context, *, raw_args: str = ""):
    tokens = raw_args.strip().split()
    amount = _parse_signed_amount(tokens)
    target = _extract_target_user(ctx, tokens)
    if amount is None or target is None:
        await ctx.send(
            embed=make_embed(
                "Invalid Usage",
                f"Usage: `{PREFIX}addbal <amount> pc @user`",
                (186, 108, 108),
            )
        )
        return

    bot.db.add_balance(target.id, amount)
    user_row = bot.db.ensure_user(target.id)
    mention_str = target.mention if hasattr(target, "mention") else f"<@{target.id}>"
    await ctx.send(
        embed=make_embed(
            "Balance Updated",
            f"Adjusted {mention_str}'s balance by **{amount:+,} pc**.\nNew balance: **{int(user_row['balance'] or 0):,} pc**",
            (112, 186, 134),
        )
    )


@bot.command(name="addredeems")
@commands.is_owner()
async def addredeems_cmd(ctx: commands.Context, *, raw_args: str = ""):
    tokens = raw_args.strip().split()
    amount = _parse_signed_amount(tokens)
    target = _extract_target_user(ctx, tokens)
    if amount is None or target is None:
        await ctx.send(
            embed=make_embed(
                "Invalid Usage",
                f"Usage: `{PREFIX}addredeems <amount> @user`",
                (186, 108, 108),
            )
        )
        return

    bot.db.add_redeems(target.id, amount)
    user_row = bot.db.ensure_user(target.id)
    mention_str = target.mention if hasattr(target, "mention") else f"<@{target.id}>"
    await ctx.send(
        embed=make_embed(
            "Redeems Updated",
            f"Adjusted {mention_str}'s redeems by **{amount:+,}**.\nNew redeems: **{int(user_row['redeems'] or 0):,}**",
            (112, 186, 134),
        )
    )


@bot.command(name="addshards")
@commands.is_owner()
async def addshards_cmd(ctx: commands.Context, *, raw_args: str = ""):
    tokens = raw_args.strip().split()
    amount = _parse_signed_amount(tokens)
    target = _extract_target_user(ctx, tokens)
    if amount is None or target is None:
        await ctx.send(
            embed=make_embed(
                "Invalid Usage",
                f"Usage: `{PREFIX}addshards <amount> @user`",
                (186, 108, 108),
            )
        )
        return

    bot.db.add_shards(target.id, amount)
    user_row = bot.db.ensure_user(target.id)
    mention_str = target.mention if hasattr(target, "mention") else f"<@{target.id}>"
    await ctx.send(
        embed=make_embed(
            "Shards Updated",
            f"Adjusted {mention_str}'s shards by **{amount:+,}**.\nNew shards: **{int(user_row['shards'] or 0):,}**",
            (112, 186, 134),
        )
    )


@bot.command(name="spawnmon")
@commands.is_owner()
async def spawnmon_cmd(ctx: commands.Context, *, args: str = ""):
    """
    Syntax:
      p!spawnmon <mon_name> <level> <iv%[(stat-val,...)]> [shiny] [gmax]
    """
    raw = args.strip()
    if not raw:
        await bot.trigger_random_spawn(ctx.channel)
        return

    flag_tokens = re.findall(r"\b(?:shiny|gmax)\b", raw, flags=re.IGNORECASE)
    force_shiny = any(f.lower() == "shiny" for f in flag_tokens)
    force_gmax = any(f.lower() == "gmax" for f in flag_tokens)
    cleaned_core = re.sub(r"\b(?:shiny|gmax)\b", "", raw, flags=re.IGNORECASE).strip()

    match = re.match(
        r"^(.+?)\s+(\d+)\s+([0-9]+(?:\.[0-9]+)?\s*%?(?:\s*\([^)]*\))?)\s*$",
        cleaned_core,
        flags=re.IGNORECASE,
    )

    if not match:
        pdata = await bot.pokeapi.get_pokemon_data(cleaned_core)
        if not pdata:
            await ctx.send(
                embed=make_embed(
                    "Not Found",
                    f"Could not find a pokémon matching `{cleaned_core}`.\nUsage: `{PREFIX}spawnmon <mon> <level> <iv%> [shiny] [gmax]`",
                    (186, 108, 108),
                )
            )
            return
        mon = build_pokemon_payload(
            pdata,
            force_shiny=force_shiny,
            force_gmax=force_gmax,
            exact_forced_flags=True,
        )
        await bot.trigger_random_spawn(ctx.channel, custom_mon=mon)
        return

    mon_query = match.group(1).strip()
    custom_level = max(1, min(100, int(match.group(2))))
    iv_spec_raw = match.group(3).strip()

    try:
        target_iv_pct, pinned_ivs = parse_iv_spec(iv_spec_raw)
    except ValueError:
        await ctx.send(
            embed=make_embed(
                "Invalid IV Format",
                "Could not parse IV specification. Example: `80%(atk-31,spd-31)` or `75.5`.",
                (186, 108, 108),
            )
        )
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

    mon = build_pokemon_payload(
        pdata,
        force_shiny=force_shiny,
        force_gmax=force_gmax,
        custom_level=custom_level,
        custom_iv_pct=target_iv_pct,
        pinned_ivs=pinned_ivs if pinned_ivs else None,
        exact_forced_flags=True,
    )
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
