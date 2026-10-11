import os
import motor.motor_asyncio
from pymongo.errors import ConnectionFailure

# MongoDB Connection Setup
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("❌ MONGO_URI environment variable is missing! Please set it in Render.")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client.pokemon_bot_db

# Collections
collections_col = db.collections          # user_id, guild_id, pokemon_list
shiny_hunts_col = db.shiny_hunts          # user_id, guild_id, pokemon
reserves_col = db.reserves                # guild_id, pokemon, user_id (one doc per reservation or grouped)
guild_settings_col = db.guild_settings    # guild_id, allowed_roles (list of role IDs)


async def test_db_connection():
    try:
        await client.admin.command('ping')
        print("✅ Successfully connected to MongoDB Atlas!")
    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        raise e


# --- Guild Role Settings ---
async def get_allowed_roles(guild_id: int) -> list:
    doc = await guild_settings_col.find_one({"guild_id": guild_id})
    return doc.get("allowed_roles", []) if doc else []

async def add_allowed_role(guild_id: int, role_id: int):
    roles = await get_allowed_roles(guild_id)
    if role_id not in roles:
        roles.append(role_id)
        await guild_settings_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"allowed_roles": roles}},
            upsert=True
        )

async def remove_allowed_role(guild_id: int, role_id: int):
    roles = await get_allowed_roles(guild_id)
    if role_id in roles:
        roles.remove(role_id)
        await guild_settings_col.update_one(
            {"guild_id": guild_id},
            {"$set": {"allowed_roles": roles}},
            upsert=True
        )


# --- Shiny Hunt Database Operations ---
async def set_shiny_hunt(user_id: int, guild_id: int, pokemon: str):
    await shiny_hunts_col.update_one(
        {"user_id": user_id, "guild_id": guild_id},
        {"$set": {"pokemon": pokemon.lower().strip()}},
        upsert=True
    )

async def get_shiny_hunt(user_id: int, guild_id: int):
    doc = await shiny_hunts_col.find_one({"user_id": user_id, "guild_id": guild_id})
    return doc.get("pokemon") if doc else None

async def remove_shiny_hunt(user_id: int, guild_id: int):
    await shiny_hunts_col.delete_one({"user_id": user_id, "guild_id": guild_id})


# --- Collection Database Operations ---
async def get_collection(user_id: int, guild_id: int) -> list:
    doc = await collections_col.find_one({"user_id": user_id, "guild_id": guild_id})
    return doc.get("pokemon_list", []) if doc else []

async def add_to_collection(user_id: int, guild_id: int, mons: list):
    current = set(await get_collection(user_id, guild_id))
    for m in mons:
        current.add(m.lower().strip())
    await collections_col.update_one(
        {"user_id": user_id, "guild_id": guild_id},
        {"$set": {"pokemon_list": list(current)}},
        upsert=True
    )

async def remove_from_collection(user_id: int, guild_id: int, mons: list):
    current = set(await get_collection(user_id, guild_id))
    for m in mons:
        current.discard(m.lower().strip())
    await collections_col.update_one(
        {"user_id": user_id, "guild_id": guild_id},
        {"$set": {"pokemon_list": list(current)}},
        upsert=True
    )


# --- Reserve Database Operations ---
async def add_reserve(guild_id: int, pokemon: str, user_id: int):
    pokemon = pokemon.lower().strip()
    await reserves_col.update_one(
        {"guild_id": guild_id, "pokemon": pokemon, "user_id": user_id},
        {"$set": {"guild_id": guild_id, "pokemon": pokemon, "user_id": user_id}},
        upsert=True
    )

async def remove_reserve(guild_id: int, pokemon: str, user_id: int):
    pokemon = pokemon.lower().strip()
    await reserves_col.delete_one({"guild_id": guild_id, "pokemon": pokemon, "user_id": user_id})

async def remove_global_reserve(guild_id: int, pokemon: str):
    pokemon = pokemon.lower().strip()
    await reserves_col.delete_many({"guild_id": guild_id, "pokemon": pokemon})

async def clear_user_reserves(guild_id: int, user_id: int):
    await reserves_col.delete_many({"guild_id": guild_id, "user_id": user_id})

async def clear_all_reserves(guild_id: int):
    await reserves_col.delete_many({"guild_id": guild_id})

async def get_user_reserves(guild_id: int, user_id: int) -> list:
    cursor = reserves_col.find({"guild_id": guild_id, "user_id": user_id})
    return [doc["pokemon"] async for doc in cursor]

async def get_all_reserves(guild_id: int) -> dict:
    # Returns {pokemon: [user_ids]}
    cursor = reserves_col.find({"guild_id": guild_id})
    mapping = {}
    async for doc in cursor:
        mon = doc["pokemon"]
        uid = doc["user_id"]
        mapping.setdefault(mon, []).set_default if False else None
        if mon not in mapping:
            mapping[mon] = []
        if uid not in mapping[mon]:
            mapping[mon].append(uid)
    return mapping

async def get_reserves_for_pokemon(guild_id: int, pokemon: str) -> list:
    pokemon = pokemon.lower().strip()
    cursor = reserves_col.find({"guild_id": guild_id, "pokemon": pokemon})
    return [doc["user_id"] async for doc in cursor]
