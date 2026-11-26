import os
import io
import json
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

GMAX_EMOJI = "<:Gmax:1504098787658961028>"
SHINY_EMOJI = "✨"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=("p!", "P!"), owner_id=OWNER_ID, intents=intents)

mongo = AsyncIOMotorClient(MONGO_URI)
db = mongo["poketwo_mini"]
users_col = db["users"]
config_col = db["bot_config"]

POKEDEX_FILE = "pokedex.json"
POKEDEX: list[dict] = []          # [{"dex_id": 25, "name": "Pikachu", "slug": "pikachu", "rarity": 40, "gmax": False}, ...]
POKEDEX_BY_NAME: dict[str, dict] = {}
EMOJI_CACHE: dict[str, str] = {}   # {"pikachu": "<:pikachu:123456789>"}

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

force_shiny_next = False

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
    global POKEDEX, POKEDEX_BY_NAME
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
    for p in POKEDEX:
        POKEDEX_BY_NAME[p["name"].lower()] = p
        if p.get("gmax"):
            base_title = p["name"].replace("Gigantamax ", "", 1).strip().lower()
            POKEDEX_BY_NAME.setdefault(f"gmax {base_title}", p)
    print(f"✅ Loaded {len(POKEDEX)} Pokémon entries into Pokédex.")

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

# ==========================================
# 🎨 SPAWN IMAGE GENERATOR (Background + Art)
# ==========================================
def get_sprite_url(dex_id: int, shiny: bool = False) -> str:
    if shiny:
        return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/shiny/{dex_id}.png"
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{dex_id}.png"

def _generate_fallback_background(width=800, height=500) -> Image.Image:
    bg = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(bg)
    for y in range(int(height * 0.65)):
        r = int(110 + (y / (height * 0.65)) * 60)
        g = int(195 + (y / (height * 0.65)) * 40)
        b = 245
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
    for y in range(int(height * 0.65), height):
        progress = (y - height * 0.65) / (height * 0.35)
        r = int(76 - progress * 25)
        g = int(175 - progress * 45)
        b = int(80 - progress * 25)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
    return bg

