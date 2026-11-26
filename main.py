import os
import io
import re
import json
import math
import random
import asyncio
from datetime import datetime, timezone, timedelta
import aiohttp
from PIL import Image, ImageDraw
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

# ==========================================
# ⚙️ CONFIG & DATABASE
# ==========================================
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_ID = int(os.getenv("OWNER_ID") or 772797011899973633)

GMAX_EMOJI = "<:Gmax:1575503911932919948>"
MALE_EMOJI = "<:male:1566169579300851852>"
FEMALE_EMOJI = "<:Female:1566169649249263627>"
GENDERLESS_EMOJI = "❔"
SHINY_EMOJI = "✨"

NATURES = [
    "Adamant", "Bashful", "Bold", "Brave", "Calm", "Careful", "Docile",
    "Gentle", "Hardy", "Hasty", "Impish", "Jolly", "Lax", "Lonely",
    "Mild", "Modest", "Naive", "Naughty", "Quiet", "Quirky", "Rash",
    "Relaxed", "Sassy", "Serious", "Timid",
]

GENDERLESS_IDS = {
    81, 82, 100, 101, 120, 121, 132, 137, 172, 201, 233, 292, 337, 338,
    343, 344, 361, 374, 375, 376, 377, 378, 379, 382, 383, 384, 385, 386,
    436, 437, 462, 474, 479, 480, 481, 482, 483, 484, 486, 487, 489, 490,
    492, 493, 494, 599, 600, 601, 615, 622, 623, 638, 639, 640, 643, 644,
    645, 646, 647, 648, 649, 703, 716, 717, 718, 721, 772, 773, 774, 781,
    785, 786, 787, 788, 789, 790, 791, 792, 793, 794, 795, 796, 797, 798,
    799, 800, 801, 802, 803, 804, 805, 806, 807, 808, 809, 854, 855, 876,
    888, 889, 890, 893, 894, 895, 896, 897, 898, 905, 916, 926, 931, 936,
    937, 964, 970, 979, 981, 982, 984, 985, 986, 987, 988, 989, 990, 991,
    992, 993, 994, 995, 996, 997, 998, 999, 1000, 1001, 1002, 1003, 1004,
    1005, 1006, 1007, 1008, 1009, 1010, 1014, 1015, 1016, 1017, 1018, 1019,
    1020, 1021, 1022, 1023, 1024, 1025,
}

TYPE_BIOME_PALETTES = {
    "grass":   ((22, 78, 52), (56, 148, 82), (132, 206, 118)),
    "bug":     ((26, 82, 48), (68, 152, 74), (154, 214, 104)),
    "water":   ((14, 48, 96), (26, 108, 176), (72, 178, 224)),
    "ice":     ((58, 108, 158), (124, 184, 224), (198, 232, 248)),
    "fire":    ((68, 20, 16), (168, 58, 24), (238, 132, 42)),
    "ground":  ((92, 62, 34), (166, 122, 68), (218, 182, 118)),
    "rock":    ((64, 58, 54), (118, 108, 98), (168, 156, 142)),
    "electric":((34, 42, 88), (74, 92, 168), (242, 208, 68)),
    "flying":  ((54, 124, 198), (116, 182, 236), (196, 228, 248)),
    "psychic": ((68, 28, 92), (138, 66, 168), (222, 138, 214)),
    "ghost":   ((28, 20, 56), (68, 44, 116), (128, 92, 176)),
    "dark":    ((16, 18, 30), (38, 42, 66), (86, 78, 128)),
    "dragon":  ((26, 36, 88), (58, 82, 168), (118, 168, 232)),
    "fairy":   ((98, 48, 92), (176, 104, 164), (242, 184, 222)),
    "steel":   ((58, 68, 82), (108, 122, 142), (176, 190, 208)),
    "poison":  ((58, 26, 76), (114, 52, 138), (168, 106, 188)),
    "fighting":((88, 34, 28), (156, 68, 48), (216, 126, 74)),
    "normal":  ((56, 118, 168), (92, 168, 124), (154, 206, 122)),
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=("p!", "P!"), owner_id=OWNER_ID, intents=intents)

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["poketwo_mini"]
users_col = db["users"]
config_col = db["bot_config"]

POKEDEX_FILE = "pokedex.json"
POKEDEX: list[dict] = []
POKEDEX_BY_NAME: dict[str, dict] = {}
GMAX_POKEDEX: list[dict] = []
EMOJI_CACHE: dict[str, str] = {}
TYPE_CACHE: dict[int, list[str]] = {}

STARTERS = ["Bulbasaur", "Charmander", "Squirtle", "Pikachu", "Eevee", "Rowlet", "Froakie", "Sprigatito"]
LEGENDARY_IDS = {
    144, 145, 146, 150, 151, 243, 244, 245, 249, 250, 251,
    377, 378, 379, 380, 381, 382, 383, 384, 385, 386,
    480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493,
    494, 638, 639, 640, 641, 642, 643, 644, 645, 646, 647, 648, 649,
    716, 717, 718, 719, 720, 721, 785, 786, 787, 788, 789, 790, 791, 792, 800, 801, 802, 807, 808, 809,
    888, 889, 890, 891, 892, 893, 894, 895, 896, 897, 898,
    905, 1001, 1002, 1003, 1004, 1007, 1008, 1014, 1015, 1016, 1017, 1024, 1025,
}
GMAX_ELIGIBLE_SLUGS = {
    "venusaur", "charizard", "blastoise", "butterfree", "pikachu", "meowth",
    "machamp", "gengar", "kingler", "lapras", "eevee", "snorlax", "garbodor",
    "melmetal", "rillaboom", "cinderace", "inteleon", "corviknight", "drednaw",
    "coalossal", "flapple", "appletun", "sandaconda", "toxtricity", "centiskorch",
    "hatterene", "grimmsnarl", "alcremie", "copperajah", "duraludon", "urshifu",
}

# Force-shine state: None | "shiny" | "gmax_shiny"
force_shiny_mode: str | None = None

# ==========================================
# 👑 OWNER CHECK HELPERS
# ==========================================
async def get_owner_ids() -> set[int]:
    ids = set()
    if OWNER_ID:
        ids.add(OWNER_ID)
    doc = await config_col.find_one({"_id": "owner"})
    if doc and doc.get("owner_ids"):
        ids.update(int(uid) for uid in doc["owner_ids"])
    return ids

def is_bot_owner():
    async def predicate(ctx):
        owner_ids = await get_owner_ids()
        if owner_ids:
            return ctx.author.id in owner_ids
        return await bot.is_owner(ctx.author)
    return commands.check(predicate)

