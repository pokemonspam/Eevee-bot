import os
import re
import io
import aiohttp
import asyncio
import imagehash
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from aiohttp import web
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient


import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient

async def clean_database():
    mongo_client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = mongo_client["pokemon_bot"]
    phash_col = db["phash_database"]

    # Delete corrupted records
    res1 = await phash_col.delete_one({"pokemon": {"$regex": "^sobble$", "$options": "i"}})
    res2 = await phash_col.delete_one({"pokemon": {"$regex": "^pikipek$", "$options": "i"}})
    print(f"🗑️ Cleaned database - Sobble removed: {res1.deleted_count}, Pikipek removed: {res2.deleted_count}")

asyncio.run(clean_database())



# Import dataset helpers and registries from dataset.py
from dataset import (
    parse_pokemon_list,
    format_pokemon_name,
    get_evolution_family,
    get_pokemon_variants,
    get_base_pokemon,
    validate_species,
    POKEMON_FORMS,
    REGIONAL_FORMS
)


# Setup Bot Client
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix= ("E!","e!") , intents=intents)

# Setup MongoDB
mongo_url = os.getenv("MONGO_URI")
mongo_client = AsyncIOMotorClient(mongo_url)
db = mongo_client["pokemon_bot"]
bot.db = db

# Memory cache for active channel spawns to map to naming bot outputs
bot.recent_spawns = {}

# -------------------------------------------------------------
# DUMMY PORT SERVER FOR RENDER FREE WEB SERVICE
# -------------------------------------------------------------
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))  # Render automatically sets PORT
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"✅ Dummy web server listening on port {port}")


@bot.event
async def setup_hook():
    await bot.load_extension("starboard")
    print("✅ Loaded starboard extension successfully!")
    
    # Launch the dummy HTTP server so Render detects an open port
    asyncio.create_task(start_dummy_server())

reserves_col = db["reserves"]
collections_col = db["collections"]
shiny_col = db["shiny_hunts"]
roles_col = db["staff_roles"]
settings_col = db["guild_settings"]
phash_col = db["phash_database"]


# Helper: Check Reserve Staff Permissions
async def is_staff(ctx):
    if ctx.author.guild_permissions.administrator:
        return True
    doc = await roles_col.find_one({"guild_id": ctx.guild.id})
    if doc and "roles" in doc:
        user_role_ids = [role.id for role in ctx.author.roles]
        if any(rid in doc["roles"] for rid in user_role_ids):
            return True
    return False


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game(name="E!sh | E!cl | E!r | E!learn"))


