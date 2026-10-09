import os
import discord
import requests
import imagehash
from PIL import Image
from io import BytesIO

# Initialize the Discord Bot client
intents = discord.Intents.default()
intents.message_content = True  # Allows Eevee to read message text/embeds
client = discord.Client(intents=intents)

# This is a public community URL containing standard Pokétwo spawn pHashes
ONLINE_DB_URL = "https://githubusercontent.com"
pokemon_db = {}

@client.event
async def on_ready():
    global pokemon_db
    print(f"Logged in as {client.user.name} (ID: {client.user.id})")
    print("Connecting to the cloud pHash database...")
    
    try:
        response = requests.get(ONLINE_DB_URL)
        pokemon_db = response.json()
        print(f"Successfully loaded {len(pokemon_db)} Pokémon profiles into memory!")
    except Exception as e:
        print(f"Error loading database: {e}")

@client.event
async def on_message(message):
    # Change 'Pokétwo#8236' to the exact name or ID of the Pokétwo bot in your server
    if message.author.name == "Pokétwo" or message.author.id == 716390085896962058:
        # Check if the message contains an embed with an image (a spawn notification)
        if message.embeds:
            embed = message.embeds[0]
            if embed.image and embed.image.url:
                spawn_url = embed.image.url
                await message.channel.send("🔍 *Eevee is scanning the spawn pattern...*")
                
                try:
                    # 1. Fetch the image from the Discord CDN
                    img_response = requests.get(spawn_url)
                    spawn_img = Image.open(BytesIO(img_response.content))
                    
                    # 2. Compute its perceptual hash
                    spawn_hash = imagehash.phash(spawn_img, hash_size=8)
                    
                    best_match = None
                    lowest_distance = 999
                    
                    # 3. Match against the preloaded online database
                    for poke_id, data in pokemon_db.items():
                        db_hash = imagehash.hex_to_hash(data["phash"])
                        distance = spawn_hash - db_hash
                        
                        if distance < lowest_distance:
                            lowest_distance = distance
                            best_match = data["name"]
                    
                    # 4. Output the result if the match is precise enough
                    if lowest_distance <= 12 and best_match:
                        await message.channel.send(f"🚨 **Spawn Detected!** That looks like a wild **{best_match}**!")
                    else:
                        await message.channel.send("⚠️ Visual profile matches multiple targets. Try scanning again.")
                        
                except Exception as e:
                    print(f"Scanning error: {e}")
                    await message.channel.send("❌ Failed to process the spawn image buffer.")

# Securely grab the token from Render's dashboard environment variables
client.run(os.environ.get("DISCORD_TOKEN")
