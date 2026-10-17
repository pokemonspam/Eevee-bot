import os
import re
import imagehash
import numpy as np
from PIL import Image
from datasets import load_dataset
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
import asyncio
from concurrent.futures import ThreadPoolExecutor

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
    folder = parts[-2] if len(parts) >= 2 else "unknown"
    return folder.replace("_", " ").replace("-", " ").strip().title()

def process_single_item(item):
    """Heavy lifting function that runs in parallel threads"""
    try:
        raw_img = item.get("image")
        path_info = item.get("path", "")
        
        if not raw_img:
            return None

        pokemon_name = clean_pokemon_name(path_info)
        if pokemon_name.lower() == "unknown":
            return None

        img = process_image_canvas(raw_img)
        p_hash = str(imagehash.phash(img))
        d_hash = str(imagehash.dhash(img))
        vfs = extract_visual_features(img)

        return {
            "pokemon": pokemon_name,
            "shortest_name": pokemon_name.lower(),
            "phash": p_hash,
            "dhash": d_hash,
            "visual_features": vfs
        }
    except Exception:
        return None

async def perfect_sync():
    print("🚀 Connecting to MongoDB and caching existing state...", flush=True)
    existing_docs = await phash_col.find({}).to_list(length=None)
    cache = {doc["shortest_name"]: doc for doc in existing_docs}
    print(f"📦 Loaded {len(cache)} existing records into local memory cache.", flush=True)

    print("🚀 Opening authenticated streaming connection to Hugging Face...", flush=True)
    dataset = load_dataset(
        "SpreadSheets/Poketwo-Spawn-Images", 
        streaming=True, 
        split="train", 
        token=HF_TOKEN
    )

    count = 0
    batch_items = []
    
    # Thread pool to process images concurrently using multi-core CPU
    executor = ThreadPoolExecutor(max_workers=4)

    print("⚡ High-speed concurrent sync pipeline active!", flush=True)

    loop = asyncio.get_running_loop()
    
    # Collect items in chunks and process them concurrently
    chunk = []
    for item in dataset:
        chunk.append(item)
        if len(chunk) >= 50: # Process in parallel chunks of 50
            futures = [loop.run_in_executor(executor, process_single_item, it) for it in chunk]
            results = await asyncio.gather(*futures)
            
            modified_keys = set()
            for res in results:
                if not res:
                    continue
                
                key = res["shortest_name"]
                if key not in cache:
                    cache[key] = {
                        "pokemon": res["pokemon"],
                        "shortest_name": key,
                        "phash": res["phash"],
                        "phashes": [],
                        "dhash": res["dhash"],
                        "dhashes": [],
                        "visual_features": res["visual_features"],
                        "visual_features_list": []
                    }

                doc = cache[key]
                old_p = doc.get("phashes", [])
                old_d = doc.get("dhashes", [])
                old_vfs = doc.get("visual_features_list", [])

                combined_p = list(dict.fromkeys(old_p + [res["phash"]]))[:120]
                combined_d = list(dict.fromkeys(old_d + [res["dhash"]]))[:120]
                combined_vfs = (old_vfs + [res["visual_features"]])[:120]

                doc["phash"] = combined_p[0]
                doc["phashes"] = combined_p
                doc["dhash"] = combined_d[0]
                doc["dhashes"] = combined_d
                doc["visual_features"] = combined_vfs[0]
                doc["visual_features_list"] = combined_vfs

                modified_keys.add(key)
                count += 1

            if modified_keys:
                operations = [
                    UpdateOne({"shortest_name": k}, {"$set": cache[k]}, upsert=True)
                    for k in modified_keys
                ]
                await phash_col.bulk_write(operations, ordered=False)
                print(f"🔥 Progress: Processed & synced {count} total images...", flush=True)

            chunk = []

    print(f"🎉 Dataset streaming sync complete! Total processed: {count} images.", flush=True)

if __name__ == "__main__":
    asyncio.run(perfect_sync())