async def create_spawn_banner(dex_id: int, is_gmax: bool = False) -> discord.File:
    bg_folder = "backgrounds"
    if os.path.isdir(bg_folder):
        bg_files = [f for f in os.listdir(bg_folder) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    else:
        bg_files = []

    if bg_files:
        bg = Image.open(os.path.join(bg_folder, random.choice(bg_files))).convert("RGBA").resize((800, 500))
    else:
        bg = _generate_fallback_background(800, 500)

    art_url = get_sprite_url(dex_id, shiny=False)
    async with aiohttp.ClientSession() as session:
        async with session.get(art_url) as resp:
            art_bytes = await resp.read()

    size = (340, 340) if is_gmax else (290, 290)
    sprite = Image.open(io.BytesIO(art_bytes)).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    paste_x = (bg.width - sprite.width) // 2
    paste_y = (bg.height - sprite.height) // 2 + (10 if is_gmax else 25)
    bg.alpha_composite(sprite, (paste_x, paste_y))

    buf = io.BytesIO()
    bg.convert("RGB").save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return discord.File(fp=buf, filename="spawn.jpg")

def generate_pokemon_data(mon_entry: dict, force_shiny: bool = False) -> dict:
    ivs = [random.randint(0, 31) for _ in range(6)]
    iv_percent = round((sum(ivs) / 186) * 100, 2)
    is_shiny = True if force_shiny else (random.randint(1, 4096) == 1)
    return {
        "dex_id": mon_entry["dex_id"],
        "name": mon_entry["name"],
        "slug": mon_entry["slug"],
        "gmax": bool(mon_entry.get("gmax", False)),
        "level": random.randint(1, 40),
        "ivs": ivs,
        "iv_percent": iv_percent,
        "shiny": is_shiny,
    }

# ==========================================
# ⚡ SPAWN & INCENSE ENGINE
# ==========================================
channel_state: dict[int, dict] = {}
active_incense: set[int] = set()
SPAWN_THRESHOLD = 15

async def trigger_spawn(channel: discord.TextChannel, forced_mon: dict = None):
    if forced_mon:
        chosen = forced_mon
    else:
        weights = [p["rarity"] for p in POKEDEX]
        chosen = random.choices(POKEDEX, weights=weights, k=1)[0]

    channel_state[channel.id] = {"count": 0, "spawn": chosen}

    is_gmax = bool(chosen.get("gmax", False))
    banner_file = await create_spawn_banner(chosen["dex_id"], is_gmax=is_gmax)
    title_prefix = f"{GMAX_EMOJI} " if is_gmax else ""
    embed = discord.Embed(
        title=f"{title_prefix}A wild pokémon has appeared!",
        description="Guess the pokémon and type `p!c <pokémon>` to catch it!",
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
            await trigger_spawn(message.channel)

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
    global force_shiny_next

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

    should_shine = force_shiny_next
    if should_shine:
        force_shiny_next = False

    caught_mon = generate_pokemon_data(active_spawn, force_shiny=should_shine)
    emoji_str = await ensure_pokemon_emoji(active_spawn)

    # Update hunt chain: increment on target catch, preserve on other non-shiny catches, reset on shiny
    hunt_target = user.get("hunt_target")
    hunt_chain = user.get("hunt_chain", 0)
    chain_msg = ""

    if caught_mon["shiny"]:
        if hunt_target and hunt_chain > 0:
            chain_msg = f"Shiny streak reset. ({hunt_chain})"
        hunt_chain = 0
    elif hunt_target:
        base_caught = active_spawn["name"].replace("Gigantamax ", "", 1).strip().lower()
        if hunt_target.lower() in (active_spawn["name"].lower(), base_caught):
            hunt_chain += 1
            chain_msg = f"🔗 **Hunt Chain:** **{hunt_chain}** ({hunt_target})"
        else:
            chain_msg = f"🔗 **Hunt Chain:** **{hunt_chain}** ({hunt_target})"

    new_catches = user.get("catches", 0) + 1
    coins_earned = random.randint(25, 60)
    shards_earned = 0
    bonus_text = ""

    if new_catches % 100 == 0:
        coins_earned += 2500
        shards_earned += 10
        bonus_text = "🎊 **100th Catch Milestone!** +2,500 Pokécoins & +10 Shards!"
    elif new_catches % 10 == 0:
        coins_earned += 350
        shards_earned += 1
        bonus_text = f"🏅 **{new_catches}th Catch Milestone!** +350 Pokécoins & +1 Shard!"

    await users_col.update_one(
        {"user_id": ctx.author.id},
        {
            "$push": {"pokemon": caught_mon},
            "$inc": {"coins": coins_earned, "shards": shards_earned, "catches": 1},
            "$set": {"hunt_chain": hunt_chain},
        },
    )

    is_gmax = bool(caught_mon.get("gmax"))
    gmax_tag = f" {GMAX_EMOJI}" if is_gmax else ""
    shiny_tag = f" {SHINY_EMOJI}" if caught_mon["shiny"] else ""

    catch_line = (
        f"🎉 Congratulations {ctx.author.mention}! You caught a Level {caught_mon['level']} "
        f"{emoji_str} **{caught_mon['name']}**{gmax_tag}{shiny_tag} ({caught_mon['iv_percent']}% IV) "
        f"and received **{coins_earned} Pokécoins**!"
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

@bot.command(name="p", aliases=["pokemon"])
async def list_pokemon(ctx, page: int = 1):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user or not user.get("pokemon"):
        await ctx.send("❌ You have no pokémon yet! Use `p!start`.")
        return

    mons = user["pokemon"]
    per_page = 15
    total_pages = max(1, (len(mons) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    slice_mons = mons[start : start + per_page]

    lines = []
    for idx, m in enumerate(slice_mons, start=start + 1):
        emoji = EMOJI_CACHE.get(m["slug"].replace("-gmax", ""), "🔹")
        gmax = f" {GMAX_EMOJI}" if m.get("gmax") else ""
        star = f" {SHINY_EMOJI}" if m.get("shiny") else ""
        sel = " **(Selected)**" if idx == user.get("selected", 1) else ""
        lines.append(f"`{idx}` | {emoji} **{m['name']}**{gmax}{star} • Lvl. {m['level']} • {m['iv_percent']}%{sel}")

    embed = discord.Embed(
        title=f"{ctx.author.display_name}'s Pokémon (Page {page}/{total_pages})",
        description="\n".join(lines),
        color=discord.Color.blue(),
    )
    embed.set_footer(text=f"Total: {len(mons)} | Use p!s <number> or p!i <number>")
    await ctx.send(embed=embed)

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

@bot.command(name="i", aliases=["info"])
async def pokemon_info(ctx, number: int = None):
    user = await users_col.find_one({"user_id": ctx.author.id})
    if not user or not user.get("pokemon"):
        await ctx.send("❌ You have no pokémon.")
        return

    idx = number or user.get("selected", 1)
    if idx < 1 or idx > len(user["pokemon"]):
        await ctx.send("❌ Invalid pokémon number.")
        return

    m = user["pokemon"][idx - 1]
    hp, atk, dfn, spa, spd, spe = m["ivs"]
    gmax = f" {GMAX_EMOJI}" if m.get("gmax") else ""
    star = f" {SHINY_EMOJI}" if m.get("shiny") else ""

    embed = discord.Embed(
        title=f"Level {m['level']} {m['name']}{gmax}{star} (#{idx})",
        description=(
            f"**IVs ({m['iv_percent']}%)**\n"
            f"• **HP:** {hp}/31\n"
            f"• **Attack:** {atk}/31\n"
            f"• **Defense:** {dfn}/31\n"
            f"• **Sp. Atk:** {spa}/31\n"
            f"• **Sp. Def:** {spd}/31\n"
            f"• **Speed:** {spe}/31"
        ),
        color=discord.Color.gold() if m.get("shiny") else discord.Color.green(),
    )
    embed.set_thumbnail(url=get_sprite_url(m["dex_id"], shiny=m.get("shiny", False)))
    await ctx.send(embed=embed)

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
# 💰 POKÉCOINS, SHARDS, DAILY, SHOP & REDEEMS
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
        await users_col.update_one(
            {"user_id": ctx.author.id},
            {"$inc": {"coins": -(250 * gained)}, "$set": {"pokemon": mons}},
        )
        await ctx.send(f"🍬 Fed **{gained} Rare Candy(s)**! **{mons[sel_idx]['name']}** grew to **Level {new_lvl}**!")

    elif item == "incense":
        if shards < 50:
            await ctx.send("❌ You need **50 Shards** to activate Incense.")
            return
        if ctx.channel.id in active_incense:
            await ctx.send("❌ An incense is already running in this channel!")
            return

        await users_col.update_one({"user_id": ctx.author.id}, {"$inc": {"shards": -50}})
        active_incense.add(ctx.channel.id)
        await ctx.send("🕯️ **Incense Activated!** 15 Pokémon will spawn here over the next few minutes!")

        async def run_incense_loop():
            try:
                for _ in range(15):
                    await trigger_spawn(ctx.channel)
                    await asyncio.sleep(15)
                await ctx.channel.send("🕯️ The incense has ended.")
            finally:
                active_incense.discard(ctx.channel.id)

        asyncio.create_task(run_incense_loop())
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
    await ctx.send(
        f"✅ Granted {emoji_str} **{mon_data['name']}**{gmax_tag}{star} "
        f"(Lvl. {mon_data['level']} • {mon_data['iv_percent']}% IV) to {member.mention}!"
    )

@bot.command(name="forcespawn", aliases=["fs"])
@is_bot_owner()
async def force_spawn(ctx, *, mon_name: str = None):
    forced = POKEDEX_BY_NAME.get(mon_name.strip().lower()) if mon_name else None
    await trigger_spawn(ctx.channel, forced_mon=forced)

@bot.command(name="forceshine", aliases=["fshine"])
@is_bot_owner()
async def force_shine(ctx):
    global force_shiny_next
    force_shiny_next = not force_shiny_next
    state_label = "ENABLED ✨ (next caught Pokémon will be shiny)" if force_shiny_next else "DISABLED"
    await ctx.send(f"✨ Force Shine is now **{state_label}**.")

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