# ==========================================
# 📚 POKÉDEX LOADER & APPLICATION EMOJI SYNC
# ==========================================
async def load_pokedex():
    global POKEDEX, POKEDEX_BY_NAME, GMAX_POKEDEX
    if os.path.exists(POKEDEX_FILE):
        with open(POKEDEX_FILE, "r", encoding="utf-8") as f:
            POKEDEX = json.load(f)
    else:
        print("⏳ Fetching 1,025 Pokémon from PokéAPI (one-time setup)...")
        url = "https://pokeapi.co/api/v2/pokemon?limit=1025"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()

        entries = []
        for idx, item in enumerate(data["results"], start=1):
            slug = item["name"]
            display_name = slug.replace("-", " ").title()
            rarity = 3 if idx in LEGENDARY_IDS else 35
            entries.append({
                "dex_id": idx,
                "name": display_name,
                "slug": slug,
                "rarity": rarity,
                "gmax": False,
            })

            if slug in GMAX_ELIGIBLE_SLUGS:
                gmax_slug = f"{slug}-gmax"
                entries.append({
                    "dex_id": idx,
                    "name": f"Gigantamax {display_name}",
                    "slug": gmax_slug,
                    "rarity": 6,
                    "gmax": True,
                })

        with open(POKEDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)
        POKEDEX = entries

    POKEDEX_BY_NAME = {}
    GMAX_POKEDEX = []
    for p in POKEDEX:
        POKEDEX_BY_NAME[p["name"].lower()] = p
        if p.get("gmax"):
            GMAX_POKEDEX.append(p)
            base_title = p["name"].replace("Gigantamax ", "", 1).strip().lower()
            POKEDEX_BY_NAME.setdefault(f"gmax {base_title}", p)
    print(f"✅ Loaded {len(POKEDEX)} Pokémon entries ({len(GMAX_POKEDEX)} Gmax) into Pokédex.")

async def get_pokemon_types(dex_id: int, slug: str = "") -> list[str]:
    if dex_id in TYPE_CACHE:
        return TYPE_CACHE[dex_id]
    try:
        query_key = slug or str(dex_id)
        url = f"https://pokeapi.co/api/v2/pokemon/{query_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    types = [t["type"]["name"].lower() for t in data.get("types", [])]
                    if types:
                        TYPE_CACHE[dex_id] = types
                        return types
    except Exception:
        pass
    TYPE_CACHE[dex_id] = ["normal"]
    return ["normal"]

async def ensure_pokemon_emoji(mon: dict) -> str:
    """Fetches or uploads a small box icon as a Bot Application Emoji on demand."""
    base_slug = mon["slug"].replace("-gmax", "")
    if base_slug in EMOJI_CACHE:
        return EMOJI_CACHE[base_slug]

    emoji_name = base_slug.replace("-", "_")[:32]
    try:
        if not EMOJI_CACHE:
            existing = await bot.fetch_application_emojis()
            for e in existing:
                EMOJI_CACHE[e.name.replace("_", "-")] = str(e)
            if base_slug in EMOJI_CACHE:
                return EMOJI_CACHE[base_slug]

        icon_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/versions/generation-viii/icons/{mon['dex_id']}.png"
        async with aiohttp.ClientSession() as session:
            async with session.get(icon_url) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    created = await bot.create_application_emoji(name=emoji_name, image=img_bytes)
                    EMOJI_CACHE[base_slug] = str(created)
                    return str(created)
    except Exception as e:
        print(f"Emoji sync note for {base_slug}: {e}")

    return "🔹"

async def ensure_user_doc(user_id: int) -> dict:
    user = await users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "selected": 1,
            "coins": 0,
            "shards": 0,
            "redeems": 0,
            "catches": 0,
            "daily_streak": 0,
            "last_daily": None,
            "hunt_target": None,
            "hunt_chain": 0,
            "pokemon": [],
        }
        await users_col.insert_one(user)
    return user

def get_gender_emoji(mon: dict) -> str:
    gender = mon.get("gender")
    if gender == "Male":
        return MALE_EMOJI
    if gender == "Female":
        return FEMALE_EMOJI
    if gender == "Genderless" or mon.get("dex_id") in GENDERLESS_IDS:
        return GENDERLESS_EMOJI
    return MALE_EMOJI

# ==========================================
# 🎨 SPAWN IMAGE GENERATOR (Biome + Art)
# ==========================================
def get_sprite_url(dex_id: int, shiny: bool = False) -> str:
    if shiny:
        return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/shiny/{dex_id}.png"
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{dex_id}.png"

