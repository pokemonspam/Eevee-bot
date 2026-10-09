import os
import discord
import requests
import imagehash
from PIL import Image
from io import BytesIO

# Main Discord Bot Code
intents = discord.Intents.default()
intents.message_content = True  
client = discord.Client(intents=intents)

ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}

@client.event
async def on_ready():
    global pokemon_db
    print(f"Logged in as {client.user.name} (ID: {client.user.id})")
    try:
        response = requests.get(ONLINE_DB_URL)
        pokemon_db = response.json()
        print(f"Loaded {len(pokemon_db)} Pokémon profiles into memory!")
    except Exception as e:
        print(f"Error loading database: {e}")

@client.event
async def on_message(message):
    # Triggers if Poketwo sends a message
    if message.author.name == "Pokétwo" or message.author.id == 716390085896962058:
        if message.embeds:
            embed = message.embeds[0]
            if embed.image and embed.image.url:
                spawn_url = embed.image.url
                await message.channel.send("🔍 *Eevee is scanning the spawn pattern...*")
                
                try:
                    img_response = requests.get(spawn_url)
                    spawn_img = Image.open(BytesIO(img_response.content))
                    spawn_hash = imagehash.phash(spawn_img, hash_size=8)
                    
                    best_match = None
                    lowest_distance = 999
                    
                    for poke_id, data in pokemon_db.items():
                        db_hash = imagehash.hex_to_hash(data["phash"])
                        distance = spawn_hash - db_hash
                        if distance < lowest_distance:
                            lowest_distance = distance
                            best_match = data["name"]
                    
                    if lowest_distance <= 12 and best_match:
                        await message.channel.send(f"🚨 **Spawn Detected!** That looks like a wild **{best_match}**!")
                    else:
                        await message.channel.send("⚠️ Visual profile matches multiple targets.")
                except Exception as e:
                    print(f"Scanning error: {e}")

# Securely grab the token from Railway's environment variables
client.run(os.environ.get("DISCORD_TOKEN"))
