import os
import re
import imagehash
import numpy as np
from PIL import Image
from datasets import load_dataset
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
import asyncio

HF_TOKEN = os.getenv("HF_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["pokemon_bot"]
phash_col = db["phash_database"]

def process_image_canvas(img: Image.Image) -> Image.Image:
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
            if r in [1, 2] and c in [1, 2]:
                mean_color *= 2.0
            features.extend(mean_color)
    features = np.array(features, dtype=float)
    norm = np.linalg.norm(features)
    if norm > 0:
        features /= norm
    return features.tolist()

def clean_pokemon_name(path_str: str) -> str:
    parts = path_str.replace("\\", "/").split("/")
    if len(parts) >= 2:
        folder = parts[-2]
    else:
        folder = "unknown"
    return folder.replace("_", " ").replace("-", " ").strip().title()

async def perfect_sync():
    print("🚀 Connecting to MongoDB and caching existing state...")
    existing_docs = await phash_col.find({}).to_list(length=None)
    cache = {doc["shortest_name"]: doc for doc in existing_docs}
    print(f"📦 Loaded {len(cache)} existing records into local memory cache.")

    print("🚀 Opening authenticated streaming connection to Hugging Face...")
    dataset = load_dataset(
        "SpreadSheets/Poketwo-Spawn-Images", 
        streaming=True, 
        split="train", 
        token=HF_TOKEN
    )

    count = 0
    modified_keys = set()

    print("⚡ Sync pipeline active! Progress will log every 500 images...")

    for item in dataset:
        try:
            raw_img = item.get("image")
            path_info = item.get("path", "")
            
            if not raw_img:
                continue

            pokemon_name = clean_pokemon_name(path_info)
            if pokemon_name.lower() == "unknown":
                continue

            img = process_image_canvas(raw_img)
            p_hash = str(imagehash.phash(img))
            d_hash = str(imagehash.dhash(img))
            vfs = extract_visual_features(img)

            key = pokemon_name.lower()

            if key not in cache:
                cache[key] = {
                    "pokemon": pokemon_name,
                    "shortest_name": key,
                    "phash": p_hash,
                    "phashes": [],
                    "dhash": d_hash,
                    "dhashes": [],
                    "visual_features": vfs,
                    "visual_features_list": []
                }

            doc = cache[key]
            old_p = doc.get("phashes", [])
            old_d = doc.get("dhashes", [])
            old_vfs = doc.get("visual_features_list", [])

            combined_p = list(dict.fromkeys(old_p + [p_hash]))[:120]
            combined_d = list(dict.fromkeys(old_d + [d_hash]))[:120]
            combined_vfs = (old_vfs + [vfs])[:120]

            doc["phash"] = combined_p[0]
            doc["phashes"] = combined_p
            doc["dhash"] = combined_d[0]
            doc["dhashes"] = combined_d
            doc["visual_features"] = combined_vfs[0]
            doc["visual_features_list"] = combined_vfs

            modified_keys.add(key)
            count += 1

            if len(modified_keys) >= 500:
                operations = [
                    UpdateOne({"shortest_name": k}, {"$set": cache[k]}, upsert=True)
                    for k in modified_keys
                ]
                await phash_col.bulk_write(operations, ordered=False)
                modified_keys.clear()
                print(f"🔥 Progress: Processed & synced {count} images... (Latest: {pokemon_name})")

        except Exception as e:
            print(f"⚠️ Error on item: {e}")

    if modified_keys:
        operations = [
            UpdateOne({"shortest_name": k}, {"$set": cache[k]}, upsert=True)
            for k in modified_keys
        ]
        await phash_col.bulk_write(operations, ordered=False)

    print(f"🎉 Dataset streaming sync complete! Total processed: {count} images.")

if __name__ == "__main__":
    asyncio.run(perfect_sync())
