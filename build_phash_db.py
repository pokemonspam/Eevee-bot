import os
import asyncio
import imagehash
from PIL import Image
from motor.motor_asyncio import AsyncIOMotorClient

# Connect to MongoDB
mongo_client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = mongo_client["pokemon_bot"]
phash_col = db["phash_database"]

SPRITE_FOLDER = "./pokemon_sprites"  # Put your sprite images here

async def build_database():
    print("🔄 Generating pHashes for dataset sprites...")
    count = 0
    
    for filename in os.listdir(SPRITE_FOLDER):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            pokemon_name = os.path.splitext(filename)[0].replace("_", " ").title()
            path = os.path.join(SPRITE_FOLDER, filename)
            
            try:
                with Image.open(path) as img:
                    # Compute perceptual hash
                    h = str(imagehash.phash(img))
                    
                    # Store in MongoDB (using hash as key or document)
                    await phash_col.update_one(
                        {"pokemon": pokemon_name},
                        {"$set": {"phash": h}},
                        upsert=True
                    )
                    count += 1
            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")
                
    print(f"✅ Successfully registered {count} Pokémon pHashes into MongoDB!")

if __name__ == "__main__":
    asyncio.run(build_database())
  