# ==========================================
# 🎨 FEATURE EXTRACTOR & AUGMENTATION
# ==========================================
def process_image_canvas(img: Image.Image) -> Image.Image:
    """Converts transparent WEBP/PNG images to RGB by placing them on a clean white background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        converted = img.convert("RGBA")
        canvas = Image.new("RGBA", converted.size, (255, 255, 255, 255))
        canvas.alpha_composite(converted)
        return canvas.convert("RGB")
    return img.convert("RGB")

def extract_visual_features(img: Image.Image):
    img_resized = img.resize((32, 32)).convert("RGB")
    arr = np.array(img_resized)
    
    h, w, _ = arr.shape
    gh, gw = h // 4, w // 4
    features = []
    
    for r in range(4):
        for c in range(4):
            patch = arr[r*gh:(r+1)*gh, c*gw:(c+1)*gw]
            mean_color = patch.mean(axis=(0, 1))
            
            # Center-weighting: multiply middle 2x2 grid cells (where sprite sits)
            if r in [1, 2] and c in [1, 2]:
                mean_color *= 2.0
                
            features.extend(mean_color)
            
    features = np.array(features, dtype=float)
    norm = np.linalg.norm(features)
    if norm > 0:
        features /= norm
    return features.tolist()

def calculate_color_similarity(vec1, vec2):
    v1, v2 = np.array(vec1), np.array(vec2)
    dot_product = np.dot(v1, v2)
    norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)
    if norm_product == 0:
        return 0.0
    return float(dot_product / norm_product)

def generate_exhaustive_variants(img: Image.Image):
    """Generates a streamlined matrix of variations to stay well under 512MB RAM."""
    variants = []
    base = process_image_canvas(img)
    w, h = base.size

    # Reduced bounds to prevent OOM
    orientations = [base, base.transpose(Image.FLIP_LEFT_RIGHT)]
    scales = [0.90, 1.0, 1.10]
    rotations = [-6, 0, 6]
    brightness_levels = [0.85, 1.0, 1.15]
    contrast_levels = [1.0, 1.25]

    for b in orientations:
        for scale in scales:
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            resized = b.resize((nw, nh), resample=Image.BICUBIC)
            canvas = Image.new("RGB", (w, h), (0, 0, 0))
            if scale < 1.0:
                canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2))
            else:
                crop_x, crop_y = (nw - w) // 2, (nh - h) // 2
                canvas = resized.crop((crop_x, crop_y, crop_x + w, crop_y + h))
            
            for angle in rotations:
                rotated = canvas if angle == 0 else canvas.rotate(angle, resample=Image.BICUBIC, expand=False)
                for b_val in brightness_levels:
                    brightened = rotated if b_val == 1.0 else ImageEnhance.Brightness(rotated).enhance(b_val)
                    for c_val in contrast_levels:
                        final_img = brightened if c_val == 1.0 else ImageEnhance.Contrast(brightened).enhance(c_val)
                        variants.append(final_img)

    return variants


def extract_all_exhaustive_variant_data(img: Image.Image):
    all_variants = generate_exhaustive_variants(img)
    phashes, dhashes, visual_features = [], [], []

    for var_img in all_variants:
        phashes.append(str(imagehash.phash(var_img)))
        dhashes.append(str(imagehash.dhash(var_img)))
        visual_features.append(extract_visual_features(var_img))

    return list(dict.fromkeys(phashes)), list(dict.fromkeys(dhashes)), visual_features


# ==========================================
# 🧠 HUGGING FACE VISION API HELPER (FALLBACK)
# ==========================================
HF_API_URL = "https://api-inference.huggingface.co/models/merve/pokemon-classifier"

async def identify_pokemon_via_hf(image_bytes: bytes) -> str:
    token = os.getenv("HF_TOKEN")
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token.strip()}"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(HF_API_URL, headers=headers, data=image_bytes, timeout=10) as response:
                if response.status == 200:
                    result = await response.json()
                    if isinstance(result, list) and len(result) > 0:
                        top_pred = result[0]
                        confidence = top_pred.get("score", 0.0)
                        if confidence >= 0.30:
                            raw_name = top_pred.get("label", "").lower()
                            if validate_species(raw_name):
                                return raw_name
        except Exception:
            pass

    return None


# ==========================================
# ⚡ HIGH-PRECISION DUAL-ENGINE MATCHING
# ==========================================
async def identify_pokemon_dual_engine(image_bytes: bytes):
    try:
        raw_img = Image.open(io.BytesIO(image_bytes))
        if hasattr(raw_img, "seek"):
            raw_img.seek(0)
            
        spawn_img = process_image_canvas(raw_img)
        flipped_spawn_img = spawn_img.transpose(Image.FLIP_LEFT_RIGHT)
        
        spawn_p_orig = imagehash.phash(spawn_img)
        spawn_p_flip = imagehash.phash(flipped_spawn_img)
        spawn_d_orig = imagehash.dhash(spawn_img)
        spawn_d_flip = imagehash.dhash(flipped_spawn_img)
        
        spawn_features_orig = extract_visual_features(spawn_img)
        spawn_features_flip = extract_visual_features(flipped_spawn_img)

        cursor = phash_col.find({})
        best_doc = None
        highest_score = -1.0

        async for doc in cursor:
            db_phashes = doc.get("phashes", [])
            if not db_phashes and doc.get("phash"):
                db_phashes = [doc.get("phash")]

            max_p_score = 0.0
            for p_str in db_phashes:
                if p_str:
                    db_p = imagehash.hex_to_hash(p_str)
                    s_orig = max(0.0, 1.0 - ((spawn_p_orig - db_p) / 22.0))
                    s_flip = max(0.0, 1.0 - ((spawn_p_flip - db_p) / 22.0))
                    best_sp = max(s_orig, s_flip)
                    if best_sp > max_p_score:
                        max_p_score = best_sp

            db_dhashes = doc.get("dhashes", db_phashes)
            max_d_score = 0.0
            for d_str in db_dhashes:
                if d_str:
                    db_d = imagehash.hex_to_hash(d_str)
                    d_orig_score = max(0.0, 1.0 - ((spawn_d_orig - db_d) / 22.0))
                    d_flip_score = max(0.0, 1.0 - ((spawn_d_flip - db_d) / 22.0))
                    best_sd = max(d_orig_score, d_flip_score)
                    if best_sd > max_d_score:
                        max_d_score = best_sd

            db_vf_list = doc.get("visual_features_list", [])
            if not db_vf_list and doc.get("visual_features"):
                db_vf_list = [doc.get("visual_features")]

            max_color_score = 0.0
            for vf in db_vf_list:
                if vf:
                    c_orig = calculate_color_similarity(spawn_features_orig, vf)
                    c_flip = calculate_color_similarity(spawn_features_flip, vf)
                    best_c = max(c_orig, c_flip)
                    if best_c > max_color_score:
                        max_color_score = best_c

            total_score = (max_p_score * 0.50) + (max_d_score * 0.35) + (max_color_score * 0.15)

            if total_score > highest_score:
                highest_score = total_score
                best_doc = doc

        if best_doc:
            accuracy_pct = int(min(1.0, max(0.0, highest_score)) * 100)
            return best_doc, accuracy_pct

    except Exception as e:
        print(f"Dual-engine identification error: {e}")

    return None, 0


# ==========================================
# 🧠 SAFE AUTO-LEARNING ENGINE (STRICT 120 VARIANTS CAP)
# ==========================================
async def append_pokemon_spawn_data(formatted_name: str, spawn_img: Image.Image):
    with io.BytesIO() as buf:
        spawn_img.save(buf, format="PNG")
        raw_bytes = buf.getvalue()
    
    matched_doc, current_accuracy = await identify_pokemon_dual_engine(raw_bytes)

    if matched_doc and matched_doc.get("pokemon", "").lower() == formatted_name.lower() and current_accuracy >= 95:
        print(f"🎯 '{formatted_name}' has reached {current_accuracy}% accuracy (>=95%). Mastered!")
        return False, current_accuracy

    print(f"🔄 Accuracy for '{formatted_name}' is {current_accuracy}% (<95%). Generating variant matrix...")

    new_p, new_d, new_vfs = extract_all_exhaustive_variant_data(spawn_img)

    existing_doc = await phash_col.find_one({"pokemon": {"$regex": f"^{re.escape(formatted_name)}$", "$options": "i"}})

    if existing_doc:
        old_p = existing_doc.get("phashes", [existing_doc.get("phash")] if "phash" in existing_doc else [])
        old_d = existing_doc.get("dhashes", [existing_doc.get("dhash")] if "dhash" in existing_doc else [])
        old_vfs = existing_doc.get("visual_features_list", [existing_doc.get("visual_features")] if "visual_features" in existing_doc else [])

        # HARD CAP: Limit variants to 120 so records never bloat or hijack other matches
        MAX_VARIANTS = 120
        combined_p = list(dict.fromkeys(old_p + new_p))[:MAX_VARIANTS]
        combined_d = list(dict.fromkeys(old_d + new_d))[:MAX_VARIANTS]
        combined_vfs = (old_vfs + new_vfs)[:MAX_VARIANTS]

        await phash_col.update_one(
            {"_id": existing_doc["_id"]},
            {
                "$set": {
                    "pokemon": formatted_name,
                    "phash": combined_p[0],
                    "phashes": combined_p,
                    "dhash": combined_d[0],
                    "dhashes": combined_d,
                    "visual_features": combined_vfs[0],
                    "visual_features_list": combined_vfs
                }
            }
        )
    else:
        await phash_col.insert_one({
            "pokemon": formatted_name,
            "shortest_name": formatted_name.lower(),
            "phash": new_p[0],
            "phashes": new_p,
            "dhash": new_d[0],
            "dhashes": new_d,
            "visual_features": new_vfs[0],
            "visual_features_list": new_vfs
        })

    _, new_accuracy = await identify_pokemon_dual_engine(raw_bytes)
    print(f"🧠 AUTO-LEARN SUCCESS: Clean variants added for '{formatted_name}'. Accuracy: {new_accuracy}%")
    return True, new_accuracy


# ==========================================
# 📚 EXHAUSTIVE DUAL-ENGINE EMBED LEARNER (E!learn)
# ==========================================
@bot.command(name="learn")
async def learn_embed(ctx):
    if not ctx.message.reference:
        await ctx.send(embed=discord.Embed(description="❌ Please reply to a Pokémon info embed.", color=discord.Color.red()))
        return

    try:
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except Exception:
        await ctx.send(embed=discord.Embed(description="❌ Could not fetch the replied message.", color=discord.Color.red()))
        return

    if not replied_msg.embeds:
        await ctx.send(embed=discord.Embed(description="❌ The replied message does not contain an embed.", color=discord.Color.red()))
        return

    embed = replied_msg.embeds[0]
    embed_text = embed.description or ""
    for field in embed.fields:
        embed_text += f"\n{field.name}\n{field.value}"

    pokemon_name = None
    alt_names = []
    types_list = []
    type_emojis = []

    lines = embed_text.split("\n")
    current_section = None

    for line in lines:
        line_stripped = line.strip()
        if "Types" in line_stripped:
            current_section = "types"
            continue
        elif "Names" in line_stripped:
            current_section = "names"
            continue
        elif "Appearance" in line_stripped or "Region" in line_stripped or "Base Stats" in line_stripped:
            current_section = None
            continue

        if current_section == "types":
            if line_stripped:
                types_list.append(line_stripped)
                found_emojis = re.findall(r"<a?:[a-zA-Z0-9\_]+:\d+>|[\U0001f300-\U0001f64f]|[\U0001f680-\U0001f6ff]|[\u2600-\u27bf]", line_stripped)
                type_emojis.extend(found_emojis)
        elif current_section == "names":
            if any(flag in line_stripped for flag in ["🇯🇵", "🇬🇧", "🇩🇪", "🇫🇷", "🇪🇸"]):
                parts = line_stripped.split()
                if len(parts) >= 2:
                    alt_name = " ".join(parts[1:])
                    if re.match(r"^[A-Za-z\s\.\'\-]+$", alt_name):
                        alt_names.append(alt_name)
                    if "🇬🇧" in line_stripped and re.match(r"^[A-Za-z\s\.\'\-]+$", alt_name):
                        pokemon_name = alt_name

    full_embed_header = (embed.title or "") + " " + (embed.description or "")
    for region in ["Hisuian", "Galarian", "Alolan", "Paldean"]:
        if region.lower() in full_embed_header.lower() and pokemon_name and not pokemon_name.lower().startswith(region.lower()):
            pokemon_name = f"{region} {pokemon_name}"

    if not pokemon_name and alt_names:
        pokemon_name = alt_names[0]

    if not embed.image or not embed.image.url:
        await ctx.send(embed=discord.Embed(description="❌ No sprite image found in the embed.", color=discord.Color.red()))
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(embed.image.url) as resp:
                if resp.status == 200:
                    image_bytes = await resp.read()
                    raw_img = Image.open(io.BytesIO(image_bytes))
                    if hasattr(raw_img, "seek"):
                        raw_img.seek(0)
                    img = process_image_canvas(raw_img)
                else:
                    await ctx.send(embed=discord.Embed(description="❌ Failed to download sprite image.", color=discord.Color.red()))
                    return
    except Exception as e:
        await ctx.send(embed=discord.Embed(description=f"❌ Error processing image: {e}", color=discord.Color.red()))
        return

    if not pokemon_name:
        await ctx.send(embed=discord.Embed(description="❌ Could not parse Pokémon details from this embed layout.", color=discord.Color.red()))
        return

    formatted_name = format_pokemon_name(pokemon_name.lower())
    all_valid_names = [formatted_name] + alt_names
    shortest_copy_name = min(all_valid_names, key=len).lower()

    new_p, new_d, new_vfs = extract_all_exhaustive_variant_data(img)

    existing_doc = await phash_col.find_one({"pokemon": {"$regex": f"^{re.escape(formatted_name)}$", "$options": "i"}})

    if existing_doc:
        old_p = existing_doc.get("phashes", [existing_doc.get("phash")] if "phash" in existing_doc else [])
        old_d = existing_doc.get("dhashes", [existing_doc.get("dhash")] if "dhash" in existing_doc else [])
        old_vfs = existing_doc.get("visual_features_list", [existing_doc.get("visual_features")] if "visual_features" in existing_doc else [])

        MAX_VARIANTS = 120
        combined_p = list(dict.fromkeys(old_p + new_p))[:MAX_VARIANTS]
        combined_d = list(dict.fromkeys(old_d + new_d))[:MAX_VARIANTS]
        combined_vfs = (old_vfs + new_vfs)[:MAX_VARIANTS]

        await phash_col.update_one(
            {"_id": existing_doc["_id"]},
            {
                "$set": {
                    "pokemon": formatted_name,
                    "alt_names": list(dict.fromkeys(existing_doc.get("alt_names", []) + alt_names)),
                    "types": list(dict.fromkeys(existing_doc.get("types", []) + types_list)),
                    "type_emojis": list(dict.fromkeys(existing_doc.get("type_emojis", []) + type_emojis)),
                    "shortest_name": shortest_copy_name,
                    "phash": combined_p[0],
                    "phashes": combined_p,
                    "dhash": combined_d[0],
                    "dhashes": combined_d,
                    "visual_features": combined_vfs[0],
                    "visual_features_list": combined_vfs
                }
            }
        )
        total_variants = len(combined_p)
        action_msg = "Preserved historical data & merged variants"
    else:
        await phash_col.insert_one({
            "pokemon": formatted_name,
            "alt_names": alt_names,
            "types": types_list,
            "type_emojis": list(dict.fromkeys(type_emojis)),
            "shortest_name": shortest_copy_name,
            "phash": new_p[0],
            "phashes": new_p,
            "dhash": new_d[0],
            "dhashes": new_d,
            "visual_features": new_vfs[0],
            "visual_features_list": new_vfs
        })
        total_variants = len(new_p)
        action_msg = "Created new unique record"

    _, verified_score = await identify_pokemon_dual_engine(image_bytes)

    await ctx.send(embed=discord.Embed(
        title="🧠 High-Precision Learning Complete!",
        description=(
            f"**Pokémon:** {formatted_name}\n"
            f"**Shortest Copy Name:** `{shortest_copy_name}`\n"
            f"**Status:** {action_msg} ✅\n"
            f"**Total Stored Signatures:** `{total_variants}` variants\n"
            f"**Verified Target Accuracy:** `{verified_score}%`"
        ),
        color=discord.Color.green()
    ))


# ==========================================
# ⚡ SPAWN LISTENER & AUTO-LEARNER (WITH STRICT 60% CONFIDENCE GUARD)
# ==========================================
@bot.event
async def on_message(message: discord.Message):
    try:
        if message.author.id == bot.user.id:
            return

        # -------------------------------------------------------------
        # 1. POKÉTWO MESSAGE HANDLER (ID: 716390085896962058)
        # -------------------------------------------------------------
        if message.guild and message.author.id == 716390085896962058:
            
            if message.content and "congratulations" in message.content.lower() and "you caught a" in message.content.lower():
                if message.channel.id in bot.recent_spawns:
                    spawn_data = bot.recent_spawns[message.channel.id]
                    match = re.search(r"you caught a level \d+ (.+?)(?:\s*[♂♀]|\s*\()", message.content, re.IGNORECASE)
                    if match:
                        pokemon_name = match.group(1).strip().title()
                        if pokemon_name and len(pokemon_name) <= 25 and validate_species(pokemon_name):
                            formatted_catch_name = format_pokemon_name(pokemon_name)
                            spawn_img = spawn_data.get("image_obj")
                            if spawn_img:
                                await append_pokemon_spawn_data(formatted_catch_name, spawn_img)
                            del bot.recent_spawns[message.channel.id]
                return

            if message.embeds:
                embed = message.embeds[0]
                if embed.title and "has appeared" in embed.title.lower():
                    matched_doc = None
                    spawned_pokemon = None
                    shortest_name = None
                    type_emojis = []
                    accuracy_score = 0

                    if embed.image and embed.image.url:
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(embed.image.url) as resp:
                                    if resp.status == 200:
                                        image_bytes = await resp.read()
                                        raw_spawn = Image.open(io.BytesIO(image_bytes))
                                        if hasattr(raw_spawn, "seek"):
                                            raw_spawn.seek(0)
                                        spawn_img = process_image_canvas(raw_spawn)
                                        
                                        bot.recent_spawns[message.channel.id] = {
                                            "image_obj": spawn_img
                                        }

                                        # CASCADE STEP 1: Strict Local Match (Requires 95%+ Confidence)
                                        matched_doc, accuracy_score = await identify_pokemon_dual_engine(image_bytes)
                                        if matched_doc and accuracy_score >= 95:
                                            spawned_pokemon = matched_doc.get("pokemon")
                                            shortest_name = matched_doc.get("shortest_name", spawned_pokemon.lower() if spawned_pokemon else "")
                                            type_emojis = matched_doc.get("type_emojis", [])

                                        # CASCADE STEP 2: Hugging Face Fallback
                                        if not spawned_pokemon:
                                            hf_result = await identify_pokemon_via_hf(image_bytes)
                                            if hf_result:
                                                spawned_pokemon = hf_result
                                                shortest_name = hf_result.lower()
                                                accuracy_score = 65

                                        # CASCADE STEP 3: Local match ONLY if confidence is solid (>= 60%)
                                        if not spawned_pokemon and matched_doc and accuracy_score >= 60:
                                            spawned_pokemon = matched_doc.get("pokemon")
                                            shortest_name = matched_doc.get("shortest_name", spawned_pokemon.lower() if spawned_pokemon else "")
                                            type_emojis = matched_doc.get("type_emojis", [])

                        except Exception as hash_err:
                            print(f"Vision processing error: {hash_err}")

                    if spawned_pokemon:
                        guild_id = message.guild.id
                        target_clean = spawned_pokemon.lower()
                        formatted_target = format_pokemon_name(target_clean)
                        if not shortest_name:
                            shortest_name = formatted_target.lower()

                        sh_pings = []
                        col_pings = []
                        res_pings = []

                        sh_cursor = shiny_col.find({"target": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                        sh_users = await sh_cursor.to_list(length=100)
                        for doc in sh_users:
                            member = message.guild.get_member(doc["user_id"])
                            if not member:
                                try:
                                    member = await message.guild.fetch_member(doc["user_id"])
                                except Exception:
                                    pass
                            if member:
                                sh_pings.append(member.mention)

                        col_cursor = collections_col.find({"pokemon": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                        col_users = await col_cursor.to_list(length=100)
                        for doc in col_users:
                            member = message.guild.get_member(doc["user_id"])
                            if not member:
                                try:
                                    member = await message.guild.fetch_member(doc["user_id"])
                                except Exception:
                                    pass
                            if member:
                                col_pings.append(member.mention)

                        res_cursor = reserves_col.find({"guild_id": guild_id, "pokemon": {"$regex": f"^{re.escape(formatted_target)}$", "$options": "i"}})
                        res_users = await res_cursor.to_list(length=100)
                        for doc in res_users:
                            member = message.guild.get_member(doc["user_id"])
                            if not member:
                                try:
                                    member = await message.guild.fetch_member(doc["user_id"])
                                except Exception:
                                    pass
                            if member:
                                res_pings.append(member.mention)

                        guild_setting = await settings_col.find_one({"guild_id": guild_id})
                        only_ping_mode = guild_setting.get("only_ping", True) if guild_setting else True

                        emojis_str = " ".join(type_emojis) if type_emojis else ""
                        header_line = f"**{formatted_target}** {emojis_str} : {accuracy_score}%".strip()

                        output_lines = [header_line]
                        if sh_pings:
                            output_lines.append(f"Shiny hunt pings: {', '.join(sh_pings)}")
                        if col_pings:
                            output_lines.append(f"Collection pings: {', '.join(col_pings)}")
                        if res_pings:
                            output_lines.append(f"Reserved pings: {', '.join(res_pings)}")

                        output_lines.append(f"**Click to Copy ->** `@Pokétwo#8236 c {shortest_name}`")

                        has_pings = bool(sh_pings or col_pings or res_pings)
                        if not only_ping_mode or has_pings:
                            await message.channel.send("\n".join(output_lines))

        # -------------------------------------------------------------
        # 2. SPY & LEARN LISTENER: Vegetaaaaa Bot (ID: 1307910235737948252)
        # -------------------------------------------------------------
        VEGETAAAAA_BOT_ID = 1307910235737948252

        if message.author.id == VEGETAAAAA_BOT_ID and message.channel.id in bot.recent_spawns:
            content = message.content.strip()
            match = re.match(r"^([A-Za-z0-9\-\.\'\s]+?)\s*(?:[\:\<]|[\u2600-\u27bf]|[\U0001f300-\U0001f64f]|[\U0001f680-\U0001f6ff])", content)
            if match:
                pokemon_name = match.group(1).strip().title()
            else:
                pokemon_name = content.split()[0].strip().title()

            if pokemon_name and len(pokemon_name) <= 25 and validate_species(pokemon_name):
                formatted_veg_name = format_pokemon_name(pokemon_name)
                spawn_data = bot.recent_spawns[message.channel.id]
                spawn_img = spawn_data.get("image_obj")
                if spawn_img:
                    await append_pokemon_spawn_data(formatted_veg_name, spawn_img)
                del bot.recent_spawns[message.channel.id]

    except Exception as e:
        print(f"Error in spawn/spy listener: {e}")

    await bot.process_commands(message)


# ==========================================
# 🧪 TEST SPAWN COMMAND (E!testspawn)
# ==========================================
@bot.command(name="testspawn")
async def test_spawn(ctx):
    if not ctx.message.reference:
        embed = discord.Embed(
            description="❌ Please reply to an existing Pokétwo spawn message to test it.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    try:
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except Exception:
        await ctx.send(embed=discord.Embed(description="❌ Could not fetch the replied message.", color=discord.Color.red()))
        return

    if not replied_msg.embeds:
        await ctx.send(embed=discord.Embed(description="❌ The replied message does not contain an embed.", color=discord.Color.red()))
        return

    embed = replied_msg.embeds[0]
    spawned_pokemon = None
    shortest_name = None
    type_emojis = []
    accuracy_score = 0

    if embed.image and embed.image.url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(embed.image.url) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
                        
                        matched_doc, accuracy_score = await identify_pokemon_dual_engine(image_bytes)
                        if matched_doc and accuracy_score >= 95:
                            spawned_pokemon = matched_doc.get("pokemon")
                            shortest_name = matched_doc.get("shortest_name", spawned_pokemon.lower() if spawned_pokemon else "")
                            type_emojis = matched_doc.get("type_emojis", [])

                        if not spawned_pokemon:
                            hf_result = await identify_pokemon_via_hf(image_bytes)
                            if hf_result:
                                spawned_pokemon = hf_result
                                shortest_name = hf_result.lower()
                                accuracy_score = 65

                        # REJECT low confidence guesses (<60%)
                        if not spawned_pokemon and matched_doc and accuracy_score >= 60:
                            spawned_pokemon = matched_doc.get("pokemon")
                            shortest_name = matched_doc.get("shortest_name", spawned_pokemon.lower() if spawned_pokemon else "")
                            type_emojis = matched_doc.get("type_emojis", [])

                        if spawned_pokemon and not shortest_name:
                            shortest_name = spawned_pokemon.lower()

        except Exception as e:
            print(f"Testspawn check error: {e}")

    if not spawned_pokemon:
        await ctx.send(embed=discord.Embed(
            description=f"❌ Could not identify Pokémon (Confidence below 60%). Use `E!learn` on an info embed!",
            color=discord.Color.red()
        ))
        return

    formatted_target = format_pokemon_name(spawned_pokemon.lower())
    emojis_str = " ".join(type_emojis) if type_emojis else ""
    await ctx.send(embed=discord.Embed(
        description=f"✅ **Successfully Identified!**\n**Pokémon:** {formatted_target} {emojis_str} : {accuracy_score}%\n**Copy Command:** `@Pokétwo#8236 c {shortest_name}`",
        color=discord.Color.green()
    ))


# ==========================================
# ⚙️ ONLYPING TOGGLE COMMAND (E!onlyping)
# ==========================================
@bot.group(name="onlyping", invoke_without_command=True)
async def onlyping_group(ctx):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can configure spawn alert settings.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    guild_setting = await settings_col.find_one({"guild_id": ctx.guild.id})
    current_status = guild_setting.get("only_ping", True) if guild_setting else True
    status_str = "Enabled (Only naming when there are pings)" if current_status else "Disabled (Naming every spawn)"

    embed = discord.Embed(
        title="⚙️ OnlyPing Settings",
        description=f"**Current Status:** {status_str}\n\n**Usage:**\n`E!onlyping enable` - Name only when there are pings.\n`E!onlyping disable` - Name every spawn regardless of pings.",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@onlyping_group.command(name="enable")
async def onlyping_enable(ctx):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can configure spawn alert settings.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    guild_setting = await settings_col.find_one({"guild_id": ctx.guild.id})
    current_status = guild_setting.get("only_ping", True) if guild_setting else True

    if current_status:
        embed = discord.Embed(
            description="❌ OnlyPing is **already enabled**!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    await settings_col.update_one(
        {"guild_id": ctx.guild.id},
        {"$set": {"only_ping": True}},
        upsert=True
    )
    embed = discord.Embed(
        description="✅ **OnlyPing enabled!** The bot will now only name/alert spawns when there are active pings.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@onlyping_group.command(name="disable")
async def onlyping_disable(ctx):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can configure spawn alert settings.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    guild_setting = await settings_col.find_one({"guild_id": ctx.guild.id})
    current_status = guild_setting.get("only_ping", True) if guild_setting else True

    if not current_status:
        embed = discord.Embed(
            description="❌ OnlyPing is **already disabled**!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    await settings_col.update_one(
        {"guild_id": ctx.guild.id},
        {"$set": {"only_ping": False}},
        upsert=True
    )
    embed = discord.Embed(
        description="✅ **OnlyPing disabled!** The bot will now name and alert **every** single spawn.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


# --- Interactive Pagination Views & Rest of Commands ---
class CollectionPaginationView(discord.ui.View):
    def __init__(self, user_id, all_pokemon, per_page=20):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.all_pokemon = all_pokemon
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = (len(all_pokemon) + per_page - 1) // per_page

    def get_embed(self):
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        current_mons = self.all_pokemon[start_idx:end_idx]

        lines = [f"• {mon}" for mon in current_mons]

        embed = discord.Embed(
            title=f"📦 Your Collection (Page {self.current_page}/{self.total_pages})",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Total Pokémon: {len(self.all_pokemon)}")
        return embed

    @discord.ui.button(label="  ◀️  ", style=discord.ButtonStyle.primary, custom_id="prev_page")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This list belongs to someone else.", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="  ▶️  ", style=discord.ButtonStyle.primary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This list belongs to someone else.", ephemeral=True)
            return

        if self.current_page < self.total_pages:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()


class ReservePaginationView(discord.ui.View):
    def __init__(self, author_id, formatted_lines, title="📋 Server Reserves", per_page=20):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.formatted_lines = formatted_lines
        self.title = title
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = max(1, (len(formatted_lines) + per_page - 1) // per_page)

    def get_embed(self):
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        current_lines = self.formatted_lines[start_idx:end_idx]

        embed = discord.Embed(
            title=f"{self.title} (Page {self.current_page}/{self.total_pages})",
            description="\n".join(current_lines) if current_lines else "No active reserves.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Total Reserved Entries: {len(self.formatted_lines)}")
        return embed

    @discord.ui.button(label="  ◀️  ", style=discord.ButtonStyle.primary, custom_id="reserve_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You cannot interact with this menu.", ephemeral=True)
            return

        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="  ▶️  ", style=discord.ButtonStyle.primary, custom_id="reserve_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You cannot interact with this menu.", ephemeral=True)
            return

        if self.current_page < self.total_pages:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        else:
            await interaction.response.defer()

class ClearConfirmView(discord.ui.View):
    def __init__(self, author_id, target_user=None, guild_id=None):
        super().__init__(timeout=30)
        self.author_id = author_id
        self.target_user = target_user
        self.guild_id = guild_id
        self.confirmed = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger, custom_id="clear_yes")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You cannot interact with this menu.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        if self.target_user:
            await reserves_col.delete_one({"guild_id": self.guild_id, "user_id": self.target_user.id})
            embed = discord.Embed(
                description=f"✅ Cleared all reserves for {self.target_user.mention}.",
                color=discord.Color.green()
            )
        else:
            await reserves_col.delete_many({"guild_id": self.guild_id})
            embed = discord.Embed(
                description="✅ Cleared all reserves across the entire server.",
                color=discord.Color.green()
            )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary, custom_id="clear_no")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You cannot interact with this menu.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            description="❌ Reserve clear action canceled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=self)

@bot.group(name="cl", invoke_without_command=True)
async def collection_group(ctx):
    embed = discord.Embed(
        title="📦 Collection Commands",
        description=(
            "**`E!cl`** - Display this collection help list.\n"
            "**`E!cl list`** - View your personal collection list.\n"
            "**`E!cl add <mons>`** - Add Pokémon to your collection.\n"
            "**`E!cl remove <mons>`** - Remove Pokémon from your collection.\n"
            "**`E!cl clear`** - Clear your entire collection."
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)


@collection_group.command(name="list")
async def collection_list(ctx, page: int = 1):
    user_doc = await collections_col.find_one({"user_id": ctx.author.id})
    if not user_doc or not user_doc.get("pokemon"):
        embed = discord.Embed(
            description="❌ Your collection is currently empty.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    all_pokemon = user_doc["pokemon"]
    view = CollectionPaginationView(ctx.author.id, all_pokemon)
    
    if page >= 1 and page <= view.total_pages:
        view.current_page = page

    if view.total_pages > 1:
        await ctx.send(embed=view.get_embed(), view=view)
    else:
        await ctx.send(embed=view.get_embed())


@collection_group.command(name="add")
async def collection_add(ctx, *, mons: str = None):
    try:
        if not mons:
            embed = discord.Embed(
                description="❌ Please specify at least one Pokémon to add.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        raw_list = parse_pokemon_list(mons)
        final_mons = []
        display_names = []
        invalid_items = []

        for item in raw_list:
            is_all = item.startswith("all ")
            clean_item = item[4:].strip() if is_all else item.strip()
            
            if validate_species(clean_item) or validate_species(item):
                if is_all:
                    forms = get_pokemon_variants(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in POKEMON_FORMS:
                    base_name = get_base_pokemon(clean_item)
                    final_mons.append(base_name)
                    display_names.append(base_name)
                elif clean_item in REGIONAL_FORMS:
                    formatted_name = REGIONAL_FORMS[clean_item]
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
                else:
                    formatted_name = format_pokemon_name(item if validate_species(item) else clean_item)
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
            else:
                invalid_items.append(item)

        if final_mons:
            unique_mons = list(dict.fromkeys(final_mons))
            unique_display = list(dict.fromkeys(display_names))
            await collections_col.update_one(
                {"user_id": ctx.author.id},
                {"$addToSet": {"pokemon": {"$each": unique_mons}}},
                upsert=True
            )
            added_str = ", ".join(unique_display)
            embed = discord.Embed(
                description=f"✅ Added to your collection: **{added_str}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        if invalid_items:
            bad_words = ", ".join([f'"{w}"' for w in invalid_items])
            embed = discord.Embed(
                description=f"⚠️ Added valid Pokémon, but ignored invalid items: {bad_words}",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            
    except Exception as e:
        print(f"Error in collection_add: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


@collection_group.command(name="remove")
async def collection_remove(ctx, *, mons: str = None):
    try:
        if not mons:
            embed = discord.Embed(
                description="❌ Please specify at least one Pokémon to remove.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        raw_list = parse_pokemon_list(mons)
        final_mons = []
        display_names = []
        invalid_items = []

        for item in raw_list:
            is_all = item.startswith("all ")
            clean_item = item[4:].strip() if is_all else item.strip()
            
            if validate_species(clean_item) or validate_species(item):
                if is_all:
                    forms = get_pokemon_variants(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in POKEMON_FORMS:
                    base_name = get_base_pokemon(clean_item)
                    final_mons.append(base_name)
                    display_names.append(base_name)
                elif clean_item in REGIONAL_FORMS:
                    formatted_name = REGIONAL_FORMS[clean_item]
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
                else:
                    formatted_name = format_pokemon_name(item if validate_species(item) else clean_item)
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
            else:
                invalid_items.append(item)

        if final_mons:
            unique_mons = list(dict.fromkeys(final_mons))
            unique_display = list(dict.fromkeys(display_names))
            await collections_col.update_one(
                {"user_id": ctx.author.id},
                {"$pull": {"pokemon": {"$in": unique_mons}}}
            )
            removed_str = ", ".join(unique_display)
            embed = discord.Embed(
                description=f"✅ Removed from your collection: **{removed_str}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        if invalid_items:
            bad_words = ", ".join([f'"{w}"' for w in invalid_items])
            embed = discord.Embed(
                description=f"⚠️ Removed valid Pokémon, but ignored unknown items: {bad_words}",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            
    except Exception as e:
        print(f"Error in collection_remove: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))

@collection_group.command(name="clear")
async def collection_clear(ctx):
    try:
        result = await collections_col.delete_one({"user_id": ctx.author.id})
        if result.deleted_count > 0:
            embed = discord.Embed(
                description="✅ Your collection has been completely cleared.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                description="❌ Your collection is already empty.",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Error in collection_clear: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


# ==========================================
# 📋 RESERVE COMMANDS (E!r)
# ==========================================

@bot.group(name="r", invoke_without_command=True)
async def reserve_group(ctx, target: discord.Member = None, page: int = 1):
    if target:
        await reserve_user(ctx, target=target, page=page)
        return

    embed = discord.Embed(
        title="📋 Reserve Commands",
        description=(
            "## View & Lookup Commands\n"
            "**`E!r`** - Display this reserve command help list.\n"
            "**`E!r list`** - View all active server reserves.\n"
            "**`E!r @user`** - View reserved Pokémon for a specific user.\n"
            "**`E!r search <mons>`** - Search which users have specific Pokémon reserved.\n\n"
            "## Management Commands (Staff)\n"
            "**`E!r add <mons> [@user]`** - Add Pokémon/families to reserves.\n"
            "**`E!r remove <mons> [@user]`** - Remove specified reserves.\n"
            "**`E!r clear @user`** - Clear all reserves for a specific user.\n"
            "**`E!r clear`** - Clear all reserves across the entire server.\n"
            "**`E!r e @mainuser`** - Exchange reserves from a replied message.\n\n"
            "## Admin Role Permissions\n"
            "**`E!r role list`** - View authorized staff roles.\n"
            "**`E!r role add @Role`** - Grant reserve staff permissions.\n"
            "**`E!r role remove @Role`** - Revoke reserve staff permissions."
        ),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)



@reserve_group.command(name="list")
async def reserve_list(ctx, page: int = 1):
    try:
        cursor = reserves_col.find({"guild_id": ctx.guild.id})
        reserves = await cursor.to_list(length=1000)

        if not reserves:
            embed = discord.Embed(
                description="🔍 No active reserves found for this server.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        mon_to_users = {}
        for doc in reserves:
            user_id = doc["user_id"]
            member = ctx.guild.get_member(user_id)
            user_mention = member.mention if member else f"<@{user_id}>"
            
            for mon in doc.get("pokemon", []):
                formatted_mon = format_pokemon_name(mon)
                if formatted_mon not in mon_to_users:
                    mon_to_users[formatted_mon] = []
                if user_mention not in mon_to_users[formatted_mon]:
                    mon_to_users[formatted_mon].append(user_mention)

        formatted_lines = [
            f"• **{mon}** - {', '.join(users)}"
            for mon, users in sorted(mon_to_users.items(), key=lambda item: item[0].lower())
        ]

        view = ReservePaginationView(ctx.author.id, formatted_lines, per_page=20)
        if 1 <= page <= view.total_pages:
            view.current_page = page

        if view.total_pages > 1:
            await ctx.send(embed=view.get_embed(), view=view)
        else:
            await ctx.send(embed=view.get_embed())

    except Exception as e:
        print(f"Error in reserve_list: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))



@reserve_group.command(name="e")
async def reserve_exchange(ctx, main_user: discord.Member = None):
    if not await is_staff(ctx):
        embed = discord.Embed(
            description="❌ You do not have permission to use staff exchange commands.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not ctx.message.reference:
        embed = discord.Embed(
            description="❌ Please reply to a message containing the user list (e.g., `@user - all furfrou, alolan vulpix, pikachu`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    try:
        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    except Exception:
        await ctx.send(embed=discord.Embed(description="❌ Could not fetch the replied message.", color=discord.Color.red()))
        return

    if main_user:
        giver_id = main_user.id
    elif replied_msg.author and not replied_msg.author.bot:
        giver_id = replied_msg.author.id
    else:
        giver_id = ctx.author.id

    giver_doc = await reserves_col.find_one({"guild_id": ctx.guild.id, "user_id": giver_id})
    giver_pokemon = set(giver_doc.get("pokemon", [])) if giver_doc else set()

    if not giver_pokemon:
        giver_mention = f"<@{giver_id}>"
        embed = discord.Embed(
            description=f"❌ {giver_mention} has no Pokémon in their reserves to give away.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    current_giver_pool = set(giver_pokemon)
    lines = replied_msg.content.split("\n")
    
    transfers_made = 0
    error_report = []
    total_pulled_mons = [] 

    for line in lines:
        if not line.strip():
            continue
        
        mentioned_users = [m for m in replied_msg.mentions if str(m.id) in line or m.mention in line]
        if not mentioned_users:
            continue

        parts = line.split("-") if "-" in line else line.split(":")
        if len(parts) < 2:
            continue
        
        pokemon_raw_text = parts[1].strip()
        criteria_list = [c.strip() for c in pokemon_raw_text.split(",") if c.strip()]

        for user in mentioned_users:
            user_valid_mons = []

            for criterion in criteria_list:
                crit_lower = criterion.lower()

                if crit_lower.startswith("all "):
                    target_species = crit_lower[4:].strip()
                    matching_mons = [
                        mon for mon in current_giver_pool 
                        if target_species in mon.lower() or mon.lower().startswith(target_species)
                    ]
                    
                    if matching_mons:
                        user_valid_mons.extend(matching_mons)
                        for m in matching_mons:
                            current_giver_pool.remove(m)
                    else:
                        error_report.append(f"`{criterion}` (for {user.display_name}) - No matching Pokémon found in <@{giver_id}>'s reserves")
                
                else:
                    formatted_mon = format_pokemon_name(criterion)
                    
                    if formatted_mon in current_giver_pool:
                        user_valid_mons.append(formatted_mon)
                        current_giver_pool.remove(formatted_mon)
                    elif criterion in current_giver_pool:
                        user_valid_mons.append(criterion)
                        current_giver_pool.remove(criterion)
                    else:
                        error_report.append(f"`{criterion}` (for {user.display_name}) - Not in <@{giver_id}>'s reserves or typed wrong")

            if user_valid_mons:
                await reserves_col.update_one(
                    {"guild_id": ctx.guild.id, "user_id": user.id},
                    {"$addToSet": {"pokemon": {"$each": user_valid_mons}}},
                    upsert=True
                )
                transfers_made += len(user_valid_mons)
                total_pulled_mons.extend(user_valid_mons)

    if total_pulled_mons:
        await reserves_col.update_one(
            {"guild_id": ctx.guild.id, "user_id": giver_id},
            {"$pull": {"pokemon": {"$in": total_pulled_mons}}}
        )

    if transfers_made > 0 and not error_report:
        embed = discord.Embed(
            description=f"✅ Exchange successful!\n Successfully distributed **{transfers_made}** Pokémon from <@{giver_id}>'s reserves.",
            color=discord.Color.green()
        )
    elif transfers_made > 0 and error_report:
        embed = discord.Embed(
            description=(
                f"⚠️ Distributed valid Pokémon (**{transfers_made}** transferred from <@{giver_id}>), but encountered some issues:\n\n"
                f"❌ **What went wrong:**\n• " + "\n• ".join(error_report)
            ),
            color=discord.Color.gold()
        )
    else:
        embed = discord.Embed(
            description=(
                f"❌ Exchange failed. None of the specified Pokémon could be transferred.\n\n"
                f"❌ **What went wrong:**\n• " + ("\n• ".join(error_report) if error_report else "No valid entries found in the replied message.")
            ),
            color=discord.Color.red()
        )

    await ctx.send(embed=embed)




@reserve_group.command(name="add")
async def reserve_add(ctx, *, args: str = None):
    try:
        if not await is_staff(ctx):
            embed = discord.Embed(
                description="❌ You do not have permission to modify reserves.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if not args:
            embed = discord.Embed(
                description="❌ Please specify Pokémon to reserve (e.g. `E!r add Charmander @User`).",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        target_user = ctx.author
        if ctx.message.mentions:
            target_user = ctx.message.mentions[0]
            for mention in ctx.message.mentions:
                args = args.replace(mention.mention, "").replace(f"<@!{mention.id}>", "")

        raw_list = parse_pokemon_list(args)
        final_mons = []
        display_names = []
        invalid_items = []

        for item in raw_list:
            is_all = item.startswith("all ")
            clean_item = item[4:].strip() if is_all else item.strip()
            
            if validate_species(clean_item) or validate_species(item):
                if is_all:
                    forms = get_pokemon_variants(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in POKEMON_FORMS:
                    base_name = get_base_pokemon(clean_item)
                    final_mons.append(base_name)
                    display_names.append(base_name)
                elif clean_item in REGIONAL_FORMS:
                    formatted_name = REGIONAL_FORMS[clean_item]
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
                else:
                    formatted_name = format_pokemon_name(clean_item)
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
            else:
                invalid_items.append(item)

        if final_mons:
            unique_mons = list(dict.fromkeys(final_mons))
            unique_display = list(dict.fromkeys(display_names))
            
            await reserves_col.update_one(
                {"guild_id": ctx.guild.id, "user_id": target_user.id},
                {"$addToSet": {"pokemon": {"$each": unique_mons}}},
                upsert=True
            )
            added_str = ", ".join(unique_display)
            embed = discord.Embed(
                description=f"✅ Added to reserves for {target_user.mention}: **{added_str}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        if invalid_items:
            bad_words = ", ".join([f'"{w}"' for w in invalid_items])
            embed = discord.Embed(
                description=f"⚠️ Added valid Pokémon, but ignored unknown items: {bad_words}",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)

    except Exception as e:
        print(f"Error in reserve_add: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


@reserve_group.command(name="remove")
async def reserve_remove(ctx, *, args: str = None):
    try:
        if not await is_staff(ctx):
            embed = discord.Embed(
                description="❌ You do not have permission to modify reserves.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if not args:
            embed = discord.Embed(
                description="❌ Please specify Pokémon to remove from reserves.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        target_user = ctx.author
        if ctx.message.mentions:
            target_user = ctx.message.mentions[0]
            for mention in ctx.message.mentions:
                args = args.replace(mention.mention, "").replace(f"<@!{mention.id}>", "")

        raw_list = parse_pokemon_list(args)
        final_mons = []
        display_names = []
        invalid_items = []

        for item in raw_list:
            is_all = item.startswith("all ")
            clean_item = item[4:].strip() if is_all else item.strip()
            
            if validate_species(clean_item) or validate_species(item):
                if is_all:
                    forms = get_pokemon_variants(clean_item)
                    final_mons.extend(forms)
                    display_names.append(f"All {format_pokemon_name(clean_item)}")
                elif clean_item in POKEMON_FORMS:
                    base_name = get_base_pokemon(clean_item)
                    final_mons.append(base_name)
                    display_names.append(base_name)
                elif clean_item in REGIONAL_FORMS:
                    formatted_name = REGIONAL_FORMS[clean_item]
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
                else:
                    formatted_name = format_pokemon_name(clean_item)
                    final_mons.append(formatted_name)
                    display_names.append(formatted_name)
            else:
                invalid_items.append(item)

        if final_mons:
            unique_mons = list(dict.fromkeys(final_mons))
            unique_display = list(dict.fromkeys(display_names))
            
            await reserves_col.update_one(
                {"guild_id": ctx.guild.id, "user_id": target_user.id},
                {"$pull": {"pokemon": {"$in": unique_mons}}}
            )
            removed_str = ", ".join(unique_display)
            embed = discord.Embed(
                description=f"✅ Removed from reserves for {target_user.mention}: **{removed_str}**",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        if invalid_items:
            bad_words = ", ".join([f'"{w}"' for w in invalid_items])
            embed = discord.Embed(
                description=f"⚠️ Removed valid Pokémon, but ignored unknown items: {bad_words}",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)

    except Exception as e:
        print(f"Error in reserve_remove: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))




@reserve_group.command(name="search")
async def reserve_search(ctx, *, mon: str = None):
    try:
        if not mon:
            embed = discord.Embed(
                description="❌ Please specify a Pokémon to search.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        is_all = mon.startswith("all ")
        clean_mon = mon[4:].strip() if is_all else mon.strip()

        if is_all:
            target_mons = get_pokemon_variants(clean_mon)
        elif clean_mon in POKEMON_FORMS:
            target_mons = [get_base_pokemon(clean_mon)]
        elif clean_mon in REGIONAL_FORMS:
            target_mons = [REGIONAL_FORMS[clean_mon]]
        else:
            target_mons = [format_pokemon_name(clean_mon)]

        cursor = reserves_col.find({"guild_id": ctx.guild.id})
        all_reserves = await cursor.to_list(length=1000)

        mon_to_users = {}

        for doc in all_reserves:
            user_id = doc["user_id"]
            member = ctx.guild.get_member(user_id)
            user_mention = member.mention if member else f"<@{user_id}>"

            user_pokemon = [format_pokemon_name(p) for p in doc.get("pokemon", [])]

            for target in target_mons:
                formatted_target = format_pokemon_name(target)
                if formatted_target in user_pokemon:
                    if formatted_target not in mon_to_users:
                        mon_to_users[formatted_target] = []
                    if user_mention not in mon_to_users[formatted_target]:
                        mon_to_users[formatted_target].append(user_mention)

        if not mon_to_users:
            searched_name = f"All {format_pokemon_name(clean_mon)}" if is_all else format_pokemon_name(clean_mon)
            embed = discord.Embed(
                description=f"🔍 No user has reserved **{searched_name}**.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        formatted_lines = [
            f"• **{pokemon}** - {', '.join(users)}"
            for pokemon, users in sorted(mon_to_users.items())
        ]

        embed = discord.Embed(
            title=f"🔍 Reserve Search Results",
            description="\n".join(formatted_lines),
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        print(f"Error in reserve_search: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))



@reserve_group.command(name="user")
async def reserve_user(ctx, target: discord.Member = None, page: int = 1):
    if not target:
        target = ctx.author

    user_doc = await reserves_col.find_one({"guild_id": ctx.guild.id, "user_id": target.id})
    if not user_doc or not user_doc.get("pokemon"):
        embed = discord.Embed(
            description=f"🔍 {target.mention} has no reserved Pokémon.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
        return

    all_pokemon = user_doc["pokemon"]
    formatted_lines = [f"• {format_pokemon_name(mon)}" for mon in sorted(all_pokemon)]

    title = f"📋 Reserves for {target.display_name}"
    view = ReservePaginationView(ctx.author.id, formatted_lines, title=title, per_page=20)
    
    if 1 <= page <= view.total_pages:
        view.current_page = page

    if view.total_pages > 1:
        await ctx.send(embed=view.get_embed(), view=view)
    else:
        await ctx.send(embed=view.get_embed())



@reserve_group.command(name="clear")
async def reserve_clear(ctx, target: discord.Member = None):
    try:
        if not await is_staff(ctx):
            embed = discord.Embed(
                description="❌ You do not have permission to use staff commands.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if target:
            prompt_text = f"⚠️ Are you sure you want to clear all reserves for {target.mention}?"
        else:
            prompt_text = "⚠️ Are you sure you want to **clear ALL reserves** across the entire server?"

        embed = discord.Embed(
            description=prompt_text,
            color=discord.Color.gold()
        )
        view = ClearConfirmView(author_id=ctx.author.id, target_user=target, guild_id=ctx.guild.id)
        await ctx.send(embed=embed, view=view)

    except Exception as e:
        print(f"Error in reserve_clear: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


def parse_roles_from_input(ctx, raw_input: str):
    items = [item.strip() for item in raw_input.split(",") if item.strip()]
    valid_roles = []
    invalid_roles = []

    for item in items:
        role = None
        match = re.search(r"<@&(\d+)>", item)
        if match:
            role_id = int(match.group(1))
            role = ctx.guild.get_role(role_id)
        elif item.isdigit():
            role = ctx.guild.get_role(int(item))
        else:
            role = discord.utils.get(ctx.guild.roles, name=item)

        if role:
            valid_roles.append(role)
        else:
            invalid_roles.append(item)

    return valid_roles, invalid_roles


@reserve_group.group(name="role", invoke_without_command=True)
async def reserve_role_group(ctx):
    embed = discord.Embed(
        title="🛡️ Reserve Staff Role Commands",
        description=(
            "**`E!r role list`** - View configured staff roles.\n"
            "**`E!r role add @Role1, @Role2`** - Grant reserve staff permissions.\n"
            "**`E!r role remove @Role1, @Role2`** - Revoke reserve staff permissions."
        ),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_role_group.command(name="list")
async def reserve_role_list(ctx):
    doc = await roles_col.find_one({"guild_id": ctx.guild.id})
    if not doc or not doc.get("roles"):
        embed = discord.Embed(
            description="ℹ️ No staff roles configured. Administrators have default access.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    roles = [f"<@&{rid}>" for rid in doc["roles"]]
    embed = discord.Embed(
        title="🛡️ Authorized Reserve Staff Roles",
        description="\n".join(roles),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@reserve_role_group.command(name="add")
async def reserve_role_add(ctx, *, roles_input: str = None):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can manage staff roles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not roles_input:
        embed = discord.Embed(
            description="❌ Please specify at least one role (e.g. `E!r role add @Staff, @Mod`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    valid_roles, invalid_roles = parse_roles_from_input(ctx, roles_input)

    if not valid_roles and invalid_roles:
        embed = discord.Embed(
            description=f"❌ Could not find any valid roles from: `{', '.join(invalid_roles)}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    role_ids = [r.id for r in valid_roles]
    await roles_col.update_one(
        {"guild_id": ctx.guild.id},
        {"$addToSet": {"roles": {"$each": role_ids}}},
        upsert=True
    )

    added_mentions = ", ".join([r.mention for r in valid_roles])
    desc = f"✅ {added_mentions} were added successfully."
    if invalid_roles:
        desc += f"\n❌ **Could not find / Invalid roles:** `{', '.join(invalid_roles)}`"

    embed = discord.Embed(description=desc, color=discord.Color.green())
    await ctx.send(embed=embed)


@reserve_role_group.command(name="remove")
async def reserve_role_remove(ctx, *, roles_input: str = None):
    if not ctx.author.guild_permissions.administrator:
        embed = discord.Embed(
            description="❌ Only server administrators can manage staff roles.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if not roles_input:
        embed = discord.Embed(
            description="❌ Please specify at least one role to remove (e.g. `E!r role remove @Staff`).",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    valid_roles, invalid_roles = parse_roles_from_input(ctx, roles_input)

    if not valid_roles and invalid_roles:
        embed = discord.Embed(
            description=f"❌ Could not find any valid roles from: `{', '.join(invalid_roles)}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    role_ids = [r.id for r in valid_roles]
    await roles_col.update_one(
        {"guild_id": ctx.guild.id},
        {"$pull": {"roles": {"$in": role_ids}}}
    )

    removed_mentions = ", ".join([r.mention for r in valid_roles])
    desc = f"✅ {removed_mentions} were removed successfully."
    if invalid_roles:
        desc += f"\n❌ **Could not find / Invalid roles:** `{', '.join(invalid_roles)}`"

    embed = discord.Embed(description=desc, color=discord.Color.green())
    await ctx.send(desc=desc)


# ==========================================
# ✨️ SHINY HUNT COMMANDS (E!sh)
# ==========================================

@bot.group(name="sh", invoke_without_command=True)
async def shiny_group(ctx, *, target_mon: str = None):
    if target_mon:
        clean_target = target_mon.strip().lower()
        if not validate_species(clean_target):
            embed = discord.Embed(
                description=f"❌ **{target_mon}** is not a valid Pokémon.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        formatted_mon = format_pokemon_name(clean_target)
        await shiny_col.update_one(
            {"user_id": ctx.author.id},
            {"$set": {"target": formatted_mon}},
            upsert=True
        )
        embed = discord.Embed(
            description=f"✅ Set active shiny hunt to ✨️ **{formatted_mon}**.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
        return

    user_doc = await shiny_col.find_one({"user_id": ctx.author.id})
    target = user_doc.get("target", "None") if user_doc else "None"

    embed = discord.Embed(
        title="✨️ Shiny Hunt",
        description=f"**Current Active Hunt:** ✨️ **{target}**\n\nUse **`E!sh <mon>`** to set a new target.",
        color=discord.Color.purple()
    )
    await ctx.send(embed=embed)

@shiny_group.command(name="clear")
async def shiny_clear(ctx):
    try:
        result = await shiny_col.delete_one({"user_id": ctx.author.id})
        if result.deleted_count > 0:
            embed = discord.Embed(
                description="✅ Your active shiny hunt has been cleared.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                description="❌ You do not have an active shiny hunt to clear.",
                color=discord.Color.red()
            )
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Error in shiny_clear: {e}")
        await ctx.send(embed=discord.Embed(description=f"❌ An error occurred: `{e}`", color=discord.Color.red()))


# Run Bot safely from environment variables
bot.run(os.getenv("DISCORD_TOKEN"))
