import os, json, discord, requests, imagehash
from PIL import Image
from io import BytesIO

intents = discord.Intents.default()
intents.message_content = True  
client = discord.Client(intents=intents)

ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}
COLLECTION_FILE = "collection.json"

if os.path.exists(COLLECTION_FILE):
    with open(COLLECTION_FILE, "r") as f:
        try:
            db_data = json.load(f)
            user_collections = db_data.get("collection", {})
            shiny_hunts = db_data.get("shiny", {})
            reserve_list = db_data.get("reserve", [])  
        except:
            user_collections, shiny_hunts, reserve_list = {}, {}, []
else:
    user_collections, shiny_hunts, reserve_list = {}, {}, []

def save_data():
    with open(COLLECTION_FILE, "w") as f:
        json.dump({"collection": user_collections, "shiny": shiny_hunts, "reserve": reserve_list}, f, indent=4)

@client.event
async def on_ready():
    global pokemon_db
    print(f"Logged in as {client.user.name}")
    try:
        response = requests.get(ONLINE_DB_URL)
        pokemon_db = response.json()
        print("Loaded database!")
    except Exception as e:
        print(f"DB Error: {e}")
@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_id = str(message.author.id)
    msg_lower = message.content.lower().strip()

    if msg_lower == "e!tags":
        active = {uid: hunts for uid, hunts in shiny_hunts.items() if hunts}
        if not active:
            return await message.channel.send("✨ No active shiny hunters! Use `e!sh add <name>`.")
        lines = ["🌟 **Server Shiny Hunters Master List:**\n"]
        for uid, hunts in active.items():
            u = client.get_user(int(uid))
            name = u.name if u else f"User: {uid}"
            lines.append(f"• **@{name}** is hunting: *{', '.join(sorted(hunts))}*")
        return await message.channel.send("\n".join(lines))

    if msg_lower.startswith("e!cl add "):
        name = message.content[9:].strip().title()
        if not name:
            return await message.channel.send("⚠️ Specify a name! Example: `e!cl add Pikachu`")
        if user_id not in user_collections: user_collections[user_id] = []
        if name not in user_collections[user_id]:
            user_collections[user_id].append(name)
            save_data()
            await message.channel.send(f"✅ **{name}** added to your col list!")
        else:
            await message.channel.send(f"⚠️ **{name}** is already in your col list!")
        return

    if msg_lower.startswith("e!cl remove ") or msg_lower.startswith("e!cl del "):
        l = 12 if msg_lower.startswith("e!cl remove ") else 9
        name = message.content[l:].strip().title()
        if user_id in user_collections and name in user_collections[user_id]:
            user_collections[user_id].remove(name)
            save_data()
            await message.channel.send(f"❌ **{name}** removed from your col list!")
        else:
            await message.channel.send(f"⚠️ **{name}** not found.")
        return

    if msg_lower in ["e!cl list", "e!cl view"]:
        if user_id in user_collections and user_collections[user_id]:
            lines = [f"{i+1}. **{n}**" for i, n in enumerate(sorted(user_collections[user_id]))]
            await message.channel.send(f"📋 **Your Collection Wishlist:**\n" + "\n".join(lines))
        else:
            await message.channel.send("📁 Your collection list is empty!")
        return

    if msg_lower == "e!cl clear":
        if user_id in user_collections and user_collections[user_id]:
            user_collections[user_id] = []
            save_data()
            await message.channel.send("🗑️ Collection cleared!")
        else:
            await message.channel.send("⚠️ Already empty.")
        return

    if msg_lower == "e!sh clear":
        if user_id in shiny_hunts and shiny_hunts[user_id]:
            shiny_hunts[user_id] = []
            save_data()
            await message.channel.send("✨🗑️ Shiny Hunt list cleared!")
        else:
            await message.channel.send("⚠️ Already empty.")
        return

    if msg_lower in ["e!sh list", "e!sh view"]:
        if user_id in shiny_hunts and shiny_hunts[user_id]:
            lines = [f"{i+1}. ✨ **{n}**" for i, n in enumerate(sorted(shiny_hunts[user_id]))]
            await message.channel.send(f"🌟 **Your Active Shiny Hunts:**\n" + "\n".join(lines))
        else:
            await message.channel.send("✨ Not tracking any shiny targets! Use `e!sh add <name>`.")
        return

    if msg_lower.startswith("e!sh remove ") or msg_lower.startswith("e!sh del "):
        l = 12 if msg_lower.startswith("e!sh remove ") else 9
        name = message.content[l:].strip().title()
        if user_id in shiny_hunts and name in shiny_hunts[user_id]:
            shiny_hunts[user_id].remove(name)
            save_data()
            await message.channel.send(f"❌ **{name}** removed.")
        else:
            await message.channel.send(f"⚠️ **{name}** not found.")
        return

    if msg_lower.startswith("e!sh add ") or (msg_lower.startswith("e!sh ") and not message.mentions):
        name = message.content[9:].strip().title() if msg_lower.startswith("e!sh add ") else message.content[5:].strip().title()
        if name:
            if user_id not in shiny_hunts: shiny_hunts[user_id] = []
            if name not in shiny_hunts[user_id]:
                shiny_hunts[user_id].append(name)
                save_data()
                await message.channel.send(f"✨ **{name}** added to Shiny Hunts!")
            else:
                await message.channel.send(f"⚠️ Already hunting **{name}**!")
        return
    if msg_lower == "e!r clear":
        global reserve_list
        if reserve_list:
            reserve_list = []
            save_data()
            await message.channel.send("📦🗑️ **Server Reserve List cleared!**")
        else:
            await message.channel.send("⚠️ Already empty.")
        return

    if msg_lower in ["e!r list", "e!r view"]:
        if reserve_list:
            lines = [f"{i+1}. 📦 **{n}**" for i, n in enumerate(sorted(reserve_list))]
            await message.channel.send(f"📋 **Entire Server Reserve List:**\n" + "\n".join(lines))
        else:
            await message.channel.send("📦 Server Reserve List is empty! Add with `e!r add <name>`.")
        return

    if msg_lower.startswith("e!r remove ") or msg_lower.startswith("e!r del "):
        l = 11 if msg_lower.startswith("e!r remove ") else 8
        name = message.content[l:].strip().title()
        if name in reserve_list:
            reserve_list.remove(name)
            save_data()
            await message.channel.send(f"❌ **{name}** removed from Reserves!")
        else:
            await message.channel.send(f"⚠️ **{name}** not found.")
        return

    if msg_lower.startswith("e!r add "):
        name = message.content[8:].strip().title()
        if not name:
            return await message.channel.send("⚠️ Specify a Pokémon! Example: `e!r add Mewtwo`")
        if name not in reserve_list:
            reserve_list.append(name)
            save_data()
            await message.channel.send(f"📦 **{name}** added to server Reserve List!")
        else:
            await message.channel.send(f"⚠️ **{name}** is already on the list!")
        return

    if msg_lower.startswith("e!r ") and message.mentions:
        target = message.mentions[0]  # Securely handles the first mentioned user object
        tid = str(target.id)
        c_dt = user_collections.get(tid, [])
        s_dt = shiny_hunts.get(tid, [])
        summary = f"📋 **Wishlist Profile for {target.name}:**\n\n🔹 **Collection:** {', '.join(sorted(c_dt)) if c_dt else '*None*'}\n✨ **Shiny Hunts:** {', '.join(sorted(s_dt)) if s_dt else '*None*'}\n"
        return await message.channel.send(summary)

    if message.author.name == "Pokétwo" or message.author.id == 716390085896962058:
        if message.embeds:
            for emb in message.embeds:
                if emb.image and emb.image.url:
                    url = emb.image.url
                    is_shiny = "shiny" in url.lower()
                    try:
                        res = requests.get(url)
                        img = Image.open(BytesIO(res.content))
                        hsh = imagehash.phash(img, hash_size=8)
                        match, low_dist = None, 999
                        for p_id, d in pokemon_db.items():
                            dist = hsh - imagehash.hex_to_hash(d["phash"])
                            if dist < low_dist:
                                low_dist = dist
                                match = d["name"]
                        if low_dist <= 12 and match:
                            await message.channel.send(f"🚨 **Spawn Detected!** That looks like a {'✨ SHINY ' if is_shiny else 'wild '}**{match}**!")
                            pings = []
                            for uid, col in user_collections.items():
                                if match in col: pings.append(f"<@{uid}> (Collection)")
                            if is_shiny:
                                for uid, sh in shiny_hunts.items():
                                    if match in sh: pings.append(f"<@{uid}> (✨ SHINY TARGET!)")
                            if pings or (match in reserve_list):
                                msg = "🔔 **Target Alert!** " + " ".join(pings)
                                if match in reserve_list:
                                    msg += " ⚠️ **[Server Reserve Match Found!]**"
                                await message.channel.send(msg)
                    except Exception as e:
                        print(f"Scanner Error: {e}")

# Securely boots the script process using your dashboard settings environment token
client.run(os.environ.get("DISCORD_TOKEN"))