def _generate_biome_background(types: list[str], width=800, height=500) -> Image.Image:
    primary_type = types[0] if types else "normal"
    top_c, mid_c, ground_c = TYPE_BIOME_PALETTES.get(primary_type, TYPE_BIOME_PALETTES["normal"])

    bg = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(bg)
    horizon_y = int(height * 0.64)

    for y in range(horizon_y):
        ratio = y / max(1, horizon_y)
        r = int(top_c[0] + (mid_c[0] - top_c[0]) * ratio)
        g = int(top_c[1] + (mid_c[1] - top_c[1]) * ratio)
        b = int(top_c[2] + (mid_c[2] - top_c[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Scenery silhouettes tailored to biome type
    if primary_type in ("grass", "bug"):
        for x in range(40, width, 95):
            trunk_x = x + 18
            draw.rectangle([trunk_x - 6, horizon_y - 75, trunk_x + 6, horizon_y + 12], fill=(54, 36, 22, 235))
            draw.ellipse([x - 24, horizon_y - 135, x + 60, horizon_y - 45], fill=(mid_c[0], mid_c[1], mid_c[2], 230))
    elif primary_type in ("rock", "ground"):
        peaks = [(0, horizon_y + 10), (140, horizon_y - 115), (290, horizon_y + 10),
                 (470, horizon_y - 135), (650, horizon_y + 10), (800, horizon_y - 90), (800, horizon_y + 10)]
        draw.polygon(peaks, fill=(mid_c[0], mid_c[1], mid_c[2], 220))
    elif primary_type in ("fire", "electric", "psychic", "ghost", "dark"):
        glow_cx, glow_cy = width // 2, int(height * 0.45)
        for radius, alpha in [(220, 45), (150, 75), (90, 110)]:
            draw.ellipse(
                [glow_cx - radius, glow_cy - radius, glow_cx + radius, glow_cy + radius],
                fill=(ground_c[0], ground_c[1], ground_c[2], alpha),
            )

    for y in range(horizon_y, height):
        ratio = (y - horizon_y) / max(1, height - horizon_y)
        r = int(ground_c[0] * (1.0 - 0.25 * ratio))
        g = int(ground_c[1] * (1.0 - 0.25 * ratio))
        b = int(ground_c[2] * (1.0 - 0.25 * ratio))
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    return bg

async def create_spawn_banner(dex_id: int, is_gmax: bool = False, slug: str = "") -> discord.File:
    types = await get_pokemon_types(dex_id, slug=slug)
    bg_folder = "backgrounds"
    matched_bg = None

    if os.path.isdir(bg_folder):
        all_imgs = [f for f in os.listdir(bg_folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
        for t in types:
            candidates = [f for f in all_imgs if t in f.lower()]
            if candidates:
                matched_bg = os.path.join(bg_folder, random.choice(candidates))
                break
        if not matched_bg and all_imgs:
            matched_bg = os.path.join(bg_folder, random.choice(all_imgs))

    if matched_bg:
        bg = Image.open(matched_bg).convert("RGBA").resize((800, 500))
    else:
        bg = _generate_biome_background(types, 800, 500)

    art_url = get_sprite_url(dex_id, shiny=False)
    async with aiohttp.ClientSession() as session:
        async with session.get(art_url) as resp:
            art_bytes = await resp.read()

    size = (420, 420) if is_gmax else (370, 370)
    sprite = Image.open(io.BytesIO(art_bytes)).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    paste_x = (bg.width - sprite.width) // 2
    paste_y = (bg.height - sprite.height) // 2 + (6 if is_gmax else 20)
    bg.alpha_composite(sprite, (paste_x, paste_y))

    buf = io.BytesIO()
    bg.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return discord.File(fp=buf, filename="spawn.jpg")

def compute_stats(level: int, ivs: list[int]) -> list[int]:
    hp_iv, atk_iv, def_iv, spa_iv, spd_iv, spe_iv = ivs
    hp = int(((2 * 60 + hp_iv) * level) / 100) + level + 10
    other_ivs = [atk_iv, def_iv, spa_iv, spd_iv, spe_iv]
    other_stats = [int(((2 * 60 + iv) * level) / 100) + 5 for iv in other_ivs]
    return [hp, *other_stats]

def generate_pokemon_data(mon_entry: dict, force_shiny: bool = False) -> dict:
    level = random.randint(1, 40)
    ivs = [random.randint(0, 31) for _ in range(6)]
    iv_percent = round((sum(ivs) / 186) * 100, 2)
    is_shiny = True if force_shiny else (random.randint(1, 4096) == 1)
    if mon_entry["dex_id"] in GENDERLESS_IDS:
        gender = "Genderless"
    else:
        gender = random.choice(["Male", "Female"])
    nature = random.choice(NATURES)
    return {
        "dex_id": mon_entry["dex_id"],
        "name": mon_entry["name"],
        "slug": mon_entry["slug"],
        "gmax": bool(mon_entry.get("gmax", False)),
        "level": level,
        "xp": 0,
        "next_xp": level * 50,
        "nature": nature,
        "gender": gender,
        "ivs": ivs,
        "iv_percent": iv_percent,
        "shiny": is_shiny,
    }

def get_milestone_reward(total_catches: int) -> tuple[int, str]:
    """Awards PC only at exact powers of 10 (10 -> 35, 100 -> 350, 1000 -> 3500, ...)."""
    if total_catches < 10:
        return 0, ""
    n = total_catches
    power = 0
    while n > 1 and n % 10 == 0:
        n //= 10
        power += 1
    if n == 1 and power >= 1:
        reward = 35 * (10 ** (power - 1))
        return reward, f"🏅 **{total_catches:,}th Catch Milestone!** +{reward:,} Pokécoins!"
    return 0, ""

# ==========================================
# ⚡ SPAWN & INCENSE ENGINE
# ==========================================
channel_state: dict[int, dict] = {}
# channel_id -> {"remaining": int, "interval": int, "ends_at": datetime, "paused": bool, "task": asyncio.Task | None}
active_incenses: dict[int, dict] = {}
SPAWN_THRESHOLD = 15

def _format_incense_status(inc: dict) -> str:
    now = datetime.now(timezone.utc)
    if inc.get("paused"):
        return (
            f"Incense: Paused.\n"
            f"Spawns Remaining: {inc['remaining']}.\n"
            f"Spawn Interval: {inc['interval']}s."
        )
    ends_at: datetime = inc["ends_at"]
    secs_left = max(0, int((ends_at - now).total_seconds()))
    mins_left = max(1, math.ceil(secs_left / 60)) if secs_left > 0 else 0
    end_str = ends_at.strftime("%d/%m/%Y %H:%M")
    return (
        f"Incense: Active.\n"
        f"Spawns Remaining: {inc['remaining']}.\n"
        f"Spawn Interval: {inc['interval']}s.\n"
        f"Ends in {mins_left}m at | {end_str}"
    )

async def trigger_spawn(channel: discord.TextChannel, forced_mon: dict = None, force_gmax_mode: bool = False):
    if forced_mon:
        chosen = forced_mon
    elif force_gmax_mode and GMAX_POKEDEX:
        chosen = random.choice(GMAX_POKEDEX)
    else:
        weights = [p["rarity"] for p in POKEDEX]
        chosen = random.choices(POKEDEX, weights=weights, k=1)[0]

    channel_state[channel.id] = {"count": 0, "spawn": chosen}

    is_gmax = bool(chosen.get("gmax", False))
    banner_file = await create_spawn_banner(chosen["dex_id"], is_gmax=is_gmax, slug=chosen.get("slug", ""))
    title_prefix = f"{GMAX_EMOJI} " if is_gmax else ""

    inc = active_incenses.get(channel.id)
    description = "Guess the pokémon and type `p!c <pokémon>` to catch it!"
    if inc and inc.get("remaining", 0) > 0:
        description += f"\n\n{_format_incense_status(inc)}"

    embed = discord.Embed(
        title=f"{title_prefix}A wild pokémon has appeared!",
        description=description,
        color=0x2B2D31,
    )
    embed.set_image(url="attachment://spawn.jpg")
    await channel.send(file=banner_file, embed=embed)

@bot.event
async def on_ready():
    await load_pokedex()
    try:
        existing = await bot.fetch_application_emojis()
        for e in existing:
            EMOJI_CACHE[e.name.replace("_", "-")] = str(e)
        print(f"✅ Cached {len(EMOJI_CACHE)} Pokémon Application Emojis.")
    except Exception as e:
        print(f"Emoji cache note: {e}")
    print(f"⚡ Pokétwo Mini online as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    if not message.content.lower().startswith("p!"):
        state = channel_state.setdefault(message.channel.id, {"count": 0, "spawn": None})
        state["count"] += 1
        if state["count"] >= SPAWN_THRESHOLD:
            gmax_spawn = (force_shiny_mode == "gmax_shiny")
            await trigger_spawn(message.channel, force_gmax_mode=gmax_spawn)

    await bot.process_commands(message)

# ==========================================
# 🎮 STARTER, CATCHING, HUNT & COLLECTION
# ==========================================
@bot.command(name="start")
async def start_game(ctx, *, choice: str = None):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if user and user.get("pokemon"):
        await ctx.send("❌ You already started! Use `p!p` to view your Pokémon.")
        return

    if not choice:
        starter_list = ", ".join(f"**{s}**" for s in STARTERS)
        embed = discord.Embed(
            title="Welcome to Pokétwo Mini!",
            description=f"Choose a starter using `p!start <name>`:\n\n{starter_list}",
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)
        return

    matched = next((s for s in STARTERS if s.lower() == choice.strip().lower()), None)
    if not matched:
        await ctx.send(f"❌ Invalid starter. Pick from: {', '.join(STARTERS)}")
        return

    entry = POKEDEX_BY_NAME[matched.lower()]
    starter_mon = generate_pokemon_data(entry)
    starter_mon["level"] = 5
    starter_mon["next_xp"] = 250
    await ensure_pokemon_emoji(entry)

    await users_col.update_one(
        {"user_id": ctx.author.id},
        {
            "$set": {
                "selected": 1,
                "pokemon": [starter_mon],
            },
            "$inc": {"coins": 500},
            "$setOnInsert": {
                "shards": 0,
                "redeems": 0,
                "catches": 0,
                "daily_streak": 0,
                "last_daily": None,
                "hunt_target": None,
                "hunt_chain": 0,
            },
        },
        upsert=True,
    )
    await ctx.send(f"🎉 Congratulations {ctx.author.mention}! You chose **{matched}** and received **500 Pokécoins**!")

@bot.command(name="c", aliases=["catch"])
async def catch_pokemon(ctx, *, guess: str = None):
    global force_shiny_mode

    state = channel_state.get(ctx.channel.id)
    if not state or not state.get("spawn"):
        await ctx.send("❌ There is no wild pokémon in this channel right now.")
        return

    if not guess:
        await ctx.send("❌ Usage: `p!c <pokémon name>`")
        return

    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user or not user.get("pokemon"):
        await ctx.send("❌ Type `p!start` first to begin your journey!")
        return

    active_spawn = state["spawn"]
    clean_guess = guess.strip().lower()
    valid_names = {active_spawn["name"].lower()}
    if active_spawn.get("gmax"):
        base_name = active_spawn["name"].replace("Gigantamax ", "", 1).strip().lower()
        valid_names.update({base_name, f"gmax {base_name}"})

    if clean_guess not in valid_names:
        await ctx.send("❌ That is the wrong pokémon!")
        return

    state["spawn"] = None

    mon_to_generate = active_spawn
    should_shine = False

    if force_shiny_mode == "gmax_shiny":
        if active_spawn.get("gmax"):
            should_shine = True
            force_shiny_mode = None
        else:
            base_slug = active_spawn["slug"].replace("-gmax", "")
            gmax_entry = (
                POKEDEX_BY_NAME.get(f"gigantamax {active_spawn['name'].lower()}")
                or POKEDEX_BY_NAME.get(f"gmax {active_spawn['name'].lower()}")
            )
            if base_slug in GMAX_ELIGIBLE_SLUGS and gmax_entry:
                mon_to_generate = gmax_entry
                should_shine = True
                force_shiny_mode = None
    elif force_shiny_mode == "shiny":
        should_shine = True
        force_shiny_mode = None

    caught_mon = generate_pokemon_data(mon_to_generate, force_shiny=should_shine)

    # Update hunt chain: increment only when catching hunt_target, reset only on shiny
    hunt_target = user.get("hunt_target")
    hunt_chain = user.get("hunt_chain", 0)
    chain_msg = ""

    base_caught = caught_mon["name"].replace("Gigantamax ", "", 1).strip().lower()
    is_hunt_target = bool(
        hunt_target and hunt_target.lower() in (caught_mon["name"].lower(), base_caught)
    )

    if caught_mon["shiny"]:
        if hunt_target and hunt_chain > 0:
            chain_msg = f"Shiny streak reset. ({hunt_chain})"
        hunt_chain = 0
    elif is_hunt_target:
        hunt_chain += 1
        chain_msg = f"+1 Shiny chain! ({hunt_chain})"

    new_catches = user.get("catches", 0) + 1
    coins_earned, bonus_text = get_milestone_reward(new_catches)

    await users_col.update_one(
        {"user_id": ctx.author.id},
        {
            "$push": {"pokemon": caught_mon},
            "$inc": {"coins": coins_earned, "catches": 1},
            "$set": {"hunt_chain": hunt_chain},
        },
    )

    is_gmax = bool(caught_mon.get("gmax"))
    gmax_tag = f" {GMAX_EMOJI}" if is_gmax else ""
    shiny_tag = f" {SHINY_EMOJI}" if caught_mon["shiny"] else ""
    gender_tag = f" {get_gender_emoji(caught_mon)}"

    catch_line = (
        f"Congratulations {ctx.author.mention}! You caught a "
        f"Level {caught_mon['level']} {caught_mon['name']}{gmax_tag}{shiny_tag}{gender_tag} ({caught_mon['iv_percent']:.2f}%)!"
    )

    extra_blocks = []
    if caught_mon["shiny"]:
        if is_gmax:
            extra_blocks.append(f"**{caught_mon['name']}** has the Gigantamax factor! {GMAX_EMOJI}")
        if chain_msg:
            extra_blocks.append(chain_msg)
        extra_blocks.append(f"These colors seem unusual... {SHINY_EMOJI}")
    else:
        if chain_msg:
            extra_blocks.append(chain_msg)

    if bonus_text:
        extra_blocks.append(bonus_text)

    full_message = catch_line
    if extra_blocks:
        full_message += "\n\n" + "\n\n".join(extra_blocks)

    await ctx.send(full_message)

@bot.command(name="hunt", aliases=["h", "sh"])
async def shiny_hunt(ctx, *, pokemon_name: str = None):
    user = await ensure_user_doc(ctx.author.id)

    if not pokemon_name:
        target = user.get("hunt_target")
        chain = user.get("hunt_chain", 0)
        if not target:
            await ctx.send("🔍 You don't have an active hunt. Use `p!hunt <pokémon>` to start one!")
            return
        await ctx.send(f"🔍 **Active Hunt:** **{target}** | **Chain:** **{chain}**")
        return

    sub = pokemon_name.strip().lower()
    if sub in ("clear", "stop", "reset"):
        await users_col.update_one({"user_id": ctx.author.id}, {"$set": {"hunt_target": None, "hunt_chain": 0}})
        await ctx.send("✅ Cleared your hunt target and reset your chain to **0**.")
        return

    entry = POKEDEX_BY_NAME.get(sub)
    if not entry:
        await ctx.send(f"❌ Could not find **{pokemon_name}** in the Pokédex.")
        return

    new_chain = user.get("hunt_chain", 0) if (user.get("hunt_target") or "").lower() == entry["name"].lower() else 0
    await users_col.update_one(
        {"user_id": ctx.author.id},
        {"$set": {"hunt_target": entry["name"], "hunt_chain": new_chain}},
    )
    await ctx.send(f"🎯 Now hunting **{entry['name']}**! Current chain: **{new_chain}**.")

@bot.command(name="hint")
async def spawn_hint(ctx):
    state = channel_state.get(ctx.channel.id)
    if not state or not state.get("spawn"):
        await ctx.send("❌ There is no wild pokémon right now.")
        return

    name = state["spawn"]["name"]
    indices = set(random.sample(range(len(name)), max(1, len(name) // 3)))
    hint_chars = [ch if (i in indices or ch == " ") else r"\_" for i, ch in enumerate(name)]
    await ctx.send(f"🔍 The wild pokémon is: **{''.join(hint_chars)}**")

# ==========================================
# 📋 COLLECTION FILTERING, SORTING & PAGINATION
# ==========================================
def parse_pokemon_query(raw_args: str | None) -> tuple[dict, int]:
    """Parses Pokétwo-style flags: --sh, --gmax, --n <name>, --lim <n>, --o <iv|iv+|iv-|lvl|lvl+|lvl->."""
    opts = {
        "shiny_only": False,
        "gmax_only": False,
        "name_filter": None,
        "order": None,
        "limit": None,
    }
    page = 1
    if not raw_args:
        return opts, page

    text = raw_args.strip()

    lim_match = re.search(r"--lim\s+(\d+)", text, flags=re.IGNORECASE)
    if lim_match:
        opts["limit"] = max(1, int(lim_match.group(1)))
        text = re.sub(r"--lim\s+\d+", "", text, flags=re.IGNORECASE)

    order_match = re.search(r"--o\s+(iv\+|iv-|iv|lvl\+|lvl-|lvl)", text, flags=re.IGNORECASE)
    if order_match:
        opts["order"] = order_match.group(1).lower()
        text = re.sub(r"--o\s+(?:iv\+|iv-|iv|lvl\+|lvl-|lvl)", "", text, flags=re.IGNORECASE)

    name_match = re.search(r"--n\s+(.+?)(?=\s+--|\s+\d+$|$)", text, flags=re.IGNORECASE)
    if name_match:
        opts["name_filter"] = name_match.group(1).strip().lower()
        text = text[:name_match.start()] + text[name_match.end():]

    if re.search(r"--sh\b", text, flags=re.IGNORECASE):
        opts["shiny_only"] = True
        text = re.sub(r"--sh\b", "", text, flags=re.IGNORECASE)

    if re.search(r"--gmax\b", text, flags=re.IGNORECASE):
        opts["gmax_only"] = True
        text = re.sub(r"--gmax\b", "", text, flags=re.IGNORECASE)

    page_match = re.search(r"\b(\d+)\b", text.strip())
    if page_match:
        page = max(1, int(page_match.group(1)))

    return opts, page

def filter_and_sort_pokemon(mons: list[dict], opts: dict) -> list[tuple[int, dict]]:
    """Returns list of (true_1_based_index, mon_dict) matching filters and sort order."""
    indexed = [(i + 1, m) for i, m in enumerate(mons)]

    if opts.get("shiny_only"):
        indexed = [(idx, m) for idx, m in indexed if m.get("shiny")]

    if opts.get("gmax_only"):
        indexed = [(idx, m) for idx, m in indexed if m.get("gmax")]

    name_filter = opts.get("name_filter")
    if name_filter:
        indexed = [(idx, m) for idx, m in indexed if name_filter in m.get("name", "").lower()]

    order = opts.get("order")
    if order in ("iv", "iv-"):
        indexed.sort(key=lambda pair: pair[1].get("iv_percent", 0.0), reverse=True)
    elif order == "iv+":
        indexed.sort(key=lambda pair: pair[1].get("iv_percent", 0.0), reverse=False)
    elif order in ("lvl", "lvl-"):
        indexed.sort(key=lambda pair: pair[1].get("level", 1), reverse=True)
    elif order == "lvl+":
        indexed.sort(key=lambda pair: pair[1].get("level", 1), reverse=False)

    if opts.get("limit"):
        indexed = indexed[: opts["limit"]]

    return indexed

def build_pokemon_embed(user_doc: dict, opts: dict, page: int) -> tuple[discord.Embed, int, int, list[tuple[int, dict]]]:
    filtered = filter_and_sort_pokemon(user_doc.get("pokemon", []), opts)
    total_filtered = len(filtered)
    per_page = 15
    total_pages = max(1, (max(1, total_filtered) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end = min(start + per_page, total_filtered)
    slice_items = filtered[start:end]

    lines = []
    selected_idx = user_doc.get("selected", 1)
    for true_idx, m in slice_items:
        emoji = EMOJI_CACHE.get(m["slug"].replace("-gmax", ""), "🔹")
        gmax_tag = f" {GMAX_EMOJI}" if m.get("gmax") else ""
        shiny_tag = f" {SHINY_EMOJI}" if m.get("shiny") else ""
        gender_tag = f" {get_gender_emoji(m)}"
        sel_tag = " **(Selected)**" if true_idx == selected_idx else ""
        lines.append(
            f"`{true_idx}` {emoji} **{m['name']}**{gmax_tag}{shiny_tag}{gender_tag} • "
            f"Lvl. {m['level']} • {m.get('iv_percent', 0.0):.2f}%{sel_tag}"
        )

    if not lines:
        lines.append("No matching pokémon found.")

    if total_filtered > 0:
        footer_text = f"Showing entries {start + 1}–{end} out of {total_filtered} (Page {page}/{total_pages})."
    else:
        footer_text = "Showing 0 entries."

    embed = discord.Embed(
        title="Your pokémon",
        description="\n".join(lines),
        color=0xEB459E,
    )
    embed.set_footer(text=footer_text)
    return embed, page, total_pages, filtered

class PokemonPageView(discord.ui.View):
    def __init__(self, author_id: int, opts: dict, page: int, total_pages: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.opts = opts
        self.page = page
        self.total_pages = total_pages
        self._sync_buttons()

    def _sync_buttons(self):
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

    async def _turn_page(self, interaction: discord.Interaction, delta: int):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can flip these pages.", ephemeral=True)
            return

        user_doc = await users_col.find_one({"user_id": self.author_id})
        if not user_doc or not user_doc.get("pokemon"):
            await interaction.response.send_message("❌ No Pokémon found.", ephemeral=True)
            return

        self.page = max(1, min(self.page + delta, self.total_pages))
        embed, self.page, self.total_pages, _ = build_pokemon_embed(user_doc, self.opts, self.page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._turn_page(interaction, -1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._turn_page(interaction, 1)

@bot.command(name="p", aliases=["pokemon"])
async def list_pokemon(ctx, *, query: str = None):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user or not user.get("pokemon"):
        await ctx.send("❌ You have no pokémon yet! Use `p!start`.")
        return

    if not EMOJI_CACHE:
        try:
            existing = await bot.fetch_application_emojis()
            for e in existing:
                EMOJI_CACHE[e.name.replace("_", "-")] = str(e)
        except Exception:
            pass

    opts, page = parse_pokemon_query(query)
    embed, current_page, total_pages, _ = build_pokemon_embed(user, opts, page)
    view = PokemonPageView(ctx.author.id, opts, current_page, total_pages) if total_pages > 1 else None
    await ctx.send(embed=embed, view=view)

@bot.command(name="s", aliases=["select"])
async def select_pokemon(ctx, number: int = None):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user or not user.get("pokemon"):
        await ctx.send("❌ You have no pokémon.")
        return

    if not number or number < 1 or number > len(user["pokemon"]):
        await ctx.send(f"❌ Pick a valid number between `1` and `{len(user['pokemon'])}`.")
        return

    await users_col.update_one({"user_id": ctx.author.id}, {"$set": {"selected": number}})
    chosen = user["pokemon"][number - 1]
    await ctx.send(f"✅ Selected your Level {chosen['level']} **{chosen['name']}** (`#{number}`).")

# ==========================================
# 🔍 POKÉMON INFO WITH NEXT / PREV ARROWS
# ==========================================
def build_pokemon_info_embed(author: discord.abc.User, m: dict, display_num: int, total_count: int) -> discord.Embed:
    level = m.get("level", 1)
    xp = m.get("xp", 0)
    next_xp = m.get("next_xp", level * 50)
    nature = m.get("nature", "Hardy")
    gender = m.get("gender", "Male")
    ivs = m.get("ivs", [15, 15, 15, 15, 15, 15])
    hp_iv, atk_iv, def_iv, spa_iv, spd_iv, spe_iv = ivs
    hp, atk, dfn, spa, spd, spe = compute_stats(level, ivs)
    iv_percent = m.get("iv_percent", round(sum(ivs) / 186 * 100, 2))
    gmax = f" {GMAX_EMOJI}" if m.get("gmax") else ""
    star = f" {SHINY_EMOJI}" if m.get("shiny") else ""
    gender_tag = f" {get_gender_emoji(m)}"

    description = (
        f"**Details**\n"
        f"**XP:** {xp}/{next_xp}\n"
        f"**Nature:** {nature}\n"
        f"**Gender:** {gender}\n\n"
        f"**Stats**\n"
        f"**HP:** {hp} – **IV:** {hp_iv}/31\n"
        f"**Attack:** {atk} – **IV:** {atk_iv}/31\n"
        f"**Defense:** {dfn} – **IV:** {def_iv}/31\n"
        f"**Sp. Atk:** {spa} – **IV:** {spa_iv}/31\n"
        f"**Sp. Def:** {spd} – **IV:** {spd_iv}/31\n"
        f"**Speed:** {spe} – **IV:** {spe_iv}/31\n"
        f"**Total IV:** {iv_percent:.2f}%"
    )

    embed = discord.Embed(
        title=f"Level {level} {m['name']}{gmax}{star}{gender_tag}",
        description=description,
        color=discord.Color.gold() if m.get("shiny") else 0x58B9FF,
    )
    if author.display_avatar:
        embed.set_thumbnail(url=author.display_avatar.url)
    embed.set_image(url=get_sprite_url(m["dex_id"], shiny=m.get("shiny", False)))
    embed.set_footer(text=f"Displaying pokémon {display_num} out of {total_count}.")
    return embed

class PokemonInfoView(discord.ui.View):
    def __init__(self, author_id: int, index: int, total_count: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.index = index          # 1-based index
        self.total_count = total_count
        self._sync_buttons()

    def _sync_buttons(self):
        self.prev_mon.disabled = self.index <= 1
        self.next_mon.disabled = self.index >= self.total_count

    async def _step_mon(self, interaction: discord.Interaction, delta: int):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can browse these Pokémon.", ephemeral=True)
            return

        user_doc = await users_col.find_one({"user_id": self.author_id})
        mons = (user_doc or {}).get("pokemon", [])
        if not mons:
            await interaction.response.send_message("❌ No Pokémon found.", ephemeral=True)
            return

        self.total_count = len(mons)
        self.index = max(1, min(self.index + delta, self.total_count))
        self._sync_buttons()
        embed = build_pokemon_info_embed(interaction.user, mons[self.index - 1], self.index, self.total_count)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_mon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._step_mon(interaction, -1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_mon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._step_mon(interaction, 1)

@bot.command(name="i", aliases=["info"])
async def pokemon_info(ctx, number: int = None):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user or not user.get("pokemon"):
        await ctx.send("❌ You have no pokémon.")
        return

    mons = user["pokemon"]
    total_count = len(mons)
    idx = number if number is not None else user.get("selected", 1)
    if idx < 1 or idx > total_count:
        await ctx.send(f"❌ Pick a valid pokémon number between `1` and `{total_count}`.")
        return

    embed = build_pokemon_info_embed(ctx.author, mons[idx - 1], idx, total_count)
    view = PokemonInfoView(ctx.author.id, idx, total_count) if total_count > 1 else None
    await ctx.send(embed=embed, view=view)

@bot.command(name="release")
async def release_pokemon(ctx, number: int = None):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user or len(user.get("pokemon", [])) <= 1:
        await ctx.send("❌ You must keep at least 1 Pokémon!")
        return

    if not number or number < 1 or number > len(user["pokemon"]):
        await ctx.send("❌ Specify a valid Pokémon number to release.")
        return

    mons = user["pokemon"]
    released = mons.pop(number - 1)
    new_sel = min(user.get("selected", 1), len(mons))

    await users_col.update_one(
        {"user_id": ctx.author.id},
        {"$set": {"pokemon": mons, "selected": new_sel}, "$inc": {"coins": 25}},
    )
    await ctx.send(f"👋 Released **{released['name']}** and received **25 Pokécoins**.")

# ==========================================
# 💰 POKÉCOINS, SHARDS, DAILY, SHOP, INCENSE & REDEEMS
# ==========================================
@bot.command(name="bal", aliases=["balance"])
async def check_balance(ctx, target: discord.User = None):
    member = target or ctx.author
    user = await users_col.find_one({"user_id": member.id})
    if not user:
        await ctx.send(f"❌ {member.display_name} hasn't started yet! Use `p!start`.")
        return

    embed = discord.Embed(
        title=f"{member.display_name}'s Balance",
        color=0x2B2D31,
    )
    embed.add_field(name="Pokécoins", value=f"{user.get('coins', 0):,}", inline=True)
    embed.add_field(name="Shards", value=f"{user.get('shards', 0):,}", inline=True)
    embed.add_field(name="Redeems", value=f"{user.get('redeems', 0):,}", inline=True)
    embed.set_footer(text=f"Total Catches: {user.get('catches', 0):,}")
    await ctx.send(embed=embed)

@bot.command(name="daily")
async def claim_daily(ctx):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user:
        await ctx.send("❌ Type `p!start` first!")
        return

    now = datetime.now(timezone.utc)
    last_daily = user.get("last_daily")
    streak = user.get("daily_streak", 0)

    if last_daily:
        last_dt = datetime.fromisoformat(last_daily)
        elapsed = now - last_dt
        if elapsed < timedelta(hours=20):
            remaining = timedelta(hours=20) - elapsed
            hrs, rem = divmod(int(remaining.total_seconds()), 3600)
            mins = rem // 60
            await ctx.send(f"⏳ You already claimed your daily! Come back in **{hrs}h {mins}m**.")
            return
        streak = streak + 1 if elapsed <= timedelta(hours=48) else 1
    else:
        streak = 1

    reward_coins = 500 + min(streak * 100, 1500)
    reward_shards = 2 if streak % 3 == 0 else 0
    got_redeem = (streak % 7 == 0)

    await users_col.update_one(
        {"user_id": ctx.author.id},
        {
            "$inc": {
                "coins": reward_coins,
                "shards": reward_shards,
                "redeems": 1 if got_redeem else 0,
            },
            "$set": {"daily_streak": streak, "last_daily": now.isoformat()},
        },
    )

    extras = []
    if reward_shards:
        extras.append(f"+{reward_shards} Shards")
    if got_redeem:
        extras.append("+1 Redeem 🎟️")
    bonus_line = f"\n✨ **Streak Bonus:** {' & '.join(extras)}!" if extras else ""

    await ctx.send(
        f"🎁 **Daily Reward Claimed!** (Streak: **{streak} days**)\n"
        f"You received **{reward_coins:,} Pokécoins**!{bonus_line}"
    )

@bot.command(name="shop")
async def view_shop(ctx):
    embed = discord.Embed(
        title="🛒 Pokétwo Shop",
        description=(
            "Use `p!buy <item> [amount]` to purchase:\n\n"
            "💎 **`shards <amount>`** — **200 Pokécoins each**\n"
            "• Exchange Pokécoins for Shards (`p!buy shards 50`).\n\n"
            "🎟️ **`redeem`** — **200 Shards**\n"
            "• Spawn any Pokémon of your choice (`p!rs <pokemon>`).\n\n"
            "🕯️ **`incense`** — **50 Shards**\n"
            "• Spawns 15 Pokémon automatically (1 every 15s) in this channel!\n\n"
            "🍬 **`candy`** — **250 Pokécoins**\n"
            "• Levels up your currently selected Pokémon by +1 Level."
        ),
        color=0x2B2D31,
    )
    await ctx.send(embed=embed)

async def _run_incense_loop(channel: discord.TextChannel):
    inc = active_incenses.get(channel.id)
    if not inc:
        return
    try:
        while inc["remaining"] > 0:
            if inc.get("paused"):
                await asyncio.sleep(2)
                continue
            await trigger_spawn(channel, force_gmax_mode=(force_shiny_mode == "gmax_shiny"))
            inc["remaining"] -= 1
            if inc["remaining"] <= 0:
                break
            await asyncio.sleep(inc["interval"])
        if inc.get("remaining", 0) <= 0:
            await channel.send("🕯️ The incense has ended.")
    finally:
        active_incenses.pop(channel.id, None)

@bot.command(name="incense")
async def incense_control(ctx, action: str = None):
    inc = active_incenses.get(ctx.channel.id)
    if not inc:
        await ctx.send("❌ There is no active incense in this channel. Buy one with `p!buy incense`.")
        return

    cmd = (action or "status").strip().lower()
    if cmd == "pause":
        inc["paused"] = True
        await ctx.send(f"Paused the incense in {ctx.channel.mention}. Use `p!incense resume` to resume it.")
    elif cmd == "resume":
        inc["paused"] = False
        inc["ends_at"] = datetime.now(timezone.utc) + timedelta(seconds=inc["remaining"] * inc["interval"])
        await ctx.send(f"Resumed the incense in {ctx.channel.mention}.")
    else:
        await ctx.send(_format_incense_status(inc))

@bot.command(name="buy")
async def buy_item(ctx, item: str = None, amount: int = 1):
    if not item:
        await ctx.send("❌ Usage: `p!buy <shards | redeem | incense | candy> [amount]`")
        return

    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user:
        await ctx.send("❌ Type `p!start` first!")
        return

    if amount < 1:
        await ctx.send("❌ Amount must be at least `1`.")
        return

    item = item.strip().lower()
    coins = user.get("coins", 0)
    shards = user.get("shards", 0)

    if item in ("shard", "shards"):
        cost = 200 * amount
        if coins < cost:
            await ctx.send(f"❌ You need **{cost:,} Pokécoins** to buy **{amount:,} Shards**.")
            return
        await users_col.update_one({"user_id": ctx.author.id}, {"$inc": {"coins": -cost, "shards": amount}})
        await ctx.send(f"💎 Exchanged **{cost:,} Pokécoins** for **{amount:,} Shards**!")

    elif item == "redeem":
        cost = 200 * amount
        if shards < cost:
            await ctx.send(f"❌ You need **{cost:,} Shards** to buy **{amount} Redeem(s)**.")
            return
        await users_col.update_one({"user_id": ctx.author.id}, {"$inc": {"shards": -cost, "redeems": amount}})
        await ctx.send(f"🎟️ Purchased **{amount} Redeem(s)** for **{cost:,} Shards**! Use `p!rs <pokémon>`.")

    elif item == "candy":
        cost = 250 * amount
        if coins < cost:
            await ctx.send(f"❌ You need **{cost:,} Pokécoins** to buy **{amount} Rare Candy(s)**.")
            return
        if not user.get("pokemon"):
            await ctx.send("❌ You don't have a Pokémon selected.")
            return
        sel_idx = user.get("selected", 1) - 1
        mons = user["pokemon"]
        new_lvl = min(100, mons[sel_idx]["level"] + amount)
        gained = new_lvl - mons[sel_idx]["level"]
        if gained <= 0:
            await ctx.send("❌ Your selected Pokémon is already Level 100!")
            return
        mons[sel_idx]["level"] = new_lvl
        mons[sel_idx]["next_xp"] = new_lvl * 50
        await users_col.update_one(
            {"user_id": ctx.author.id},
            {"$inc": {"coins": -(250 * gained)}, "$set": {"pokemon": mons}},
        )
        await ctx.send(f"🍬 Fed **{gained} Rare Candy(s)**! **{mons[sel_idx]['name']}** grew to **Level {new_lvl}**!")

    elif item == "incense":
        if shards < 50:
            await ctx.send("❌ You need **50 Shards** to activate Incense.")
            return
        if ctx.channel.id in active_incenses:
            await ctx.send("❌ An incense is already running in this channel!")
            return

        total_spawns = 15
        interval_sec = 15
        await users_col.update_one({"user_id": ctx.author.id}, {"$inc": {"shards": -50}})
        active_incenses[ctx.channel.id] = {
            "remaining": total_spawns,
            "interval": interval_sec,
            "ends_at": datetime.now(timezone.utc) + timedelta(seconds=total_spawns * interval_sec),
            "paused": False,
        }
        await ctx.send("🕯️ **Incense Activated!** 15 Pokémon will spawn here over the next few minutes!")
        asyncio.create_task(_run_incense_loop(ctx.channel))
    else:
        await ctx.send("❌ Unknown item. Check `p!shop`.")

@bot.command(name="rs", aliases=["redeemspawn", "redeem"])
async def redeem_spawn(ctx, *, pokemon_name: str = None):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user:
        await ctx.send("❌ Type `p!start` first!")
        return

    if user.get("redeems", 0) < 1:
        await ctx.send("❌ You don't have any Redeems! Buy one in `p!shop` for 200 Shards.")
        return

    if not pokemon_name:
        await ctx.send("❌ Usage: `p!rs <pokémon name>`")
        return

    target = POKEDEX_BY_NAME.get(pokemon_name.strip().lower())
    if not target:
        await ctx.send(f"❌ Could not find **{pokemon_name}** in the Pokédex.")
        return

    await users_col.update_one({"user_id": ctx.author.id}, {"$inc": {"redeems": -1}})
    await ctx.send(f"🎟️ {ctx.author.mention} used a Redeem to spawn **{target['name']}**!")
    await trigger_spawn(ctx.channel, forced_mon=target)

# ==========================================
# 👑 OWNER-ONLY COMMANDS
# ==========================================
@bot.command(name="owner")
async def add_bot_owner(ctx, member: discord.User = None):
    target = member or ctx.author
    current_owners = await get_owner_ids()

    if current_owners:
        is_allowed = (ctx.author.id in current_owners) or (await bot.is_owner(ctx.author))
        if not is_allowed:
            await ctx.send("❌ Only the bot owner can use this command.")
            return

    await config_col.update_one(
        {"_id": "owner"},
        {"$addToSet": {"owner_ids": target.id}},
        upsert=True,
    )
    bot.owner_id = target.id
    await ctx.send(f"👑 Added {target.mention} (`{target.id}`) as a bot owner!")

@bot.command(name="addbal", aliases=["addpc"])
@is_bot_owner()
async def owner_add_bal(ctx, amount: int, target: discord.User = None):
    member = target or ctx.author
    await ensure_user_doc(member.id)
    await users_col.update_one({"user_id": member.id}, {"$inc": {"coins": amount}})
    await ctx.send(f"✅ Added **{amount:,} Pokécoins** to {member.mention}'s balance.")

@bot.command(name="addshards")
@is_bot_owner()
async def owner_add_shards(ctx, amount: int, target: discord.User = None):
    member = target or ctx.author
    await ensure_user_doc(member.id)
    await users_col.update_one({"user_id": member.id}, {"$inc": {"shards": amount}})
    await ctx.send(f"✅ Added **{amount:,} Shards** to {member.mention}'s balance.")

@bot.command(name="addredeems", aliases=["addredeem"])
@is_bot_owner()
async def owner_add_redeems(ctx, amount: int, target: discord.User = None):
    member = target or ctx.author
    await ensure_user_doc(member.id)
    await users_col.update_one({"user_id": member.id}, {"$inc": {"redeems": amount}})
    await ctx.send(f"✅ Added **{amount:,} Redeem(s)** to {member.mention}'s balance.")

@bot.command(name="givemon")
@is_bot_owner()
async def owner_give_pokemon(ctx, pokemon_name: str, target: discord.User = None, shiny: str = None):
    member = target or ctx.author
    entry = POKEDEX_BY_NAME.get(pokemon_name.strip().lower())
    if not entry:
        await ctx.send(f"❌ Pokémon `{pokemon_name}` not found in Pokédex.")
        return

    await ensure_user_doc(member.id)
    force_shiny = bool(shiny and shiny.lower() in ("shiny", "true", "yes"))
    mon_data = generate_pokemon_data(entry, force_shiny=force_shiny)
    emoji_str = await ensure_pokemon_emoji(entry)

    await users_col.update_one({"user_id": member.id}, {"$push": {"pokemon": mon_data}})
    gmax_tag = f" {GMAX_EMOJI}" if mon_data.get("gmax") else ""
    star = f" {SHINY_EMOJI}" if mon_data.get("shiny") else ""
    gender_tag = f" {get_gender_emoji(mon_data)}"
    await ctx.send(
        f"✅ Granted {emoji_str} **{mon_data['name']}**{gmax_tag}{star}{gender_tag} "
        f"(Lvl. {mon_data['level']} • {mon_data['iv_percent']:.2f}% IV) to {member.mention}!"
    )

@bot.command(name="forcespawn", aliases=["fs"])
@is_bot_owner()
async def force_spawn(ctx, *, mon_name: str = None):
    forced = POKEDEX_BY_NAME.get(mon_name.strip().lower()) if mon_name else None
    await trigger_spawn(ctx.channel, forced_mon=forced, force_gmax_mode=(force_shiny_mode == "gmax_shiny"))

@bot.command(name="forceshine", aliases=["fshine"])
@is_bot_owner()
async def force_shine(ctx, mode: str = None):
    global force_shiny_mode
    if mode and mode.strip().lower() == "gmax":
        force_shiny_mode = None if force_shiny_mode == "gmax_shiny" else "gmax_shiny"
        if force_shiny_mode == "gmax_shiny":
            await ctx.send(f"✨ {GMAX_EMOJI} Force Shine **GMAX** is now **ENABLED** — next Gmax spawn & catch will be Gmax + Shiny!")
        else:
            await ctx.send("✨ Force Shine **GMAX** is now **DISABLED**.")
        return

    if mode and mode.strip().lower() in ("off", "clear", "reset"):
        force_shiny_mode = None
        await ctx.send("✨ Force Shine is now **DISABLED**.")
        return

    force_shiny_mode = None if force_shiny_mode == "shiny" else "shiny"
    if force_shiny_mode == "shiny":
        await ctx.send("✨ Force Shine is now **ENABLED** — next caught Pokémon will be shiny.")
    else:
        await ctx.send("✨ Force Shine is now **DISABLED**.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, (commands.NotOwner, commands.CheckFailure)):
        await ctx.send("❌ Only the bot owner can use this command.")
    elif isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
        await ctx.send(f"❌ Invalid usage: `{error}`")
    else:
        raise error

if __name__ == "__main__":
    bot.run(TOKEN)
